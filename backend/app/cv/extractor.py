"""
Builds a structured game-state dict from YOLO detections + OCR text.

Output schema (all fields optional – set to None if undetected):
{
  "screen_type": "hand" | "shop" | "blind_select" | "unknown",
  "confidence": float,   # min confidence across all detected fields
  "low_confidence": bool,
  "hand": [{"rank": "A", "suit": "Spades", "enhanced": false}, ...],
  "jokers": [{"name": "Blueprint", "slot": 0}, ...],
  "consumables": [...],
  "score": {"chips": int, "mult": int, "current": int},
  "resources": {"hands": int, "discards": int, "money": int},
  "blind": {"target": int, "name": str},
  "ante": int,
  "shop": {"items": [...]}
}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from .detector import BalatroDetector
from .ocr import read_number, read_text

logger = logging.getLogger(__name__)

CARD_RANKS = list("A23456789") + ["10", "J", "Q", "K"]
CARD_SUITS = ["Spades", "Hearts", "Clubs", "Diamonds"]

# Map OCR'd text → normalised suit
SUIT_MAP = {
    "s": "Spades", "spades": "Spades",
    "h": "Hearts", "hearts": "Hearts",
    "c": "Clubs",  "clubs": "Clubs",
    "d": "Diamonds", "diamonds": "Diamonds",
}


def _normalize_ocr_name(raw: str) -> str:
    cleaned = " ".join(raw.replace("\n", " ").split())
    if not cleaned:
        return ""
    return cleaned[:80]


@dataclass
class GameState:
    screen_type: str = "unknown"
    confidence: float = 1.0
    low_confidence: bool = False
    hand: list[dict] = field(default_factory=list)
    jokers: list[dict] = field(default_factory=list)
    consumables: list[dict] = field(default_factory=list)
    score: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)
    blind: dict = field(default_factory=dict)
    ante: int | None = None
    shop: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "screen_type": self.screen_type,
            "confidence": round(self.confidence, 3),
            "low_confidence": self.low_confidence,
            "hand": self.hand,
            "jokers": self.jokers,
            "consumables": self.consumables,
            "score": self.score,
            "resources": self.resources,
            "blind": self.blind,
            "ante": self.ante,
            "shop": self.shop,
        }


class StateExtractor:
    def __init__(self, detector: BalatroDetector, conf_threshold: float = 0.6):
        self._detector = detector
        self._conf_threshold = conf_threshold

    def extract(self, image: Image.Image) -> GameState:
        entities, ui_dets = self._detector.run(image)
        state = GameState()
        confidences: list[float] = []

        # ── Screen type heuristic ──────────────────────────────────────────────
        ui_labels = {d.label for d in ui_dets}

        if "button_reroll" in ui_labels:
            state.screen_type = "shop"
        elif "button_play" in ui_labels or "button_discard" in ui_labels:
            state.screen_type = "hand"
        elif "panel_blind" in ui_labels and "button_play" not in ui_labels:
            state.screen_type = "blind_select"

        # ── Cards in hand ─────────────────────────────────────────────────────
        card_dets = [d for d in entities if d.label == "card"]
        for det in sorted(card_dets, key=lambda d: d.x1):
            confidences.append(det.confidence)
            if det.crop:
                text = read_text(det.crop)
                card = _parse_card_text(text)
                state.hand.append(card)

        # ── Jokers ────────────────────────────────────────────────────────────
        joker_dets = [d for d in entities if d.label == "card_joker"]
        for i, det in enumerate(sorted(joker_dets, key=lambda d: d.x1)):
            confidences.append(det.confidence)
            name = _normalize_ocr_name(read_text(det.crop) if det.crop else "")
            state.jokers.append({"name": name or f"Joker {i+1}", "slot": i})

        # ── Consumables (tarot / planet / spectral) ───────────────────────────
        for label in ("card_tarot", "card_planet", "card_spectral"):
            for det in [d for d in entities if d.label == label]:
                confidences.append(det.confidence)
                name = _normalize_ocr_name(read_text(det.crop) if det.crop else "")
                state.consumables.append({"type": label.split("_")[1], "name": name})

        # ── UI: score panel ───────────────────────────────────────────────────
        for det in [d for d in ui_dets if d.label == "panel_score"]:
            if det.crop:
                val = read_number(det.crop)
                state.score["current"] = val

        # ── UI: resource panels ───────────────────────────────────────────────
        label_key = {
            "panel_hand": "hands",
            "panel_discard": "discards",
            "panel_money": "money",
        }
        for det in ui_dets:
            key = label_key.get(det.label)
            if key and det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.resources[key] = val

        # ── Blind target ──────────────────────────────────────────────────────
        for det in [d for d in ui_dets if d.label == "panel_blind"]:
            if det.crop:
                val = read_number(det.crop)
                if val:
                    state.blind["target"] = val

        # ── Shop items ────────────────────────────────────────────────────────
        if state.screen_type == "shop":
            shop_items = [d for d in entities if d.label in (
                "card_joker", "card_tarot", "card_planet",
                "card_spectral", "card_voucher",
            )]
            state.shop["items"] = []
            for det in shop_items:
                name = _normalize_ocr_name(read_text(det.crop) if det.crop else "")
                state.shop["items"].append({
                    "type": det.label.split("_")[1] if "_" in det.label else det.label,
                    "name": name,
                })

        # ── Confidence summary ────────────────────────────────────────────────
        if confidences:
            state.confidence = min(confidences)
            state.low_confidence = state.confidence < self._conf_threshold
        else:
            # no detections at all → definitely low confidence
            state.low_confidence = True
            state.confidence = 0.0

        return state


def _parse_card_text(text: str) -> dict:
    """Best-effort parse of OCR'd playing card text like 'A♠' or '10 Hearts'."""
    text = text.strip()
    rank, suit = None, None
    for r in sorted(CARD_RANKS, key=len, reverse=True):
        if text.upper().startswith(r.upper()):
            rank = r
            remainder = text[len(r):].strip()
            for key, val in SUIT_MAP.items():
                if key in remainder.lower():
                    suit = val
                    break
            break
    return {"rank": rank, "suit": suit, "enhanced": False}
