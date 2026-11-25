"""LLM Configuration with Automatic Fallback.

Configures primary LLM (Groq / Grok) with seamless failover to fallback LLM (Google Gemini)
when the primary provider encounters rate limits, capacity constraints, or service interruptions.
Also normalizes model output formats across different providers.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

import httpx
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from pydantic import ConfigDict

logger = logging.getLogger("mcp_using_langchain.llm")


def extract_text_content(content: Any) -> str:
    """Normalizes raw model response/chunk content into a clean string.

    Handles differences between providers:
    - Plain strings (e.g., Groq / OpenAI chunks: "Hello")
    - List of message/content blocks (e.g., Gemini: [{'type': 'text', 'text': 'Hello'}])
    - Dictionaries with a 'text' key
    - Other objects with a .text attribute

    Args:
        content: The raw content field from an AIMessage or AIMessageChunk.

    Returns:
        Extracted plain text string.
    """
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(getattr(block, "text", "")))
        return "".join(parts)
    if isinstance(content, dict) and "text" in content:
        return str(content.get("text", ""))
    if hasattr(content, "text"):
        return str(getattr(content, "text", ""))
    return str(content)


def is_retryable_or_fallback_error(err: BaseException) -> Tuple[bool, str]:
    """Classifies whether an exception is an eligible retryable/fallback error.

    Eligible errors:
    - HTTP 429 / Rate Limit errors
    - Quota exhaustion errors
    - Retryable temporary server errors (5xx: 500, 502, 503, 504)
    - Retryable connection failures and timeouts

    Non-eligible errors (must NOT trigger fallback):
    - asyncio.CancelledError (task cancellation)
    - Guardrail violations (e.g. OutputGuardrailViolation)
    - HTTP 400 Bad Request
    - HTTP 401 Unauthorized / AuthenticationError
    - HTTP 403 Forbidden / PermissionDeniedError
    - HTTP 404 / 422 Invalid parameters
    """
    if isinstance(err, asyncio.CancelledError):
        return False, "CANCELLED"

    # Check for known Guardrail violations
    err_cls_name = err.__class__.__name__
    if "GuardrailViolation" in err_cls_name:
        return False, f"GUARDRAIL_VIOLATION ({err_cls_name})"

    # Check HTTP status code if available
    status_code: Optional[int] = None
    if hasattr(err, "status_code") and isinstance(getattr(err, "status_code"), int):
        status_code = getattr(err, "status_code")
    elif hasattr(err, "response") and getattr(err, "response", None) is not None:
        resp = getattr(err, "response")
        if hasattr(resp, "status_code") and isinstance(getattr(resp, "status_code"), int):
            status_code = getattr(resp, "status_code")

    if status_code is not None:
        if status_code == 429:
            return True, "RATE_LIMIT (HTTP 429)"
        if status_code in (500, 502, 503, 504):
            return True, f"SERVER_ERROR (HTTP {status_code})"
        if status_code in (400, 401, 403, 404, 422):
            return False, f"NON_RETRYABLE_CLIENT_ERROR (HTTP {status_code})"

    # Check for Groq / OpenAI / Cloud SDK specific exception types
    if "RateLimitError" in err_cls_name or "Quota" in err_cls_name or "ResourceExhausted" in err_cls_name:
        return True, f"RATE_LIMIT ({err_cls_name})"
    if "InternalServerError" in err_cls_name or "ServiceUnavailable" in err_cls_name or "BadGateway" in err_cls_name:
        return True, f"SERVER_ERROR ({err_cls_name})"
    if "AuthenticationError" in err_cls_name or "PermissionDenied" in err_cls_name or "Unauthorized" in err_cls_name:
        return False, f"AUTHENTICATION_ERROR ({err_cls_name})"
    if "BadRequestError" in err_cls_name or "UnprocessableEntity" in err_cls_name or "NotFoundError" in err_cls_name:
        return False, f"BAD_REQUEST_ERROR ({err_cls_name})"
    if "APIConnectionError" in err_cls_name or "APITimeoutError" in err_cls_name:
        return True, f"CONNECTION_OR_TIMEOUT ({err_cls_name})"

    # Check standard Python / httpx networking & timeout exceptions
    if isinstance(err, (httpx.TimeoutException, TimeoutError, asyncio.TimeoutError)):
        return True, f"TIMEOUT ({err_cls_name})"
    if isinstance(err, (httpx.NetworkError, httpx.ConnectError, ConnectionError, OSError)):
        return True, f"CONNECTION_ERROR ({err_cls_name})"

    # Fallback to examining exception message text safely
    err_msg = str(err).lower()
    if any(k in err_msg for k in ["rate limit", "rate_limit", "quota", "resource_exhausted", "resourceexhausted", "too many requests", "tokens per minute", "requests per minute", "429"]):
        return True, "RATE_LIMIT_TEXT"
    if any(k in err_msg for k in ["bad gateway", "service unavailable", "gateway timeout", "internal server error", "500", "502", "503", "504"]):
        return True, "SERVER_ERROR_TEXT"
    if any(k in err_msg for k in ["connection reset", "connection refused", "timed out", "connect error", "broken pipe"]):
        return True, "CONNECTION_TIMEOUT_TEXT"
    if any(k in err_msg for k in ["unauthorized", "invalid api key", "bad request", "invalid_request", "invalid argument", "permission denied", "forbidden"]):
        return False, "NON_RETRYABLE_CLIENT_TEXT"

    return False, f"UNCLASSIFIED_ERROR ({err_cls_name})"


class FallbackChatModel(BaseChatModel):
    """Custom ChatModel that wraps a primary model and an optional fallback model.

    Features:
    - Automatic failover on HTTP 429 / rate limits, quota errors, 5xx server errors, connection/timeout errors.
    - Zero retry stalling on rate limits when paired with max_retries=0.
    - Strict non-fallback on client errors (400, 401, 403, 404, 422, guardrail violations).
    - Preserves tools, messages, arguments, and system instructions across providers.
    - Safe streaming: activates fallback only if primary fails before any content was committed.
      If partial output was already sent, raises controlled error rather than duplicating response.
    - Prevents duplicate tool execution during agent graph execution.
    - Explicit structured logging for primary failure, classification, fallback activation, success and failure.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    primary: Any
    fallback: Optional[Any] = None
    primary_name: str = "Groq"
    fallback_name: str = "Gemini"

    @property
    def _llm_type(self) -> str:
        return "fallback-chat-model"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.fallback:
            return self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        try:
            return self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as e:
            is_eligible, classification = is_retryable_or_fallback_error(e)
            if is_eligible and self.fallback:
                safe_msg = type(e).__name__
                logger.warning(
                    "Primary LLM (%s) failed with classification '%s' (%s). Activating fallback LLM (%s)...",
                    self.primary_name,
                    classification,
                    safe_msg,
                    self.fallback_name,
                )
                try:
                    res = self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    logger.info("Fallback LLM (%s) successfully generated response.", self.fallback_name)
                    return res
                except Exception as fb_err:
                    logger.error(
                        "Fallback LLM (%s) also failed: %s (%s)",
                        self.fallback_name,
                        type(fb_err).__name__,
                        str(fb_err)[:200],
                    )
                    raise fb_err
            else:
                logger.error(
                    "Primary LLM (%s) encountered non-fallback error [%s]: %s (%s)",
                    self.primary_name,
                    classification,
                    type(e).__name__,
                    str(e)[:200],
                )
                raise e

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.fallback:
            return await self.primary._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

        try:
            return await self.primary._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as e:
            is_eligible, classification = is_retryable_or_fallback_error(e)
            if is_eligible and self.fallback:
                safe_msg = type(e).__name__
                logger.warning(
                    "Primary LLM (%s) failed with classification '%s' (%s). Activating fallback LLM (%s)...",
                    self.primary_name,
                    classification,
                    safe_msg,
                    self.fallback_name,
                )
                try:
                    res = await self.fallback._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    logger.info("Fallback LLM (%s) successfully generated response.", self.fallback_name)
                    return res
                except Exception as fb_err:
                    logger.error(
                        "Fallback LLM (%s) also failed: %s (%s)",
                        self.fallback_name,
                        type(fb_err).__name__,
                        str(fb_err)[:200],
                    )
                    raise fb_err
            else:
                logger.error(
                    "Primary LLM (%s) encountered non-fallback error [%s]: %s (%s)",
                    self.primary_name,
                    classification,
                    type(e).__name__,
                    str(e)[:200],
                )
                raise e

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        if not self.fallback:
            yield from self.primary._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
            return

        has_emitted_content = False
        buffered_empty_chunks: List[ChatGenerationChunk] = []

        try:
            for chunk in self.primary._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
                content = chunk.message.content if hasattr(chunk, "message") else ""
                has_content = bool(content and (not isinstance(content, str) or content.strip()))
                has_tools = bool(
                    getattr(chunk.message, "tool_calls", None)
                    or getattr(chunk.message, "tool_call_chunks", None)
                )
                if has_content or has_tools:
                    for b in buffered_empty_chunks:
                        yield b
                    buffered_empty_chunks.clear()
                    has_emitted_content = True
                    yield chunk
                else:
                    buffered_empty_chunks.append(chunk)

            for b in buffered_empty_chunks:
                yield b
            buffered_empty_chunks.clear()

        except Exception as e:
            is_eligible, classification = is_retryable_or_fallback_error(e)
            if is_eligible and not has_emitted_content and self.fallback:
                logger.warning(
                    "Primary LLM (%s) failed with classification '%s' (%s) before output was emitted. Activating fallback LLM (%s)...",
                    self.primary_name,
                    classification,
                    type(e).__name__,
                    self.fallback_name,
                )
                buffered_empty_chunks.clear()
                try:
                    for chunk in self.fallback._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
                        yield chunk
                    logger.info("Fallback LLM (%s) stream finished successfully.", self.fallback_name)
                except Exception as fb_err:
                    logger.error(
                        "Fallback LLM (%s) stream also failed: %s (%s)",
                        self.fallback_name,
                        type(fb_err).__name__,
                        str(fb_err)[:200],
                    )
                    raise fb_err
            else:
                if has_emitted_content:
                    logger.error(
                        "Primary LLM (%s) failed [%s] after partial response was already committed. Not restarting to prevent duplicate output.",
                        self.primary_name,
                        classification,
                    )
                else:
                    logger.error(
                        "Primary LLM (%s) failed with non-fallback error [%s]: %s (%s)",
                        self.primary_name,
                        classification,
                        type(e).__name__,
                        str(e)[:200],
                    )
                raise e

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if not self.fallback:
            async for chunk in self.primary._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                yield chunk
            return

        has_emitted_content = False
        buffered_empty_chunks: List[ChatGenerationChunk] = []

        try:
            async for chunk in self.primary._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                content = chunk.message.content if hasattr(chunk, "message") else ""
                has_content = bool(content and (not isinstance(content, str) or content.strip()))
                has_tools = bool(
                    getattr(chunk.message, "tool_calls", None)
                    or getattr(chunk.message, "tool_call_chunks", None)
                )
                if has_content or has_tools:
                    for b in buffered_empty_chunks:
                        yield b
                    buffered_empty_chunks.clear()
                    has_emitted_content = True
                    yield chunk
                else:
                    buffered_empty_chunks.append(chunk)

            for b in buffered_empty_chunks:
                yield b
            buffered_empty_chunks.clear()

        except Exception as e:
            is_eligible, classification = is_retryable_or_fallback_error(e)
            if is_eligible and not has_emitted_content and self.fallback:
                logger.warning(
                    "Primary LLM (%s) failed with classification '%s' (%s) before output was emitted. Activating fallback LLM (%s)...",
                    self.primary_name,
                    classification,
                    type(e).__name__,
                    self.fallback_name,
                )
                buffered_empty_chunks.clear()
                try:
                    async for chunk in self.fallback._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                        yield chunk
                    logger.info("Fallback LLM (%s) stream finished successfully.", self.fallback_name)
                except Exception as fb_err:
                    logger.error(
                        "Fallback LLM (%s) stream also failed: %s (%s)",
                        self.fallback_name,
                        type(fb_err).__name__,
                        str(fb_err)[:200],
                    )
                    raise fb_err
            else:
                if has_emitted_content:
                    logger.error(
                        "Primary LLM (%s) failed [%s] after partial response was already committed. Not restarting to prevent duplicate output.",
                        self.primary_name,
                        classification,
                    )
                else:
                    logger.error(
                        "Primary LLM (%s) failed with non-fallback error [%s]: %s (%s)",
                        self.primary_name,
                        classification,
                        type(e).__name__,
                        str(e)[:200],
                    )
                raise e

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, Callable, BaseTool]],
        **kwargs: Any,
    ) -> FallbackChatModel:
        new_primary = self.primary.bind_tools(tools, **kwargs)
        new_fallback = self.fallback.bind_tools(tools, **kwargs) if self.fallback else None
        return FallbackChatModel(
            primary=new_primary,
            fallback=new_fallback,
            primary_name=self.primary_name,
            fallback_name=self.fallback_name,
        )

    def bind(self, **kwargs: Any) -> FallbackChatModel:
        new_primary = self.primary.bind(**kwargs)
        new_fallback = self.fallback.bind(**kwargs) if self.fallback else None
        return FallbackChatModel(
            primary=new_primary,
            fallback=new_fallback,
            primary_name=self.primary_name,
            fallback_name=self.fallback_name,
        )


