"""
Build the full RAG index.

Usage:
    # Wiki corpus only:
    python scripts/build_index.py

    # Regenerate synergy notes via serverless inference (~$0.20):
    python scripts/build_index.py --synergies
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from openai import OpenAI

from app.config import settings
from app.cv.joker_names import ALL_JOKER_NAMES
from app.rag.ingest import (
    iter_wiki_cards,
    generate_synergy_notes,
    iter_mechanics_docs,
    iter_strategy_guides,
    save_jsonl,
    load_jsonl,
)
from app.rag.retriever import RAGRetriever

DATA_DIR = Path(__file__).parent.parent / "data"
WIKI_CACHE = DATA_DIR / "wiki_cards.jsonl"
MECHANICS_CACHE = DATA_DIR / "mechanics.jsonl"
GUIDES_CACHE = DATA_DIR / "strategy_guides.jsonl"
SYNERGY_CACHE = DATA_DIR / "synergies.jsonl"

# Canonical joker list sourced from cv/joker_names.py (single source of truth)
JOKER_NAMES: list[str] = sorted(ALL_JOKER_NAMES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synergies", action="store_true", help="Generate synergy corpus via serverless inference")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if cache exists")
    args = parser.parse_args()

    all_docs: list[dict] = []

    # ── 1. Wiki cards ──────────────────────────────────────────────────────────
    if WIKI_CACHE.exists() and not args.force:
        print(f"Loading wiki cache ({WIKI_CACHE})…")
        wiki_docs = load_jsonl(WIKI_CACHE)
    else:
        print("Scraping Balatro wiki…")
        wiki_docs = list(iter_wiki_cards())
        save_jsonl(wiki_docs, WIKI_CACHE)
    print(f"  {len(wiki_docs)} wiki card docs")
    all_docs.extend(wiki_docs)

    # ── 2. Deterministic mechanics corpus ─────────────────────────────────────
    if MECHANICS_CACHE.exists() and not args.force:
        print(f"Loading mechanics cache ({MECHANICS_CACHE})…")
        mechanics_docs = load_jsonl(MECHANICS_CACHE)
    else:
        print("Building mechanics corpus…")
        mechanics_docs = list(iter_mechanics_docs())
        save_jsonl(mechanics_docs, MECHANICS_CACHE)
    print(f"  {len(mechanics_docs)} mechanics docs")
    all_docs.extend(mechanics_docs)

    # ── 3. Curated strategy guides ────────────────────────────────────────────
    if GUIDES_CACHE.exists() and not args.force:
        print(f"Loading strategy cache ({GUIDES_CACHE})…")
        guide_docs = load_jsonl(GUIDES_CACHE)
    else:
        print("Building curated strategy corpus…")
        guide_docs = list(iter_strategy_guides())
        save_jsonl(guide_docs, GUIDES_CACHE)
    print(f"  {len(guide_docs)} strategy guide docs")
    all_docs.extend(guide_docs)

    # ── 4. Synergy corpus ─────────────────────────────────────────────────────
    if args.synergies:
        if SYNERGY_CACHE.exists() and not args.force:
            print(f"Loading synergy cache ({SYNERGY_CACHE})…")
            synergy_docs = load_jsonl(SYNERGY_CACHE)
        else:
            client = OpenAI(
                api_key=settings.model_access_key,
                base_url=settings.inference_base_url.rstrip("/") + "/",
            )
            print(f"Generating synergy notes for {len(JOKER_NAMES)} jokers via serverless inference…")
            print("  Estimated cost: ~$0.15-0.25")
            synergy_docs = list(generate_synergy_notes(JOKER_NAMES, client, model=settings.synergy_model))
            save_jsonl(synergy_docs, SYNERGY_CACHE)
        print(f"  {len(synergy_docs)} synergy docs")
        all_docs.extend(synergy_docs)

    # ── 5. Index everything ───────────────────────────────────────────────────
    print(f"\nIndexing {len(all_docs)} total docs into ChromaDB…")
    retriever = RAGRetriever(
        persist_dir=settings.chroma_persist_dir,
        embed_model=settings.embed_model,
    )
    retriever.index_documents(all_docs)
    print("Done! RAG index is ready.")


if __name__ == "__main__":
    main()
