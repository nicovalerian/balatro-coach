"""
YOLO ONNX inference wrapper.
Runs both proj-airi models:
  - entities: cards, jokers, tarots, planets, spectrals
  - ui:       score panels, hand count, discard count, money, buttons
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Try importing onnxruntime; if missing, detector will raise on first use
try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False
    logger.warning("onnxruntime not installed – CV pipeline disabled")

# ── label maps (from proj-airi v2 datasets, Sept 2025) ───────────────────────
ENTITY_LABELS: list[str] = [
    "card_description",      # 0 – text panel below a card (good for OCR)
    "card_pack",             # 1 – booster pack
    "joker_card",            # 2 – joker
    "planet_card",           # 3 – planet consumable
    "poker_card_back",       # 4 – face-down playing card
    "poker_card_description",# 5 – rank/suit text panel on a playing card
    "poker_card_front",      # 6 – face-up playing card
    "poker_card_stack",      # 7 – deck pile
    "spectral_card",         # 8 – spectral consumable
    "tarot_card",            # 9 – tarot consumable
]

UI_LABELS: list[str] = [
    "button_back",               # 0
    "button_card_pack_skip",     # 1
    "button_cash_out",           # 2
    "button_discard",            # 3
    "button_level_select",       # 4
    "button_level_skip",         # 5
    "button_main_menu",          # 6
    "button_main_menu_play",     # 7
    "button_new_run",            # 8
    "button_new_run_play",       # 9
    "button_options",            # 10
    "button_play",               # 11
    "button_purchase",           # 12
    "button_run_info",           # 13
    "button_sell",               # 14
    "button_sort_hand_rank",     # 15
    "button_sort_hand_suits",    # 16
    "button_store_next_round",   # 17
    "button_store_reroll",       # 18
    "button_use",                # 19
    "ui_card_value",             # 20
    "ui_data_cash",              # 21
    "ui_data_discards_left",     # 22
    "ui_data_hands_left",        # 23
    "ui_round_ante_current",     # 24
    "ui_round_ante_left",        # 25
    "ui_round_round_current",    # 26
    "ui_round_round_left",       # 27
    "ui_score_chips",            # 28
    "ui_score_current",          # 29
    "ui_score_mult",             # 30
    "ui_score_round_score",      # 31
    "ui_score_target_score",     # 32
]


@dataclass
class Detection:
    label: str
    confidence: float
    # normalised [0,1] xyxy
    x1: float
    y1: float
    x2: float
    y2: float
    # pixel crop from original image (set later)
    crop: Image.Image | None = field(default=None, repr=False)


def _iou(a: tuple, b: tuple) -> float:
    """IoU between two (conf, cls, x1, y1, x2, y2) tuples."""
    ax1, ay1, ax2, ay2 = a[2], a[3], a[4], a[5]
    bx1, by1, bx2, by2 = b[2], b[3], b[4], b[5]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    a_area = (ax2 - ax1) * (ay2 - ay1)
    b_area = (bx2 - bx1) * (by2 - by1)
    return inter / (a_area + b_area - inter)


def _nms(raw: list, iou_threshold: float) -> list:
    """Greedy per-class NMS. raw items: (conf, cls, x1, y1, x2, y2)."""
    from collections import defaultdict
    by_class: dict[int, list] = defaultdict(list)
    for item in raw:
        by_class[item[1]].append(item)
    kept = []
    for cls_items in by_class.values():
        cls_items.sort(key=lambda x: x[0], reverse=True)
        suppressed = [False] * len(cls_items)
        for i in range(len(cls_items)):
            if suppressed[i]:
                continue
            kept.append(cls_items[i])
            for j in range(i + 1, len(cls_items)):
                if not suppressed[j] and _iou(cls_items[i], cls_items[j]) > iou_threshold:
                    suppressed[j] = True
    return kept


class YOLODetector:
    """Thin ONNX wrapper for a single YOLO11n model."""

    def __init__(self, model_path: Path, labels: list[str], input_size: int = 640):
        if not _ORT_AVAILABLE:
            raise RuntimeError("onnxruntime is required for CV features")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Run `python scripts/download_models.py` first."
            )
        self._labels = labels
        self._input_size = input_size
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name

    def detect(self, image: Image.Image, conf_threshold: float = 0.25, iou_threshold: float = 0.65) -> list[Detection]:
        """Run inference and return detections above conf_threshold, after NMS."""
        orig_w, orig_h = image.size
        resized = image.resize((self._input_size, self._input_size), Image.BILINEAR)
        arr = np.array(resized, dtype=np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis]  # NCHW

        outputs = self._session.run(None, {self._input_name: arr})
        # YOLO11 output: [1, num_classes+4, num_anchors]
        pred = outputs[0][0].T  # (num_anchors, 4+num_classes)

        raw: list[tuple[float, int, float, float, float, float]] = []
        for row in pred:
            x_c, y_c, w, h = row[:4]
            class_scores = row[4:]
            cls = int(np.argmax(class_scores))
            conf = float(class_scores[cls])
            if conf < conf_threshold:
                continue
            x1 = max(0.0, (x_c - w / 2) / self._input_size)
            y1 = max(0.0, (y_c - h / 2) / self._input_size)
            x2 = min(1.0, (x_c + w / 2) / self._input_size)
            y2 = min(1.0, (y_c + h / 2) / self._input_size)
            raw.append((conf, cls, x1, y1, x2, y2))

        # Per-class greedy NMS
        kept = _nms(raw, iou_threshold)

        detections: list[Detection] = []
        for conf, cls, x1, y1, x2, y2 in kept:
            px1, py1 = int(x1 * orig_w), int(y1 * orig_h)
            px2, py2 = int(x2 * orig_w), int(y2 * orig_h)
            crop = image.crop((px1, py1, px2, py2)) if px2 > px1 and py2 > py1 else None
            label = self._labels[cls] if cls < len(self._labels) else f"cls_{cls}"
            detections.append(Detection(label=label, confidence=conf, x1=x1, y1=y1, x2=x2, y2=y2, crop=crop))
        return detections


class BalatroDetector:
    """Combines entities + UI detectors into a single interface."""

    def __init__(
        self,
        entities_path: Path,
        ui_path: Path,
        conf_threshold: float = 0.25,
    ):
        self.conf_threshold = conf_threshold
        self._entities = YOLODetector(entities_path, ENTITY_LABELS)
        self._ui = YOLODetector(ui_path, UI_LABELS)

    def run(self, image: Image.Image) -> tuple[list[Detection], list[Detection]]:
        """Returns (entity_detections, ui_detections)."""
        entities = self._entities.detect(image, self.conf_threshold)
        ui = self._ui.detect(image, self.conf_threshold)
        return entities, ui


def load_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")
