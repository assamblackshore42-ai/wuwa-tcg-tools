from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .catalog import Card, CardCatalog

Image = NDArray[Any]
Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class RecognitionConfig:
    max_reference_edge: int = 900
    reference_features: int = 900
    frame_features: int = 1_600
    ratio_threshold: float = 0.72
    reprojection_threshold: float = 5.0
    minimum_good_matches: int = 8
    minimum_inliers: int = 6
    confident_inliers: int = 10
    confident_inlier_ratio: float = 0.45
    confident_score_margin: float = 1.15


@dataclass(frozen=True, slots=True)
class RecognitionCandidate:
    card: Card
    reference_path: Path
    score: float
    good_matches: int
    inliers: int
    inlier_ratio: float
    contains_click: bool
    polygon: tuple[Point, Point, Point, Point]

    @property
    def confidence(self) -> float:
        evidence = min(1.0, self.inliers / 20.0)
        return min(1.0, evidence * self.inlier_ratio * 1.6)


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    candidates: tuple[RecognitionCandidate, ...]
    elapsed_ms: float
    is_confident: bool

    @property
    def primary(self) -> RecognitionCandidate | None:
        return self.candidates[0] if self.candidates else None


@dataclass(slots=True)
class _IndexedVariant:
    card: Card
    image_path: Path
    image_size: tuple[int, int]
    keypoints: Any
    descriptors: NDArray[Any]


class RecognitionEngine:
    """Matches visible local features without requiring a complete card outline."""

    def __init__(
        self,
        catalog: CardCatalog,
        config: RecognitionConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.config = config or RecognitionConfig()
        self._sift = cv2.SIFT_create(  # type: ignore[attr-defined]
            nfeatures=self.config.reference_features
        )
        self._matcher = cv2.BFMatcher(cv2.NORM_L2)
        self._index: list[_IndexedVariant] = []

    @property
    def indexed_variant_count(self) -> int:
        return len(self._index)

    def build_index(self, progress: Callable[[int, int], None] | None = None) -> None:
        variants = [(card, variant) for card in self.catalog.cards for variant in card.variants]
        index: list[_IndexedVariant] = []

        for position, (card, variant) in enumerate(variants, start=1):
            image = decode_image(variant.image_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = _resize_to_max_edge(gray, self.config.max_reference_edge)
            keypoints, descriptors = self._sift.detectAndCompute(gray, None)
            if descriptors is not None and len(keypoints) >= self.config.minimum_good_matches:
                index.append(
                    _IndexedVariant(
                        card=card,
                        image_path=variant.image_path,
                        image_size=(gray.shape[1], gray.shape[0]),
                        keypoints=keypoints,
                        descriptors=descriptors,
                    )
                )
            if progress is not None:
                progress(position, len(variants))

        self._index = index

    def recognize(self, frame: Image, click: Point, limit: int = 3) -> RecognitionResult:
        started = time.perf_counter()
        if not self._index:
            raise RuntimeError("Recognition index has not been built")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_sift = cv2.SIFT_create(  # type: ignore[attr-defined]
            nfeatures=self.config.frame_features
        )
        frame_keypoints, frame_descriptors = frame_sift.detectAndCompute(gray, None)
        if frame_descriptors is None or len(frame_keypoints) < self.config.minimum_good_matches:
            return RecognitionResult((), _elapsed_ms(started), False)

        best_by_card: dict[str, RecognitionCandidate] = {}
        for reference in self._index:
            candidate = self._match_reference(reference, frame_keypoints, frame_descriptors, click)
            if candidate is None:
                continue
            current = best_by_card.get(candidate.card.code)
            if current is None or _candidate_key(candidate) > _candidate_key(current):
                best_by_card[candidate.card.code] = candidate

        candidates = sorted(best_by_card.values(), key=_candidate_key, reverse=True)
        clicked = [candidate for candidate in candidates if candidate.contains_click]
        ranked = clicked if clicked else candidates
        top = tuple(ranked[:limit])
        return RecognitionResult(top, _elapsed_ms(started), self._is_confident(top))

    def _match_reference(
        self,
        reference: _IndexedVariant,
        frame_keypoints: Any,
        frame_descriptors: NDArray[Any],
        click: Point,
    ) -> RecognitionCandidate | None:
        pairs = self._matcher.knnMatch(reference.descriptors, frame_descriptors, k=2)
        good = [
            first
            for pair in pairs
            if len(pair) == 2
            for first, second in [pair]
            if first.distance < self.config.ratio_threshold * second.distance
        ]
        if len(good) < self.config.minimum_good_matches:
            return None

        source_points = np.asarray(
            [reference.keypoints[match.queryIdx].pt for match in good], dtype=np.float32
        ).reshape(-1, 1, 2)
        frame_points = np.asarray(
            [frame_keypoints[match.trainIdx].pt for match in good], dtype=np.float32
        ).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(
            source_points,
            frame_points,
            cv2.RANSAC,
            self.config.reprojection_threshold,
        )
        if homography is None or mask is None:
            return None

        inliers = int(mask.ravel().sum())
        if inliers < self.config.minimum_inliers:
            return None

        width, height = reference.image_size
        corners = np.asarray(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        projected = cv2.perspectiveTransform(corners, homography).reshape(4, 2)
        if not np.isfinite(projected).all() or abs(cv2.contourArea(projected)) < 400:
            return None

        contains_click = cv2.pointPolygonTest(projected, click, False) >= 0
        inlier_ratio = inliers / len(good)
        score = inliers + inlier_ratio * 10 + (50 if contains_click else 0)
        polygon = tuple((float(point[0]), float(point[1])) for point in projected)

        return RecognitionCandidate(
            card=reference.card,
            reference_path=reference.image_path,
            score=score,
            good_matches=len(good),
            inliers=inliers,
            inlier_ratio=inlier_ratio,
            contains_click=contains_click,
            polygon=polygon,  # type: ignore[arg-type]
        )

    def _is_confident(self, candidates: tuple[RecognitionCandidate, ...]) -> bool:
        if not candidates:
            return False
        first = candidates[0]
        if (
            not first.contains_click
            or first.inliers < self.config.confident_inliers
            or first.inlier_ratio < self.config.confident_inlier_ratio
        ):
            return False
        if len(candidates) == 1:
            return True
        return first.score >= candidates[1].score * self.config.confident_score_margin


def decode_image(path: Path) -> Image:
    """Decode an image while supporting non-ASCII Windows paths."""

    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to decode image: {path}")
    return image


def _resize_to_max_edge(image: Image, max_edge: int) -> Image:
    height, width = image.shape[:2]
    scale = min(1.0, max_edge / max(height, width))
    if scale == 1.0:
        return image
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def _candidate_key(candidate: RecognitionCandidate) -> tuple[bool, float, int]:
    return candidate.contains_click, candidate.score, candidate.inliers


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1_000
