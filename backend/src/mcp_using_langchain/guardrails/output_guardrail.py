"""Layer 4: Output Guardrail.

Scans, validates, buffers, and sanitizes agent responses before returning them to the user:
- Scans agent responses for PII and sensitive credentials.
- Masks detectable personal information (emails, phone numbers, addresses).
- Blocks and redacts prohibited credentials (passwords, hashes, CVVs, credit cards).
- Provides StreamingGuardrailBuffer for secure real-time token accumulation and validation.
- Validates output structure and handles unexpected output types safely.
- Preserves legitimate analytical results (Markdown tables, metrics, narratives).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from mcp_using_langchain.guardrails.pii_guardrail import (
    ARGON2_REGEX,
    BCRYPT_REGEX,
    CREDIT_CARD_REGEX,
    CVV_REGEX,
    EMAIL_REGEX,
    PASSWORD_KEY_VALUE_REGEX,
    PHONE_REGEX,
    STREET_ADDRESS_REGEX,
    luhn_checksum_is_valid,
    mask_pii_text,
)
from mcp_using_langchain.guardrails.code_guardrail import CODE_BLOCK_PATTERN


@dataclass(frozen=True)
class OutputValidationResult:
    """Represents the outcome of Layer 4 output guardrail validation."""
    is_safe: bool
    sanitized_text: str = ""
    reason: Optional[str] = None
    rejection_message: Optional[str] = None


class OutputGuardrailViolation(Exception):
    """Exception raised when streaming output violates security guardrails."""
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


RESTRICTED_OUTPUT_KEYWORDS = re.compile(
    r"\b(?:password_hash(?:es)?|credit_card_number|secret_keys?|private_keys?|auth_tokens?|api_secrets?)\b",
    re.IGNORECASE,
)


def check_output_safety(text: str, context: str = "") -> OutputValidationResult:
    """Validates output text (with optional carry-forward context) for security violations.

    Detects:
    - PII: Emails, phone numbers, valid credit card numbers, CVVs, physical addresses.
    - Credentials: Bcrypt/Argon2 password hashes, plaintext passwords.
    - Restricted Keywords: password_hash, credit_card_number, secret_key, etc.
    - Prohibited Code Generation: Markdown code blocks with programming languages.

    Args:
        text: The candidate text chunk to validate and emit.
        context: Optional carry-forward overlap text from previously emitted chunks
                 to catch items split across boundaries.

    Returns:
        OutputValidationResult indicating safety, sanitized text, and violation reason.
    """
    if not text:
        return OutputValidationResult(is_safe=True, sanitized_text="")

    combined = f"{context}{text}" if context else text

    # 1. Prohibited Password Hashes
    if BCRYPT_REGEX.search(combined) or ARGON2_REGEX.search(combined):
        return OutputValidationResult(
            is_safe=False,
            reason="Prohibited credential hash detected",
            rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Prohibited credential hash detected).",
        )

    # 2. Plaintext Password / Credential Key-Values
    pw_match = PASSWORD_KEY_VALUE_REGEX.search(combined)
    if pw_match:
        val = pw_match.group(2).strip()
        if not val.startswith("[REDACTED"):
            return OutputValidationResult(
                is_safe=False,
                reason="Plaintext password or credential assignment detected",
                rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Credential leak detected).",
            )

    # 3. CVVs / Security Codes
    cvv_match = CVV_REGEX.search(combined)
    if cvv_match and "[REDACTED_CVV]" not in cvv_match.group(0):
        return OutputValidationResult(
            is_safe=False,
            reason="Payment CVV/security code detected",
            rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Payment security code detected).",
        )

    # 4. Credit Card Numbers (with Luhn check or 15/16-digit format)
    for cc_match in CREDIT_CARD_REGEX.finditer(combined):
        raw_cc = cc_match.group(0)
        digits = re.sub(r"\D", "", raw_cc)
        if len(digits) in (15, 16) or luhn_checksum_is_valid(digits):
            return OutputValidationResult(
                is_safe=False,
                reason="Payment credit card number detected",
                rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Credit card number detected).",
            )

    # 5. Email Addresses
    for email_match in EMAIL_REGEX.finditer(combined):
        email_str = email_match.group(0)
        if not email_str.startswith("[REDACTED"):
            return OutputValidationResult(
                is_safe=False,
                reason="Personally Identifiable Information (email address) detected",
                rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Email address detected).",
            )

    # 6. Phone Numbers
    for phone_match in PHONE_REGEX.finditer(combined):
        phone_str = phone_match.group(0)
        if not phone_str.startswith("[REDACTED"):
            digits = re.sub(r"\D", "", phone_str)
            if len(digits) >= 10:
                return OutputValidationResult(
                    is_safe=False,
                    reason="Personally Identifiable Information (phone number) detected",
                    rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Phone number detected).",
                )

    # 7. Street Addresses
    for addr_match in STREET_ADDRESS_REGEX.finditer(combined):
        addr_str = addr_match.group(0)
        if not addr_str.startswith("[REDACTED"):
            return OutputValidationResult(
                is_safe=False,
                reason="Personally Identifiable Information (physical address) detected",
                rejection_message="Security Policy Notice: Output generation blocked by system guardrails (Address detected).",
            )

    # 8. Restricted Keywords
    for kw_match in RESTRICTED_OUTPUT_KEYWORDS.finditer(combined):
        kw_str = kw_match.group(0)
        if not kw_str.startswith("[REDACTED"):
            return OutputValidationResult(
                is_safe=False,
                reason=f"Restricted security keyword '{kw_str}' detected",
                rejection_message=f"Security Policy Notice: Output generation blocked by system guardrails (Restricted keyword '{kw_str}').",
            )

    # 9. Prohibited Code Generation
    if CODE_BLOCK_PATTERN.search(combined):
        return OutputValidationResult(
            is_safe=False,
            reason="Prohibited programming code generation block detected",
            rejection_message="Security Policy Notice: Output generation blocked by system guardrails (General programming code generation prohibited).",
        )

    sanitized = mask_pii_text(text)
    return OutputValidationResult(
        is_safe=True,
        sanitized_text=sanitized,
    )


class StreamingGuardrailBuffer:
    """Intermediate validation buffer between LLM token generation and SSE delivery.

    Accumulates generated tokens into sentence or size-based validation chunks,
    validates them against Layer 4 output guardrails with carry-forward overlap,
    and safely yields validated text chunks to SSE without exposing unvalidated text.
    """

    def __init__(
        self,
        min_chunk_size: int = 30,
        max_chunk_size: int = 120,
        overlap_size: int = 40,
    ) -> None:
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.buffer: str = ""
        self.carry_forward: str = ""
        self.emitted_text: str = ""
        self.is_violated: bool = False
        self.violation_reason: Optional[str] = None
        self.violation_message: Optional[str] = None
        self._delimiter_pat = re.compile(r"(?<=[.!?])(?:\s+|\n+)|\n+")

    def add_token(self, token: str) -> List[str]:
        """Appends a token, validates any ready chunks, and returns validated chunks to emit.

        If a guardrail violation is detected, raises OutputGuardrailViolation, discards
        the pending buffer, and halts further emission.
        """
        if self.is_violated or not token:
            return []

        self.buffer += token
        ready_chunks: List[str] = []

        while True:
            match = self._delimiter_pat.search(self.buffer)
            if match:
                split_idx = match.end()
                candidate = self.buffer[:split_idx]
                remaining = self.buffer[split_idx:]
            elif len(self.buffer) >= self.max_chunk_size:
                safe_cutoff = len(self.buffer) - (self.min_chunk_size // 2)
                space_idx = self.buffer.rfind(" ", 0, safe_cutoff)
                if space_idx != -1:
                    split_idx = space_idx + 1
                    candidate = self.buffer[:split_idx]
                    remaining = self.buffer[split_idx:]
                else:
                    break
            else:
                break

            validation = check_output_safety(candidate, context=self.carry_forward)
            if not validation.is_safe:
                self.is_violated = True
                self.violation_reason = validation.reason
                self.violation_message = validation.rejection_message
                self.buffer = ""  # Discard pending unsafe buffer immediately!
                raise OutputGuardrailViolation(
                    reason=validation.reason or "Security violation",
                    message=validation.rejection_message or "Content blocked by output guardrails.",
                )

            chunk_to_emit = validation.sanitized_text if validation.sanitized_text else candidate
            ready_chunks.append(chunk_to_emit)
            self.emitted_text += chunk_to_emit
            combined_emitted = self.carry_forward + chunk_to_emit
            self.carry_forward = combined_emitted[-self.overlap_size:]
            self.buffer = remaining

        return ready_chunks

    def flush(self) -> List[str]:
        """Validates and flushes any remaining buffered text at end of generation.

        If remaining text violates guardrails, raises OutputGuardrailViolation
        and discards the buffer.
        """
        if self.is_violated or not self.buffer:
            self.buffer = ""
            return []

        remaining = self.buffer
        self.buffer = ""  # Clear so it is never re-flushed

        validation = check_output_safety(remaining, context=self.carry_forward)
        if not validation.is_safe:
            self.is_violated = True
            self.violation_reason = validation.reason
            self.violation_message = validation.rejection_message
            raise OutputGuardrailViolation(
                reason=validation.reason or "Security violation",
                message=validation.rejection_message or "Content blocked by output guardrails.",
            )

        chunk_to_emit = validation.sanitized_text if validation.sanitized_text else remaining
        self.emitted_text += chunk_to_emit
        return [chunk_to_emit]

    def clear(self) -> None:
        """Discards buffer safely."""
        self.buffer = ""


def validate_and_sanitize_output(response: Any) -> str:
    """Validates and sanitizes final assistant output.

    Handles unexpected types, masks any lingering PII, redacts sensitive
    credentials, and ensures analytical tables and markdown structure remain intact.

    Args:
        response: Raw output from supervisor or agent (str, dict, None, etc.)

    Returns:
        Sanitized, validated string response ready for the client.
    """
    # 1. Handle unexpected output types safely
    if response is None:
        return "No response generated by the agent."

    if isinstance(response, str):
        text = response
    elif isinstance(response, (dict, list)):
        try:
            text = json.dumps(response, indent=2, ensure_ascii=False)
        except Exception:
            text = str(response)
    else:
        text = str(response)

    # 2. Check for empty or whitespace-only output
    if not text.strip():
        return "The agent returned an empty response. Please refine your query."

    # 3. Scan and mask detectable PII and sensitive credentials
    sanitized = mask_pii_text(text)

    # 4. Final safety sanity check: ensure no raw credentials leak through
    # (e.g. if a full bcrypt or argon hash remains, replace it)
    # mask_pii_text handles bcrypt, argon2, credit cards, emails, phones, CVVs.

    return sanitized
