"""Layer 1: Input Validation Guardrail.

Enforces structural and type constraints on raw user queries before
they reach the supervisor or any specialist agents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

DEFAULT_MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "2000"))


@dataclass(frozen=True)
class InputValidationResult:
    """Represents the outcome of input validation."""
    is_valid: bool
    error_message: Optional[str] = None
    cleaned_query: str = ""


def validate_input(
    query: Any,
    max_length: Optional[int] = None,
) -> InputValidationResult:
    """Validates user query string constraints.

    Checks:
    1. Type is string.
    2. Non-empty string.
    3. Non-whitespace-only string.
    4. Length within configured maximum bound.

    Returns:
        InputValidationResult with validity status, error message, and trimmed query.
    """
    if max_length is None:
        max_length = DEFAULT_MAX_QUERY_LENGTH

    # 1. Type validation
    if not isinstance(query, str):
        return InputValidationResult(
            is_valid=False,
            error_message="Input query must be a string.",
            cleaned_query="",
        )

    # 2. Empty validation
    if len(query) == 0:
        return InputValidationResult(
            is_valid=False,
            error_message="Input query cannot be empty.",
            cleaned_query="",
        )

    # 3. Whitespace-only validation
    cleaned = query.strip()
    if not cleaned:
        return InputValidationResult(
            is_valid=False,
            error_message="Input query cannot be empty or whitespace only.",
            cleaned_query="",
        )

    # 4. Maximum length check
    if len(query) > max_length:
        return InputValidationResult(
            is_valid=False,
            error_message=(
                f"Input query exceeds maximum allowed length of {max_length} "
                f"characters (received {len(query)} characters)."
            ),
            cleaned_query="",
        )

    return InputValidationResult(
        is_valid=True,
        error_message=None,
        cleaned_query=cleaned,
    )
