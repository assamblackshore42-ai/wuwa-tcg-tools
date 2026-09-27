from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QSignalSpy, QTest

from wuwatcg_assistant.ui import VideoWidget


def test_video_widget_maps_letterboxed_click_to_source(qtbot: object) -> None:
    import numpy as np

    widget = VideoWidget()
    widget.resize(800, 600)
    widget.set_frame(np.zeros((720, 1280, 3), dtype=np.uint8))

    assert widget.map_to_source(QPointF(400, 300)) == (640.0, 360.0)
    assert widget.map_to_source(QPointF(400, 20)) is None


def test_video_widget_maps_drag_rectangle_to_source(qtbot: object) -> None:
    import numpy as np

    widget = VideoWidget()
    widget.resize(800, 600)
    widget.set_frame(np.zeros((720, 1280, 3), dtype=np.uint8))

    region = widget.rectangle_to_source(QPointF(600, 500), QPointF(200, 200))

    assert region == ((320.0, 200.0), (960.0, 200.0), (960.0, 680.0), (320.0, 680.0))


def test_video_widget_emits_region_after_drag(qtbot: object) -> None:
    import numpy as np

    widget = VideoWidget()
    widget.resize(800, 600)
    widget.set_frame(np.zeros((720, 1280, 3), dtype=np.uint8))
    widget.show()
    spy = QSignalSpy(widget.source_region_selected)

    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(200, 200))
    QTest.mouseMove(widget, QPoint(600, 500))
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(600, 500))

    assert spy.count() == 1
    assert spy.at(0)[0] == (
        (320.0, 200.0),
        (960.0, 200.0),
        (960.0, 680.0),
        (320.0, 680.0),
    )
