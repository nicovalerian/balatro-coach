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
import re
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
        "name": "Deck mechanics – what discarding does and does not do",
        "text": (
            "# Deck Mechanics – Discarding and Deck Size\n\n"
            "## Discarding does NOT thin the deck\n"
            "Discarding cards during a hand does NOT remove them from your deck permanently. "
            "Discarded cards return to the draw pool — the full deck resets every round (blind). "
            "Never advise a player to 'discard to thin the deck' as a strategy, because it has no such effect.\n\n"
            "## How to actually thin the deck\n"
            "The only ways to permanently remove cards from your deck are:\n"
            "- Selling The Fool tarot card (removes 2 cards permanently from the deck)\n"
            "- Using certain spectral cards (e.g. Ectoplasm, Hex) which remove cards\n"
            "- Some joker effects on trigger (e.g. Burnt Joker destroys played cards on scoring)\n"
            "- The 'Card Removal' voucher mechanic is not available — cards are removed only via explicit effects\n\n"
            "## Why deck thinning matters\n"
            "A smaller deck concentrates key cards: you draw your best scoring cards more often per hand. "
            "Thin decks synergize with Flush-family hands (need 5 of same suit) and set up reliable "
            "Four of a Kind / Flush Five combos. However, small decks also reduce hand-size flexibility "
            "and can leave you card-starved on long blinds.\n\n"
            "## Discard uses that ARE valid\n"
            "- Drawing into a better 5-card hand (shuffle for scoring cards)\n"
            "- Activating discard-triggered jokers (e.g. Riff-Raff, Green Joker loses mult on discard)\n"
            "- Cycling to find steel/gold cards already in hand\n"
            "Never waste discards unless you have a concrete hand improvement or discard-trigger synergy."
        ),
    },
    {
        "name": "Early game priorities – Ante 1 and 2",
        "text": (
            "# Early Game Priorities – Ante 1 and 2\n\n"
            "## Goal\n"
            "Survive Ante 1 and 2 with economy intact while establishing a scaling direction.\n\n"
            "## Ante 1 — Foundation\n"
            "- Play your highest base-scoring hand reliably. Don't chase speculative hands.\n"
            "- The small/big blinds are easy; focus on preserving hands and discards for the boss.\n"
            "- First joker purchase: prioritize universally applicable (e.g. Joker, Jolly Joker) "
            "over narrow build-specific jokers until you know what hand type you're building around.\n"
            "- Skipping small blind (for a free tag) is often worth it — you lose $1-2 reward but "
            "gain a tag (extra joker slot, card removal, etc.). Skip if the boss blind is low-pressure.\n\n"
            "## Ante 2 — Direction\n"
            "- By Ante 2 you should know your primary scoring hand (Pair, Flush, Straight, etc.).\n"
            "- Invest planet cards into that hand type only. Don't spread planets across multiple hands.\n"
            "- Build toward $5 interest breakpoints ($5, $10, $15, $20, $25): each breakpoint is $1/round.\n"
            "- Don't reroll Ante 1/2 shops unless you have excess money or a clear must-have joker.\n\n"
            "## Skip decisions\n"
            "- Skip blinds only when the reward (tag) outweighs the lost blind money.\n"
            "- Common value skips: Negative Tag (extra joker slot), Foil/Holo/Poly Tag, Card Removal.\n"
            "- Never skip if you need the blind score to stay in economy for interest breakpoints.\n"
            "- Boss blinds CANNOT be skipped — always plan a boss clear line."
        ),
    },
    {
        "name": "Mid game scaling and shop discipline",
        "text": (
            "# Mid Game Scaling – Ante 3 through 6\n\n"
            "## Goal\n"
            "Lock in a scaling engine and compound it. Blind scores grow fast; linear jokers stop working.\n\n"
            "## What to look for in shops\n"
            "- xMult jokers (Blueprint, Brainstorm, Hologram, DNA) scale multiplicatively — worth more than flat +mult.\n"
            "- Vouchers that reduce card costs or add joker slots amplify every future shop visit.\n"
            "- Spectral cards (Foil, Holographic, Polychrome) on a key joker are often worth the deck slot.\n\n"
            "## Interest vs. spending\n"
            "Interest caps at $25 ($5/round max). Value of holding $25 is 5x the value of holding $5. "
            "Breaking from $20 to $15 costs you $1/round for every round after — only worth it for "
            "a joker that produces >$1/round in value or that solves an immediate scaling problem.\n\n"
            "## Joker slot management\n"
            "- 5 joker slots by default; Negative Tag or Joker Stencil can expand effectively.\n"
            "- Audit each joker every 2 antes: is it still contributing to your scoring line?\n"
            "- Sell jokers that no longer trigger on your primary hand type.\n\n"
            "## Deck composition mid game\n"
            "- Consider removing low-value cards (2s, 3s unless suit-locked) to increase draw density.\n"
            "- Steel cards (held-in-hand xMult) and Gold cards (end-of-round $) add passive value.\n"
            "- If playing Flush, confirm your suit distribution — too many off-suit cards reduce consistency."
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


def _clean_wiki_text(text: str) -> str:
    """Strip wiki markup artifacts from scraped page text."""
    text = re.sub(r'\[edit\]', '', text)                                   # [edit] section links
    text = re.sub(r'\[\d+\]', '', text)                                    # citation numbers [1]
    text = re.sub(r'v\s*[•·]\s*d\s*[•·]\s*e', '', text, flags=re.I)      # nav templates
    text = re.sub(r'\{\{[^}]*\}\}', '', text)                             # {{template}} markers
    text = re.sub(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', r'\1', text)        # [[link|text]] → text
    text = re.sub(r'Retrieved from "https?://[^\s"]+"', '', text)         # retrieval footers
    text = re.sub(r'This page was last edited.*', '', text, flags=re.S)   # edit footers
    text = re.sub(r'\n{3,}', '\n\n', text)                                # collapse blank lines
    return text.strip()


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


def scrape_wiki_card(page_url: str) -> list[dict]:
    """
    Scrape a single card/joker wiki page → list of paragraph-level chunks.

    Each chunk carries the parent card name in metadata so retrieval stays
    attributable. Splitting into paragraphs gives finer retrieval granularity
    than one giant blob per page.
    """
    soup = _fetch(page_url)
    if not soup:
        return []
    title = soup.find("h1", {"id": "firstHeading"})
    name = title.get_text(strip=True) if title else page_url.split("/")[-1]
    content_div = soup.find("div", {"id": "mw-content-text"})
    if not content_div:
        return []

    # Collect tag text, grouping h2/h3 with their following content
    parts: list[str] = []
    current_section: list[str] = []
    for tag in content_div.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) < 10:
            continue
        if tag.name in ("h2", "h3"):
            if current_section:
                parts.append("\n".join(current_section))
            current_section = [text]
        else:
            current_section.append(text)
    if current_section:
        parts.append("\n".join(current_section))

    full_text = _clean_wiki_text("\n\n".join(parts))
    if len(full_text) < 30:
        return []

    # Split into paragraph-level chunks; each ≥80 chars gets its own doc
    raw_chunks = [c.strip() for c in full_text.split("\n\n") if len(c.strip()) >= 80]
    if not raw_chunks:
        # Fallback: single doc if no meaningful paragraph breaks
        return [{
            "name": name,
            "text": f"# {name}\n\n{full_text}",
            "metadata": {"type": "card", "name": name, "source": "wiki", "url": page_url},
        }]

    docs: list[dict] = []
    for i, chunk in enumerate(raw_chunks):
        docs.append({
            "name": name if i == 0 else f"{name} ({i})",
            "text": f"# {name}\n\n{chunk}",
            "metadata": {"type": "card", "name": name, "source": "wiki", "url": page_url},
        })
    return docs


def iter_wiki_cards() -> Iterator[dict]:
    """Yield all card docs from wiki category pages (paragraph-level chunks)."""
    seen: set[str] = set()
    for category in CARD_CATEGORIES:
        for title in _iter_category_members(category, delay=0.4):
            slug = quote(title.replace(" ", "_"), safe="_()'")
            url = f"{WIKI_BASE}/w/{slug}"
            if url in seen:
                continue
            seen.add(url)
            docs = scrape_wiki_card(url)
            if docs:
                logger.info("wiki: scraped %s (%d chunks)", docs[0]["name"], len(docs))
                yield from docs


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
