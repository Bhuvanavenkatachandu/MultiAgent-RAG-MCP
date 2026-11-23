
import math
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mcp_using_langchain.tracing import get_client, observe

from .loader import load_documents
from .embeddings import get_embeddings
from .vectorstore import (
    create_vectorstore,
    load_vectorstore
)


class BM25Index:
    """Lightweight, zero-dependency BM25 Okapi keyword indexer."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths: List[int] = []
        self.doc_term_freqs: List[Counter] = []
        self.idf: Dict[str, float] = {}

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Regex tokenization that strips trailing punctuation from keywords."""
        return re.findall(r"\w+", text.lower())

    def fit(self, documents: List[str]):
        """Builds term frequencies and inverted document frequencies from corpus."""
        self.corpus_size = len(documents)
        if self.corpus_size == 0:
            return
        total_len = 0
        df: Counter = Counter()
        self.doc_lengths = []
        self.doc_term_freqs = []

        for doc in documents:
            tokens = self.tokenize(doc)
            length = len(tokens)
            self.doc_lengths.append(length)
            total_len += length
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            for term in tf:
                df[term] += 1

        self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 1.0
        for term, freq in df.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def score(self, query: str) -> List[float]:
        """Computes BM25 Okapi score for query against every indexed document."""
        query_tokens = self.tokenize(query)
        scores = [0.0] * self.corpus_size
        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for idx in range(self.corpus_size):
                tf = self.doc_term_freqs[idx].get(term, 0)
                if tf > 0:
                    doc_len = self.doc_lengths[idx]
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                    scores[idx] += idf_val * (tf * (self.k1 + 1.0)) / denom
        return scores

    def top_k(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        """Returns top-k (document_index, score) pairs sorted by relevance."""
        scores = self.score(query)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]


