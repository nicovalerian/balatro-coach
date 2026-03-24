"""
Download the two proj-airi YOLO ONNX models from HuggingFace.

Usage:
    python scripts/download_models.py

Models:
  - proj-airi/games-balatro-2024-yolo-entities-detection
  - proj-airi/games-balatro-2024-yolo-ui-detection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import EntryNotFoundError

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

DOWNLOADS = [
    {
        "repo_id": "proj-airi/games-balatro-2024-yolo-entities-detection",
        "filenames": ["onnx/model.onnx", "model.onnx"],
        "local_name": "entities.onnx",
    },
    {
        "repo_id": "proj-airi/games-balatro-2024-yolo-ui-detection",
        "filenames": ["onnx/model.onnx", "model.onnx"],
        "local_name": "ui.onnx",
    },
]


def main():
    for spec in DOWNLOADS:
        dest = MODELS_DIR / spec["local_name"]
        if dest.exists():
            print(f"✓ {spec['local_name']} already present")
            continue
        print(f"Downloading {spec['repo_id']} …")
        path = None
        for filename in spec["filenames"]:
            try:
                path = hf_hub_download(
                    repo_id=spec["repo_id"],
                    filename=filename,
                )
                break
            except EntryNotFoundError:
                print(f"  ! missing file in repo: {filename}")
        if path is None:
            tried = ", ".join(spec["filenames"])
            raise RuntimeError(
                f"Failed to download ONNX for {spec['repo_id']}. Tried: {tried}"
            )
        import shutil
        shutil.copy(path, dest)
        print(f"  → saved to {dest}")
    print("\nAll models ready.")


if __name__ == "__main__":
    main()
