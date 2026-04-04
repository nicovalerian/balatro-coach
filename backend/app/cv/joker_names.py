"""
Canonical Balatro joker name registry + fuzzy matcher.

Used by the CV extractor to correct OCR output against the known joker roster.
Keep this list in sync with build_index.py:JOKER_NAMES (which drives synergy generation).
"""
from __future__ import annotations

import difflib

# Complete Balatro joker roster (~150 jokers as of v1.0.1f)
ALL_JOKER_NAMES: frozenset[str] = frozenset([
    # ── Common ────────────────────────────────────────────────────────────────
    "Joker", "Greedy Joker", "Lusty Joker", "Wrathful Joker", "Gluttonous Joker",
    "Jolly Joker", "Zany Joker", "Mad Joker", "Crazy Joker", "Droll Joker",
    "Sly Joker", "Wily Joker", "Clever Joker", "Devious Joker", "Crafty Joker",
    "Half Joker", "Joker Stencil", "Four Fingers", "Mime", "Credit Card",
    "Ceremonial Dagger", "Banner", "Mystic Summit", "Marble Joker", "Loyalty Card",
    "8 Ball", "Misprint", "Dusk", "Raised Fist", "Chaos the Clown",
    "Fibonacci", "Steel Joker", "Scary Face", "Abstract Joker", "Delayed Gratification",
    "Hack", "Pareidolia", "Gros Michel", "Cavendish", "Even Steven", "Odd Todd",
    "Scholar", "Business Card", "Supernova", "Ride the Bus", "Space Joker",
    "Egg", "Burglar", "Blackboard", "Runner", "Ice Cream",
    "DNA", "Splash", "Blue Joker", "Sixth Sense", "Constellation",
    "Hiker", "Card Sharp", "Red Card", "Madness", "Square Joker",
    "Seance", "Riff-Raff", "Vampire", "Shortcut", "Hologram",
    "Vagabond", "Baron", "Cloud 9", "Rocket", "Obelisk",
    "Midas Mask", "Luchador", "Photograph", "Gift Card", "Turtle Bean",
    "Erosion", "Reserved Parking", "Flash Card", "Popcorn", "Spare Trousers",
    "Ancient Joker", "Ramen", "Walkie Talkie", "Seltzer", "Castle",
    "Smiley Face", "Campfire", "Golden Ticket", "Mr. Bones", "Acrobat",
    "Sock and Buskin", "Swashbuckler", "Troubadour", "Certificate", "Smeared Joker",
    "Throwback", "Hanging Chad", "Rough Gem", "Bloodstone", "Arrowhead",
    "Onyx Agate", "Glass Joker", "Showman", "Flower Pot", "Blueprint",
    "Wee Joker", "Merry Andy", "Oops! All 6s", "The Idol", "Seeing Double",
    "Matador", "Hit the Road", "The Duo", "The Trio", "The Family",
    "The Order", "The Tribe", "Stuntman", "Invisible Joker", "Brainstorm",
    "Satellite", "Shoot the Moon", "Driver's License", "Cartomancer", "Astronomer",
    "Burnt Joker", "Bootstraps", "Caino", "Triboulet", "Yorick",
    "Chicot", "Perkeo",
    # ── Previously missing ────────────────────────────────────────────────────
    "Faceless Joker",       # earn $4 discarding 3+ face cards at once
    "Green Joker",          # +1 mult per hand played, -1 per discard used each round
    "Superposition",        # Ace + Straight: create a Tarot card
    "Todo List",            # if played hand matches random hand, earn $4
    "To the Moon",          # earn $1 more per interest tick
    "Hallucination",        # 1 in 2 chance to create Tarot when any Booster Pack opened
    "Fortune Teller",       # +1 Mult per Tarot card used this run
    "Juggler",              # +1 hand size
    "Drunkard",             # +1 discard each round
    "Swashbuckler",         # note: already in list above, kept for safety
])

# De-duplicate (frozenset handles it) — use sorted list for stable difflib matching
_NAMES_SORTED: list[str] = sorted(ALL_JOKER_NAMES)


def fuzzy_match_joker(raw: str, cutoff: float = 0.72) -> str | None:
    """
    Return the closest known joker name if similarity >= cutoff, else None.

    Examples:
        "Blueprin"  → "Blueprint"
        "Rais Fist" → "Raised Fist"
        "brainstorm" → "Brainstorm"
        ""          → None
        "xyzzy"     → None
    """
    if not raw or not raw.strip():
        return None
    # Case-insensitive: lower both sides, then return the original-cased match
    raw_lower = raw.strip().lower()
    names_lower = [n.lower() for n in _NAMES_SORTED]
    matches = difflib.get_close_matches(raw_lower, names_lower, n=1, cutoff=cutoff)
    if not matches:
        return None
    idx = names_lower.index(matches[0])
    return _NAMES_SORTED[idx]
