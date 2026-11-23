"""Layered Production Guardrails for AI Data Analyst Agent.

Provides four independent, lightweight defense layers:
- Layer 1: Input Validation (input_guardrail.py)
- Layer 2: Code Generation Blocking (code_guardrail.py)
- Layer 3: Sensitive Information Protection (pii_guardrail.py)
- Layer 4: Output Guardrail (output_guardrail.py)
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from mcp_using_langchain.guardrails.input_guardrail import (
    DEFAULT_MAX_QUERY_LENGTH,
    InputValidationResult,
    validate_input,
)
from mcp_using_langchain.guardrails.code_guardrail import (
    CodeGuardrailResult,
    check_code_generation,
)
from mcp_using_langchain.guardrails.pii_guardrail import (
    SensitiveInputResult,
    check_sensitive_input,
    mask_pii_text,
    sanitize_tool_result,
    validate_sql_query_safety,
)
from mcp_using_langchain.guardrails.output_guardrail import (
    validate_and_sanitize_output,
)


def run_input_guardrails(
    query: Any,
    max_length: Optional[int] = None,
) -> Tuple[bool, Optional[str], str]:
    """Executes input guardrails in order: Layer 1 -> Layer 2 -> Layer 3.

    Args:
        query: Raw user query
        max_length: Optional override for max query length

    Returns:
        Tuple of (passed: bool, rejection_message: Optional[str], cleaned_query: str)
    """
    # Layer 1: Input Validation
    input_res = validate_input(query, max_length=max_length)
    if not input_res.is_valid:
        return False, input_res.error_message, ""

    cleaned_query = input_res.cleaned_query

    # Layer 2: Code Generation Blocking
    code_res = check_code_generation(cleaned_query)
    if code_res.is_blocked:
        return False, code_res.rejection_message, cleaned_query

    # Layer 3: Sensitive Information Intent Check
    pii_res = check_sensitive_input(cleaned_query)
    if pii_res.is_blocked:
        return False, pii_res.rejection_message, cleaned_query

    return True, None, cleaned_query


__all__ = [
    "validate_input",
    "InputValidationResult",
    "DEFAULT_MAX_QUERY_LENGTH",
    "check_code_generation",
    "CodeGuardrailResult",
    "check_sensitive_input",
    "SensitiveInputResult",
    "mask_pii_text",
    "sanitize_tool_result",
    "validate_sql_query_safety",
    "validate_and_sanitize_output",
    "run_input_guardrails",
]
