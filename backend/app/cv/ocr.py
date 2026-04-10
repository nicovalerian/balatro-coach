"""
OCR wrapper using rapidocr-onnxruntime (same stack as proj-airi).
Reads text from PIL Image crops returned by the YOLO detectors.

Two strategies:
  read_text   – for descriptive text (card names, labels); uses standard
                grayscale preprocessing with contrast boost.
  read_number – for numeric UI elements (score, money, etc.); uses a
                specialised pipeline tuned for Balatro's pixel-art font:
                  1. Max-channel projection (isolates any coloured digit)
                  2. Inversion          (dark digits → bright on dark bg)
                  3. LANCZOS 8× upscale
                  4. Binary threshold + 1-iter erosion (thin thick strokes)
                  5. White padding (helps EAST text detector)
                  6. det=True  (good for multi-digit / larger text)
                     det=False (fallback; direct recogniser, best for
                                single-digit pixel-art crops)
                  7. Pick whichever path returned more digit characters.
"""
from __future__ import annotations

import logging
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

try:
    from rapidocr_onnxruntime import RapidOCR as _RapidOCR
    _OCR = _RapidOCR()
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
    logger.warning("rapidocr-onnxruntime not installed – OCR disabled")

# Characters that the recogniser commonly confuses for digits
_DIGIT_SUBS: dict[str, str] = {
    "口": "0",   # Chinese "mouth" looks like Balatro's pixel-art 0
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "\u4e00": "1",  # Chinese "one"
    "S": "5",
    "s": "5",
    "Z": "2",
    "B": "8",
}


def _preprocess_crop(image: Image.Image) -> Image.Image:
    """Upscale small crops and boost contrast to improve OCR on pixel-art fonts."""
    w, h = image.size
    if w < 200:
        scale = max(2, 200 // max(w, 1))
        image = image.resize((w * scale, h * scale), Image.LANCZOS)
    # Grayscale + contrast boost helps RapidOCR on stylised Balatro fonts
    image = image.convert("L").convert("RGB")
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image


def _preprocess_number_crop(image: Image.Image, scale: int = 8, pad: int = 40) -> np.ndarray:
    """
    Convert a Balatro UI number crop into a binary image suitable for OCR.

    Works on any coloured digit (blue hands, red discards, orange ante/round,
    white target score) because we use the maximum across all channels rather
    than a luminance-weighted grayscale.
    """
    try:
        import cv2
    except ImportError:
        logger.debug("cv2 not available; falling back to standard preprocessing")
        return np.array(_preprocess_crop(image))

    arr = np.array(image.convert("RGB"))
    # 1. Max-channel projection: bright where *any* channel is saturated
    max_ch = arr.max(axis=2).astype(np.uint8)
    # 2. Invert: digits → black, dark background → white (standard OCR polarity)
    inv = (255 - max_ch).astype(np.uint8)
    h, w = inv.shape
    # 3. Upscale with LANCZOS for smoother edges, better recogniser input
    big = cv2.resize(
        np.stack([inv, inv, inv], axis=2),
        (w * scale, h * scale),
        interpolation=cv2.INTER_LANCZOS4,
    )
    # 4. Binarise + 1-iter erosion to thin thick pixel-art strokes
    gray = big[:, :, 0]
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(binary, kernel, iterations=1)
    result_3ch = np.stack([eroded, eroded, eroded], axis=2)
    # 5. White padding so the EAST detector has context around glyphs
    padded = np.pad(result_3ch, ((pad, pad), (pad, pad), (0, 0)), constant_values=255)
    return padded


def read_text(image: Image.Image) -> str:
    """Return stripped text from a PIL crop, or empty string on failure."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        arr = np.array(_preprocess_crop(image))
        result, _ = _OCR(arr)
        if not result:
            return ""
        texts = [r[1] for r in result if r[1]]
        return " ".join(texts).strip()
    except Exception as exc:
        logger.debug("OCR failed: %s", exc)
        return ""


def read_number(image: Image.Image) -> int | None:
    """
    Extract an integer from a Balatro UI numeric crop.

    Uses a two-pass strategy tuned for the game's pixel-art font:
    - Pass 1: standard EAST detection (good for multi-digit, larger text)
    - Pass 2: direct recognition without detection (for single-digit crops)
    Returns the value whose textual representation contains more digits.
    """
    if not _OCR_AVAILABLE:
        return None

    try:
        arr = _preprocess_number_crop(image)

        # Pass 1 – standard detection pipeline
        result_det, _ = _OCR(arr)
        text_det = " ".join(r[1] for r in result_det if r[1]) if result_det else ""

        # Pass 2 – direct recogniser (no text-detection stage)
        result_nodet, _ = _OCR(arr, use_det=False, use_cls=False, use_rec=True)
        text_nodet = result_nodet[0][0] if result_nodet and result_nodet[0] else ""

        # Apply look-alike substitutions to both results
        def clean(t: str) -> str:
            for bad, good in _DIGIT_SUBS.items():
                t = t.replace(bad, good)
            return "".join(c for c in t if c.isdigit())

        digits_det = clean(text_det)
        digits_nodet = clean(text_nodet)

        # Prefer the result with more digit characters; break ties with nodet
        digits = digits_nodet if len(digits_nodet) >= len(digits_det) else digits_det
        return int(digits) if digits else None

    except Exception as exc:
        logger.debug("read_number failed: %s", exc)
        # Fallback to legacy method
        raw = read_text(image).replace(",", "").replace(".", "").strip()
        digits = "".join(c for c in raw if c.isdigit())
        return int(digits) if digits else None
