"""
RAG pipeline evaluation tests.

Metrics:
  Hit@K      — 1 if any relevant doc appears in top-K results (binary)
  MRR        — Mean Reciprocal Rank (1/rank of first relevant, 0 if missing)
  Precision@K — fraction of top-K results that are relevant

Run: cd backend && pytest tests/test_rag_eval.py -v -s

For reranker tests (downloads ~86 MB model):
  pytest tests/test_rag_eval.py -v -s --run-slow
"""
from __future__ import annotations

import pytest

# ── Golden evaluation dataset ─────────────────────────────────────────────────
# Queries cover: boss-blind rules, economy, joker order, planets, deck mechanics,
# scoring tables, early-game survival, anti-synergy, and card-specific lookups.
# relevant_keywords match against retrieved chunk metadata["name"] or leading text.

GOLDEN_DATASET = [
    {
        "id": "boss_blind_skip",
        "query": "Can I skip the boss blind to preserve hands for later?",
        "relevant_keywords": ["boss blind", "Boss blind"],
    },
    {
        "id": "economy_interest",
        "query": "Should I spend money in the shop or keep it for interest breakpoints?",
        "relevant_keywords": ["Economy", "economy", "Mid game scaling"],
    },
    {
        "id": "joker_order",
        "query": "Does the left-to-right order of my jokers change my final score?",
        "relevant_keywords": ["Scoring order", "joker positioning"],
    },
    {
        "id": "planet_tiers",
        "query": "Which poker hands benefit most from leveling up with planet cards?",
        "relevant_keywords": ["Planet card scaling", "planet card"],
    },
    {
        "id": "deck_thinning",
        "query": "Does discarding cards permanently remove them from my deck?",
        "relevant_keywords": ["Deck mechanics", "discard", "deck"],
    },
    {
        "id": "hand_base_values",
        "query": "What are the base chip and mult values for Pair and Straight at level 1?",
        "relevant_keywords": ["Poker hand base scoring", "Base Scoring", "base scoring"],
    },
    {
        "id": "early_survival",
        "query": "What should I focus on to survive early antes in Ante 1 and 2?",
        "relevant_keywords": ["Early", "Ante 1", "survival"],
    },
    {
        "id": "anti_synergy",
        "query": "When should I sell a joker that no longer fits my build?",
        # Both "Pivoting builds" and "Mid game scaling" give relevant guidance on selling jokers
        "relevant_keywords": ["anti-synergy", "Pivoting", "pivoting", "Mid game scaling"],
    },
    {
        "id": "card_hologram",
        "query": "What effect does the Hologram joker have?",
        "relevant_keywords": ["Hologram"],
    },
    {
        "id": "card_blueprint",
        "query": "How does the Blueprint joker work in Balatro?",
        "relevant_keywords": ["Blueprint"],
    },
]


# ── Relevance judgement ───────────────────────────────────────────────────────

def _is_relevant(chunk: dict, keywords: list[str]) -> bool:
    name = chunk["metadata"].get("name", "").lower()
    text_head = chunk["text"][:300].lower()
    return any(kw.lower() in name or kw.lower() in text_head for kw in keywords)


# ── Metrics computation ───────────────────────────────────────────────────────

def _compute_metrics(retriever, dataset: list[dict], top_k: int = 5) -> dict:
    hits: list[int] = []
    reciprocal_ranks: list[float] = []
    precisions: list[float] = []
    per_query: list[dict] = []

    for item in dataset:
        results = retriever.retrieve(item["query"], top_k=top_k)
        relevant_mask = [_is_relevant(r, item["relevant_keywords"]) for r in results]

        hit = int(any(relevant_mask))
        hits.append(hit)

        rr = 0.0
        for rank, is_rel in enumerate(relevant_mask, 1):
            if is_rel:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        precision = sum(relevant_mask) / top_k if top_k else 0.0
        precisions.append(precision)

        per_query.append({
            "id": item["id"],
            "query": item["query"][:60],
            "hit": bool(hit),
            "rr": round(rr, 3),
            "precision": round(precision, 3),
            "top_names": [r["metadata"].get("name", "?")[:40] for r in results],
        })

    n = len(dataset)
    return {
        f"Hit@{top_k}": round(sum(hits) / n, 3),
        "MRR": round(sum(reciprocal_ranks) / n, 3),
        f"Precision@{top_k}": round(sum(precisions) / n, 3),
        "per_query": per_query,
    }


