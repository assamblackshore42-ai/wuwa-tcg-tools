from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import qVersion

from wuwatcg_assistant import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CARD_ASSET_DIR = PROJECT_ROOT / "assets" / "cards"


def test_runtime_dependencies_are_available() -> None:
    assert __version__ == "0.1.0"
    assert qVersion()
    assert cv2.SIFT_create() is not None


def test_card_manifest_matches_local_assets() -> None:
    metadata = json.loads((CARD_ASSET_DIR / "metadata.json").read_text(encoding="utf-8"))
    cards = metadata["cards"]

    assert metadata["total"] == 198
    assert len(cards) == metadata["total"]
    assert len({card["file_name"] for card in cards}) == len(cards)
    assert all((CARD_ASSET_DIR / card["file_name"]).is_file() for card in cards)


def test_opencv_can_decode_unicode_card_path() -> None:
    card_path = CARD_ASSET_DIR / "SD01-001_漂泊者（女）.webp"
    encoded = np.fromfile(card_path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    assert image is not None
    assert image.ndim == 3
    assert image.shape[0] > image.shape[1]
