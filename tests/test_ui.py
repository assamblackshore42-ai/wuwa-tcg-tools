from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPixmap, QResizeEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QSizePolicy, QSplitter

from wuwatcg_assistant.catalog import CardCatalog
from wuwatcg_assistant.ui import MainWindow, ScalableImageLabel, VideoWidget


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


def test_card_image_scales_up_with_available_space(qtbot: object) -> None:
    label = ScalableImageLabel()
    label.resize(300, 330)
    source = QPixmap(600, 900)
    source.fill(QColor("red"))
    label.set_source_pixmap(source)
    first_size = label.pixmap().size()

    label.resize(600, 660)
    label.resizeEvent(QResizeEvent(label.size(), first_size))

    assert label.pixmap().width() > first_size.width()
    assert label.pixmap().height() > first_size.height()


def test_result_pane_is_flexible_and_resizable(qtbot: object) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)
    splitter = window.centralWidget()

    assert isinstance(splitter, QSplitter)
    result_pane = splitter.widget(1)
    assert result_pane.maximumWidth() > 10_000
    assert result_pane.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert splitter.isCollapsible(1) is False