def _print_metrics(label: str, metrics: dict, top_k: int) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    for q in metrics["per_query"]:
        status = "[OK]  " if q["hit"] else "[FAIL]"
        print(f"  {status} [{q['id'][:25]:<25}] RR={q['rr']:.3f}  top: {q['top_names'][:3]}")
    print(f"  {'-'*50}")
    print(
        f"  Hit@{top_k}={metrics[f'Hit@{top_k}']:.3f}  "
        f"MRR={metrics['MRR']:.3f}  "
        f"Precision@{top_k}={metrics[f'Precision@{top_k}']:.3f}"
    )
    print(f"{'='*60}")


# ── Retrieval metric tests ────────────────────────────────────────────────────

class TestRetrievalMetrics:
    """Baseline retrieval quality — hybrid dense+BM25, no reranker."""

    def test_hit_at_5(self, test_retriever):
        metrics = _compute_metrics(test_retriever, GOLDEN_DATASET, top_k=5)
        _print_metrics("Baseline (no reranker), top_k=5", metrics, top_k=5)
        assert metrics["Hit@5"] >= 0.6, (
            f"Hit@5={metrics['Hit@5']:.3f} < 0.6. "
            "Check that strategy guides are indexed and golden keywords match doc names."
        )

    def test_mrr(self, test_retriever):
        metrics = _compute_metrics(test_retriever, GOLDEN_DATASET, top_k=5)
        assert metrics["MRR"] >= 0.4, (
            f"MRR={metrics['MRR']:.3f} < 0.4. "
            "Relevant documents are not ranking highly enough."
        )

    def test_hit_at_3(self, test_retriever):
        metrics = _compute_metrics(test_retriever, GOLDEN_DATASET, top_k=3)
        _print_metrics("Baseline (no reranker), top_k=3", metrics, top_k=3)
        assert metrics["Hit@3"] >= 0.5, (
            f"Hit@3={metrics['Hit@3']:.3f} < 0.5."
        )

    def test_card_queries_retrieve_card_docs(self, test_retriever):
        """Card-specific queries should surface the correct card doc in top-3."""
        card_queries = [
            ("What does Hologram do?", "Hologram"),
            ("How does Blueprint work?", "Blueprint"),
        ]
        for query, expected_name in card_queries:
            results = test_retriever.retrieve(query, top_k=3)
            names = [r["metadata"].get("name", "") for r in results]
            assert any(expected_name.lower() in n.lower() for n in names), (
                f"Query '{query}': expected '{expected_name}' in top-3, got {names}"
            )

    def test_guide_queries_retrieve_guide_docs(self, test_retriever):
        """Strategy queries should surface guide docs, not card docs."""
        results = test_retriever.retrieve(
            "When should I break interest to buy a joker?", top_k=5
        )
        has_guide = any(r["metadata"].get("type") == "guide" for r in results)
        assert has_guide, "Strategy query returned no guide-type documents in top-5"


# ── Reranker tests ────────────────────────────────────────────────────────────

@pytest.mark.slow
class TestRerankerMetrics:
    """Reranker quality tests — require cross-encoder model download."""

    def test_reranker_hit_at_5(self, test_retriever_with_reranker):
        metrics = _compute_metrics(test_retriever_with_reranker, GOLDEN_DATASET, top_k=5)
        _print_metrics("With cross-encoder reranker, top_k=5", metrics, top_k=5)
        assert metrics["Hit@5"] >= 0.6, (
            f"Hit@5={metrics['Hit@5']:.3f} with reranker — below minimum threshold."
        )

    def test_reranker_does_not_degrade_mrr(self, test_retriever, test_retriever_with_reranker):
        """Reranker must not hurt MRR by more than 15% vs. baseline."""
        base = _compute_metrics(test_retriever, GOLDEN_DATASET, top_k=5)
        reranked = _compute_metrics(test_retriever_with_reranker, GOLDEN_DATASET, top_k=5)
        print(f"\n  Baseline MRR:  {base['MRR']:.3f}")
        print(f"  Reranked MRR:  {reranked['MRR']:.3f}")
        assert reranked["MRR"] >= base["MRR"] * 0.85, (
            f"Reranker degraded MRR from {base['MRR']:.3f} to {reranked['MRR']:.3f} (>15% drop)"
        )


