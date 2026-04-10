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

from .detector import BalatroDetector, Detection
from .edition import detect_edition
from .joker_classifier import JokerClassifier
from .joker_names import ALL_JOKER_NAMES, fuzzy_match_joker
from .ocr import read_number, read_text

logger = logging.getLogger(__name__)

# Lazy singleton — loaded on first joker crop
_joker_clf: JokerClassifier | None = None


def _get_joker_classifier() -> JokerClassifier:
    global _joker_clf
    if _joker_clf is None:
        _joker_clf = JokerClassifier()
    return _joker_clf

CARD_RANKS = list("A23456789") + ["10", "J", "Q", "K"]

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

        if "button_store_reroll" in ui_labels:
            state.screen_type = "shop"
        elif "button_play" in ui_labels or "button_discard" in ui_labels:
            state.screen_type = "hand"
        elif ("button_level_select" in ui_labels or "button_level_skip" in ui_labels) and "button_play" not in ui_labels:
            state.screen_type = "blind_select"

        # Fallback: infer from entity types when UI buttons weren't detected
        if state.screen_type == "unknown" and entities:
            entity_labels = {d.label for d in entities}
            shop_labels = {"tarot_card", "planet_card", "spectral_card", "card_pack"}
            if "poker_card_front" in entity_labels:
                state.screen_type = "hand"
            elif entity_labels & shop_labels and "poker_card_front" not in entity_labels:
                state.screen_type = "shop"

        # ── Cards in hand ─────────────────────────────────────────────────────
        card_dets = [d for d in entities if d.label == "poker_card_front"]
        # Build a lookup: for each card_front, find the closest poker_card_description
        desc_dets = [d for d in entities if d.label == "poker_card_description"]
        for det in sorted(card_dets, key=lambda d: d.x1):
            confidences.append(det.confidence)
            # Prefer the description panel (cleaner text) over the card art
            crop = _find_nearest_description(det, desc_dets) or det.crop
            text = read_text(crop) if crop else ""
            card = _parse_card_text(text)
            card["edition"] = detect_edition(det.crop) if det.crop else "base"
            state.hand.append(card)

        # ── Jokers ────────────────────────────────────────────────────────────
        joker_dets = [d for d in entities if d.label == "joker_card"]
        # Build a lookup: for each joker, find the closest card_description panel
        card_desc_dets = [d for d in entities if d.label == "card_description"]
        clf = _get_joker_classifier()
        for i, det in enumerate(sorted(joker_dets, key=lambda d: d.x1)):
            confidences.append(det.confidence)
            # 1. Visual classifier (index-based) — most accurate
            name = clf.identify(det.crop) if det.crop else None
            # 2. OCR on description panel or card crop — fallback
            if name is None:
                desc_crop = _find_nearest_description(det, card_desc_dets)
                crop = desc_crop or det.crop
                raw = _normalize_ocr_name(read_text(crop) if crop else "")
                name = fuzzy_match_joker(raw) or None
            # 3. If still unidentified, label clearly so the LLM doesn't invent stats
            if not name:
                name = f"Joker {i+1} (unidentified)"
            edition = detect_edition(det.crop) if det.crop else "base"
            state.jokers.append({"name": name, "slot": i, "edition": edition})

        # ── Consumables (tarot / planet / spectral) ───────────────────────────
        label_to_type = {"tarot_card": "tarot", "planet_card": "planet", "spectral_card": "spectral"}
        for label, ctype in label_to_type.items():
            for det in [d for d in entities if d.label == label]:
                confidences.append(det.confidence)
                desc_crop = _find_nearest_description(det, card_desc_dets)
                crop = desc_crop or det.crop
                raw = _normalize_ocr_name(read_text(crop) if crop else "")
                name = fuzzy_match_joker(raw) or raw
                # Skip if OCR read a joker name — it's a misdetection from a nearby joker crop
                if name in ALL_JOKER_NAMES:
                    continue
                state.consumables.append({"type": ctype, "name": name})

        # ── UI: score panels ──────────────────────────────────────────────────
        for det in [d for d in ui_dets if d.label == "ui_score_round_score"]:
            if det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.score["current"] = val
        for det in [d for d in ui_dets if d.label == "ui_score_chips"]:
            if det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.score["chips"] = val
        for det in [d for d in ui_dets if d.label == "ui_score_mult"]:
            if det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.score["mult"] = val

        # ── UI: resource panels ───────────────────────────────────────────────
        label_key = {
            "ui_data_hands_left": "hands",
            "ui_data_discards_left": "discards",
            "ui_data_cash": "money",
        }
        for det in ui_dets:
            key = label_key.get(det.label)
            if key and det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.resources[key] = val

        # ── Blind target + ante ───────────────────────────────────────────────
        for det in [d for d in ui_dets if d.label == "ui_score_target_score"]:
            if det.crop:
                val = read_number(det.crop)
                if val:
                    state.blind["target"] = val
        for det in [d for d in ui_dets if d.label == "ui_round_ante_current"]:
            if det.crop:
                val = read_number(det.crop)
                if val is not None:
                    state.ante = val

        # ── Shop items ────────────────────────────────────────────────────────
        if state.screen_type == "shop":
            shop_type_map = {
                "joker_card": "joker",
                "tarot_card": "tarot",
                "planet_card": "planet",
                "spectral_card": "spectral",
                "card_pack": "pack",
            }
            shop_items = [d for d in entities if d.label in shop_type_map]
            state.shop["items"] = []
            for det in shop_items:
                desc_crop = _find_nearest_description(det, card_desc_dets)
                crop = desc_crop or det.crop
                raw = _normalize_ocr_name(read_text(crop) if crop else "")
                name = fuzzy_match_joker(raw) or raw
                state.shop["items"].append({
                    "type": shop_type_map[det.label],
                    "name": name,
                })

        # ── Confidence summary ────────────────────────────────────────────────
        if confidences:
            state.confidence = sum(confidences) / len(confidences)
            state.low_confidence = state.confidence < self._conf_threshold
        else:
            # no detections at all → definitely low confidence
            state.low_confidence = True
            state.confidence = 0.0

        return state


def _find_nearest_description(det: Detection, desc_dets: list) -> Image.Image | None:
    """Return the crop of the description panel closest to det (by horizontal centre)."""
    if not desc_dets:
        return None
    det_cx = (det.x1 + det.x2) / 2
    best = min(desc_dets, key=lambda d: abs((d.x1 + d.x2) / 2 - det_cx))
    # Only use it if it's reasonably close (within 10% of image width)
    if abs((best.x1 + best.x2) / 2 - det_cx) > 0.10:
        return None
    return best.crop


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
