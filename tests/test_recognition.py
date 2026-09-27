from pathlib import Path

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
