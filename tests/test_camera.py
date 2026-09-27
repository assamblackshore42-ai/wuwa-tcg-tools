import numpy as np
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QVideoFrame

from wuwatcg_assistant.camera import select_highest_quality_format, video_frame_to_bgr


class StubResolution:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class StubCameraFormat:
    def __init__(self, width: int, height: int, max_fps: float) -> None:
        self._resolution = StubResolution(width, height)
        self._max_fps = max_fps

    def resolution(self) -> StubResolution:
        return self._resolution

    def maxFrameRate(self) -> float:  # noqa: N802
        return self._max_fps


def test_highest_quality_camera_format_prefers_resolution_then_frame_rate() -> None:
    full_hd_30 = StubCameraFormat(1920, 1080, 30.0)
    full_hd_60 = StubCameraFormat(1920, 1080, 60.0)
    ultra_hd_30 = StubCameraFormat(3840, 2160, 30.0)

    selected = select_highest_quality_format([full_hd_30, ultra_hd_30, full_hd_60])

    assert selected is ultra_hd_30


def test_highest_quality_camera_format_prefers_frame_rate_at_same_resolution() -> None:
    full_hd_30 = StubCameraFormat(1920, 1080, 30.0)
    full_hd_60 = StubCameraFormat(1920, 1080, 60.0)

    selected = select_highest_quality_format([full_hd_30, full_hd_60])

    assert selected is full_hd_60


def test_highest_quality_camera_format_handles_device_without_formats() -> None:
    assert select_highest_quality_format([]) is None


def test_qt_video_frame_is_converted_to_opencv_bgr() -> None:
    image = QImage(3, 2, QImage.Format.Format_RGBA8888)
    image.fill(QColor(255, 0, 0))

    frame = video_frame_to_bgr(QVideoFrame(image))

    assert frame is not None
    assert frame.shape == (2, 3, 3)
    assert np.array_equal(frame[0, 0], np.asarray([0, 0, 255], dtype=np.uint8))
