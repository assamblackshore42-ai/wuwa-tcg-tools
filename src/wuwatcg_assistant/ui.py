from __future__ import annotations

import math
from typing import Any, override

import cv2
from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThread, QThreadPool, Signal
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraController
from .catalog import CardCatalog
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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "カメラを開始してください")
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
                QPen(QColor("#5ce1e6"), 3),
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
        self.setWindowTitle("鳴潮：対決 カードアシスタント")
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
        self._camera_selector = QComboBox()
        self._camera_button = QPushButton("カメラ開始")
        self._camera_button.clicked.connect(self._toggle_camera)
        self._status = QLabel("カード画像を準備しています…")
        self._status.setWordWrap(True)

        self._card_image = ScalableImageLabel("認識結果")
        self._card_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._card_image.setMinimumHeight(330)
        self._card_image.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._card_image.setFrameShape(QFrame.Shape.StyledPanel)
        self._card_name = QLabel("カードをクリックしてください")
        self._card_name.setFont(QFont(self.font().family(), 16, QFont.Weight.Bold))
        self._card_name.setWordWrap(True)
        self._card_meta = QLabel()
        self._card_meta.setWordWrap(True)
        self._candidate_list = QListWidget()
        self._candidate_list.setMaximumHeight(150)
        self._candidate_list.currentRowChanged.connect(self._show_candidate)

        self._build_layout()
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.camera_error.connect(self._on_camera_error)
        self._camera.camera_opened.connect(self._status.setText)
        self._camera.devices_changed.connect(self._refresh_camera_devices)
        self._refresh_camera_devices()
        self._video.source_clicked.connect(self._recognize_at)
        self._video.source_region_selected.connect(self._recognize_region)

        if build_index:
            self._start_indexing()

    def _build_layout(self) -> None:
        controls = QHBoxLayout()
        controls.addWidget(QLabel("入力:"))
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
        right_layout.addWidget(self._card_name)
        right_layout.addWidget(self._card_meta)
        right_layout.addWidget(QLabel("認識候補"))
        right_layout.addWidget(self._candidate_list)
        right = QWidget()
        right.setLayout(right_layout)
        right.setMinimumWidth(330)
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

    def _start_indexing(self) -> None:
        self._index_worker = _IndexWorker(self._engine)
        self._index_worker.progress.connect(self._on_index_progress)
        self._index_worker.ready.connect(self._on_index_ready)
        self._index_worker.failed.connect(self._on_index_failed)
        self._index_worker.start()

    def _on_index_progress(self, current: int, total: int) -> None:
        self._status.setText(f"カード画像を準備しています… {current}/{total}")

    def _on_index_ready(self) -> None:
        self._index_ready = True
        self._status.setText(
            f"準備完了（画像 {self._engine.indexed_variant_count}件）。"
            "カメラ映像内のカードをクリックしてください。"
        )

    def _on_index_failed(self, message: str) -> None:
        self._status.setText(f"カード画像の準備に失敗しました: {message}")

    def _toggle_camera(self) -> None:
        if self._camera.is_active:
            self._stop_camera()
            return

        device_id = self._camera_selector.currentData()
        if not isinstance(device_id, bytes):
            self._status.setText("Windows上で利用可能なカメラが見つかりません。")
            return
        self._camera_selector.setEnabled(False)
        self._camera_button.setText("カメラ停止")
        self._status.setText(f"{self._camera_selector.currentText()} に接続しています…")
        self._camera.start(device_id)

    def _stop_camera(self) -> None:
        self._camera.stop()
        self._camera_selector.setEnabled(self._camera_selector.count() > 0)
        self._camera_button.setText("カメラ開始")
        self._status.setText("カメラを停止しました。")

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
        self._status.setText(message)
        self._camera.stop()
        self._camera_selector.setEnabled(self._camera_selector.count() > 0)
        self._camera_button.setText("カメラ開始")

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
            self._status.setText("カード画像の準備が終わるまでお待ちください。")
            return
        if self._latest_frame is None:
            self._status.setText("先にカメラを開始してください。")
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
        action = "選択範囲" if region is not None else "クリック位置"
        self._status.setText(f"{action}のカードを認識しています…")
        self._thread_pool.start(task)

    def _on_recognition_completed(self, request_id: int, result: RecognitionResult) -> None:
        if request_id != self._request_id:
            return
        self._candidates = result.candidates
        self._candidate_list.clear()
        if not result.candidates:
            self._clear_result()
            self._status.setText(
                "カードを認識できませんでした。見えている絵柄部分をクリックしてください。"
            )
            return

        for candidate in result.candidates:
            item = QListWidgetItem(
                f"{candidate.card.code}  {candidate.card.name}  ({candidate.confidence:.0%})"
            )
            self._candidate_list.addItem(item)
        self._candidate_list.setCurrentRow(0)
        certainty = "高確信" if result.is_confident else "候補を確認してください"
        self._status.setText(f"{certainty}・処理時間 {result.elapsed_ms:.0f} ms")

    def _on_recognition_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            self._status.setText(f"認識処理に失敗しました: {message}")

    def _show_candidate(self, row: int) -> None:
        if row < 0 or row >= len(self._candidates):
            return
        candidate = self._candidates[row]
        pixmap = QPixmap(str(candidate.reference_path))
        self._card_image.set_source_pixmap(pixmap)
        self._card_name.setText(candidate.card.name)
        type_label = "キャラクター" if candidate.card.card_type == "character" else "アクション"
        self._card_meta.setText(
            f"カード番号: {candidate.card.code}\n"
            f"種類: {type_label}\n"
            f"一致特徴点: {candidate.inliers}/{candidate.good_matches}\n"
            f"推定確信度: {candidate.confidence:.0%}"
        )
        self._video.set_selection(self._last_click, candidate.polygon, self._last_region)

    def _clear_result(self) -> None:
        self._candidates = ()
        self._candidate_list.clear()
        self._card_image.clear_image("認識結果なし")
        self._card_name.setText("カードをクリックしてください")
        self._card_meta.clear()
        self._video.set_selection(self._last_click, analysis_region=self._last_region)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_camera()
        if self._index_worker is not None and self._index_worker.isRunning():
            self._index_worker.requestInterruption()
            self._index_worker.wait(5_000)
        self._thread_pool.waitForDone(5_000)
        event.accept()
