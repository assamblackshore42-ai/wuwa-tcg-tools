from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CardType = Literal["action", "character"]


@dataclass(frozen=True, slots=True)
class CardVariant:
    """One reference artwork for a card."""

    source_id: int
    image_path: Path


@dataclass(frozen=True, slots=True)
class Card:
    """A card and all reference artworks that identify it."""

    code: str
    name: str
    card_type: CardType
    variants: tuple[CardVariant, ...]


@dataclass(frozen=True, slots=True)
class CardCatalog:
    cards: tuple[Card, ...]

    @classmethod
    def load(cls, asset_directory: Path) -> CardCatalog:
        metadata_path = asset_directory / "metadata.json"
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        grouped: dict[str, list[dict[str, object]]] = {}

        for raw_card in data["cards"]:
            grouped.setdefault(str(raw_card["code"]), []).append(raw_card)

        cards: list[Card] = []
        for code, records in sorted(grouped.items()):
            first = records[0]
            card_type = str(first["card_type"])
            if card_type not in {"action", "character"}:
                raise ValueError(f"Unsupported card type for {code}: {card_type}")

            variants = tuple(
                CardVariant(
                    source_id=int(str(record["id"])),
                    image_path=asset_directory / str(record["file_name"]),
                )
                for record in records
            )
            missing = [
                str(variant.image_path) for variant in variants if not variant.image_path.is_file()
            ]
            if missing:
                message = f"Missing reference images for {code}: {', '.join(missing)}"
                raise FileNotFoundError(message)

            cards.append(
                Card(
                    code=code,
                    name=str(first["name"]),
                    card_type=card_type,  # type: ignore[arg-type]
                    variants=variants,
                )
            )

        return cls(cards=tuple(cards))

    def by_code(self, code: str) -> Card:
        return next(card for card in self.cards if card.code == code)
