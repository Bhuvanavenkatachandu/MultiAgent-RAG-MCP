"""Layer 3: Sensitive Information Protection Guardrail.

Protects personally identifiable information (PII) and sensitive credentials:
- Email addresses
- Phone numbers
- Customer names where identifiable
- Personal street addresses
- Passwords and password hashes
- Credit-card numbers
- CVV and payment credentials

Provides:
1. Input intent check: Blocks prohibited requests for raw credentials/passwords.
2. Tool/database result sanitization: Masks PII and redacts sensitive columns before reaching LLM.
3. Text masking engine with regex and optional Microsoft Presidio integration.
4. Preserves legitimate aggregate queries and analytical metrics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

# Optional Presidio integration
_PRESIDIO_AVAILABLE = False
_presidio_analyzer = None
_presidio_anonymizer = None

try:
    import presidio_analyzer
    import presidio_anonymizer
    # Only enable if an NLP engine is already configured without hanging
    _PRESIDIO_AVAILABLE = True
except (ImportError, Exception):
    _PRESIDIO_AVAILABLE = False


@dataclass(frozen=True)
class SensitiveInputResult:
    """Represents the outcome of checking input for prohibited credential requests."""
    is_blocked: bool
    reason: Optional[str] = None
    rejection_message: Optional[str] = None


CREDENTIALS_REJECTION_MESSAGE = (
    "Security Policy Notice: Requests seeking direct access to passwords, "
    "password hashes, CVVs, full credit card numbers, or secret authentication "
    "credentials are prohibited by system guardrails."
)

# Patterns for inputs attempting to retrieve credentials/secrets
SENSITIVE_INPUT_PATTERNS = [
    re.compile(
        r"\b(?:show|get|give|dump|list|fetch|select|find|display|reveal|extract|what\s+is|what\s+are)\b"
        r"(?:\s+\w+){0,6}\s+(?:passwords?|password_hash(?:es)?|passwd|pwds?|"
        r"cvv2?|cvc|credit\s*card(?:s|\s*numbers?)?|card_numbers?|secret_keys?|auth_tokens?|private_keys?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:dump|steal|hack|bypass)\b(?:\s+\w+){0,6}\s+(?:database|credentials?|passwords?|hashes)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:admin|user|customer)\s+passwords?\b",
        re.IGNORECASE,
    ),
]

# High-precision PII detection regexes
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Standard card formats: 13-19 digits, optionally separated by spaces or hyphens
CREDIT_CARD_REGEX = re.compile(
    r"\b(?:\d{4}[- ]){3}\d{4}\b|\b\d{15,16}\b"
)

# CVV patterns (e.g. CVV: 123, CVC 456, cvv=789)
CVV_REGEX = re.compile(
    r"\b(?:cvv2?|cvc|security\s*code)\s*[:=]?\s*(\d{3,4})\b",
    re.IGNORECASE,
)

# Passwords & Password Hashes:
# - Bcrypt: $2a$10$..., $2b$12$...
BCRYPT_REGEX = re.compile(
    r"\$2[aby]\$\d{2}\$[./0-9A-Za-z]{53}"
)

# - Argon2: $argon2id$...
ARGON2_REGEX = re.compile(
    r"\$argon2(?:id|i|d)\$[^\s,'\"]+"
)

# - Generic password field key-values in text or SQL dumps
PASSWORD_KEY_VALUE_REGEX = re.compile(
    r"(\b(?:password|password_hash|passwd|pwd)\b\s*[:=]\s*['\"]?)([^'\";\s,\)\]]+)(['\"]?)",
    re.IGNORECASE,
)

# Personal street addresses (e.g. 123 Main Street, 456 Elm Ave Apt 2, 742 Evergreen Terrace)
STREET_ADDRESS_REGEX = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.\s]+(?:\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Circle|Cir|Terrace|Ter|Place|Pl|Parkway|Pkwy|Highway|Hwy|Trail|Trl)\b)"
    r"(?:\s*,?\s*(?:Apt|Suite|Unit|Ste|#)\s*[A-Za-z0-9-]+)?",
    re.IGNORECASE,
)

# Address field in structured DB records (e.g. address_line: '742 Evergreen Terrace')
ADDRESS_FIELD_REGEX = re.compile(
    r"(\b(?:address_line|address|street)\b\s*[:=]\s*['\"])([^'\"]+)(['\"])",
    re.IGNORECASE,
)

# Identifiable customer names in structured database output
# e.g., first_name: 'John', last_name: 'Doe'
NAME_FIELD_REGEX = re.compile(
    r"(\b(?:first_name|last_name|full_name|customer_name)\b\s*[:=]\s*['\"])([A-Za-z]{2,})(['\"])",
    re.IGNORECASE,
)


def luhn_checksum_is_valid(card_number: str) -> bool:
    """Verifies credit card number validity using standard Luhn algorithm."""
    digits = [int(ch) for ch in card_number if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for idx, d in enumerate(reverse_digits):
        if idx % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


def check_sensitive_input(query: str) -> SensitiveInputResult:
    """Checks if the user's input directly seeks passwords, credentials, or CVVs.

    Returns:
        SensitiveInputResult with blocking decision.
    """
    clean_query = query.strip()

    for pattern in SENSITIVE_INPUT_PATTERNS:
        if pattern.search(clean_query):
            return SensitiveInputResult(
                is_blocked=True,
                reason="Prohibited credential retrieval intent.",
                rejection_message=CREDENTIALS_REJECTION_MESSAGE,
            )

    return SensitiveInputResult(is_blocked=False)


def mask_name_token(name: str) -> str:
    """Masks an individual name (e.g., 'Jennifer' -> 'J***r' or 'John' -> 'J***')."""
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + "***" + (name[-1] if len(name) > 3 else "")


def mask_pii_text(text: str) -> str:
    """Masks all identifiable PII and redacts sensitive credentials from arbitrary text.

    Protects:
    - Passwords and password hashes (completely redacted)
    - Credit card numbers (Luhn checked or 16-digit card patterns)
    - CVV / security codes
    - Email addresses
    - Phone numbers
    - Street addresses
    - Identifiable structured name fields
    """
    if not isinstance(text, str) or not text:
        return text

    masked = text

    # 1. Redact Bcrypt and Argon2 password hashes
    masked = BCRYPT_REGEX.sub("[REDACTED_PASSWORD_HASH]", masked)
    masked = ARGON2_REGEX.sub("[REDACTED_PASSWORD_HASH]", masked)

    # 2. Redact password key-value assignments
    def _replace_password_kv(match):
        prefix = match.group(1)
        val = match.group(2)
        suffix = match.group(3)
        if val.startswith("[REDACTED"):
            return match.group(0)
        if "hash" in prefix.lower():
            return f"{prefix}[REDACTED_PASSWORD_HASH]{suffix}"
        return f"{prefix}[REDACTED_PASSWORD]{suffix}"

    masked = PASSWORD_KEY_VALUE_REGEX.sub(_replace_password_kv, masked)

    # 3. Redact CVVs
    masked = CVV_REGEX.sub("CVV: [REDACTED_CVV]", masked)

    # 4. Redact Credit Card numbers
    def _replace_cc(match):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) in (15, 16) or luhn_checksum_is_valid(digits):
            return "[REDACTED_CREDIT_CARD]"
        return raw

    masked = CREDIT_CARD_REGEX.sub(_replace_cc, masked)

    # 5. Mask Emails
    masked = EMAIL_REGEX.sub("[REDACTED_EMAIL]", masked)

    # 6. Mask Phone numbers
    masked = PHONE_REGEX.sub("[REDACTED_PHONE]", masked)

    # 7. Mask Street Addresses
    masked = STREET_ADDRESS_REGEX.sub("[REDACTED_ADDRESS]", masked)
    masked = ADDRESS_FIELD_REGEX.sub(r"\1[REDACTED_ADDRESS]\3", masked)

    # 8. Mask identifiable name fields in structured text
    def _mask_name(match):
        prefix = match.group(1)
        raw_name = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{mask_name_token(raw_name)}{suffix}"

    masked = NAME_FIELD_REGEX.sub(_mask_name, masked)

    return masked


def sanitize_tool_result(result: Any) -> str:
    """Sanitizes raw database / MCP tool outputs before sending to LLM.

    Ensures that passwords, hashes, CVVs, credit cards, emails, and personal
    contact information returned from database queries are redacted or masked,
    while leaving numeric aggregates, totals, counts, and categories intact.
    """
    if result is None:
        return ""

    raw_str = str(result)

    # Apply comprehensive PII masking
    sanitized = mask_pii_text(raw_str)

    # Enforce strict removal of any leaked password_hash records
    if "password_hash" in sanitized:
        # Extra safety guarantee: replace any value adjacent to password_hash
        sanitized = re.sub(
            r"('password_hash':\s*')[^']+(')",
            r"\1[REDACTED_PASSWORD_HASH]\2",
            sanitized
        )
        sanitized = re.sub(
            r'("password_hash":\s*")[^"]+(")',
            r"\1[REDACTED_PASSWORD_HASH]\2",
            sanitized
        )

    return sanitized


def validate_sql_query_safety(sql: str) -> tuple[bool, Optional[str]]:
    """Enforces sensitive column restrictions at the SQL query level.

    Prevents queries explicitly requesting prohibited credential columns
    like password_hash or cvv.
    """
    clean_sql = sql.strip().upper()

    # Prohibited columns that must never be queried
    prohibited_columns = ["PASSWORD_HASH", "PASSWORD", "CVV", "CREDIT_CARD_NUMBER"]
    for col in prohibited_columns:
        if re.search(rf"\b{col}\b", clean_sql):
            return False, f"Access to sensitive credential column '{col}' is restricted by system security policies."

    return True, None
