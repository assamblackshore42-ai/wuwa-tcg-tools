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
Polygon = tuple[Point, Point, Point, Point]


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
    minimum_reference_span: float = 0.08
    minimum_frame_area_ratio: float = 0.001
    maximum_frame_area_ratio: float = 1.20
    maximum_corner_margin_ratio: float = 0.25
    maximum_side_ratio: float = 10.0
    maximum_opposite_side_ratio: float = 4.0


@dataclass(frozen=True, slots=True)
class RecognitionCandidate:
    card: Card
    reference_path: Path
    score: float
    good_matches: int
    inliers: int
    inlier_ratio: float
    contains_click: bool
    polygon: Polygon

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

    def recognize(
        self,
        frame: Image,
        click: Point,
        limit: int = 3,
        region: Polygon | None = None,
    ) -> RecognitionResult:
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
        if region is not None:
            region_contour = np.asarray(region, dtype=np.float32)
            selected = [
                index
                for index, keypoint in enumerate(frame_keypoints)
                if cv2.pointPolygonTest(region_contour, keypoint.pt, False) >= 0
            ]
            if len(selected) < self.config.minimum_good_matches:
                return RecognitionResult((), _elapsed_ms(started), False)
            frame_keypoints = [frame_keypoints[index] for index in selected]
            frame_descriptors = frame_descriptors[selected]

        best_by_card: dict[str, RecognitionCandidate] = {}
        for reference in self._index:
            candidate = self._match_reference(
                reference,
                frame_keypoints,
                frame_descriptors,
                click,
                frame_size=(gray.shape[1], gray.shape[0]),
            )
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
        frame_size: tuple[int, int],
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
        width, height = reference.image_size
        corners = np.asarray(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        projection = self._stable_projection(
            homography,
            mask,
            corners,
            source_points,
            frame_points,
            reference.image_size,
            frame_size,
        )
        if projection is None:
            return None

        projected, mask = projection
        inliers = int(mask.ravel().sum())

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

    def _stable_projection(
        self,
        homography: NDArray[Any] | None,
        homography_mask: NDArray[Any] | None,
        corners: NDArray[Any],
        source_points: NDArray[Any],
        frame_points: NDArray[Any],
        reference_size: tuple[int, int],
        frame_size: tuple[int, int],
    ) -> tuple[NDArray[Any], NDArray[Any]] | None:
        if homography is not None and homography_mask is not None:
            projected = cv2.perspectiveTransform(corners, homography).reshape(4, 2)
            if self._projection_is_supported(
                projected,
                homography_mask,
                source_points,
                reference_size,
                frame_size,
            ):
                return projected, homography_mask

        affine, affine_mask = cv2.estimateAffinePartial2D(
            source_points,
            frame_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=self.config.reprojection_threshold,
        )
        if affine is None or affine_mask is None:
            return None
        projected = cv2.transform(corners, affine).reshape(4, 2)
        if not self._projection_is_supported(
            projected,
            affine_mask,
            source_points,
            reference_size,
            frame_size,
        ):
            return None
        return projected, affine_mask

    def _projection_is_supported(
        self,
        polygon: NDArray[Any],
        mask: NDArray[Any],
        source_points: NDArray[Any],
        reference_size: tuple[int, int],
        frame_size: tuple[int, int],
    ) -> bool:
        inlier_mask = mask.ravel().astype(bool)
        if int(inlier_mask.sum()) < self.config.minimum_inliers:
            return False
        inlier_sources = source_points.reshape(-1, 2)[inlier_mask]
        reference_width, reference_height = reference_size
        span = np.ptp(inlier_sources, axis=0)
        if (
            span[0] / reference_width < self.config.minimum_reference_span
            or span[1] / reference_height < self.config.minimum_reference_span
        ):
            return False
        return is_plausible_card_polygon(polygon, frame_size, self.config)

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


def is_plausible_card_polygon(
    polygon: NDArray[Any],
    frame_size: tuple[int, int],
    config: RecognitionConfig | None = None,
) -> bool:
    """Reject degenerate projections before they are used as a card outline."""

    options = config or RecognitionConfig()
    points = np.asarray(polygon, dtype=np.float32).reshape(4, 2)
    if not np.isfinite(points).all() or not cv2.isContourConvex(points):
        return False

    frame_width, frame_height = frame_size
    frame_area = frame_width * frame_height
    area_ratio = abs(cv2.contourArea(points)) / frame_area
    if not options.minimum_frame_area_ratio <= area_ratio <= options.maximum_frame_area_ratio:
        return False

    margin_x = frame_width * options.maximum_corner_margin_ratio
    margin_y = frame_height * options.maximum_corner_margin_ratio
    if (
        points[:, 0].min() < -margin_x
        or points[:, 0].max() > frame_width + margin_x
        or points[:, 1].min() < -margin_y
        or points[:, 1].max() > frame_height + margin_y
    ):
        return False

    sides = np.linalg.norm(points - np.roll(points, -1, axis=0), axis=1)
    shortest_side = float(sides.min())
    if shortest_side < 10 or float(sides.max()) / shortest_side > options.maximum_side_ratio:
        return False

    for first, opposite in ((0, 2), (1, 3)):
        ratio = max(float(sides[first]), float(sides[opposite])) / min(
            float(sides[first]), float(sides[opposite])
        )
        if ratio > options.maximum_opposite_side_ratio:
            return False
    return True


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
