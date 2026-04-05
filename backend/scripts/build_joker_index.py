"""
Build the joker visual-similarity index used by JokerClassifier.

Sprite sources (fastest → most reliable)
-----------------------------------------
Option A – Extract from the game (RECOMMENDED, exact match to what YOLO crops):
    1. Open Balatro.exe with 7-Zip (or any zip tool).
    2. Navigate to:  Resources/Textures/2x/
    3. Extract  Jokers.png  (the sprite sheet, 142×190 px per joker).
    4. Run this script with --from-sheet:
           python scripts/build_joker_index.py --from-sheet path/to/Jokers.png

Option B – Auto-download individual PNGs from the Balatro Fandom Wiki:
           python scripts/build_joker_index.py --download

Option C – Supply your own PNGs in data/joker_sprites/, named <slug>.png
           (e.g. wee_joker.png, yorick.png) then just run:
           python scripts/build_joker_index.py

Output: data/joker_index.npz
    names   – (N,) array of joker name strings
    vectors – (N, 768) float32 L2-normalised feature matrix

Other flags
-----------
    --negative   also index Negative-edition variants (inverted art)
    --test       run self-test accuracy check after building
    --sprites-dir PATH   override the default data/joker_sprites/ directory
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image

# Allow running from anywhere inside the project
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.cv.joker_classifier import extract_features, MATCH_THRESHOLD

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SPRITES_DIR = ROOT / "data" / "joker_sprites"
INDEX_PATH  = ROOT / "data" / "joker_index.npz"

FANDOM_API   = "https://balatrogame.fandom.com/api.php"
HEADERS      = {"User-Agent": "balatro-coach/1.0 (joker-index-builder)"}
RATE_LIMIT_S = 0.3   # seconds between wiki API calls


# ── canonical joker names (150 as of 1.0.1n) ─────────────────────────────────
# Used to map wiki filenames back to clean display names.
JOKER_NAMES: list[str] = [
    "Joker", "Greedy Joker", "Lusty Joker", "Wrathful Joker", "Gluttonous Joker",
    "Jolly Joker", "Zany Joker", "Mad Joker", "Crazy Joker", "Droll Joker",
    "Sly Joker", "Wily Joker", "Clever Joker", "Devious Joker", "Crafty Joker",
    "Half Joker", "Joker Stencil", "Four Fingers", "Mime", "Credit Card",
    "Ceremonial Dagger", "Banner", "Mystic Summit", "Marble Joker", "Loyalty Card",
    "8 Ball", "Misprint", "Dusk", "Raised Fist", "Chaos the Clown",
    "Fibonacci", "Steel Joker", "Scary Face", "Abstract Joker", "Delayed Gratification",
    "Hack", "Pareidolia", "Gros Michel", "Even Steven", "Odd Todd",
    "Scholar", "Business Card", "Supernova", "Ride the Bus", "Space Joker",
    "Egg", "Burglar", "Blackboard", "Runner", "Ice Cream",
    "DNA", "Splash", "Blue Joker", "Sixth Sense", "Constellation",
    "Hiker", "Card Sharp", "Red Card", "Madness", "Square Joker",
    "Seance", "Riff-Raff", "Vampire", "Shortcut", "Hologram",
    "Vagabond", "Baron", "Cloud 9", "Rocket", "Obelisk",
    "Midas Mask", "Luchador", "Photograph", "Gift Card", "Turtle Bean",
    "Erosion", "Reserved Parking", "Flash Card", "Popcorn", "Spare Trousers",
    "Ancient Joker", "Ramen", "Walkie Talkie", "Selzer", "Castle",
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
]

_SLUG_MAP: dict[str, str] = {
    # wiki filename slug (lowercased, spaces→underscores, punctuation stripped)
    # → canonical display name
    # Pre-populate tricky ones; rest are auto-generated.
    "8_ball": "8 Ball",
    "oops_all_6s": "Oops! All 6s",
    "drivers_license": "Driver's License",
    "mr_bones": "Mr. Bones",
    "the_duo": "The Duo",
    "the_trio": "The Trio",
    "the_family": "The Family",
    "the_order": "The Order",
    "the_tribe": "The Tribe",
    "the_idol": "The Idol",
    "riff-raff": "Riff-Raff",
    "sock_and_buskin": "Sock and Buskin",
    "oops__all_6s": "Oops! All 6s",
}


def _to_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


def _slug_to_name(slug: str) -> str | None:
    if slug in _SLUG_MAP:
        return _SLUG_MAP[slug]
    # Auto-match: title-case each word
    candidate = " ".join(w.capitalize() for w in slug.split("_"))
    if candidate in JOKER_NAMES:
        return candidate
    # Fuzzy: check if slug matches any canonical name's slug
    for name in JOKER_NAMES:
        if _to_slug(name) == slug:
            return name
    return None


# ── wiki download ─────────────────────────────────────────────────────────────

def _wiki_image_list() -> list[str]:
    """Return all image titles in Category:Images - Jokers."""
    titles: list[str] = []
    params: dict = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:Images - Jokers",
        "cmtype": "file",
        "cmlimit": "500",
        "format": "json",
    }
    while True:
        r = requests.get(FANDOM_API, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        for m in data["query"]["categorymembers"]:
            titles.append(m["title"])
        if "query-continue" in data:
            params["cmcontinue"] = data["query-continue"]["categorymembers"]["cmcontinue"]
        elif "continue" in data:
            params["cmcontinue"] = data["continue"].get("cmcontinue", "")
        else:
            break
        time.sleep(RATE_LIMIT_S)
    log.info("Wiki: found %d images in joker category", len(titles))
    return titles


def _wiki_image_url(file_title: str) -> str | None:
    """Return direct download URL for a wiki File: page."""
    params = {
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    r = requests.get(FANDOM_API, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    pages = data["query"]["pages"]
    for page in pages.values():
        info = page.get("imageinfo", [])
        if info:
            return info[0]["url"]
    return None


def download_sprites(dest: Path) -> None:
    """Download joker sprites from the Balatro Fandom Wiki into dest/."""
    dest.mkdir(parents=True, exist_ok=True)
    log.info("Fetching joker image list from wiki…")
    titles = _wiki_image_list()

    downloaded = 0
    skipped = 0
    for title in titles:
        # title is like "File:Joker.png" or "File:Wee Joker.png"
        filename = title.removeprefix("File:")
        stem = Path(filename).stem
        slug = _to_slug(stem)
        name = _slug_to_name(slug)
        if name is None:
            log.debug("Skipping unrecognised wiki image: %s", filename)
            skipped += 1
            continue

        out_path = dest / f"{_to_slug(name)}.png"
        if out_path.exists():
            skipped += 1
            continue

        time.sleep(RATE_LIMIT_S)
        url = _wiki_image_url(title)
        if not url:
            log.warning("No URL for %s", title)
            continue

        time.sleep(RATE_LIMIT_S)
        try:
            img_r = requests.get(url, headers=HEADERS, timeout=20)
            img_r.raise_for_status()
            img = Image.open(__import__("io").BytesIO(img_r.content)).convert("RGBA")
            # Composite onto white background (some wiki images are transparent PNGs)
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            bg.save(out_path)
            log.info("  ✓ %s → %s", name, out_path.name)
            downloaded += 1
        except Exception as exc:
            log.warning("  ✗ %s: %s", name, exc)

    log.info("Download complete: %d downloaded, %d skipped", downloaded, skipped)


# ── sprite-sheet extraction ───────────────────────────────────────────────────

# Balatro Jokers.png layout (Resources/Textures/2x inside Balatro.exe)
# Each cell is 142 × 190 px, 10 jokers per row, read left-to-right top-to-bottom.
# Order matches JOKER_NAMES above (game internal order).
SHEET_CELL_W = 142
SHEET_CELL_H = 190
SHEET_COLS   = 10


def extract_from_sheet(sheet_path: Path, dest: Path) -> None:
    """
    Slice the Jokers.png sprite sheet into individual PNGs saved in dest/.

    The sprite sheet has all jokers packed in a grid of SHEET_COLS columns.
    Each cell is SHEET_CELL_W × SHEET_CELL_H pixels.
    """
    dest.mkdir(parents=True, exist_ok=True)
    log.info("Slicing sprite sheet %s  →  %s", sheet_path, dest)

    sheet = Image.open(sheet_path).convert("RGBA")
    sheet_w, sheet_h = sheet.size
    cols = SHEET_COLS
    rows = sheet_h // SHEET_CELL_H

    cells_available = cols * rows
    if cells_available < len(JOKER_NAMES):
        log.warning(
            "Sheet has %d cells but %d jokers listed — sheet layout may have changed",
            cells_available, len(JOKER_NAMES),
        )

    extracted = 0
    for idx, name in enumerate(JOKER_NAMES):
        if idx >= cells_available:
            log.warning("No cell for joker %d (%s) — skipping", idx, name)
            continue
        row = idx // cols
        col = idx % cols
        x = col * SHEET_CELL_W
        y = row * SHEET_CELL_H
        cell = sheet.crop((x, y, x + SHEET_CELL_W, y + SHEET_CELL_H))

        # Composite transparent PNG onto white background
        bg = Image.new("RGB", cell.size, (255, 255, 255))
        if cell.mode == "RGBA":
            bg.paste(cell, mask=cell.split()[3])
        else:
            bg.paste(cell)

        out = dest / f"{_to_slug(name)}.png"
        bg.save(out)
        extracted += 1

    log.info("Extracted %d sprites from sheet", extracted)


# ── index build ───────────────────────────────────────────────────────────────

def _invert(img: Image.Image) -> Image.Image:
    """Return a Negative-edition copy (inverted art)."""
    arr = np.array(img.convert("RGB"))
    return Image.fromarray(255 - arr)


def build_index(sprites_dir: Path, include_negative: bool = False) -> None:
    pngs = sorted(sprites_dir.glob("*.png"))
    if not pngs:
        log.error("No PNG files found in %s", sprites_dir)
        sys.exit(1)

    names: list[str] = []
    vectors: list[np.ndarray] = []
    missing: list[str] = []

    for path in pngs:
        slug = path.stem
        name = _slug_to_name(slug)
        if name is None:
            log.debug("Skipping %s (no canonical name)", path.name)
            continue
        try:
            img = Image.open(path).convert("RGB")
        except Exception as exc:
            log.warning("Cannot open %s: %s", path, exc)
            continue

        feat = extract_features(img)
        names.append(name)
        vectors.append(feat)

        if include_negative:
            neg_feat = extract_features(_invert(img))
            names.append(f"{name} (Negative)")
            vectors.append(neg_feat)

    # Report any canonical jokers missing from sprites dir
    found = {n.replace(" (Negative)", "") for n in names}
    for canonical in JOKER_NAMES:
        if canonical not in found:
            missing.append(canonical)
    if missing:
        log.warning(
            "%d jokers not found in sprites dir (will fall back to OCR for these): %s",
            len(missing), ", ".join(missing),
        )

    matrix = np.stack(vectors).astype(np.float32)  # (N, 768)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(INDEX_PATH), names=np.array(names), vectors=matrix)
    log.info(
        "Saved joker index: %d entries → %s  (threshold %.2f)",
        len(names), INDEX_PATH, MATCH_THRESHOLD,
    )


# ── self-test ─────────────────────────────────────────────────────────────────

def self_test(sprites_dir: Path) -> None:
    """
    Quick accuracy check: re-identify each sprite against the full index.
    Expected: 100 % top-1 accuracy (each sprite should match itself).
    Reports any jokers that fall below MATCH_THRESHOLD.
    """
    if not INDEX_PATH.exists():
        log.error("Index not built yet – run without --test first")
        return

    from app.cv.joker_classifier import JokerClassifier
    clf = JokerClassifier()

    correct = wrong = below_threshold = 0
    for path in sorted(sprites_dir.glob("*.png")):
        slug = path.stem
        name = _slug_to_name(slug)
        if name is None:
            continue
        img = Image.open(path).convert("RGB")
        pred = clf.identify(img)
        if pred is None:
            log.warning("  THRESHOLD  %-30s → (no match)", name)
            below_threshold += 1
        elif pred == name:
            correct += 1
        else:
            log.warning("  WRONG      %-30s → %s", name, pred)
            wrong += 1

    total = correct + wrong + below_threshold
    log.info(
        "Self-test: %d/%d correct  |  %d wrong  |  %d below threshold (%.0f %%)",
        correct, total, wrong, below_threshold,
        100.0 * correct / total if total else 0,
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build or test joker visual index")
    parser.add_argument("--sprites-dir", default=str(SPRITES_DIR), help="Directory of joker PNGs")
    parser.add_argument("--from-sheet", metavar="JOKERS_PNG",
                        help="Slice Jokers.png sprite sheet extracted from Balatro.exe "
                             "(open Balatro.exe with 7-Zip → Resources/Textures/2x/Jokers.png)")
    parser.add_argument("--negative", action="store_true", help="Include Negative-edition variants")
    parser.add_argument("--download", action="store_true", help="Download sprites from wiki")
    parser.add_argument("--test", action="store_true", help="Run self-test accuracy check")
    args = parser.parse_args()

    sprites_dir = Path(args.sprites_dir)

    if args.from_sheet:
        extract_from_sheet(Path(args.from_sheet), sprites_dir)
    elif args.download or not any(sprites_dir.glob("*.png")):
        log.info("Downloading sprites from Balatro Fandom Wiki…")
        download_sprites(sprites_dir)

    log.info("Building index from %s…", sprites_dir)
    build_index(sprites_dir, include_negative=args.negative)

    if args.test:
        self_test(sprites_dir)


if __name__ == "__main__":
    main()