def get_configured_llm() -> BaseChatModel:
    """Initializes primary LLM with automatic Google Gemini fallback.

    Configuration hierarchy:
    1. If both GROQ_API_KEY (or GROK_API_KEY) and GEMINI_API_KEY (or GOOGLE_API_KEY) are provided:
       Initializes ChatGroq as primary (with max_retries=0 to avoid stalling on 429 rate limits)
       and ChatGoogleGenerativeAI as seamless fallback via FallbackChatModel.
    2. If only GROQ_API_KEY is provided:
       Initializes ChatGroq as primary with FallbackChatModel (fallback=None).
    3. If only GEMINI_API_KEY (or GOOGLE_API_KEY) is provided:
       Initializes ChatGoogleGenerativeAI as primary with FallbackChatModel (fallback=None).
    4. If neither is provided:
       Raises ValueError informing the user to configure at least one API key.

    Returns:
        BaseChatModel configured for supervisor and agent execution.
    """
    groq_api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not groq_api_key and not gemini_api_key:
        raise ValueError(
            "Neither GROQ_API_KEY (or GROK_API_KEY) nor GEMINI_API_KEY (or GOOGLE_API_KEY) is configured. "
            "Please configure at least one LLM API key in your environment."
        )

    groq_llm: Optional[ChatGroq] = None
    if groq_api_key:
        groq_model = os.getenv("GROQ_MODEL") or os.getenv("GROK_MODEL") or "qwen/qwen3.8-27b"
        groq_max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "800"))
        # Set max_retries=0 so Groq fails immediately on HTTP 429 without sleeping/retrying,
        # enabling immediate failover to the configured fallback model.
        groq_llm = ChatGroq(
            model=groq_model,
            api_key=groq_api_key,
            max_tokens=groq_max_tokens,
            max_retries=0,
        )

    gemini_llm: Optional[ChatGoogleGenerativeAI] = None
    if gemini_api_key:
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        gemini_max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", os.getenv("GROQ_MAX_TOKENS", "800")))
        gemini_llm = ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=gemini_api_key,
            max_output_tokens=gemini_max_tokens,
        )

    if groq_llm and gemini_llm:
        primary_name = f"Groq ({os.getenv('GROQ_MODEL') or os.getenv('GROK_MODEL') or 'qwen/qwen3.8-27b'})"
        fallback_name = f"Gemini ({os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')})"
        print(f"Initialized primary {primary_name} with automatic fallback to {fallback_name}.")
        return FallbackChatModel(
            primary=groq_llm,
            fallback=gemini_llm,
            primary_name=primary_name,
            fallback_name=fallback_name,
        )
    elif groq_llm:
        primary_name = f"Groq ({os.getenv('GROQ_MODEL') or os.getenv('GROK_MODEL') or 'qwen/qwen3.8-27b'})"
        print(f"Initialized primary {primary_name} without fallback.")
        return FallbackChatModel(
            primary=groq_llm,
            fallback=None,
            primary_name=primary_name,
        )
    else:
        primary_name = f"Gemini ({os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')})"
        print(f"Initialized primary {primary_name}.")
        return FallbackChatModel(
            primary=gemini_llm,
            fallback=None,
            primary_name=primary_name,
        )
