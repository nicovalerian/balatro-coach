"""
RAG data ingestion pipeline.
Run once (or on a schedule) via: python scripts/build_index.py

Sources:
  1. Balatro Wiki (balatrowiki.org) – card-level chunks (one per card/joker)
  2. Steam guides – primers and run guides (guide-level chunks)
  3. Synergy corpus – LLM-generated joker synergy notes (card-level chunks)

Chunk strategy:
  - card-level: metadata {"type": "card", "name": "<JokerName>"}
  - guide-level: metadata {"type": "guide", "source": "<steam|other>"}
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

logger = logging.getLogger(__name__)

WIKI_BASE = "https://balatrowiki.org"
WIKI_API = f"{WIKI_BASE}/api.php"
HEADERS = {"User-Agent": "balatro-coach-bot/1.0 (research; non-commercial)"}

# ── Wiki scraping ─────────────────────────────────────────────────────────────

CARD_CATEGORIES = [
    "Jokers",
    "Tarot Cards",
    "Planet Cards",
    "Spectral Cards",
    "Vouchers",
    "Blinds",
]


def _fetch(url: str, delay: float = 1.0) -> BeautifulSoup | None:
    try:
        time.sleep(delay)
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as exc:
        logger.warning("fetch failed %s: %s", url, exc)
        return None


def scrape_wiki_card(page_url: str) -> dict | None:
    """Scrape a single card/joker wiki page → {name, text, metadata}."""
    soup = _fetch(page_url)
    if not soup:
        return None
    title = soup.find("h1", {"id": "firstHeading"})
    name = title.get_text(strip=True) if title else page_url.split("/")[-1]
    content_div = soup.find("div", {"id": "mw-content-text"})
    if not content_div:
        return None

    # Extract all paragraphs and list items
    parts: list[str] = []
    for tag in content_div.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(" ", strip=True)
        if text and len(text) > 10:
            parts.append(text)

    full_text = "\n".join(parts)
    if len(full_text) < 30:
        return None

    return {
        "name": name,
        "text": f"# {name}\n\n{full_text}",
        "metadata": {"type": "card", "name": name, "source": "wiki", "url": page_url},
    }


def iter_wiki_cards() -> Iterator[dict]:
    """Yield all card docs from wiki category pages."""
    seen: set[str] = set()
    for category in CARD_CATEGORIES:
        cmcontinue: str | None = None
        while True:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": f"Category:{category}",
                "cmtype": "page",
                "cmnamespace": 0,
                "cmlimit": "500",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            try:
                time.sleep(0.4)
                r = requests.get(WIKI_API, headers=HEADERS, params=params, timeout=20)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                logger.warning("fetch failed category %s: %s", category, exc)
                break

            for member in data.get("query", {}).get("categorymembers", []):
                title = member.get("title")
                if not title:
                    continue
                slug = quote(title.replace(" ", "_"), safe="_()'")
                url = f"{WIKI_BASE}/w/{slug}"
                if url in seen:
                    continue
                seen.add(url)
                doc = scrape_wiki_card(url)
                if doc:
                    logger.info("wiki: scraped %s", doc["name"])
                    yield doc

            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break


# ── Synergy corpus (LLM-generated) ───────────────────────────────────────────

SYNERGY_PROMPT = """You are an expert Balatro player.
For the joker named "{joker}", write a concise synergy note (max 200 words) covering:
1. What builds / hand types it powers
2. Its 2-3 best joker partners and why
3. Any anti-synergies or situations where it's weak
Format as plain text, no headers needed."""


def generate_synergy_notes(
    joker_names: list[str],
    client: OpenAI,
    model: str = "anthropic-claude-3.5-haiku",
) -> Iterator[dict]:
    """Generate synergy notes for each joker using serverless inference."""
    for name in joker_names:
        try:
            msg = client.chat.completions.create(
                model=model,
                max_completion_tokens=300,
                messages=[{
                    "role": "user",
                    "content": SYNERGY_PROMPT.format(joker=name),
                }],
            )
            text = msg.choices[0].message.content or ""
            yield {
                "name": f"{name} – synergies",
                "text": f"# {name} – Synergy Notes\n\n{text}",
                "metadata": {
                    "type": "card",
                    "name": name,
                    "source": "synergy_corpus",
                },
            }
            time.sleep(0.2)  # rate limit buffer
        except Exception as exc:
            logger.warning("synergy gen failed for %s: %s", name, exc)


# ── Serialisation helpers ─────────────────────────────────────────────────────

def save_jsonl(docs: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    logger.info("saved %d docs → %s", len(docs), path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
