from __future__ import annotations

import os
from typing import List
from dotenv import load_dotenv
from huggingface_hub import login
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

from mcp_using_langchain.cache import cache_manager

load_dotenv()


def _configure_huggingface_auth():
    """Configures Hugging Face Hub authentication using HF_TOKEN environment variable."""
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        try:
            login(token=hf_token, add_to_git_credential=False)
        except Exception:
            pass


class CachedFastEmbedEmbeddings(FastEmbedEmbeddings):
    """Embeddings wrapper caching query embeddings in Redis/RAM (~5 MB Budget).

    Caches 384-dimensional vector representations of text queries with a 24-hour TTL,
    saving ~15-25 ms of FastEmbed CPU inference on repeated or similar retrieval queries.
    """

    def embed_query(self, text: str) -> List[float]:
        # Check cache (Component 3: Query Embeddings, ~5 MB budget)
        cached_vector = cache_manager.get_embedding(text)
        if cached_vector is not None and isinstance(cached_vector, list):
            return cached_vector

        vector = super().embed_query(text)
        cache_manager.set_embedding(text, vector)
        return vector


def get_embeddings():
    _configure_huggingface_auth()

    embeddings = CachedFastEmbedEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return embeddings
