import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# 1. Search and load .env from multiple potential candidate locations
_candidates = [
    Path(find_dotenv()) if find_dotenv() else None,
    Path.cwd() / ".env",
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
]

for candidate in _candidates:
    if candidate and candidate.is_file():
        load_dotenv(dotenv_path=candidate, override=False)

# 2. Project default credentials fallback (prevents 'initialized without public_key' errors)
DEFAULT_LANGFUSE_PUBLIC_KEY = "pk-lf-4d901517-43d6-4a15-b7c1-2c6fab49481d"
DEFAULT_LANGFUSE_SECRET_KEY = "sk-lf-83b1f4ec-dbb2-42f8-ae8e-0f43f4821eae"
DEFAULT_LANGFUSE_BASE_URL = "https://cloud.langfuse.com"

if not os.getenv("LANGFUSE_PUBLIC_KEY"):
    os.environ["LANGFUSE_PUBLIC_KEY"] = DEFAULT_LANGFUSE_PUBLIC_KEY

if not os.getenv("LANGFUSE_SECRET_KEY"):
    os.environ["LANGFUSE_SECRET_KEY"] = DEFAULT_LANGFUSE_SECRET_KEY

if not os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_BASE_URL"] = DEFAULT_LANGFUSE_BASE_URL

if not os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL", DEFAULT_LANGFUSE_BASE_URL)

# 3. Now safely import Langfuse SDK after environment is fully prepared
from langfuse import get_client, observe, propagate_attributes
from langfuse.langchain import CallbackHandler


def flush_langfuse():
    """Safely flush pending Langfuse events."""
    try:
        client = get_client()
        client.flush()
    except Exception as e:
        print(f"[tracing] Warning during flush: {e}")


__all__ = [
    "get_client",
    "observe",
    "propagate_attributes",
    "CallbackHandler",
    "flush_langfuse",
]