class HybridRetriever:
    """Unified Retriever supporting FAISS, BM25+FAISS Hybrid (RRF), and Cross-Encoder Reranking."""

    def __init__(
        self,
        vectorstore,
        chunks: List[Document],
        mode: str = "hybrid",
        k: int = 4,
    ):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.mode = mode.lower()
        self.k = k

        # Initialize BM25 keyword index from chunk corpus
        self.bm25 = BM25Index()
        self.chunk_texts = [c.page_content for c in self.chunks]
        self.bm25.fit(self.chunk_texts)

        # Cross-Encoder (lazy loaded on demand)
        self._cross_encoder = None

    @property
    def cross_encoder(self):
        if self._cross_encoder is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._cross_encoder = TextCrossEncoder(model_name="Xenova/ms-marco-MiniLM-L-6-v2")
        return self._cross_encoder

    def retrieve_faiss(self, query: str, top_k: int = 5) -> Tuple[List[Document], float]:
        """Experiment 1: Pure FAISS vector similarity search."""
        t0 = time.perf_counter()
        results = self.vectorstore.similarity_search(query, k=top_k)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return results, latency_ms

    def retrieve_hybrid(self, query: str, top_k: int = 5) -> Tuple[List[Document], float]:
        """Experiment 2: BM25 + FAISS Hybrid Retrieval with Reciprocal Rank Fusion."""
        t0 = time.perf_counter()

        # FAISS search (fetch top 10 candidates)
        faiss_docs = self.vectorstore.similarity_search(query, k=min(10, len(self.chunks)))

        # BM25 search (fetch top 10 candidates)
        bm25_matches = self.bm25.top_k(query, k=min(10, len(self.chunks)))

        # Reciprocal Rank Fusion (k_rrf = 60)
        k_rrf = 60
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, doc in enumerate(faiss_docs):
            content = doc.page_content
            doc_map[content] = doc
            rrf_scores[content] = rrf_scores.get(content, 0.0) + (0.5 / (k_rrf + rank + 1))

        for rank, (idx, bm25_score) in enumerate(bm25_matches):
            if bm25_score > 0:  # Only fuse non-zero BM25 matches
                doc = self.chunks[idx]
                content = doc.page_content
                if content not in doc_map:
                    doc_map[content] = doc
                rrf_scores[content] = rrf_scores.get(content, 0.0) + (0.5 / (k_rrf + rank + 1))

        sorted_contents = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = [doc_map[c] for c, _ in sorted_contents]
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return results, latency_ms

    def retrieve_hybrid_rerank(
        self, query: str, top_k: int = 5, score_threshold: float = -6.0
    ) -> Tuple[List[Document], float, float]:
        """Experiment 3: Hybrid Retrieval + Cross-Encoder Reranking with threshold filtering."""
        # 1. Fetch hybrid candidates
        candidates, ret_latency_ms = self.retrieve_hybrid(query, top_k=min(10, len(self.chunks)))
        if not candidates:
            return [], ret_latency_ms, 0.0

        # 2. Score with Cross-Encoder
        t0 = time.perf_counter()
        candidate_texts = [c.page_content for c in candidates]
        scores = list(self.cross_encoder.rerank(query, candidate_texts))
        rerank_latency_ms = (time.perf_counter() - t0) * 1000.0

        # 3. Filter and sort by cross-encoder score
        scored_pairs = list(zip(candidates, scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        # Apply score threshold to prevent distractor noise from entering generation context
        top_score = scored_pairs[0][1] if scored_pairs else 0.0
        filtered_results = []
        for doc, score in scored_pairs:
            # Keep chunk if it is the best match, or within 5 points of top match and above floor
            if len(filtered_results) == 0 or (score >= max(score_threshold, top_score - 5.0)):
                filtered_results.append(doc)
            if len(filtered_results) >= top_k:
                break

        return filtered_results, ret_latency_ms, rerank_latency_ms

    def invoke(self, query: str) -> List[Document]:
        """LangChain-standard retrieval invoke interface."""
        if self.mode == "faiss":
            docs, _ = self.retrieve_faiss(query, top_k=self.k)
            return docs
        elif self.mode == "hybrid_rerank":
            docs, _, _ = self.retrieve_hybrid_rerank(query, top_k=self.k)
            return docs
        else:  # default to hybrid
            docs, _ = self.retrieve_hybrid(query, top_k=self.k)
            return docs


@observe(name="get-or-build-retriever", as_type="span", capture_input=False, capture_output=False)
def get_retriever(mode: Optional[str] = None, rebuild: bool = False, k: int = 4) -> HybridRetriever:
    langfuse = get_client()
    selected_mode = mode or os.getenv("RETRIEVAL_MODE", "hybrid")
    langfuse.update_current_span(input={"rebuild": rebuild, "mode": selected_mode, "k": k})

    embeddings = get_embeddings()

    # Optimal semantic chunking: 750 characters preserves complete policy paragraphs without fragmentation
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=750,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " "]
    )

    if rebuild:
        documents = load_documents()
        chunks = splitter.split_documents(documents)
        for idx, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = idx
            source_stem = Path(chunk.metadata.get("source", "doc")).stem
            chunk.metadata["title"] = chunk.metadata.get("title", source_stem)

        print(f"Created {len(chunks)} chunks")
        vectorstore = create_vectorstore(chunks, embeddings)
        langfuse.update_current_span(output={"status": "rebuilt", "chunks_count": len(chunks)})

    else:
        try:
            vectorstore = load_vectorstore(embeddings)
            # Reconstruct chunks list from docstore
            docstore = vectorstore.docstore
            index_to_id = vectorstore.index_to_docstore_id
            chunk_ids = [index_to_id[i] for i in range(len(index_to_id))]
            chunks = [docstore.search(cid) for cid in chunk_ids]
            langfuse.update_current_span(output={"status": "loaded_existing", "chunks_count": len(chunks)})

        except FileNotFoundError:
            documents = load_documents()
            chunks = splitter.split_documents(documents)
            for idx, chunk in enumerate(chunks):
                chunk.metadata["chunk_id"] = idx
                source_stem = Path(chunk.metadata.get("source", "doc")).stem
                chunk.metadata["title"] = chunk.metadata.get("title", source_stem)

            print(f"Created {len(chunks)} chunks")
            vectorstore = create_vectorstore(chunks, embeddings)
            langfuse.update_current_span(output={"status": "built_initial", "chunks_count": len(chunks)})

    return HybridRetriever(
        vectorstore=vectorstore,
        chunks=chunks,
        mode=selected_mode,
        k=k,
    )


