"""
Joker identification via spatial colour-histogram embedding similarity.

Approach
--------
1.  At build time (scripts/build_joker_index.py) each reference sprite is
    converted to a 768-dim feature vector and stored in data/joker_index.npz.
2.  At runtime, the same transform is applied to the YOLO joker crop.
3.  Cosine similarity against the index returns the closest match.

Feature: spatial colour histogram
    - Strip the outer frame (≈18 % of each edge) where edition overlays live.
    - Resize inner art to 32 × 32.
    - Divide into a 4 × 4 spatial grid (8 × 8 px per cell).
    - Per cell: 16-bin histogram for each of R, G, B  →  3 × 16 = 48 values.
    - Concatenate all 16 cells  →  768-dim L2-normalised vector.

Why this works
--------------
Each Balatro joker has a distinct colour palette and spatial composition
(e.g. Wee Joker is mostly blue/white at the top and white at the bottom,
Yorick is brown/warm throughout). The spatial histogram captures both the
*what* (palette) and *where* (spatial layout) of those colours, which is
enough to uniquely identify all 150 jokers even at low crop resolution.

Editions are handled by stripping the frame rather than the art centre,
so Foil/Holographic overlays (which live on the frame) don't corrupt the
feature.  Negative editions invert the art; a separate inverted copy of each
reference can be added to the index for full coverage (see build_joker_index).

Confidence gate
---------------
If the best cosine similarity is below MATCH_THRESHOLD the classifier
returns None so the caller can fall back to OCR or "Unknown".
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── tuneable constants ────────────────────────────────────────────────────────
FRAME_FRAC = 0.18          # fraction of each edge to strip as frame
GRID = 4                   # spatial grid side (GRID × GRID cells)
BINS = 16                  # colour histogram bins per channel per cell
MATCH_THRESHOLD = 0.72     # cosine similarity below this → no match (return None)
# ─────────────────────────────────────────────────────────────────────────────

_FEATURE_DIM = GRID * GRID * 3 * BINS   # 768

_DEFAULT_INDEX = Path(__file__).parent.parent.parent / "data" / "joker_index.npz"


def extract_features(image: Image.Image) -> np.ndarray:
    """
    Return a 768-dim L2-normalised float32 feature vector for a joker crop.

    Works on any PIL Image (RGB or RGBA).  Safe to call on arbitrarily-sized
    crops from the YOLO detector.
    """
    arr = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = arr.shape

    # ── 1. strip frame ────────────────────────────────────────────────────────
    fh = max(1, int(h * FRAME_FRAC))
    fw = max(1, int(w * FRAME_FRAC))
    art = arr[fh: h - fh, fw: w - fw]
    if art.size == 0:
        art = arr   # crop too small to strip; use full image

    # ── 2. resize to GRID*8 × GRID*8 ─────────────────────────────────────────
    cell_px = 8
    target = GRID * cell_px
    art_img = Image.fromarray((art * 255).astype(np.uint8)).resize(
        (target, target), Image.BILINEAR
    )
    art = np.array(art_img, dtype=np.float32) / 255.0

    # ── 3. spatial colour histogram ───────────────────────────────────────────
    feat_parts: list[np.ndarray] = []
    for row in range(GRID):
        for col in range(GRID):
            cell = art[
                row * cell_px: (row + 1) * cell_px,
                col * cell_px: (col + 1) * cell_px,
            ]   # (8, 8, 3)
            for ch in range(3):
                hist, _ = np.histogram(cell[:, :, ch], bins=BINS, range=(0.0, 1.0))
                feat_parts.append(hist.astype(np.float32))

    feat = np.concatenate(feat_parts)   # (768,)

    # ── 4. L2 normalise ───────────────────────────────────────────────────────
    norm = np.linalg.norm(feat)
    if norm > 0:
        feat /= norm
    return feat


class JokerClassifier:
    """
    Lazy-loading nearest-neighbour joker classifier.

    Usage
    -----
    clf = JokerClassifier()          # loads index on first call
    name = clf.identify(crop_image)  # returns str or None
    """

    def __init__(self, index_path: Path = _DEFAULT_INDEX):
        self._index_path = index_path
        self._names: list[str] | None = None
        self._vectors: np.ndarray | None = None   # (N, 768) float32

    def _load(self):
        if not self._index_path.exists():
            logger.warning(
                "Joker index not found at %s. "
                "Run scripts/build_joker_index.py to build it.",
                self._index_path,
            )
            self._names = []
            self._vectors = np.zeros((0, _FEATURE_DIM), dtype=np.float32)
            return
        data = np.load(self._index_path, allow_pickle=True)
        self._names = list(data["names"])
        self._vectors = data["vectors"].astype(np.float32)
        logger.info("Loaded joker index: %d entries from %s", len(self._names), self._index_path)

    @property
    def ready(self) -> bool:
        if self._vectors is None:
            self._load()
        return len(self._names) > 0   # type: ignore[arg-type]

    def identify(self, crop: Image.Image) -> str | None:
        """
        Return the closest matching joker name, or None if below threshold.

        Returns None (not a fallback string) so callers can chain with OCR.
        """
        if self._vectors is None:
            self._load()
        if not self._names:
            return None
        try:
            feat = extract_features(crop)
            sims = self._vectors @ feat          # (N,) cosine similarities
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            if best_sim < MATCH_THRESHOLD:
                logger.debug(
                    "Joker classifier: best match '%s' sim=%.3f below threshold %.2f",
                    self._names[best_idx], best_sim, MATCH_THRESHOLD,
                )
                return None
            return self._names[best_idx]
        except Exception as exc:
            logger.debug("Joker classifier failed: %s", exc)
            return None

    def top_k(self, crop: Image.Image, k: int = 3) -> list[tuple[str, float]]:
        """Return top-k (name, similarity) pairs, for debugging."""
        if self._vectors is None:
            self._load()
        if not self._names:
            return []
        feat = extract_features(crop)
        sims = self._vectors @ feat
        indices = np.argsort(sims)[::-1][:k]
        return [(self._names[i], float(sims[i])) for i in indices]