# ── Component unit tests ──────────────────────────────────────────────────────

class TestRRFMerge:
    def test_higher_ranked_wins(self):
        from app.rag.retriever import _rrf_merge

        dense = [{"id": "a", "text": "x", "metadata": {}, "score": 0.9}]
        sparse = [
            {"id": "b", "text": "y", "metadata": {}, "score": 5.0},
            {"id": "a", "text": "x", "metadata": {}, "score": 3.0},
        ]
        result = _rrf_merge(dense, sparse)
        # "a" appears in both lists so should score higher than "b" (only in sparse)
        assert result[0]["id"] == "a"

    def test_deduplication(self):
        from app.rag.retriever import _rrf_merge

        same = [{"id": "x", "text": "t", "metadata": {}, "score": 1.0}]
        result = _rrf_merge(same, same)
        assert sum(1 for r in result if r["id"] == "x") == 1

    def test_empty_inputs(self):
        from app.rag.retriever import _rrf_merge

        assert _rrf_merge([], []) == []
        assert len(_rrf_merge([{"id": "a", "text": "t", "metadata": {}, "score": 1.0}], [])) == 1


class TestMakeId:
    def test_unique_ids_for_different_docs(self):
        from app.rag.retriever import _make_id

        doc_a = {"text": "# Joker\n\nGives +4 Mult."}
        doc_b = {"text": "# Hologram\n\nGains +0.25 Mult per card added."}
        assert _make_id(doc_a) != _make_id(doc_b)

    def test_same_doc_same_id(self):
        from app.rag.retriever import _make_id

        doc = {"text": "# Joker\n\nGives +4 Mult."}
        assert _make_id(doc) == _make_id(doc)

    def test_id_uses_full_text(self):
        """Two docs sharing the same first 200 chars but differing later must get different IDs."""
        from app.rag.retriever import _make_id

        prefix = "# Test Card\n\n" + "x" * 200
        doc_a = {"text": prefix + " extra_a"}
        doc_b = {"text": prefix + " extra_b"}
        assert _make_id(doc_a) != _make_id(doc_b)


class TestAdaptiveSplit:
    def test_card_query_biases_toward_card_collection(self):
        from app.rag.retriever import RAGRetriever
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            r = RAGRetriever(Path(tmp), rerank_model=None)
            card_k, guide_k = r._adaptive_split("What does Hologram joker do?", top_k=9)
            assert card_k >= guide_k, f"Card query: expected card_k >= guide_k, got {card_k}/{guide_k}"

    def test_strategy_query_biases_toward_guide_collection(self):
        from app.rag.retriever import RAGRetriever
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            r = RAGRetriever(Path(tmp), rerank_model=None)
            card_k, guide_k = r._adaptive_split(
                "How do I manage economy and interest breakpoints in early ante?", top_k=9
            )
            assert guide_k >= card_k, (
                f"Strategy query: expected guide_k >= card_k, got {card_k}/{guide_k}"
            )


class TestBuildRagQuery:
    def test_includes_joker_names_as_sentence(self):
        from app.llm.coach import build_rag_query

        game_state = {
            "jokers": [{"name": "Hologram"}, {"name": "Blueprint"}],
            "shop": {"items": []},
        }
        query = build_rag_query("What should I play?", game_state, [])
        assert "Hologram" in query
        assert "Blueprint" in query
        # Should be natural-sentence format, not just space-joined tokens
        assert "Active jokers:" in query

    def test_includes_shop_items(self):
        from app.llm.coach import build_rag_query

        game_state = {
            "jokers": [],
            "shop": {"items": [{"name": "Hack"}, {"name": "Cavendish"}]},
        }
        query = build_rag_query("Should I buy something?", game_state, [])
        assert "Hack" in query or "Cavendish" in query

    def test_adds_scoring_hint_for_card_tokens(self):
        from app.llm.coach import build_rag_query

        query = build_rag_query("I have AH KH QH JH 10H in my hand", None, [])
        assert "chips" in query.lower() or "scoring" in query.lower()

    def test_adds_mechanic_hint_for_synergy_terms(self):
        from app.llm.coach import build_rag_query

        query = build_rag_query("What are the best xmult synergies?", None, [])
        assert "synergy" in query.lower() or "timing" in query.lower()

    def test_no_game_state_uses_message_only(self):
        from app.llm.coach import build_rag_query

        query = build_rag_query("How do I win Balatro?", None, [])
        assert "How do I win Balatro?" in query


