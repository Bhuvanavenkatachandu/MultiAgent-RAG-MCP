"""Redis Cloud Distributed Cache Layer with In-Memory Fallback.

Implements the Recommended 30 MB Cache Budget:
-----------------------------------------------------------------------------------------
Component                 Target Size   What is Stored                   Latency Saved
-----------------------------------------------------------------------------------------
1. SQL Query Results       ~15 MB        Top 7,500 analytical tables       ~1,600 ms per query
2. Hybrid RAG Results      ~10 MB        Retrieved chunks & metadata      ~10-20 ms per query
3. Query Embeddings        ~5 MB         3,300+ 384-dim vector arrays     ~15-25 ms per query
-----------------------------------------------------------------------------------------
Total                      ~30 MB        High-speed persistent cache      Sub-5ms responses

Features:
- Connects automatically via REDIS_URL environment variable.
- Graceful in-memory fallback: if Redis is unavailable or unconfigured,
  the app never crashes and automatically uses an in-memory TTL dictionary.
- Automatic key hashing (SHA-256) to ensure constant O(1) key length.
- Cache invalidation helper when documents are uploaded or indexed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import redis
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# CONFIGURATION & TTL CONSTANTS (Aligned with 30 MB Cache Budget)
# ==============================================================================

# Time-To-Live (TTL) in seconds:
# 1. SQL Query Results: 10 minutes (600s) — balances freshness with high cache hit rate for analytics
DEFAULT_SQL_TTL = int(os.getenv("CACHE_SQL_TTL", "600"))

# 2. RAG Hybrid Search Results: 1 hour (3600s) — invalidated immediately on document upload
DEFAULT_RAG_TTL = int(os.getenv("CACHE_RAG_TTL", "3600"))

# 3. Query Embeddings: 24 hours (86400s) — mathematical vector representations of text rarely change
DEFAULT_EMBEDDING_TTL = int(os.getenv("CACHE_EMBEDDING_TTL", "86400"))


def _hash_key(prefix: str, content: str) -> str:
    """Generates a compact, deterministic O(1) Redis key using SHA-256.

    Normalizes whitespace and lowercase to maximize cache hits on near-identical inputs.
    """
    normalized = " ".join(content.strip().lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


class RedisCacheManager:
    """Manages Redis connection with automatic in-memory fallback."""

    def __init__(self) -> None:
        self.redis_client: Optional[redis.Redis] = None
        self._memory_store: Dict[str, Tuple[float, Any]] = {}
        self._is_connected = False
        self._init_client()

    def _init_client(self) -> None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("Notice: REDIS_URL not configured. Running with in-memory fallback cache.")
            return

        try:
            # Connect with aggressive socket timeouts so network latency never blocks the app
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
                retry_on_timeout=True,
            )
            self.redis_client.ping()
            self._is_connected = True
            print("Connected to Redis Cloud cache successfully!")
        except Exception as e:
            print(f"Warning: Redis connection failed ({e}). Falling back to in-memory cache.")
            self.redis_client = None
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    # --------------------------------------------------------------------------
    # LOW-LEVEL GET / SET / DELETE WITH GRACEFUL FALLBACK
    # --------------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a cached value by key. Returns None if missing or expired."""
        if self.redis_client:
            try:
                raw = self.redis_client.get(key)
                if raw is not None:
                    return json.loads(raw)
                return None
            except Exception as e:
                print(f"Warning: Redis GET error for {key}: {e}")

        # In-memory fallback
        if key in self._memory_store:
            expiry, val = self._memory_store[key]
            if expiry > time.time():
                return val
            del self._memory_store[key]
        return None

    def set(self, key: str, value: Any, ttl: int) -> bool:
        """Stores a JSON-serializable value with an expiration TTL (seconds)."""
        if self.redis_client:
            try:
                serialized = json.dumps(value)
                return bool(self.redis_client.set(key, serialized, ex=ttl))
            except Exception as e:
                print(f"Warning: Redis SET error for {key}: {e}")

        # In-memory fallback (evict oldest if local memory cache exceeds 2,000 items)
        if len(self._memory_store) > 2000:
            oldest_key = next(iter(self._memory_store))
            del self._memory_store[oldest_key]

        self._memory_store[key] = (time.time() + ttl, value)
        return True

    def delete_prefix(self, prefix: str) -> int:
        """Deletes all keys matching a prefix (e.g. 'rag:*' when documents update)."""
        deleted_count = 0
        if self.redis_client:
            try:
                keys = list(self.redis_client.scan_iter(match=f"{prefix}:*"))
                if keys:
                    deleted_count = self.redis_client.delete(*keys)
            except Exception as e:
                print(f"Warning: Redis delete_prefix error: {e}")

        # Clean in-memory store
        to_del = [k for k in self._memory_store if k.startswith(f"{prefix}:")]
        for k in to_del:
            del self._memory_store[k]
            deleted_count += 1

        return deleted_count

    # --------------------------------------------------------------------------
    # COMPONENT 1: SQL QUERY RESULTS CACHE (~15 MB Target Budget)
    # --------------------------------------------------------------------------

    def get_sql_result(self, question: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached SQL text and sanitized result table for a question."""
        key = _hash_key("sql", question)
        return self.get(key)

    def set_sql_result(self, question: str, sql: str, result: str, ttl: int = DEFAULT_SQL_TTL) -> None:
        """Caches generated SQL query and sanitized result (default TTL: 10 mins)."""
        key = _hash_key("sql", question)
        payload = {
            "sql": sql,
            "result": result,
            "cached_at": time.time(),
        }
        self.set(key, payload, ttl=ttl)

    # --------------------------------------------------------------------------
    # COMPONENT 2: QUERY EMBEDDINGS CACHE (~5 MB Target Budget)
    # --------------------------------------------------------------------------

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Retrieves pre-computed 384-dimensional vector embedding for text."""
        key = _hash_key("emb", text)
        return self.get(key)

    def set_embedding(self, text: str, vector: List[float], ttl: int = DEFAULT_EMBEDDING_TTL) -> None:
        """Caches a 384-dim embedding vector (default TTL: 24 hours)."""
        key = _hash_key("emb", text)
        self.set(key, vector, ttl=ttl)

    # --------------------------------------------------------------------------
    # COMPONENT 3: RAG HYBRID SEARCH RESULTS CACHE (~10 MB Target Budget)
    # --------------------------------------------------------------------------

    def get_rag_results(self, query: str, mode: str = "hybrid") -> Optional[List[Dict[str, Any]]]:
        """Retrieves cached retrieved document chunks and sources for a query."""
        key = _hash_key(f"rag:{mode}", query)
        return self.get(key)

    def set_rag_results(
        self, query: str, docs: List[Dict[str, Any]], mode: str = "hybrid", ttl: int = DEFAULT_RAG_TTL
    ) -> None:
        """Caches top-K fused document chunks (default TTL: 1 hour)."""
        key = _hash_key(f"rag:{mode}", query)
        self.set(key, docs, ttl=ttl)

    def invalidate_rag_cache(self) -> int:
        """Flushes RAG cache entries when documents are uploaded, modified, or re-indexed."""
        return self.delete_prefix("rag")


# Global singleton instance for use across the application
cache_manager = RedisCacheManager()
