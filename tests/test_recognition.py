from pathlib import Path

import cv2
import numpy as np

from wuwatcg_assistant.catalog import CardCatalog
from wuwatcg_assistant.recognition import RecognitionEngine, decode_image

ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "cards"


def test_exact_reference_image_is_recognized_at_clicked_position() -> None:
    complete_catalog = CardCatalog.load(ASSET_DIRECTORY)
    expected = complete_catalog.by_code("BP01-050")
    distractor = complete_catalog.by_code("BP01-049")
    engine = RecognitionEngine(CardCatalog(cards=(expected, distractor)))
    engine.build_index()
    frame = decode_image(expected.variants[0].image_path)

    result = engine.recognize(frame, (frame.shape[1] / 2, frame.shape[0] / 2))

    assert result.primary is not None
    assert result.primary.card.code == expected.code
    assert result.primary.contains_click
    assert result.is_confident


def test_click_selects_visible_card_when_two_cards_overlap() -> None:
    complete_catalog = CardCatalog.load(ASSET_DIRECTORY)
    left_card = complete_catalog.by_code("BP01-050")
    right_card = complete_catalog.by_code("BP01-049")
    engine = RecognitionEngine(CardCatalog(cards=(left_card, right_card)))
    engine.build_index()

    left_image = decode_image(left_card.variants[0].image_path)
    right_image = decode_image(right_card.variants[0].image_path)
    height, width = left_image.shape[:2]
    right_image = cv2.resize(right_image, (width, height))
    offset = int(width * 0.55)
    frame = np.zeros((height, width + offset, 3), dtype=np.uint8)
    frame[:, :width] = left_image
    frame[:, offset : offset + width] = right_image

    left_result = engine.recognize(frame, (width * 0.25, height * 0.5))
    right_result = engine.recognize(frame, (width * 1.25, height * 0.5))

    assert left_result.primary is not None
    assert left_result.primary.card.code == left_card.code
    assert right_result.primary is not None
    assert right_result.primary.card.code == right_card.code
