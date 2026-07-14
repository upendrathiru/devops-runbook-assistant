"""
Retrieval pipeline: embeds chunks, builds a vector index, and serves
top-k nearest-neighbour search for a query.

Embedding backend
------------------
Default: TF-IDF vectors (scikit-learn) — no network access, no GPU, no API
key required, and good enough for keyword-heavy runbook text. This plays
the same architectural role as "OpenAI embedding, or a local model" in the
spec; swap `TfidfEmbeddingIndex` for a sentence-transformers or OpenAI
embedding-backed index in production without touching any other module —
see `EmbeddingIndex` interface below.

Vector store
------------
Chunk vectors + metadata are persisted to a single pickle file (data/index.pkl).
This plays the same role as FAISS/Pinecone/Weaviate in the spec. For larger
corpora, swap in a real FAISS `IndexFlatIP` behind the same `search()` interface.
"""
import pickle
import os
from dataclasses import asdict
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import INDEX_PATH, TOP_K, MIN_SIMILARITY
from ingestion import Chunk, load_and_chunk_documents


class EmbeddingIndex:
    """Interface any embedding/vector-store backend should implement."""

    def build(self, chunks: List[Chunk]) -> None:
        raise NotImplementedError

    def search(self, query: str, top_k: int = TOP_K) -> List[Tuple[Chunk, float]]:
        raise NotImplementedError

    def save(self, path: str) -> None:
        raise NotImplementedError

    @classmethod
    def load(cls, path: str) -> "EmbeddingIndex":
        raise NotImplementedError


class TfidfEmbeddingIndex(EmbeddingIndex):
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_df=0.9,
        )
        self.matrix = None
        self.chunks: List[Chunk] = []

    def build(self, chunks: List[Chunk]) -> None:
        self.chunks = chunks
        texts = [c.text for c in chunks]
        if not texts:
            self.matrix = None
            return
        self.matrix = self.vectorizer.fit_transform(texts)

    def search(self, query: str, top_k: int = TOP_K) -> List[Tuple[Chunk, float]]:
        if self.matrix is None or not self.chunks:
            return []
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.matrix)[0]
        ranked_idx = np.argsort(-sims)[:top_k]
        results = [(self.chunks[i], float(sims[i])) for i in ranked_idx if sims[i] >= MIN_SIMILARITY]
        return results

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "matrix": self.matrix,
                "chunks": [asdict(c) for c in self.chunks],
            }, f)

    @classmethod
    def load(cls, path: str) -> "TfidfEmbeddingIndex":
        with open(path, "rb") as f:
            data = pickle.load(f)
        idx = cls()
        idx.vectorizer = data["vectorizer"]
        idx.matrix = data["matrix"]
        idx.chunks = [Chunk(**c) for c in data["chunks"]]
        return idx


_INDEX_SINGLETON: TfidfEmbeddingIndex = None


def get_index(rebuild: bool = False) -> TfidfEmbeddingIndex:
    """
    Returns a process-wide singleton index, loading from disk if present,
    or building fresh from the docs directory otherwise.
    """
    global _INDEX_SINGLETON
    if _INDEX_SINGLETON is not None and not rebuild:
        return _INDEX_SINGLETON

    if not rebuild and os.path.exists(INDEX_PATH):
        _INDEX_SINGLETON = TfidfEmbeddingIndex.load(INDEX_PATH)
        return _INDEX_SINGLETON

    chunks = load_and_chunk_documents()
    idx = TfidfEmbeddingIndex()
    idx.build(chunks)
    idx.save(INDEX_PATH)
    _INDEX_SINGLETON = idx
    return _INDEX_SINGLETON


if __name__ == "__main__":
    index = get_index(rebuild=True)
    print(f"Indexed {len(index.chunks)} chunks.")
    for chunk, score in index.search("how do I roll back a deployment"):
        print(f"{score:.3f}  [{chunk.source_title} / {chunk.section}]  {chunk.text[:70]}...")
