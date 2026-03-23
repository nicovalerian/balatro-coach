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

# ── label maps (from proj-airi datasets) ──────────────────────────────────────
ENTITY_LABELS: list[str] = [
    "card",
    "card_joker",
    "card_tarot",
    "card_planet",
    "card_spectral",
    "card_voucher",
    "card_stack",
]

UI_LABELS: list[str] = [
    "panel_score",
    "panel_hand",
    "panel_discard",
    "panel_money",
    "panel_blind",
    "button_play",
    "button_discard",
    "button_reroll",
    "joker_slot",
    "consumable_slot",
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

    def detect(self, image: Image.Image, conf_threshold: float = 0.25) -> list[Detection]:
        """Run inference and return detections above conf_threshold."""
        orig_w, orig_h = image.size
        resized = image.resize((self._input_size, self._input_size), Image.BILINEAR)
        arr = np.array(resized, dtype=np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis]  # NCHW

        outputs = self._session.run(None, {self._input_name: arr})
        # YOLO11 output: [1, num_classes+4, num_anchors]
        pred = outputs[0][0].T  # (num_anchors, 4+num_classes)

        detections: list[Detection] = []
        for row in pred:
            x_c, y_c, w, h = row[:4]
            class_scores = row[4:]
            cls = int(np.argmax(class_scores))
            conf = float(class_scores[cls])
            if conf < conf_threshold:
                continue
            # convert cx,cy,w,h (normalised to input size) → xyxy normalised to orig
            x1 = (x_c - w / 2) / self._input_size
            y1 = (y_c - h / 2) / self._input_size
            x2 = (x_c + w / 2) / self._input_size
            y2 = (y_c + h / 2) / self._input_size
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(1, x2), min(1, y2)

            # pixel crop
            px1, py1 = int(x1 * orig_w), int(y1 * orig_h)
            px2, py2 = int(x2 * orig_w), int(y2 * orig_h)
            crop = image.crop((px1, py1, px2, py2)) if px2 > px1 and py2 > py1 else None

            label = self._labels[cls] if cls < len(self._labels) else f"cls_{cls}"
            detections.append(
                Detection(
                    label=label,
                    confidence=conf,
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    crop=crop,
                )
            )
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
