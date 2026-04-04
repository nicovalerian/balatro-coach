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

JOKER_RARITY_CATEGORIES = {
    "Common": "Common Jokers",
    "Uncommon": "Uncommon Jokers",
    "Rare": "Rare Jokers",
    "Legendary": "Legendary Jokers",
}

JOKER_ACTIVATION_CATEGORIES = {
    "independent": "Activates Independently Jokers",
    "on_played": "Activates On Played Jokers",
    "on_scored": "Activates On Scored Jokers",
    "on_held": "Activates On Held Jokers",
    "on_discard": "Activates On Discard Jokers",
    "on_other_jokers": "Activates On Other Jokers",
}

STRATEGY_GUIDES = [
    {
        "name": "Poker hand base scoring reference (Level 1)",
        "text": (
            "# Poker Hand Base Scoring (Level 1)\n\n"
            "Use these base values before joker/card modifier effects:\n"
            "- High Card: 5 chips x 1 mult\n"
            "- Pair: 10 chips x 2 mult\n"
            "- Two Pair: 20 chips x 2 mult\n"
            "- Three of a Kind: 30 chips x 3 mult\n"
            "- Straight: 30 chips x 4 mult\n"
            "- Flush: 35 chips x 4 mult\n"
            "- Full House: 40 chips x 4 mult\n"
            "- Four of a Kind: 60 chips x 7 mult\n"
            "- Straight Flush: 100 chips x 8 mult\n"
            "- Royal Flush: 100 chips x 8 mult\n\n"
            "Card chips are added to base hand chips before multiplication.\n"
            "Face cards J/Q/K contribute 10 chips each and Ace contributes 11 chips."
        ),
    },
    {
        "name": "Boss blind constraints and assumptions",
        "text": (
            "# Boss Blind Constraints and Assumptions\n\n"
            "Key constraints for coaching correctness:\n"
            "- Boss Blinds cannot be skipped.\n"
            "- Small/Big blinds can be skipped for tags, but Boss Blind must be played.\n"
            "- If user only says \"Ante X boss blind\" without name/effect, do not assume a specific boss.\n"
            "- Ask for boss name/effect when that changes line selection.\n"
            "- In Ante 1, use blind target pressure and remaining hands/discards to plan survival."
        ),
    },
    {
        "name": "Scoring order and joker positioning",
        "text": (
            "# Scoring Order and Joker Positioning\n\n"
            "Balatro scoring generally resolves left-to-right across jokers, and order often changes output.\n"
            "As a default optimization heuristic: place chip sources first, additive multiplier next, and "
            "xMult scaling later so multiplicative effects apply to a larger base.\n\n"
            "When uncertain, compare two candidate orders by estimating final value as:\n"
            "(base chips + chip adders) * (base mult + additive mult) * multiplicative stack.\n"
            "If a joker copies another joker, evaluate both copy target and position interactions before locking order."
        ),
    },
    {
        "name": "Economy and shop discipline",
        "text": (
            "# Economy and Shop Discipline\n\n"
            "Treat economy as compounding power. Preserve interest breakpoints when possible, avoid low-impact rerolls, "
            "and only break economy for high-leverage pickups (build-defining jokers, survival tools, or immediate blind solutions).\n\n"
            "A practical loop:\n"
            "1) secure blind clear consistency,\n"
            "2) improve scaling engine,\n"
            "3) spend aggressively only when a shop meaningfully upgrades your trajectory."
        ),
    },
    {
        "name": "Pivoting builds and anti-synergy checks",
        "text": (
            "# Pivoting Builds and Anti-synergy Checks\n\n"
            "Prioritize coherent scaling over collection quality. A lower-rarity joker that reinforces your current engine "
            "often beats a disconnected high-rarity pickup.\n\n"
            "Before buying/selling, check:\n"
            "- Does this improve my next 2-3 blinds?\n"
            "- Does it conflict with current triggers (played/held/discard timing)?\n"
            "- Does it dilute key synergies or hand focus?\n"
            "If yes, delay pivot unless current line cannot beat upcoming blind pressure."
        ),
    },
    {
        "name": "Early ante survival checklist",
        "text": (
            "# Early Ante Survival Checklist\n\n"
            "When asking \"how do I survive\" in ante 1-2:\n"
            "1) First verify exact blind target and active boss effect.\n"
            "2) Compute best guaranteed base hand score from current cards.\n"
            "3) Prioritize line that clears current blind with highest margin, not speculative scaling.\n"
            "4) If current line is short, identify required chips/mult delta and the most reliable source.\n"
            "5) Preserve economy breakpoints unless breaking them is required to avoid lethal miss.\n"
            "6) Avoid anti-synergy pivots that reduce immediate clear probability."
        ),
    },
    {
        "name": "Planet card scaling tiers and hand strategy",
        "text": (
            "# Planet Card Scaling Tiers and Hand Strategy\n\n"
            "## Straight-family (Straight, Straight Flush)\n"
            "Exceptional planet scaling (+30 chips/+3 mult per level for Straight; +40/+4 for Straight Flush). "
            "Viable to take enabler jokers and invest heavily in planets. "
            "Retriggers are hard to enable on Straights, making Ante 12+ difficult; plan exit strategy early.\n\n"
            "## Full House family (Full House, Flush House)\n"
            "Slightly weaker scaling than Straight (+25/+2 for Full House) but often easier to construct. "
            "Flush House's planet (Ceres, +40/+4) matches Straight Flush strength — "
            "single-suit deck enables this without losing much scaling. "
            "Flush House's planet card is secret (not labeled), making it harder to plan leveling before pivoting.\n\n"
            "## Naked Flush\n"
            "Garbage base scaling (+15 chips/+2 mult per level) — worse than Three of a Kind. "
            "Requires high-scoring xMult jokers to compensate. "
            "Note: when Flush is paired with a ranked hand (Straight Flush, Flush House, Flush Five), "
            "the Flush component inherits that hand's stronger scaling.\n\n"
            "## Minor hands (Two Pair and below)\n"
            "Even worse scaling than naked Flush. Needs very strong jokers plus Steel cards and retrigger stacking. "
            "Missing planets is not catastrophic but still helps — grab them when free or cheap.\n\n"
            "## General guidance\n"
            "Prioritize planet cards for your primary scoring hand. "
            "High-level hands compound fast: a Straight at level 5 has 150 chips x 16 mult base before any card chips. "
            "Tracking times-played helps estimate how many planets you've likely consumed."
        ),
    },
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


def _iter_category_members(category_title: str, delay: float = 0.2) -> Iterator[str]:
    cmcontinue: str | None = None
    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_title}",
            "cmtype": "page",
            "cmnamespace": 0,
            "cmlimit": "500",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        try:
            time.sleep(delay)
            r = requests.get(WIKI_API, headers=HEADERS, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("fetch failed category %s: %s", category_title, exc)
            return

        for member in data.get("query", {}).get("categorymembers", []):
            title = member.get("title")
            if title:
                yield title

        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break


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
        for title in _iter_category_members(category, delay=0.4):
            slug = quote(title.replace(" ", "_"), safe="_()'")
            url = f"{WIKI_BASE}/w/{slug}"
            if url in seen:
                continue
            seen.add(url)
            doc = scrape_wiki_card(url)
            if doc:
                logger.info("wiki: scraped %s", doc["name"])
                yield doc


def iter_mechanics_docs() -> Iterator[dict]:
    """Build deterministic mechanics docs for jokers from category membership."""
    rarity_by_joker: dict[str, str] = {}
    activation_by_joker: dict[str, list[str]] = {}

    for rarity, category in JOKER_RARITY_CATEGORIES.items():
        for title in _iter_category_members(category):
            rarity_by_joker[title] = rarity

    for activation_key, category in JOKER_ACTIVATION_CATEGORIES.items():
        for title in _iter_category_members(category):
            activation_by_joker.setdefault(title, []).append(activation_key)

    all_jokers = sorted(set(rarity_by_joker) | set(activation_by_joker))
    for name in all_jokers:
        rarity = rarity_by_joker.get(name, "Unknown")
        activation = activation_by_joker.get(name, [])
        activation_text = ", ".join(sorted(activation)) if activation else "unknown"
        yield {
            "name": f"{name} – mechanics",
            "text": (
                f"# {name} – Mechanics Summary\n\n"
                f"- Joker rarity: {rarity}\n"
                f"- Activation timing tags: {activation_text}\n"
                "- Positioning note: activation timing and left-to-right ordering can change final scoring output.\n"
                "- Synergy practice: prioritize coherent trigger timing and scaling over isolated high-rarity value."
            ),
            "metadata": {
                "type": "card",
                "name": name,
                "source": "mechanics_corpus",
                "rarity": rarity,
                "activation_tags": activation_text,
            },
        }


def iter_strategy_guides() -> Iterator[dict]:
    """Yield curated strategy docs for practical coaching context."""
    for guide in STRATEGY_GUIDES:
        yield {
            "name": guide["name"],
            "text": guide["text"],
            "metadata": {
                "type": "guide",
                "name": guide["name"],
                "source": "community_meta",
            },
        }


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
