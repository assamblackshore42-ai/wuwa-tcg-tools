from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, override

import cv2
from PySide6.QtCore import (
    QByteArray,
    QObject,
    QPointF,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThread,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraController
from .catalog import CardCatalog
from .i18n import Language, tr
from .recognition import (
    Image,
    Point,
    Polygon,
    RecognitionCandidate,
    RecognitionEngine,
    RecognitionResult,
)


class VideoWidget(QWidget):
    source_clicked = Signal(float, float)
    source_region_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._pixmap: QPixmap | None = None
        self._source_size: tuple[int, int] | None = None
        self._polygon: tuple[Point, Point, Point, Point] | None = None
        self._analysis_region: Polygon | None = None
        self._click: Point | None = None
        self._drag_origin: QPointF | None = None
        self._drag_position: QPointF | None = None
        self._recognition_outline_color = QColor("#5ce1e6")
        self._language = Language.JA

    def set_frame(self, frame: Image) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(image.copy())
        self._source_size = width, height
        self.update()

    def set_selection(
        self,
        click: Point | None,
        polygon: Polygon | None = None,
        analysis_region: Polygon | None = None,
    ) -> None:
        self._click = click
        self._polygon = polygon
        self._analysis_region = analysis_region
        self.update()

    @property
    def recognition_outline_color(self) -> QColor:
        return QColor(self._recognition_outline_color)

    def set_recognition_outline_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._recognition_outline_color = QColor(color)
        self.update()

    def set_language(self, language: Language) -> None:
        self._language = language
        self.update()

    def map_to_source(self, position: QPointF) -> Point | None:
        if self._source_size is None:
            return None
        target = self._target_rect()
        if not target.contains(position):
            return None
        source_width, source_height = self._source_size
        x = (position.x() - target.x()) * source_width / target.width()
        y = (position.y() - target.y()) * source_height / target.height()
        return x, y

    def rectangle_to_source(self, start: QPointF, end: QPointF) -> Polygon | None:
        first = self.map_to_source(start)
        second = self.map_to_source(end)
        if first is None or second is None:
            return None
        left, right = sorted((first[0], second[0]))
        top, bottom = sorted((first[1], second[1]))
        return (left, top), (right, top), (right, bottom), (left, bottom)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.map_to_source(event.position()) is not None
        ):
            self._drag_origin = event.position()
            self._drag_position = event.position()
            self.update()
        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None:
            self._drag_position = self._clamp_to_video(event.position())
            self.update()
        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            end = self._clamp_to_video(event.position())
            distance = math.hypot(end.x() - self._drag_origin.x(), end.y() - self._drag_origin.y())
            if distance < 8:
                point = self.map_to_source(self._drag_origin)
                if point is not None:
                    self.source_clicked.emit(*point)
            else:
                region = self.rectangle_to_source(self._drag_origin, end)
                if region is not None:
                    self.source_region_selected.emit(region)
            self._drag_origin = None
            self._drag_position = None
            self.update()
        super().mouseReleaseEvent(event)

    @override
    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#11151c"))
        if self._pixmap is None:
            painter.setPen(QColor("#aeb8c5"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr(self._language, "camera_prompt"),
            )
            return

        target = self._target_rect()
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        if self._analysis_region is not None:
            self._draw_source_polygon(
                painter,
                target,
                self._analysis_region,
                QPen(QColor("#ffd166"), 2, Qt.PenStyle.DashLine),
            )
        if self._polygon is not None:
            self._draw_source_polygon(
                painter,
                target,
                self._polygon,
                QPen(self._recognition_outline_color, 3),
            )
        if self._click is not None:
            point = self._source_to_widget(self._click, target)
            painter.setPen(QPen(QColor("white"), 2))
            painter.setBrush(QBrush(QColor("#ff5263")))
            painter.drawEllipse(point, 6, 6)
        if self._drag_origin is not None and self._drag_position is not None:
            painter.setPen(QPen(QColor("#ffd166"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(255, 209, 102, 35)))
            painter.drawRect(QRectF(self._drag_origin, self._drag_position).normalized())

    def _target_rect(self) -> QRectF:
        if self._source_size is None:
            return QRectF()
        source_width, source_height = self._source_size
        scale = min(self.width() / source_width, self.height() / source_height)
        width = source_width * scale
        height = source_height * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def _source_to_widget(self, point: Point, target: QRectF) -> QPointF:
        source_width, source_height = self._source_size or (1, 1)
        return QPointF(
            target.x() + point[0] * target.width() / source_width,
            target.y() + point[1] * target.height() / source_height,
        )

    def _clamp_to_video(self, position: QPointF) -> QPointF:
        target = self._target_rect()
        return QPointF(
            min(max(position.x(), target.left()), target.right()),
            min(max(position.y(), target.top()), target.bottom()),
        )

    def _draw_source_polygon(
        self,
        painter: QPainter,
        target: QRectF,
        polygon: Polygon,
        pen: QPen,
    ) -> None:
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        points = [self._source_to_widget(point, target) for point in polygon]
        for start, end in zip(points, points[1:] + points[:1], strict=True):
            painter.drawLine(start, end)


class ScalableImageLabel(QLabel):
    """Display a source pixmap at the largest size that fits the label."""

    def __init__(self, placeholder: str = "") -> None:
        super().__init__(placeholder)
        self._source_pixmap = QPixmap()

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self.setText("")
        self._rescale_pixmap()

    def clear_image(self, placeholder: str = "") -> None:
        self._source_pixmap = QPixmap()
        self.clear()
        self.setText(placeholder)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _rescale_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        target_size = self.contentsRect().size()
        if target_size.isEmpty():
            return
        self.setPixmap(
            self._source_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class UiFontRole(StrEnum):
    """Semantic roles for text outside the recognition interface."""

    BODY = "body"
    LABEL = "label"
    EMPHASIS = "emphasis"
    SECTION_TITLE = "section_title"


DEFAULT_UI_BASE_FONT_PT = 11.25
UI_FONT_SCALE = {
    UiFontRole.BODY: (1.0, QFont.Weight.Normal),
    UiFontRole.LABEL: (0.95, QFont.Weight.Medium),
    UiFontRole.EMPHASIS: (1.1, QFont.Weight.Bold),
    UiFontRole.SECTION_TITLE: (1.2, QFont.Weight.Bold),
}


def _apply_ui_font(widget: QWidget, base_size: float, role: UiFontRole) -> None:
    """Apply the centralized UI type scale while retaining the OS font family."""
    multiplier, weight = UI_FONT_SCALE[role]
    font = QFont(widget.font())
    font.setPointSizeF(base_size * multiplier)
    font.setWeight(weight)
    widget.setFont(font)


class LifeCounter(QWidget):
    """A compact counter for the local player's life."""

    INITIAL_LIFE = 20

    def __init__(self) -> None:
        super().__init__()
        self._language = Language.JA

        self._card = QFrame()
        self._card.setObjectName("lifeCounterCard")
        self._card.setStyleSheet(
            "QFrame#lifeCounterCard {"
            " background-color: palette(base);"
            " border: 1px solid palette(mid);"
            " border-radius: 10px;"
            "}"
        )
        card_layout = QVBoxLayout(self._card)

        header = QHBoxLayout()

        self._title = QLabel()
        header.addWidget(self._title)
        header.addStretch()

        self._close_button = QPushButton()
        self._close_button.setIcon(_lucide_icon("x", QColor("#657687")))
        self._close_button.setIconSize(QSize(18, 18))
        self._close_button.setFixedSize(28, 28)
        self._close_button.setFlat(True)
        self._close_button.clicked.connect(lambda: self._set_counter_visible(False))
        header.addWidget(self._close_button)

        self._value = QSpinBox()
        self._value.setRange(0, 999)
        self._value.setValue(self.INITIAL_LIFE)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._value.setFont(QFont(self.font().family(), 38, QFont.Weight.Bold))

        self._decrease_button = QPushButton()
        self._decrease_button.setIcon(_lucide_icon("chevron-left", QColor("#657687")))
        self._decrease_button.setIconSize(QSize(30, 30))
        self._decrease_button.setFixedSize(52, 52)
        self._decrease_button.clicked.connect(lambda: self.adjust(-1))

        self._increase_button = QPushButton()
        self._increase_button.setIcon(_lucide_icon("chevron-right", QColor("#657687")))
        self._increase_button.setIconSize(QSize(30, 30))
        self._increase_button.setFixedSize(52, 52)
        self._increase_button.clicked.connect(lambda: self.adjust(1))

        counter_row = QHBoxLayout()
        counter_row.addStretch()
        counter_row.addWidget(self._decrease_button)
        counter_row.addWidget(self._value, 1)
        counter_row.addWidget(self._increase_button)
        counter_row.addStretch()

        self._reset_button = QPushButton()
        self._reset_button.clicked.connect(self.reset)

        card_layout.addLayout(header)
        card_layout.addLayout(counter_row)
        card_layout.addWidget(self._reset_button)

        self._show_button = QPushButton()
        self._show_button.clicked.connect(lambda: self._set_counter_visible(True))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card)
        layout.addWidget(self._show_button)
        self._set_counter_visible(True)
        self.set_language(Language.JA)
        self.set_base_font_size(DEFAULT_UI_BASE_FONT_PT)

    @property
    def life(self) -> int:
        return self._value.value()

    @property
    def counter_visible(self) -> bool:
        return not self._card.isHidden()

    def adjust(self, amount: int) -> None:
        self._value.setValue(self._value.value() + amount)

    def reset(self) -> None:
        self._value.setValue(self.INITIAL_LIFE)

    def set_base_font_size(self, base_size: float) -> None:
        _apply_ui_font(self._title, base_size, UiFontRole.SECTION_TITLE)
        _apply_ui_font(self._reset_button, base_size, UiFontRole.BODY)
        _apply_ui_font(self._show_button, base_size, UiFontRole.BODY)

    def set_language(self, language: Language) -> None:
        self._language = language
        self._title.setText(tr(language, "life_title"))
        self._close_button.setToolTip(tr(language, "hide_life"))
        self._close_button.setAccessibleName(tr(language, "hide_life"))
        self._value.setAccessibleName(tr(language, "life_title"))
        self._decrease_button.setToolTip(tr(language, "decrease_life"))
        self._increase_button.setToolTip(tr(language, "increase_life"))
        self._reset_button.setText(tr(language, "reset"))
        self._show_button.setText(tr(language, "show_life"))

    def _set_counter_visible(self, visible: bool) -> None:
        self._card.setVisible(visible)
        self._show_button.setVisible(not visible)


_LUCIDE_ELEMENTS = {
    "arrow-left-right": (
        '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>'
    ),
    "check": '<path d="m20 6-11 11-5-5"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "music": (
        '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'
    ),
    "refresh-ccw": (
        '<path d="M21 12a9 9 0 0 0-15-6.7L3 8"/><path d="M3 3v5h5"/>'
        '<path d="M3 12a9 9 0 0 0 15 6.7l3-2.7"/><path d="M21 21v-5h-5"/>'
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25'
        "a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73"
        "l.15.09a2 2 0 0 1 1 1.74v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73"
        "l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20"
        "a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0"
        "l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74"
        "v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73"
        'l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "sparkles": (
        '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9'
        "a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12"
        'l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>'
        '<path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>'
    ),
    "trending-down": '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "trending-up": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}


def _lucide_icon(name: str, color: QColor | None = None) -> QIcon:
    """Render a Lucide SVG icon into a Qt icon."""
    color = color or QColor("white")
    elements = _LUCIDE_ELEMENTS[name]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"'
        f' fill="none" stroke="{color.name()}" stroke-width="2"'
        f' stroke-linecap="round" stroke-linejoin="round">{elements}</svg>'
    )
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
    painter.end()
    return QIcon(pixmap)


class TurnStatePanel(QWidget):
    """Manual controls for the three once-per-turn actions."""

    ACTIONS = (
        ("level_up", "level_up", "sparkles"),
        ("switch", "switch", "arrow-left-right"),
        ("charge", "charge", "music"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._language = Language.JA
        self._action_buttons: dict[str, QPushButton] = {}
        self._action_translation_keys: dict[str, str] = {}
        self._action_labels: list[QLabel] = []

        card = QFrame()
        card.setObjectName("turnStateCard")
        card.setStyleSheet(
            "QFrame#turnStateCard { background-color: palette(base);"
            " border: 1px solid palette(mid); border-radius: 10px; }"
            "QPushButton[action='true'] { background-color: #26313d; border: 2px solid #536273;"
            " border-radius: 12px; padding: 7px; }"
            "QPushButton[action='true']:hover { background-color: #334252; border-color: #7b8da0; }"
            "QPushButton[action='true']:checked { background-color: #177e73;"
            " border-color: #5ce1cf; }"
            "QPushButton[action='true']:checked:hover { background-color: #1b8f82; }"
            "QPushButton#turnReset { background: transparent; border: 1px solid palette(mid);"
            " border-radius: 15px; padding: 3px; }"
            "QPushButton#turnReset:hover { background-color: palette(midlight); }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(9)

        header = QHBoxLayout()
        self._title = QLabel()
        header.addWidget(self._title)
        header.addStretch()
        self._reset_button = QPushButton()
        self._reset_button.setObjectName("turnReset")
        self._reset_button.setIcon(_lucide_icon("refresh-ccw", QColor("#657687")))
        self._reset_button.setIconSize(QSize(21, 21))
        self._reset_button.setFixedSize(31, 31)
        self._reset_button.clicked.connect(self.reset_actions)
        header.addWidget(self._reset_button)
        card_layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for key, translation_key, icon_name in self.ACTIONS:
            column = QVBoxLayout()
            column.setSpacing(4)
            button = QPushButton()
            button.setProperty("action", True)
            button.setCheckable(True)
            button.setIcon(_lucide_icon(icon_name))
            button.setIconSize(QSize(34, 34))
            button.setMinimumHeight(56)
            button.toggled.connect(
                lambda checked, target=button, icon=icon_name, action_key=key: self._update_action(
                    target, icon, action_key, checked
                )
            )
            self._action_buttons[key] = button
            self._action_translation_keys[key] = translation_key
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._action_labels.append(label)
            column.addWidget(button)
            column.addWidget(label)
            actions.addLayout(column, 1)
        card_layout.addLayout(actions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        self.set_language(Language.JA)
        self.set_base_font_size(DEFAULT_UI_BASE_FONT_PT)

    @property
    def used_actions(self) -> frozenset[str]:
        return frozenset(key for key, button in self._action_buttons.items() if button.isChecked())

    def reset_actions(self) -> None:
        for button in self._action_buttons.values():
            button.setChecked(False)

    def set_base_font_size(self, base_size: float) -> None:
        _apply_ui_font(self._title, base_size, UiFontRole.SECTION_TITLE)
        for label in self._action_labels:
            _apply_ui_font(label, base_size, UiFontRole.LABEL)

    def set_language(self, language: Language) -> None:
        self._language = language
        self._title.setText(tr(language, "turn_management"))
        self._reset_button.setToolTip(tr(language, "reset_turn_actions_tip"))
        self._reset_button.setAccessibleName(tr(language, "reset_turn_actions"))
        for (key, translation_key, _icon_name), label in zip(
            self.ACTIONS, self._action_labels, strict=True
        ):
            action_label = tr(language, translation_key)
            label.setText(action_label)
            button = self._action_buttons[key]
            button.setAccessibleName(action_label)
            tooltip_key = "mark_unused" if button.isChecked() else "mark_used"
            button.setToolTip(tr(language, tooltip_key, action=action_label))

    def _update_action(
        self, button: QPushButton, icon_name: str, action_key: str, checked: bool
    ) -> None:
        button.setIcon(_lucide_icon("check" if checked else icon_name))
        label = tr(self._language, self._action_translation_keys[action_key])
        tooltip_key = "mark_unused" if checked else "mark_used"
        button.setToolTip(tr(self._language, tooltip_key, action=label))


class BattleStatusCard(QWidget):
    """A standalone advantage/disadvantage card beside the life counter."""

    def __init__(self) -> None:
        super().__init__()
        self._language = Language.JA
        self._card = QFrame()
        self._card.setObjectName("battleStatusCard")
        self._card.setStyleSheet(
            "QFrame#battleStatusCard { background-color: palette(base);"
            " border: 1px solid palette(mid); border-radius: 10px; }"
            "QPushButton#advantageToggle { border: 2px solid #ffcc58; border-radius: 12px;"
            " background-color: #654b14; padding: 8px; }"
            "QPushButton#advantageToggle[disadvantaged='true'] { border-color: #80b7ff;"
            " background-color: #183d68; }"
        )

        card_layout = QVBoxLayout(self._card)
        card_layout.addStretch()
        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)
        card_layout.addWidget(self._title, 0, Qt.AlignmentFlag.AlignCenter)

        self._advantage_button = QPushButton()
        self._advantage_button.setObjectName("advantageToggle")
        self._advantage_button.setCheckable(True)
        self._advantage_button.setIconSize(QSize(42, 42))
        self._advantage_button.setMinimumSize(82, 62)
        self._advantage_button.toggled.connect(self._update_advantage)
        card_layout.addWidget(self._advantage_button, 0, Qt.AlignmentFlag.AlignCenter)

        self._advantage_label = QLabel()
        self._advantage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._advantage_label.setWordWrap(True)
        card_layout.addWidget(self._advantage_label, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card)
        self.set_language(Language.JA)
        self._update_advantage(False)
        self.set_base_font_size(DEFAULT_UI_BASE_FONT_PT)

    @property
    def is_disadvantaged(self) -> bool:
        return self._advantage_button.isChecked()

    def set_base_font_size(self, base_size: float) -> None:
        _apply_ui_font(self._title, base_size, UiFontRole.SECTION_TITLE)
        _apply_ui_font(self._advantage_label, base_size, UiFontRole.EMPHASIS)

    def set_language(self, language: Language) -> None:
        self._language = language
        self._title.setText(tr(language, "battle_status"))
        self._advantage_button.setAccessibleName(tr(language, "toggle_battle_status"))
        self._update_advantage(self.is_disadvantaged)

    def _update_advantage(self, disadvantaged: bool) -> None:
        button = self._advantage_button
        button.setProperty("disadvantaged", disadvantaged)
        if disadvantaged:
            button.setIcon(_lucide_icon("trending-down", QColor("#4f9cff")))
            button.setToolTip(tr(self._language, "disadvantage_tip"))
            self._advantage_label.setText(tr(self._language, "disadvantage"))
            self._advantage_label.setStyleSheet("color: #4f9cff;")
        else:
            button.setIcon(_lucide_icon("trending-up", QColor("#e4a91a")))
            button.setToolTip(tr(self._language, "advantage_tip"))
            self._advantage_label.setText(tr(self._language, "advantage"))
            self._advantage_label.setStyleSheet("color: #b98000;")
        button.style().unpolish(button)
        button.style().polish(button)


class _IndexWorker(QThread):
    progress = Signal(int, int)
    ready = Signal()
    failed = Signal(str)

    def __init__(self, engine: RecognitionEngine) -> None:
        super().__init__()
        self._engine = engine

    def run(self) -> None:
        try:
            self._engine.build_index(self._report_progress)
        except InterruptedError:
            return
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
            return
        self.ready.emit()

    def _report_progress(self, current: int, total: int) -> None:
        if self.isInterruptionRequested():
            raise InterruptedError
        if current == total or current % 5 == 0:
            self.progress.emit(current, total)


class _RecognitionSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class _RecognitionTask(QRunnable):
    def __init__(
        self,
        request_id: int,
        engine: RecognitionEngine,
        frame: Image,
        click: Point,
        region: Polygon | None,
    ) -> None:
        super().__init__()
        self.signals = _RecognitionSignals()
        self._request_id = request_id
        self._engine = engine
        self._frame = frame
        self._click = click
        self._region = region

    def run(self) -> None:
        try:
            result = self._engine.recognize(self._frame, self._click, region=self._region)
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self._request_id, str(error))
            return
        self.signals.completed.emit(self._request_id, result)


class MainWindow(QMainWindow):
    def __init__(
        self,
        catalog: CardCatalog,
        build_index: bool = True,
    ) -> None:
        super().__init__()
        self._language = Language.JA
        self._status_key = "preparing_images"
        self._status_values: dict[str, Any] = {}
        self._card_placeholder_key = "recognition_result"
        self.resize(1280, 800)

        self._engine = RecognitionEngine(catalog)
        self._camera = CameraController()
        self._index_worker: _IndexWorker | None = None
        self._latest_frame: Image | None = None
        self._last_click: Point | None = None
        self._last_region: Polygon | None = None
        self._candidates: tuple[RecognitionCandidate, ...] = ()
        self._request_id = 0
        self._index_ready = False
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)

        self._video = VideoWidget()
        self._settings_button = QToolButton()
        self._settings_button.setIcon(_lucide_icon("settings", QColor("#657687")))
        self._settings_button.setIconSize(QSize(22, 22))
        self._settings_button.setFixedSize(32, 32)
        self._settings_button.setStyleSheet(
            "QToolButton::menu-indicator { image: none; width: 0px; }"
        )
        self._settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._settings_menu = QMenu(self._settings_button)
        self._outline_color_action = QAction(self._settings_menu)
        self._outline_color_action.triggered.connect(self._choose_recognition_outline_color)
        self._settings_menu.addAction(self._outline_color_action)
        self._language_menu = QMenu(self._settings_menu)
        self._settings_menu.addMenu(self._language_menu)
        self._language_action_group = QActionGroup(self._language_menu)
        self._language_action_group.setExclusive(True)
        self._language_actions: dict[Language, QAction] = {}
        for language, label in (
            (Language.JA, "日本語"),
            (Language.EN, "English"),
            (Language.ZH_CN, "简体中文"),
        ):
            action = QAction(label, self._language_action_group)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, selected=language: self.set_language(selected) if checked else None
            )
            self._language_menu.addAction(action)
            self._language_actions[language] = action
        self._settings_button.setMenu(self._settings_menu)
        self._camera_selector = QComboBox()
        self._camera_button = QPushButton()
        self._camera_button.clicked.connect(self._toggle_camera)
        self._status = QLabel()
        self._status.setWordWrap(True)

        self._card_image = ScalableImageLabel()
        self._card_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._card_image.setMinimumHeight(330)
        self._card_image.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._card_image.setFrameShape(QFrame.Shape.StyledPanel)
        self._candidate_selector = QComboBox()
        self._candidate_selector.setEnabled(False)
        self._candidate_selector.currentIndexChanged.connect(self._show_candidate)
        self._life_counter = LifeCounter()
        self._battle_status = BattleStatusCard()
        self._turn_state = TurnStatePanel()

        self._build_layout()
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.camera_error.connect(self._on_camera_error)
        self._camera.camera_opened.connect(self._on_camera_opened)
        self._camera.devices_changed.connect(self._refresh_camera_devices)
        self._refresh_camera_devices()
        self._video.source_clicked.connect(self._recognize_at)
        self._video.source_region_selected.connect(self._recognize_region)
        self.set_language(Language.JA)

        if build_index:
            self._start_indexing()

    def _build_layout(self) -> None:
        controls = QHBoxLayout()
        controls.addWidget(self._settings_button)
        controls.addSpacing(4)
        self._input_label = QLabel()
        controls.addWidget(self._input_label)
        controls.addWidget(self._camera_selector)
        controls.addWidget(self._camera_button)
        controls.addStretch()

        left_layout = QVBoxLayout()
        left_layout.addLayout(controls)
        left_layout.addWidget(self._video, 1)
        left_layout.addWidget(self._status)
        left = QWidget()
        left.setLayout(left_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self._card_image, 1)
        candidate_layout = QHBoxLayout()
        self._candidate_label = QLabel()
        candidate_layout.addWidget(self._candidate_label)
        candidate_layout.addWidget(self._candidate_selector, 1)
        right_layout.addLayout(candidate_layout)
        player_state_layout = QHBoxLayout()
        player_state_layout.setSpacing(8)
        player_state_layout.addWidget(self._life_counter, 5)
        player_state_layout.addWidget(self._battle_status, 3)
        self._player_state_row = QWidget()
        self._player_state_row.setLayout(player_state_layout)
        right_layout.addWidget(self._player_state_row)
        right_layout.addWidget(self._turn_state)
        right = QWidget()
        right.setLayout(right_layout)
        right.setMinimumWidth(440)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._splitter = QSplitter()
        self._splitter.addWidget(left)
        self._splitter.addWidget(right)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([900, 380])
        self.setCentralWidget(self._splitter)

    def _choose_recognition_outline_color(self) -> None:
        color = QColorDialog.getColor(
            self._video.recognition_outline_color,
            self,
            tr(self._language, "recognition_outline_color_title"),
        )
        if color.isValid():
            self._video.set_recognition_outline_color(color)

    def set_language(self, language: Language) -> None:
        self._language = language
        self.setWindowTitle(tr(language, "window_title"))
        self._settings_button.setToolTip(tr(language, "settings"))
        self._settings_button.setAccessibleName(tr(language, "settings"))
        self._outline_color_action.setText(tr(language, "recognition_outline_color"))
        self._language_menu.setTitle(tr(language, "language"))
        self._language_actions[language].setChecked(True)
        self._input_label.setText(tr(language, "input"))
        self._candidate_label.setText(tr(language, "recognition_candidates"))
        self._camera_button.setText(
            tr(language, "camera_stop" if self._camera.is_active else "camera_start")
        )
        self._video.set_language(language)
        self._life_counter.set_language(language)
        self._turn_state.set_language(language)
        self._battle_status.set_language(language)
        if not self._candidates:
            self._candidate_selector.blockSignals(True)
            self._candidate_selector.clear()
            self._candidate_selector.addItem(tr(language, "no_candidates"))
            self._candidate_selector.blockSignals(False)
            self._card_image.clear_image(tr(language, self._card_placeholder_key))
        self._set_status(self._status_key, **self._status_values)

    def _set_status(self, key: str, **values: Any) -> None:
        self._status_key = key
        self._status_values = values
        self._status.setText(tr(self._language, key, **values))

    def _start_indexing(self) -> None:
        self._index_worker = _IndexWorker(self._engine)
        self._index_worker.progress.connect(self._on_index_progress)
        self._index_worker.ready.connect(self._on_index_ready)
        self._index_worker.failed.connect(self._on_index_failed)
        self._index_worker.start()

    def _on_index_progress(self, current: int, total: int) -> None:
        self._set_status("preparing_progress", current=current, total=total)

    def _on_index_ready(self) -> None:
        self._index_ready = True
        self._set_status("ready", count=self._engine.indexed_variant_count)

    def _on_index_failed(self, message: str) -> None:
        self._set_status("index_failed", message=message)

    def _toggle_camera(self) -> None:
        if self._camera.is_active:
            self._stop_camera()
            return

        device_id = self._camera_selector.currentData()
        if not isinstance(device_id, bytes):
            self._set_status("no_camera")
            return
        self._camera_selector.setEnabled(False)
        self._camera_button.setText(tr(self._language, "camera_stop"))
        self._set_status("connecting_camera", device=self._camera_selector.currentText())
        self._camera.start(device_id)

    def _stop_camera(self) -> None:
        self._camera.stop()
        self._camera_selector.setEnabled(self._camera_selector.count() > 0)
        self._camera_button.setText(tr(self._language, "camera_start"))
        self._set_status("camera_stopped")

    def _refresh_camera_devices(self) -> None:
        previous_id = self._camera.active_device_id or self._camera_selector.currentData()
        devices = self._camera.video_inputs()
        self._camera_selector.blockSignals(True)
        self._camera_selector.clear()
        for device in devices:
            self._camera_selector.addItem(device.name, device.device_id)
            self._camera_selector.setItemData(
                self._camera_selector.count() - 1,
                device.device_id.decode("utf-8", errors="replace"),
                Qt.ItemDataRole.ToolTipRole,
            )

        selected_index = next(
            (index for index, device in enumerate(devices) if device.device_id == previous_id),
            next((index for index, device in enumerate(devices) if device.is_default), 0),
        )
        if devices:
            self._camera_selector.setCurrentIndex(selected_index)
        self._camera_selector.blockSignals(False)
        self._camera_selector.setEnabled(bool(devices) and not self._camera.is_active)
        self._camera_button.setEnabled(bool(devices))

    def _on_camera_error(self, message: str) -> None:
        if message == "選択したカメラがWindows上で見つかりません。":
            self._set_status("selected_camera_missing")
        elif message == "カメラの開始に失敗しました。":
            self._set_status("camera_start_failed")
        else:
            self._set_status("camera_error", message=message)
        self._camera.stop()
        self._camera_selector.setEnabled(self._camera_selector.count() > 0)
        self._camera_button.setText(tr(self._language, "camera_start"))

    def _on_camera_opened(self, _message: str) -> None:
        self._set_status("camera_in_use", device=self._camera_selector.currentText())

    def _on_frame(self, frame: Image) -> None:
        self._latest_frame = frame.copy()
        self._video.set_frame(frame)

    def _recognize_at(self, x: float, y: float) -> None:
        click = (x, y)
        self._submit_recognition(click, None)

    def _recognize_region(self, region: Polygon) -> None:
        center = (
            sum(point[0] for point in region) / 4,
            sum(point[1] for point in region) / 4,
        )
        self._submit_recognition(center, region)

    def _submit_recognition(self, click: Point, region: Polygon | None) -> None:
        self._last_click = click
        self._last_region = region
        self._video.set_selection(click, analysis_region=region)
        if not self._index_ready:
            self._set_status("wait_for_images")
            return
        if self._latest_frame is None:
            self._set_status("start_camera_first")
            return

        self._request_id += 1
        task = _RecognitionTask(
            self._request_id,
            self._engine,
            self._latest_frame.copy(),
            click,
            region,
        )
        task.signals.completed.connect(self._on_recognition_completed)
        task.signals.failed.connect(self._on_recognition_failed)
        self._set_status("recognizing_region" if region is not None else "recognizing_click")
        self._thread_pool.start(task)

    def _on_recognition_completed(self, request_id: int, result: RecognitionResult) -> None:
        if request_id != self._request_id:
            return
        self._candidates = result.candidates
        self._candidate_selector.blockSignals(True)
        self._candidate_selector.clear()
        if not result.candidates:
            self._candidate_selector.addItem(tr(self._language, "no_candidates"))
            self._candidate_selector.setEnabled(False)
            self._candidate_selector.blockSignals(False)
            self._clear_result()
            self._set_status("not_recognized")
            return

        for candidate in result.candidates:
            self._candidate_selector.addItem(f"{candidate.card.code}  {candidate.card.name}")
        self._candidate_selector.setEnabled(True)
        self._candidate_selector.setCurrentIndex(0)
        self._candidate_selector.blockSignals(False)
        self._show_candidate(0)
        guidance = "" if result.is_confident else tr(self._language, "check_candidates")
        self._set_status("recognition_complete", guidance=guidance, elapsed=result.elapsed_ms)

    def _on_recognition_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            self._video.set_selection(None)
            self._set_status("recognition_failed", message=message)

    def _show_candidate(self, row: int) -> None:
        if row < 0 or row >= len(self._candidates):
            return
        candidate = self._candidates[row]
        pixmap = QPixmap(str(candidate.reference_path))
        self._card_image.set_source_pixmap(pixmap)
        self._video.set_selection(None, candidate.polygon)

    def _clear_result(self) -> None:
        self._candidates = ()
        self._candidate_selector.blockSignals(True)
        self._candidate_selector.clear()
        self._candidate_selector.addItem(tr(self._language, "no_candidates"))
        self._candidate_selector.setEnabled(False)
        self._candidate_selector.blockSignals(False)
        self._card_placeholder_key = "no_recognition_result"
        self._card_image.clear_image(tr(self._language, self._card_placeholder_key))
        self._video.set_selection(None)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_camera()
        if self._index_worker is not None and self._index_worker.isRunning():
            self._index_worker.requestInterruption()
            self._index_worker.wait(5_000)
        self._thread_pool.waitForDone(5_000)
        event.accept()
