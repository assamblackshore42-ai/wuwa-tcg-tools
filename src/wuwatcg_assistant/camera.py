from __future__ import annotations

import sys

import cv2
from PySide6.QtCore import QThread, Signal


class CameraWorker(QThread):
    frame_ready = Signal(object)
    camera_error = Signal(str)
    camera_opened = Signal(str)

    def __init__(self, camera_index: int, width: int, height: int) -> None:
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height

    def run(self) -> None:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.camera_index, backend)
        if not capture.isOpened():
            self.camera_error.emit(
                f"カメラ {self.camera_index} を開けません。DroidCamの起動状態を確認してください。"
            )
            capture.release()
            return

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.camera_opened.emit(f"カメラ {self.camera_index}: {actual_width} × {actual_height}")

        consecutive_failures = 0
        try:
            while not self.isInterruptionRequested():
                success, frame = capture.read()
                if not success or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 30:
                        self.camera_error.emit("カメラ映像を取得できなくなりました。")
                        return
                    self.msleep(30)
                    continue

                consecutive_failures = 0
                self.frame_ready.emit(frame)
        finally:
            capture.release()

    def stop(self) -> None:
        self.requestInterruption()
        self.wait(2_000)
