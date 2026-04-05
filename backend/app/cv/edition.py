"""
Edition detection for Balatro cards via frame-border color analysis.

Strategy: sample only the outer frame (~15% border) of a card crop, not
the joker art. Edition overlays are most distinct at the frame edges:

  Base        – warm brown frame (no strong channel bias, hue_std low)
  Foil        – blue/silver frame: B clearly dominant over R and G
  Holographic – purple frame: R *and* B both elevated above G
  Polychrome  – rainbow frame: high hue variance across saturated pixels
  Negative    – inverted/dark frame: very low brightness

Thresholds are calibrated conservatively to minimise false positives on
jokers whose natural art bleeds into the border (e.g. Yorick's warm orange).
Without a labelled dataset the thresholds are approximate; they can be tuned
by adding known-edition screenshots to the test suite (see cv/eval.py).
"""
from __future__ import annotations

import colorsys
import logging

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Tune these with labelled data; see EDITION_THRESHOLDS_NOTES below.
_BORDER_FRAC = 0.15      # fraction of min(h,w) used as border width
_SAT_MIN = 0.15          # minimum saturation to count a pixel toward hue_std
_SAMPLE_STEP = 3         # sample every Nth border pixel (speed vs precision)

# Detection thresholds (conservative – prefer false-negative over false-positive)
_NEG_BRIGHTNESS_MAX = 0.22     # Negative: dark frame
_FOIL_B_LEAD = 0.07            # Foil: B - max(R,G) >= this
_HOLO_PURPLE_LEAD = 0.05       # Holographic: (R+B)/2 - G >= this, and B > R
_POLY_HUE_STD_MIN = 0.36       # Polychrome: hue std of saturated border pixels

# EDITION_THRESHOLDS_NOTES
# ─────────────────────────
# Foil (B_LEAD=0.07): on test-1.jfif joker[0] border had B-max(R,G)=0.094 → Foil.
#   Yorick (warm art) had B-max(R,G)=-0.335 → correctly skipped.
# Holographic: needs R+B both above G. Distinguished from Foil because Foil has
#   B >> R while Holographic has R ≈ B >> G.  Gate: B - R < FOIL_B_LEAD.
# Polychrome: hue_std on saturated pixels. Base jokers on test-1 peaked at 0.263.
#   Playing card borders (Ace of Hearts etc.) reached 0.351 from natural suit symbols
#   and vivid background bleed → threshold at 0.36. Calibrate down once labelled
#   polychrome screenshots are available.
# Negative: typically brightness < 0.22. The inverted art makes the frame very dark.
#   Raise if false-negatives on brighter-looking Negative editions appear.


def detect_edition(crop: Image.Image) -> str:
    """
    Return one of: 'base', 'foil', 'holographic', 'polychrome', 'negative'.

    Works on any PIL Image crop (RGB). Returns 'base' on any error.
    """
    try:
        return _classify(crop)
    except Exception as exc:
        logger.debug("Edition detection failed: %s", exc)
        return "base"


def _border_pixels(arr: np.ndarray) -> np.ndarray:
    """Return (N, 3) float32 array of border pixels at _SAMPLE_STEP stride."""
    h, w, _ = arr.shape
    bw = max(1, int(min(h, w) * _BORDER_FRAC))
    top = arr[:bw, ::_SAMPLE_STEP].reshape(-1, 3)
    bot = arr[h - bw:, ::_SAMPLE_STEP].reshape(-1, 3)
    left = arr[bw:h - bw:_SAMPLE_STEP, :bw].reshape(-1, 3)
    right = arr[bw:h - bw:_SAMPLE_STEP, w - bw:].reshape(-1, 3)
    return np.concatenate([top, bot, left, right], axis=0)


def _hue_std(pixels: np.ndarray) -> float:
    """Circular-aware std of hue for pixels above saturation threshold."""
    h_vals: list[float] = []
    for px in pixels[::_SAMPLE_STEP]:
        hv, sv, _ = colorsys.rgb_to_hsv(float(px[0]), float(px[1]), float(px[2]))
        if sv >= _SAT_MIN:
            h_vals.append(hv)
    if len(h_vals) < 10:
        return 0.0
    arr = np.array(h_vals)
    # Circular mean/std: wrap hue at 1.0
    sin_mean = np.sin(2 * np.pi * arr).mean()
    cos_mean = np.cos(2 * np.pi * arr).mean()
    r = np.sqrt(sin_mean**2 + cos_mean**2)
    return float(np.sqrt(-2 * np.log(max(r, 1e-9))) / (2 * np.pi))


def _classify(crop: Image.Image) -> str:
    arr = np.array(crop.convert("RGB"), dtype=np.float32) / 255.0
    border = _border_pixels(arr)
    if len(border) == 0:
        return "base"

    brightness = float(border.mean())
    r = float(border[:, 0].mean())
    g = float(border[:, 1].mean())
    b = float(border[:, 2].mean())

    # 1. Negative – very dark frame
    if brightness < _NEG_BRIGHTNESS_MAX:
        return "negative"

    # 2. Polychrome – high hue variance in saturated border pixels
    if _hue_std(border) >= _POLY_HUE_STD_MIN:
        return "polychrome"

    # 3. Foil – blue/silver dominant (B clearly above both R and G)
    b_lead = b - max(r, g)
    if b_lead >= _FOIL_B_LEAD:
        return "foil"

    # 4. Holographic – purple (R and B both above G, but B not far ahead of R)
    purple_lead = (r + b) / 2.0 - g
    if purple_lead >= _HOLO_PURPLE_LEAD and b - r < _FOIL_B_LEAD:
        return "holographic"

    return "base"
