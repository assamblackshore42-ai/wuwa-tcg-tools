import numpy as np
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QVideoFrame

from wuwatcg_assistant.camera import video_frame_to_bgr


def test_qt_video_frame_is_converted_to_opencv_bgr() -> None:
    image = QImage(3, 2, QImage.Format.Format_RGBA8888)
    image.fill(QColor(255, 0, 0))

    frame = video_frame_to_bgr(QVideoFrame(image))

    assert frame is not None
    assert frame.shape == (2, 3, 3)
    assert np.array_equal(frame[0, 0], np.asarray([0, 0, 255], dtype=np.uint8))
