"""
OCR wrapper using rapidocr-onnxruntime (same stack as proj-airi).
Reads text from PIL Image crops returned by the YOLO detectors.
"""
from __future__ import annotations

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:
    from rapidocr_onnxruntime import RapidOCR as _RapidOCR
    _OCR = _RapidOCR()
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
    logger.warning("rapidocr-onnxruntime not installed – OCR disabled")


def read_text(image: Image.Image) -> str:
    """Return stripped text from a PIL crop, or empty string on failure."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        arr = np.array(image)
        result, _ = _OCR(arr)
        if not result:
            return ""
        # result: list of [bbox, text, confidence]
        texts = [r[1] for r in result if r[1]]
        return " ".join(texts).strip()
    except Exception as exc:
        logger.debug("OCR failed: %s", exc)
        return ""


def read_number(image: Image.Image) -> int | None:
    """Convenience: extract an integer from a crop (scores, money, etc.)."""
    raw = read_text(image).replace(",", "").replace(".", "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    return int(digits) if digits else None
