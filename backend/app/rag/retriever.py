"""
RAG retriever: hybrid dense (ChromaDB + sentence-transformers) +
sparse (BM25) retrieval, with adaptive collection weighting and
optional cross-encoder reranking.

Retrieval strategy:
  - card-level collection: best for joker/card-specific lookups
  - guide-level collection: best for strategic questions
  - adaptive split: card vs. guide fetch counts inferred from query intent
  - cross-encoder reranker: re-scores RRF candidates for precision
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

try:
    from sentence_transformers import CrossEncoder
    _CROSS_ENCODER_AVAILABLE = True
except ImportError:
    _CROSS_ENCODER_AVAILABLE = False


class RAGRetriever:
    CARD_COLLECTION = "balatro_cards"
    GUIDE_COLLECTION = "balatro_guides"

    def __init__(
        self,
        persist_dir: Path,
        embed_model: str = "all-MiniLM-L6-v2",
        rerank_model: str | None = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        reranker_candidates: int = 20,
    ):
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

        self._rerank_model_name: str | None = rerank_model
        self._reranker: "CrossEncoder | None" = None  # lazy-loaded
        self._reranker_candidates = reranker_candidates

    # ── Reranker ──────────────────────────────────────────────────────────────

    def _get_reranker(self) -> "CrossEncoder | None":
        if not _CROSS_ENCODER_AVAILABLE or not self._rerank_model_name:
            return None
        if self._reranker is None:
            try:
                self._reranker = CrossEncoder(self._rerank_model_name)
                logger.info("Loaded cross-encoder reranker: %s", self._rerank_model_name)
            except Exception as exc:
                logger.warning("Failed to load reranker '%s': %s", self._rerank_model_name, exc)
                self._rerank_model_name = None
                return None
        return self._reranker

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_documents(self, docs: list[dict]) -> None:
        """Add docs to the appropriate collection. Skips duplicates by id."""
        card_docs = [d for d in docs if d["metadata"].get("type") == "card"]
        guide_docs = [d for d in docs if d["metadata"].get("type") == "guide"]

        if card_docs:
            self._upsert(self._cards, card_docs)
            self._bm25_cards = None
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
        for i in range(0, len(docs), 100):
            collection.upsert(
                ids=ids[i:i+100],
                documents=texts[i:i+100],
                metadatas=metas[i:i+100],
            )

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        """
        Hybrid retrieval: adaptive card/guide split → dense + BM25 → RRF merge
        → optional cross-encoder reranking → top_k results.
        """
        card_k, guide_k = self._adaptive_split(query, top_k)

        reranker = self._get_reranker()
        fetch_card = card_k if not reranker else max(card_k, self._reranker_candidates // 2)
        fetch_guide = guide_k if not reranker else max(guide_k, self._reranker_candidates // 2)

        card_results = self._hybrid_query(query, self._cards, fetch_card, "card")
        guide_results = self._hybrid_query(query, self._guides, fetch_guide, "guide")

        combined = card_results + guide_results
        seen: set[str] = set()
        unique: list[dict] = []
        for r in sorted(combined, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        candidates = unique[:max(top_k, self._reranker_candidates)]

        if reranker and len(candidates) > 1:
            pairs = [(query, c["text"]) for c in candidates]
            try:
                scores = reranker.predict(pairs)
                for i in range(len(candidates)):
                    candidates[i] = {**candidates[i], "score": float(scores[i])}
                candidates.sort(key=lambda x: x["score"], reverse=True)
            except Exception as exc:
                logger.warning("Reranker prediction failed, using RRF order: %s", exc)

        return candidates[:top_k]

    def _adaptive_split(self, query: str, top_k: int) -> tuple[int, int]:
        """Weight card vs. guide collection fetch counts based on query intent."""
        lower = query.lower()
        strategy_kws = {
            "economy", "survive", "scaling", "early ante", "mid game", "planet",
            "boss blind", "ante", "skip", "reroll", "interest", "when should",
            "how do i", "priority", "discard", "deck",
        }
        card_kws = {
            "what does", "how does", "joker", "tarot", "spectral",
            "voucher", "effect of", "hologram", "blueprint",
        }
        guide_score = sum(1 for kw in strategy_kws if kw in lower)
        card_score = sum(1 for kw in card_kws if kw in lower)

        if card_score > guide_score:
            card_k = max(1, top_k * 2 // 3)
            guide_k = max(1, top_k - card_k)
        elif guide_score > card_score:
            guide_k = max(1, top_k * 2 // 3)
            card_k = max(1, top_k - guide_k)
        else:
            half = max(1, top_k // 2)
            card_k = half
            guide_k = half
        return card_k, guide_k

    def _hybrid_query(
        self,
        query: str,
        collection,
        n: int,
        kind: str,
    ) -> list[dict]:
        if collection.count() == 0:
            return []

        dense = collection.query(query_texts=[query], n_results=min(n * 2, collection.count()))
        dense_results = [
            {
                "id": dense["ids"][0][i],
                "text": dense["documents"][0][i],
                "metadata": dense["metadatas"][0][i],
                "score": 1 - dense["distances"][0][i],
            }
            for i in range(len(dense["ids"][0]))
        ]

        if not _BM25_AVAILABLE:
            return dense_results[:n]

        bm25_results = self._bm25_query(query, collection, kind, n * 2)
        return _rrf_merge(dense_results, bm25_results)[:n]

    def _bm25_query(self, query: str, collection, kind: str, n: int) -> list[dict]:
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
    return hashlib.md5(doc["text"].encode()).hexdigest()


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
