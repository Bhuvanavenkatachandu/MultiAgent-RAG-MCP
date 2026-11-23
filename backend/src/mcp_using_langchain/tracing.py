import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Ensure environment variables are loaded
_dotenv_path = find_dotenv()
if _dotenv_path:
    load_dotenv(dotenv_path=_dotenv_path, override=False)
else:
    load_dotenv(override=False)

# Ensure LANGFUSE_HOST is aligned with LANGFUSE_BASE_URL
if os.getenv("LANGFUSE_BASE_URL") and not os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL")

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
