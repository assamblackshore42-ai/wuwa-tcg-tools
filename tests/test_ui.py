from pathlib import Path
from unittest.mock import Mock

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPixmap, QResizeEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QSizePolicy, QSplitter

from wuwatcg_assistant.catalog import Card, CardCatalog
from wuwatcg_assistant.recognition import RecognitionCandidate
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


def test_completed_recognition_hides_input_selection_but_keeps_result_outline(
    qtbot: object,
) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)
    polygon = ((10.0, 20.0), (110.0, 20.0), (110.0, 170.0), (10.0, 170.0))
    candidate = RecognitionCandidate(
        card=Card(code="TEST-001", name="テスト", card_type="character", variants=()),
        reference_path=Path("missing-test-image.png"),
        score=1.0,
        good_matches=12,
        inliers=10,
        inlier_ratio=0.8,
        contains_click=True,
        polygon=polygon,
    )
    window._candidates = (candidate,)
    selection_spy = Mock()
    window._video.set_selection = selection_spy

    window._show_candidate(0)

    selection_spy.assert_called_once_with(None, polygon)


def test_failed_recognition_hides_input_selection(qtbot: object) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)
    selection_spy = Mock()
    window._video.set_selection = selection_spy

    window._on_recognition_failed(window._request_id, "failure")

    selection_spy.assert_called_once_with(None)
