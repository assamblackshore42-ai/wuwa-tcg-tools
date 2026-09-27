from pathlib import Path

from wuwatcg_assistant.catalog import CardCatalog

ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "cards"


def test_catalog_groups_alternate_artworks_by_card_code() -> None:
    catalog = CardCatalog.load(ASSET_DIRECTORY)

    assert len(catalog.cards) < 198
    assert len(catalog.by_code("BP01-001").variants) == 3
    assert catalog.by_code("SD01-001").name == "漂泊者（女）"
