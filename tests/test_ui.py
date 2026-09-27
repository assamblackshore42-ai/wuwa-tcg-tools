from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPixmap, QResizeEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QSizePolicy, QSplitter

from wuwatcg_assistant.catalog import Card, CardCatalog
from wuwatcg_assistant.i18n import Language, tr
from wuwatcg_assistant.recognition import RecognitionCandidate, RecognitionResult
from wuwatcg_assistant.ui import (
    DEFAULT_UI_BASE_FONT_PT,
    UI_FONT_SCALE,
    BattleStatusCard,
    LifeCounter,
    MainWindow,
    ScalableImageLabel,
    TurnStatePanel,
    UiFontRole,
    VideoWidget,
)


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


def test_video_widget_recognition_outline_color_can_be_changed(qtbot: object) -> None:
    widget = VideoWidget()

    assert widget.recognition_outline_color == QColor("#5ce1e6")

    widget.set_recognition_outline_color(QColor("#ff4d8d"))
    assert widget.recognition_outline_color == QColor("#ff4d8d")


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


def test_settings_menu_changes_recognition_outline_color(qtbot: object) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)

    assert window._settings_button.text() == ""
    assert not window._settings_button.icon().isNull()
    assert window._settings_button.menu() is window._settings_menu
    assert window._settings_menu.actions()[0] is window._outline_color_action
    assert window._settings_menu.actions()[1] is window._language_menu.menuAction()
    assert "menu-indicator" in window._settings_button.styleSheet()
    assert "image: none" in window._settings_button.styleSheet()

    with patch(
        "wuwatcg_assistant.ui.QColorDialog.getColor",
        return_value=QColor("#ff4d8d"),
    ):
        window._outline_color_action.trigger()

    assert window._video.recognition_outline_color == QColor("#ff4d8d")


def test_language_menu_translates_interface_and_uses_official_rule_terms(qtbot: object) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)

    window._language_actions[Language.EN].trigger()
    assert window.windowTitle() == "Wuthering Waves: Versus Card Assistant"
    assert window._life_counter._title.text() == "Your Life"
    assert [label.text() for label in window._turn_state._action_labels] == [
        "Level Up",
        "Switch",
        "Charge",
    ]
    assert window._battle_status._advantage_label.text() == "Advantage"

    window._language_actions[Language.ZH_CN].trigger()
    assert window._life_counter._title.text() == "己方生命值"
    assert [label.text() for label in window._turn_state._action_labels] == [
        "升级",
        "切换",
        "充能",
    ]
    assert window._battle_status._advantage_label.text() == "优势"

    assert tr(Language.JA, "switch") == "切り替え"
    assert tr(Language.JA, "charge") == "チャージ"


def test_life_counter_starts_at_20_and_can_be_adjusted(qtbot: object) -> None:
    counter = LifeCounter()

    assert counter.life == 20

    counter._decrease_button.click()
    assert counter.life == 19

    counter._increase_button.click()
    assert counter.life == 20

    counter.adjust(-5)
    counter._reset_button.click()
    assert counter.life == 20
    assert counter._decrease_button.text() == ""
    assert counter._increase_button.text() == ""
    assert counter._close_button.text() == ""
    assert not counter._decrease_button.icon().isNull()
    assert not counter._increase_button.icon().isNull()
    assert counter._reset_button.text() == "リセット"


def test_life_counter_is_visible_by_default_and_can_be_hidden(qtbot: object) -> None:
    counter = LifeCounter()

    assert counter.counter_visible is True

    counter._close_button.click()
    assert counter.counter_visible is False
    assert counter._show_button.isHidden() is False

    counter._show_button.click()
    assert counter.counter_visible is True


def test_typography_roles_scale_from_one_base_size(qtbot: object) -> None:
    counter = LifeCounter()
    panel = TurnStatePanel()
    battle_status = BattleStatusCard()

    counter.set_base_font_size(10.0)
    panel.set_base_font_size(10.0)
    battle_status.set_base_font_size(10.0)

    assert counter._title.font().pointSizeF() == pytest.approx(12.0, abs=0.01)
    assert counter._reset_button.font().pointSizeF() == pytest.approx(10.0, abs=0.01)
    assert counter._value.font().pointSizeF() == pytest.approx(38.0, abs=0.01)
    assert panel._title.font().pointSizeF() == pytest.approx(12.0, abs=0.01)
    assert all(
        label.font().pointSizeF() == pytest.approx(9.5, abs=0.01) for label in panel._action_labels
    )
    assert battle_status._advantage_label.font().pointSizeF() == pytest.approx(11.0, abs=0.01)
    assert UI_FONT_SCALE[UiFontRole.SECTION_TITLE][0] == 1.2


def test_player_state_row_places_battle_status_to_right_of_life(qtbot: object) -> None:
    window = MainWindow(CardCatalog(cards=()), build_index=False)
    row_layout = window._player_state_row.layout()

    assert row_layout.itemAt(0).widget() is window._life_counter
    assert row_layout.itemAt(1).widget() is window._battle_status
    assert window._life_counter._title.font().pointSizeF() == pytest.approx(13.5, abs=0.01)
    assert DEFAULT_UI_BASE_FONT_PT == 11.25


def test_battle_status_contents_are_centered_in_card(qtbot: object) -> None:
    battle_status = BattleStatusCard()
    layout = battle_status._card.layout()

    assert layout.itemAt(0).spacerItem() is not None
    assert layout.itemAt(layout.count() - 1).spacerItem() is not None
    for index in (1, 2, 3):
        assert layout.itemAt(index).alignment() & Qt.AlignmentFlag.AlignCenter


def test_turn_actions_toggle_and_reset_without_button_text(qtbot: object) -> None:
    panel = TurnStatePanel()

    assert panel.used_actions == frozenset()
    assert all(button.text() == "" for button in panel._action_buttons.values())
    assert panel._reset_button.text() == ""
    assert all(not button.icon().isNull() for button in panel._action_buttons.values())

    panel._action_buttons["level_up"].click()
    panel._action_buttons["charge"].click()
    assert panel.used_actions == frozenset({"level_up", "charge"})

    panel._reset_button.click()
    assert panel.used_actions == frozenset()


def test_advantage_toggle_is_colored_and_not_reset_with_turn_actions(qtbot: object) -> None:
    panel = TurnStatePanel()
    battle_status = BattleStatusCard()

    assert battle_status.is_disadvantaged is False
    assert battle_status._advantage_label.text() == "優勢"
    assert battle_status._advantage_button.text() == ""

    battle_status._advantage_button.click()
    assert battle_status.is_disadvantaged is True
    assert battle_status._advantage_label.text() == "劣勢"

    panel._action_buttons["switch"].click()
    panel._reset_button.click()
    assert panel.used_actions == frozenset()
    assert battle_status.is_disadvantaged is True


def test_recognition_candidates_use_compact_selector_without_confidence(qtbot: object) -> None:
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
    result = RecognitionResult(candidates=(candidate,), elapsed_ms=10.0, is_confident=False)

    window._on_recognition_completed(window._request_id, result)

    assert window._candidate_selector.count() == 1
    assert window._candidate_selector.isEnabled()
    assert window._candidate_selector.itemText(0) == "TEST-001  テスト"
    assert "%" not in window._candidate_selector.itemText(0)


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
