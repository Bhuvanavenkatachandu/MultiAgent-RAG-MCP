"""LLM Configuration with Automatic Fallback.

Configures primary LLM (Groq) with seamless failover to fallback LLM (Google Gemini)
when Groq encounters rate limits, capacity constraints, or service interruptions.
Also normalizes model output formats across different providers.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI


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


def get_configured_llm() -> BaseChatModel:
    """Initializes primary LLM with optional Google Gemini automatic fallback.

    Configuration hierarchy:
    1. If both GROQ_API_KEY and GEMINI_API_KEY (or GOOGLE_API_KEY) are provided:
       Initializes ChatGroq as primary and ChatGoogleGenerativeAI as fallback
       via LangChain's `.with_fallbacks([gemini_llm])`.
    2. If only GROQ_API_KEY is provided:
       Initializes ChatGroq as primary (no fallback).
    3. If only GEMINI_API_KEY (or GOOGLE_API_KEY) is provided:
       Initializes ChatGoogleGenerativeAI as primary.
    4. If neither is provided:
       Raises ValueError informing the user to set at least one API key.

    Returns:
        BaseChatModel configured for supervisor and agent execution.
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not groq_api_key and not gemini_api_key:
        raise ValueError(
            "Neither GROQ_API_KEY nor GEMINI_API_KEY (or GOOGLE_API_KEY) is configured. "
            "Please configure at least one LLM API key in your environment."
        )

    groq_llm: Optional[ChatGroq] = None
    if groq_api_key:
        groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        groq_max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "800"))
        groq_llm = ChatGroq(
            model=groq_model,
            api_key=groq_api_key,
            max_tokens=groq_max_tokens,
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
        print(
            f"Initialized primary Groq LLM ({os.getenv('GROQ_MODEL', 'qwen/qwen3.8-27b')}) "
            f"with automatic Gemini fallback ({os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')})."
        )
        return groq_llm.with_fallbacks([gemini_llm])
    elif groq_llm:
        print(f"Initialized primary Groq LLM ({os.getenv('GROQ_MODEL', 'qwen/qwen3.8-27b')}) without fallback.")
        return groq_llm
    else:
        print(f"Initialized primary Gemini LLM ({os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')}).")
        return gemini_llm
