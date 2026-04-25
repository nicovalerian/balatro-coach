"""
Shared pytest fixtures for RAG evaluation tests.

Sets a dummy MODEL_ACCESS_KEY so pydantic-settings doesn't fail when
modules that import app.config are loaded in tests.
"""
import os
import tempfile
from pathlib import Path

import pytest

# Must be set before any app.* import triggers Settings()
os.environ.setdefault("MODEL_ACCESS_KEY", "test-key-for-testing")

# ── Synthetic card docs added to the test index ───────────────────────────────

_SYNTHETIC_CARD_DOCS = [
    {
        "text": (
            "# Joker\n\nSimple joker that gives +4 Mult. Works with any hand type. "
            "One of the most universally applicable jokers in Balatro."
        ),
        "metadata": {"type": "card", "name": "Joker", "source": "test"},
    },
    {
        "text": (
            "# Hologram\n\nGains +0.25 Mult each time a playing card is added to your deck. "
            "Stacks quickly with card-adding effects. Best in decks that grow via Arcana packs."
        ),
        "metadata": {"type": "card", "name": "Hologram", "source": "test"},
    },
    {
        "text": (
            "# Blueprint\n\nCopies the ability of the Joker to the right of it. "
            "Position it to the left of your highest-value joker for maximum effect. "
            "Does not copy other Blueprints."
        ),
        "metadata": {"type": "card", "name": "Blueprint", "source": "test"},
    },
    {
        "text": (
            "# Brainstorm\n\nCopies the ability of the leftmost Joker. "
            "Pairs powerfully with high-value jokers at position 1. "
            "Uncommon rarity."
        ),
        "metadata": {"type": "card", "name": "Brainstorm", "source": "test"},
    },
    {
        "text": (
            "# Hack\n\nRetriggers each 2, 3, 4, or 5 card scored in a hand. "
            "Strong in low-rank hand builds. Uncommon rarity. "
            "Activates on scored cards."
        ),
        "metadata": {"type": "card", "name": "Hack", "source": "test"},
    },
]


def _build_test_index(tmp_dir: str, rerank_model: str | None = None) -> "RAGRetriever":
    from app.rag.retriever import RAGRetriever
    from app.rag.ingest import iter_strategy_guides

    retriever = RAGRetriever(
        persist_dir=Path(tmp_dir),
        embed_model="all-MiniLM-L6-v2",
        rerank_model=rerank_model,
        reranker_candidates=20,
    )
    guide_docs = list(iter_strategy_guides())
    retriever.index_documents(guide_docs + _SYNTHETIC_CARD_DOCS)
    return retriever


@pytest.fixture(scope="session")
def test_retriever():
    """Small ChromaDB index (strategy guides + 5 card docs), no reranker."""
    # ignore_cleanup_errors: ChromaDB holds SQLite file handles on Windows
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        yield _build_test_index(tmp, rerank_model=None)


@pytest.fixture(scope="session")
def test_retriever_with_reranker():
    """Same index but with cross-encoder reranker. Skipped if model unavailable."""
    try:
        from sentence_transformers import CrossEncoder  # noqa: F401
    except ImportError:
        pytest.skip("sentence_transformers not available")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        retriever = _build_test_index(
            tmp, rerank_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        # Trigger lazy load — skip if the model can't be fetched
        try:
            reranker = retriever._get_reranker()
        except Exception:
            reranker = None
        if reranker is None:
            pytest.skip("cross-encoder model could not be loaded (no internet?)")
        yield retriever


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.slow",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="use --run-slow to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
