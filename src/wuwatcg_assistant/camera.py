from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (
    QCamera,
    QCameraDevice,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrame,
    QVideoSink,
)


@dataclass(frozen=True, slots=True)
class VideoInputDevice:
    device_id: bytes
    name: str
    is_default: bool


class CameraController(QObject):
    frame_ready = Signal(object)
    camera_error = Signal(str)
    camera_opened = Signal(str)
    devices_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._media_devices = QMediaDevices(self)
        self._media_devices.videoInputsChanged.connect(self.devices_changed)
        self._capture_session = QMediaCaptureSession(self)
        self._video_sink = QVideoSink(self)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)
        self._capture_session.setVideoSink(self._video_sink)
        self._camera: QCamera | None = None
        self._active_device_id: bytes | None = None

    @property
    def is_active(self) -> bool:
        return self._camera is not None

    @property
    def active_device_id(self) -> bytes | None:
        return self._active_device_id

    def video_inputs(self) -> tuple[VideoInputDevice, ...]:
        return tuple(
            VideoInputDevice(
                device_id=bytes(device.id().data()),
                name=device.description(),
                is_default=device.isDefault(),
            )
            for device in QMediaDevices.videoInputs()
        )

    def start(self, device_id: bytes) -> None:
        self.stop()
        camera_device = self._find_device(device_id)
        if camera_device is None:
            self.camera_error.emit("選択したカメラがWindows上で見つかりません。")
            return

        camera = QCamera(camera_device, self)
        camera.errorOccurred.connect(self._on_camera_error)
        camera.activeChanged.connect(self._on_active_changed)
        self._camera = camera
        self._active_device_id = bytes(camera_device.id().data())
        self._capture_session.setCamera(camera)
        camera.start()

    def stop(self) -> None:
        if self._camera is None:
            return
        camera = self._camera
        self._camera = None
        self._active_device_id = None
        camera.stop()
        self._capture_session.setCamera(None)  # type: ignore[arg-type]
        camera.deleteLater()

    def _find_device(self, device_id: bytes) -> QCameraDevice | None:
        return next(
            (
                device
                for device in QMediaDevices.videoInputs()
                if bytes(device.id().data()) == device_id
            ),
            None,
        )

    @Slot(QVideoFrame)
    def _on_video_frame(self, frame: QVideoFrame) -> None:
        image = video_frame_to_bgr(frame)
        if image is not None:
            self.frame_ready.emit(image)

    @Slot(QCamera.Error, str)
    def _on_camera_error(self, error: QCamera.Error, message: str) -> None:
        if error != QCamera.Error.NoError:
            self.camera_error.emit(message or "カメラの開始に失敗しました。")

    @Slot(bool)
    def _on_active_changed(self, active: bool) -> None:
        if not active or self._camera is None:
            return
        device = self._camera.cameraDevice()
        self.camera_opened.emit(f"{device.description()} を使用中")


def video_frame_to_bgr(frame: QVideoFrame) -> NDArray[Any] | None:
    """Copy a Qt video frame into an OpenCV BGR image."""

    if not frame.isValid():
        return None
    image = frame.toImage()
    if image.isNull():
        return None
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    height = rgba.height()
    width = rgba.width()
    bytes_per_line = rgba.bytesPerLine()
    buffer = np.frombuffer(rgba.bits(), dtype=np.uint8, count=rgba.sizeInBytes())
    rows = buffer.reshape(height, bytes_per_line)
    pixels = rows[:, : width * 4].reshape(height, width, 4)
    return cv2.cvtColor(pixels, cv2.COLOR_RGBA2BGR).copy()
