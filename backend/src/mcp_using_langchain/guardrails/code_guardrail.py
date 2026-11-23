"""Layer 2: Code Generation Blocking Guardrail.

Prevents the Data Analyst Agent from acting as a general-purpose programming
assistant (Python, Java, JavaScript, React, debugging, coding tutorials),
while strictly allowing normal SQL, database queries, and data analytics questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CodeGuardrailResult:
    """Represents the outcome of code generation blocking check."""
    is_blocked: bool
    reason: Optional[str] = None
    rejection_message: Optional[str] = None


REJECTION_MESSAGE = (
    "I am an AI Data Analyst specialized in PostgreSQL database queries, analytics, "
    "and documentation knowledge retrieval. I cannot assist with general programming, "
    "code generation, debugging, or coding tutorials. Please ask questions related to "
    "your database data, business analytics, or knowledge base documents."
)

# Target programming languages & technologies that should be blocked
PROGRAMMING_LANGS = (
    r"(?:python|java|javascript|typescript|react(?:\.js)?|react|vue|angular|svelte|"
    r"next(?:\.js)?|node(?:\.js)?|express|c\+\+|c#|\.net|golang|rust|ruby|php|bash|powershell|"
    r"swift|kotlin|dart|flutter|html|css)"
)

# 1. Code generation / writing intents
CODE_GEN_PATTERNS = [
    # "write python code", "generate java code", "create a react component"
    re.compile(
        rf"\b(?:get|give|show|provide|write|generate|create|build|implement|develop|code|script|scaffold)\b"
        rf"(?:\s+\w+){{0,3}}\s+{PROGRAMMING_LANGS}\b"
        rf"(?:\s+(?:code|program|script|function|class|method|app|component|hook|module|library|endpoint))?",
        re.IGNORECASE,
    ),
    # "write a program/script/function in python"
    re.compile(
        rf"\b(?:get|give|show|provide|write|generate|create|build|implement|develop|code)\b"
        rf"(?:\s+\w+){{0,3}}\s+(?:program|script|function|class|method|app|component|hook|module|endpoint|algorithm)"
        rf"\s+(?:in|using|with)\s+{PROGRAMMING_LANGS}\b",
        re.IGNORECASE,
    ),
    # "get me code for ...", "give me code for ...", "write code for / to ..."
    re.compile(
        r"\b(?:get|give|show|provide|write|generate|create|build|implement|develop|code)\b"
        r"(?:\s+(?:me|us|a|an|the|some))?\s+"
        r"(?:code|program|script|function|class|method|algorithm)\s+"
        r"(?:for|to|that|calculating|computing|doing|solving)\b",
        re.IGNORECASE,
    ),
    # "code for sum of 2 numbers", "code to reverse a string", "code for fibonacci"
    re.compile(
        r"\bcode\s+(?:for|to|that)\s+\w+",
        re.IGNORECASE,
    ),
    # "write a program", "write a script", "code an app" (without database/SQL context)
    re.compile(
        r"\b(?:write|create|build|code)\s+(?:a|an|the|me\s+a)?\s*"
        r"(?:python\s+script|bash\s+script|shell\s+script|node\s+script|"
        r"web\s+app|mobile\s+app|react\s+component|rest\s+api\s+server)\b",
        re.IGNORECASE,
    ),
]

# 2. Debugging and fixing code
CODE_DEBUG_PATTERNS = [
    re.compile(
        rf"\b(?:debug|fix|troubleshoot|solve|find\s+(?:the\s+)?bugs?\s+in)\b"
        rf"(?:\s+\w+){{0,3}}\s+(?:{PROGRAMMING_LANGS}\b|"
        r"this\s+code|my\s+code|the\s+code|this\s+script|my\s+script|the\s+script|"
        r"this\s+function|my\s+function|stack\s*trace|syntax\s+error)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bwhy\s+is\s+(?:my|this)\s+(?:code|script|function|program|component|{PROGRAMMING_LANGS})"
        r"\s+(?:failing|throwing|broken|not\s+working|erroring)\b",
        re.IGNORECASE,
    ),
]

# 3. Explaining code / snippets
CODE_EXPLAIN_PATTERNS = [
    re.compile(
        rf"\b(?:explain|walkthrough|dissect)\s+(?:this|the|my)?\s*"
        rf"(?:{PROGRAMMING_LANGS}\s+)?(?:code|script|function|snippet|class|component|hook|algorithm)\b",
        re.IGNORECASE,
    ),
]

# 4. Programming tutorials and learning to code
CODE_TUTORIAL_PATTERNS = [
    re.compile(
        rf"\b(?:teach\s+me|learn|tutorial|guide\s+on\s+how\s+to\s+(?:code|program)|how\s+to\s+(?:code|program))\b"
        rf"(?:\s+\w+){{0,2}}\s+(?:in\s+)?{PROGRAMMING_LANGS}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bhow\s+to\s+(?:code|program|write\s+(?:code|software|programs?))\s+(?:in\s+)?{PROGRAMMING_LANGS}\b",
        re.IGNORECASE,
    ),
]

# 5. Raw code block blocks (e.g. ```python ... ```) or code syntax submitted for programming assistance
CODE_BLOCK_PATTERN = re.compile(
    r"```(?:python|java|javascript|typescript|jsx|tsx|cpp|c|rust|go|php|rb|sh|bash)",
    re.IGNORECASE,
)
CODE_SYNTAX_SIGNATURES = [
    re.compile(r"\bdef\s+[a-zA-Z_]\w*\s*\([^)]*\)\s*:", re.MULTILINE),
    re.compile(r"\bimport\s+React\b", re.IGNORECASE),
    re.compile(r"\bpublic\s+class\s+[A-Z]\w*", re.MULTILINE),
    re.compile(r"\bconsole\.log\(", re.IGNORECASE),
    re.compile(r"\bconst\s+[a-zA-Z_]\w*\s*=\s*\([^)]*\)\s*=>", re.MULTILINE),
]

# Explicit safe keywords for analytical and database inquiries
SAFE_DATA_KEYWORDS = re.compile(
    r"\b(?:sql|database|postgres|postgresql|table|tables|column|columns|schema|schemas|"
    r"query|queries|analytics|revenue|sales|orders?|customers?|users?|products?|inventory|"
    r"report|records?|average|sum|count|rank|ranking|growth|margin|churn|metric)\b",
    re.IGNORECASE,
)


def check_code_generation(query: str) -> CodeGuardrailResult:
    """Evaluates whether the user query is asking for programming/code generation.

    Distinguishes strictly between general programming requests (blocked) and
    database/analytical data questions (allowed, even if mentioning SQL or queries).

    Returns:
        CodeGuardrailResult indicating if the request is blocked, reason, and message.
    """
    clean_query = query.strip()

    # Rule 0: Allow purely SQL/analytical requests
    # If the user asks for SQL queries, database questions, schema inspection, or business analytics,
    # we verify whether it's genuine data analysis vs writing programming applications.
    has_sql_or_db = bool(re.search(r"\b(?:sql|database|postgres|postgresql)\b", clean_query, re.IGNORECASE))
    has_prog_lang = bool(re.search(rf"\b{PROGRAMMING_LANGS}\b", clean_query, re.IGNORECASE))

    # If the query asks for SQL analytics (e.g. "Write a SQL query for top revenue"), allow it
    if has_sql_or_db and not has_prog_lang:
        # Check if it's asking for a general program anyway
        if not any(pat.search(clean_query) for pat in CODE_GEN_PATTERNS + CODE_DEBUG_PATTERNS):
            return CodeGuardrailResult(is_blocked=False)

    # 1. Check code generation patterns
    for pat in CODE_GEN_PATTERNS:
        if pat.search(clean_query):
            return CodeGuardrailResult(
                is_blocked=True,
                reason="Prohibited code generation request.",
                rejection_message=REJECTION_MESSAGE,
            )

    # 2. Check debugging and fixing code
    for pat in CODE_DEBUG_PATTERNS:
        if pat.search(clean_query):
            return CodeGuardrailResult(
                is_blocked=True,
                reason="Prohibited code debugging/troubleshooting request.",
                rejection_message=REJECTION_MESSAGE,
            )

    # 3. Check code explanation
    for pat in CODE_EXPLAIN_PATTERNS:
        if pat.search(clean_query):
            return CodeGuardrailResult(
                is_blocked=True,
                reason="Prohibited code explanation request.",
                rejection_message=REJECTION_MESSAGE,
            )

    # 4. Check programming tutorials
    for pat in CODE_TUTORIAL_PATTERNS:
        if pat.search(clean_query):
            return CodeGuardrailResult(
                is_blocked=True,
                reason="Prohibited programming tutorial request.",
                rejection_message=REJECTION_MESSAGE,
            )

    # 5. Check embedded programming code snippets requesting assistance
    if CODE_BLOCK_PATTERN.search(clean_query):
        # A markdown code block with a programming language tag
        return CodeGuardrailResult(
            is_blocked=True,
            reason="Prohibited programming code snippet submission.",
            rejection_message=REJECTION_MESSAGE,
        )

    for syntax_pat in CODE_SYNTAX_SIGNATURES:
        if syntax_pat.search(clean_query):
            # Check if user is asking to debug/explain/run this syntax
            if re.search(r"\b(?:fix|debug|why|run|execute|explain|error|help|issue)\b", clean_query, re.IGNORECASE):
                return CodeGuardrailResult(
                    is_blocked=True,
                    reason="Prohibited programming code syntax detected.",
                    rejection_message=REJECTION_MESSAGE,
                )

    return CodeGuardrailResult(is_blocked=False)
