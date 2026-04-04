from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
import re

SUIT_MAP = {
    "S": "Spades",
    "H": "Hearts",
    "D": "Diamonds",
    "C": "Clubs",
    "♠": "Spades",
    "♤": "Spades",
    "♥": "Hearts",
    "♡": "Hearts",
    "♦": "Diamonds",
    "♢": "Diamonds",
    "♣": "Clubs",
    "♧": "Clubs",
}

RANK_TO_STRAIGHT_VALUE = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}

RANK_TO_CHIPS = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}

HAND_BASE = {
    "High Card": (5, 1),
    "Pair": (10, 2),
    "Two Pair": (20, 2),
    "Three of a Kind": (30, 3),
    "Straight": (30, 4),
    "Flush": (35, 4),
    "Full House": (40, 4),
    "Four of a Kind": (60, 7),
    "Straight Flush": (100, 8),
    "Royal Flush": (100, 8),
    "Five of a Kind": (120, 12),
    "Flush House": (140, 14),
    "Flush Five": (160, 16),
}

# chips_per_level, mult_per_level — from Planet Cards wiki table
HAND_LEVEL_SCALING: dict[str, tuple[int, int]] = {
    "High Card":        (10, 1),
    "Pair":             (15, 1),
    "Two Pair":         (20, 1),
    "Three of a Kind":  (20, 2),
    "Straight":         (30, 3),
    "Flush":            (15, 2),
    "Full House":       (25, 2),
    "Four of a Kind":   (30, 3),
    "Straight Flush":   (40, 4),
    "Royal Flush":      (40, 4),
    "Five of a Kind":   (35, 3),
    "Flush House":      (40, 4),
    "Flush Five":       (50, 3),
}


def compute_hand_stats(name: str, level: int) -> tuple[int, int]:
    """Return (chips, mult) for the given hand at the given level (1-based)."""
    base_chips, base_mult = HAND_BASE[name]
    chips_per_lvl, mult_per_lvl = HAND_LEVEL_SCALING.get(name, (0, 0))
    bonus = max(0, level - 1)
    return base_chips + bonus * chips_per_lvl, base_mult + bonus * mult_per_lvl


HAND_PRIORITY = {
    "High Card": 1,
    "Pair": 2,
    "Two Pair": 3,
    "Three of a Kind": 4,
    "Straight": 5,
    "Flush": 6,
    "Full House": 7,
    "Four of a Kind": 8,
    "Straight Flush": 9,
    "Royal Flush": 10,
    "Five of a Kind": 11,
    "Flush House": 12,
    "Flush Five": 13,
}

