from PySide6.QtCore import QPointF

from wuwatcg_assistant.ui import VideoWidget


def test_video_widget_maps_letterboxed_click_to_source(qtbot: object) -> None:
    import numpy as np

    widget = VideoWidget()
    widget.resize(800, 600)
    widget.set_frame(np.zeros((720, 1280, 3), dtype=np.uint8))

    assert widget.map_to_source(QPointF(400, 300)) == (640.0, 360.0)
    assert widget.map_to_source(QPointF(400, 20)) is None