class TestContextTruncation:
    def test_format_context_uses_1200_char_limit(self):
        """_format_context should not truncate at 700 chars (old limit)."""
        from app.llm.coach import _format_context

        long_text = "A" * 1100  # 1100 chars — would be cut at old 700 limit
        chunks = [{"text": long_text, "metadata": {"name": "Test", "source": "test"}}]
        result = _format_context(chunks)
        assert "A" * 1000 in result, (
            "Context was truncated before 1000 chars — old 700-char limit may still be in place"
        )

    def test_format_context_still_caps_at_1200(self):
        from app.llm.coach import _format_context

        # Use a character not present in the header "[LongDoc]"
        very_long = "X" * 2000
        chunks = [{"text": very_long, "metadata": {"name": "LongDoc", "source": "test"}}]
        result = _format_context(chunks)
        assert result.count("X") <= 1200


class TestRuleCorrection:
    """Coach._rule_correction catches known hallucinations."""

    def _make_coach(self):
        """Create a BalatroCoach with a mock retriever (no API calls made)."""
        from unittest.mock import MagicMock
        from app.llm.coach import BalatroCoach

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        return BalatroCoach(mock_retriever)

    def test_catches_boss_blind_skip_claim(self):
        coach = self._make_coach()
        response = "You can skip boss blind if you have enough hands."
        correction = coach._rule_correction(response, "skip the blind?", None)
        assert correction, "Expected a correction for boss-blind skip claim"
        assert "cannot be skipped" in correction.lower() or "boss blind" in correction.lower()

    def test_no_correction_for_valid_response(self):
        coach = self._make_coach()
        response = "Play a Full House here for maximum chips."
        correction = coach._rule_correction(response, "what should I play?", None)
        assert not correction, f"Unexpected correction: {correction}"

    def test_catches_assumed_the_ox_boss(self):
        coach = self._make_coach()
        response = "Watch out for The Ox debuff this round."
        correction = coach._rule_correction(
            response, "how do I beat this boss?", {"blind": {"name": ""}}
        )
        assert correction, "Expected correction for assumed The Ox boss"


class TestHandEval:
    """Deterministic hand evaluation is correct."""

    def test_royal_flush_detected(self):
        from app.llm.hand_eval import parse_cards_from_text, evaluate_best_hand

        cards = parse_cards_from_text("AH KH QH JH 10H")
        best = evaluate_best_hand(cards)
        assert best is not None
        assert best.hand_name == "Royal Flush"

    def test_pair_base_score(self):
        from app.llm.hand_eval import compute_hand_stats

        chips, mult = compute_hand_stats("Pair", level=1)
        assert chips == 10
        assert mult == 2

    def test_straight_level_scaling(self):
        from app.llm.hand_eval import compute_hand_stats

        chips_l1, mult_l1 = compute_hand_stats("Straight", level=1)
        chips_l2, mult_l2 = compute_hand_stats("Straight", level=2)
        assert chips_l2 == chips_l1 + 30  # +30 chips/level
        assert mult_l2 == mult_l1 + 3      # +3 mult/level

    def test_flush_house_is_stronger_than_full_house(self):
        from app.llm.hand_eval import compute_hand_stats

        fh_chips, fh_mult = compute_hand_stats("Full House", level=1)
        fhh_chips, fhh_mult = compute_hand_stats("Flush House", level=1)
        assert fhh_chips > fh_chips
        assert fhh_mult > fh_mult

    def test_wheel_straight_detected(self):
        from app.llm.hand_eval import parse_cards_from_text, evaluate_best_hand

        # A-2-3-4-5 (wheel straight)
        cards = parse_cards_from_text("AH 2D 3C 4S 5H")
        best = evaluate_best_hand(cards)
        assert best is not None
        assert best.hand_name == "Straight"

    def test_flush_five_highest_priority(self):
        from app.llm.hand_eval import parse_cards_from_text, evaluate_best_hand

        # Five aces of same suit (not a real Balatro deck possibility but tests logic)
        from app.llm.hand_eval import ParsedCard
        cards = [ParsedCard("A", "Hearts")] * 5
        best = evaluate_best_hand(cards)
        assert best is not None
        assert best.hand_name == "Flush Five"