CARD_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(10|[2-9JQKA])\s*([CDHS♣♧♦♢♥♡♠♤])(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_ASSUMPTION_BASE = (
    "no enhancements/editions/seals, no joker effects, and no boss/deck modifiers."
)


@dataclass(frozen=True)
class ParsedCard:
    rank: str
    suit: str


@dataclass(frozen=True)
class HandEvaluation:
    hand_name: str
    played_cards: tuple[ParsedCard, ...]
    scored_cards: tuple[ParsedCard, ...]
    hand_chips: int
    hand_mult: int
    card_chips: int

    @property
    def base_total(self) -> int:
        return (self.hand_chips + self.card_chips) * self.hand_mult


def build_hand_eval_note_from_text(
    text: str,
    level_overrides: dict[str, int] | None = None,
) -> str:
    cards = parse_cards_from_text(text)
    if len(cards) < 2:
        return ""

    best = evaluate_best_hand(cards, level_overrides=level_overrides)
    if best is None:
        return ""

    parsed_cards = ", ".join(_format_card(c) for c in cards)
    played_cards = ", ".join(_format_card(c) for c in best.played_cards)
    formula = f"({best.hand_chips} + {best.card_chips}) x {best.hand_mult} = {best.base_total}"
    level = (level_overrides or {}).get(best.hand_name, 1)
    level_note = f"Level {level}" if level > 1 else "Level 1"
    assumption_text = f"Uses {level_note} hand values, {_ASSUMPTION_BASE}"

    return (
        "**Deterministic hand evaluation from typed cards:**\n"
        f"- Parsed cards: {parsed_cards}\n"
        f"- Best playable hand (up to 5 cards): {best.hand_name} using {played_cards}\n"
        f"- Base score before jokers: {formula}\n"
        f"- Assumptions: {assumption_text}"
    )


def build_hand_eval_summary_from_text(
    text: str,
    level_overrides: dict[str, int] | None = None,
) -> str:
    cards = parse_cards_from_text(text)
    if len(cards) < 2:
        return ""

    best = evaluate_best_hand(cards, level_overrides=level_overrides)
    if best is None:
        return ""

    played_cards = ", ".join(_format_card(c) for c in best.played_cards)
    level = (level_overrides or {}).get(best.hand_name, 1)
    level_note = f" (Lvl {level})" if level > 1 else ""
    return (
        "Deterministic base-hand check: "
        f"{best.hand_name}{level_note} with {played_cards} -> "
        f"({best.hand_chips} + {best.card_chips}) x {best.hand_mult} = {best.base_total} "
        "(before jokers/editions)."
    )


def parse_cards_from_text(text: str) -> list[ParsedCard]:
    cards: list[ParsedCard] = []
    for rank_raw, suit_raw in CARD_TOKEN_RE.findall(text.upper()):
        rank = rank_raw.upper()
        suit = SUIT_MAP.get(suit_raw, SUIT_MAP.get(suit_raw.upper()))
        if suit:
            cards.append(ParsedCard(rank=rank, suit=suit))
    return cards


def evaluate_best_hand(
    cards: list[ParsedCard],
    level_overrides: dict[str, int] | None = None,
) -> HandEvaluation | None:
    if not cards:
        return None

    best_eval: HandEvaluation | None = None
    best_key: tuple[int, int, int, int] | None = None

    max_size = min(5, len(cards))
    for size in range(1, max_size + 1):
        for combo in combinations(cards, size):
            evaluation = _evaluate_combo(combo, level_overrides=level_overrides)
            key = (
                HAND_PRIORITY[evaluation.hand_name],
                evaluation.base_total,
                evaluation.card_chips,
                max(RANK_TO_STRAIGHT_VALUE[c.rank] for c in evaluation.scored_cards),
            )
            if best_key is None or key > best_key:
                best_eval = evaluation
                best_key = key

    return best_eval


def _evaluate_combo(
    cards: tuple[ParsedCard, ...],
    level_overrides: dict[str, int] | None = None,
) -> HandEvaluation:
    hand_name = _classify_hand(cards)
    rank_counts = Counter(c.rank for c in cards)
    scored = _scoring_cards(cards, rank_counts, hand_name)
    level = (level_overrides or {}).get(hand_name, 1)
    hand_chips, hand_mult = compute_hand_stats(hand_name, level)
    card_chips = sum(RANK_TO_CHIPS[c.rank] for c in scored)
    return HandEvaluation(
        hand_name=hand_name,
        played_cards=cards,
        scored_cards=scored,
        hand_chips=hand_chips,
        hand_mult=hand_mult,
        card_chips=card_chips,
    )


def _classify_hand(cards: tuple[ParsedCard, ...]) -> str:
    n = len(cards)
    rank_counts = Counter(c.rank for c in cards)
    count_values = sorted(rank_counts.values(), reverse=True)
    is_flush = n == 5 and len({c.suit for c in cards}) == 1
    is_straight = n == 5 and _is_straight([c.rank for c in cards])

    if n == 5:
        if is_flush and count_values == [5]:
            return "Flush Five"
        if is_flush and count_values == [3, 2]:
            return "Flush House"
        if count_values == [5]:
            return "Five of a Kind"
        if is_flush and is_straight and _is_royal(cards):
            return "Royal Flush"
        if is_flush and is_straight:
            return "Straight Flush"
        if count_values == [4, 1]:
            return "Four of a Kind"
        if count_values == [3, 2]:
            return "Full House"
        if is_flush:
            return "Flush"
        if is_straight:
            return "Straight"
        if count_values == [3, 1, 1]:
            return "Three of a Kind"
        if count_values == [2, 2, 1]:
            return "Two Pair"
        if count_values == [2, 1, 1, 1]:
            return "Pair"
        return "High Card"

    if count_values and count_values[0] >= 4:
        return "Four of a Kind"
    if count_values and count_values[0] == 3:
        return "Three of a Kind"
    pair_count = sum(1 for v in rank_counts.values() if v == 2)
    if pair_count >= 2:
        return "Two Pair"
    if pair_count == 1:
        return "Pair"
    return "High Card"


def _scoring_cards(
    cards: tuple[ParsedCard, ...],
    rank_counts: Counter,
    hand_name: str,
) -> tuple[ParsedCard, ...]:
    if hand_name in {
        "Straight",
        "Flush",
        "Full House",
        "Straight Flush",
        "Royal Flush",
        "Five of a Kind",
        "Flush House",
        "Flush Five",
    }:
        return cards
    if hand_name == "Four of a Kind":
        return tuple(c for c in cards if rank_counts[c.rank] == 4)
    if hand_name == "Three of a Kind":
        return tuple(c for c in cards if rank_counts[c.rank] == 3)
    if hand_name == "Two Pair":
        return tuple(c for c in cards if rank_counts[c.rank] == 2)
    if hand_name == "Pair":
        return tuple(c for c in cards if rank_counts[c.rank] == 2)
    # High card
    high = max(cards, key=lambda c: RANK_TO_STRAIGHT_VALUE[c.rank])
    return (high,)


def _is_straight(ranks: list[str]) -> bool:
    values = sorted({RANK_TO_STRAIGHT_VALUE[r] for r in ranks})
    if len(values) != 5:
        return False
    # Wheel: A-2-3-4-5
    if values == [2, 3, 4, 5, 14]:
        return True
    return values[-1] - values[0] == 4


def _is_royal(cards: tuple[ParsedCard, ...]) -> bool:
    required = {10, 11, 12, 13, 14}
    return {RANK_TO_STRAIGHT_VALUE[c.rank] for c in cards} == required


def _format_card(card: ParsedCard) -> str:
    suit_letter = {
        "Spades": "S",
        "Hearts": "H",
        "Diamonds": "D",
        "Clubs": "C",
    }.get(card.suit, card.suit[:1].upper())
    return f"{card.rank}{suit_letter}"

