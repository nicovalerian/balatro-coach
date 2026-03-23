"""
RAG retriever: hybrid dense (ChromaDB + sentence-transformers) +
sparse (BM25) retrieval, with separate card-level and guide-level collections.

Retrieval strategy:
  - card-level collection: best for joker/card-specific lookups
  - guide-level collection: best for strategic questions
  - hybrid re-rank: merge + deduplicate by relevance score
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
    logger.warning("chromadb not installed – RAG disabled")

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

class RAGRetriever:
    CARD_COLLECTION = "balatro_cards"
    GUIDE_COLLECTION = "balatro_guides"

    def __init__(self, persist_dir: Path, embed_model: str = "all-MiniLM-L6-v2"):
        if not _CHROMA_AVAILABLE:
            raise RuntimeError("chromadb is required for RAG features")

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._ef = SentenceTransformerEmbeddingFunction(model_name=embed_model)

        self._cards = self._client.get_or_create_collection(
            self.CARD_COLLECTION, embedding_function=self._ef
        )
        self._guides = self._client.get_or_create_collection(
            self.GUIDE_COLLECTION, embedding_function=self._ef
        )
        # BM25 index built lazily
        self._bm25_cards: "BM25Okapi | None" = None
        self._bm25_guides: "BM25Okapi | None" = None
        self._bm25_card_docs: list[dict] = []
        self._bm25_guide_docs: list[dict] = []

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_documents(self, docs: list[dict]) -> None:
        """Add docs to the appropriate collection. Skips duplicates by id."""
        card_docs = [d for d in docs if d["metadata"].get("type") == "card"]
        guide_docs = [d for d in docs if d["metadata"].get("type") == "guide"]

        if card_docs:
            self._upsert(self._cards, card_docs)
            self._bm25_cards = None  # invalidate cache
        if guide_docs:
            self._upsert(self._guides, guide_docs)
            self._bm25_guides = None

        logger.info(
            "indexed %d card docs, %d guide docs",
            len(card_docs), len(guide_docs),
        )

    def _upsert(self, collection, docs: list[dict]) -> None:
        ids = [_make_id(d) for d in docs]
        texts = [d["text"] for d in docs]
        metas = [d["metadata"] for d in docs]
        # chromadb upsert in batches of 100
        for i in range(0, len(docs), 100):
            collection.upsert(
                ids=ids[i:i+100],
                documents=texts[i:i+100],
                metadatas=metas[i:i+100],
            )

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        """
        Hybrid retrieval: top_k//2 from each collection.
        Falls back to dense-only if BM25 not available.
        """
        half = max(1, top_k // 2)
        card_results = self._hybrid_query(query, self._cards, half, "card")
        guide_results = self._hybrid_query(query, self._guides, half, "guide")

        combined = card_results + guide_results
        # deduplicate by id
        seen: set[str] = set()
        unique: list[dict] = []
        for r in sorted(combined, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        return unique[:top_k]

    def _hybrid_query(
        self,
        query: str,
        collection,
        n: int,
        kind: str,
    ) -> list[dict]:
        if collection.count() == 0:
            return []

        # Dense retrieval
        dense = collection.query(query_texts=[query], n_results=min(n * 2, collection.count()))
        dense_results = [
            {
                "id": dense["ids"][0][i],
                "text": dense["documents"][0][i],
                "metadata": dense["metadatas"][0][i],
                "score": 1 - dense["distances"][0][i],  # cosine: 1-dist → similarity
            }
            for i in range(len(dense["ids"][0]))
        ]

        if not _BM25_AVAILABLE:
            return dense_results[:n]

        # Sparse BM25 retrieval
        bm25_results = self._bm25_query(query, collection, kind, n * 2)

        # RRF (Reciprocal Rank Fusion) merge
        return _rrf_merge(dense_results, bm25_results)[:n]

    def _bm25_query(self, query: str, collection, kind: str, n: int) -> list[dict]:
        """Build/cache BM25 index and query it."""
        if kind == "card":
            if self._bm25_cards is None:
                all_docs = collection.get()
                self._bm25_card_docs = [
                    {"id": i, "text": t, "metadata": m}
                    for i, t, m in zip(
                        all_docs["ids"],
                        all_docs["documents"],
                        all_docs["metadatas"],
                    )
                ]
                corpus = [_tokenise(d["text"]) for d in self._bm25_card_docs]
                self._bm25_cards = BM25Okapi(corpus)
            bm25 = self._bm25_cards
            docs = self._bm25_card_docs
        else:
            if self._bm25_guides is None:
                all_docs = collection.get()
                self._bm25_guide_docs = [
                    {"id": i, "text": t, "metadata": m}
                    for i, t, m in zip(
                        all_docs["ids"],
                        all_docs["documents"],
                        all_docs["metadatas"],
                    )
                ]
                corpus = [_tokenise(d["text"]) for d in self._bm25_guide_docs]
                self._bm25_guides = BM25Okapi(corpus)
            bm25 = self._bm25_guides
            docs = self._bm25_guide_docs

        scores = bm25.get_scores(_tokenise(query))
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [
            {
                "id": docs[i]["id"],
                "text": docs[i]["text"],
                "metadata": docs[i]["metadata"],
                "score": float(scores[i]),
            }
            for i in top_idx
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_id(doc: dict) -> str:
    import hashlib
    return hashlib.md5(doc["text"][:200].encode()).hexdigest()


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _rrf_merge(
    dense: list[dict],
    sparse: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion: score = 1/(k + rank)."""
    scores: dict[str, float] = {}
    docs_by_id: dict[str, dict] = {}

    for rank, r in enumerate(dense):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (k + rank + 1)
        docs_by_id[r["id"]] = r

    for rank, r in enumerate(sparse):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (k + rank + 1)
        docs_by_id[r["id"]] = r

    ranked = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    result = []
    for doc_id in ranked:
        doc = docs_by_id[doc_id].copy()
        doc["score"] = scores[doc_id]
        result.append(doc)
    return result
