from pathlib import Path

from PySide2.QtCore import QSize, Qt, Signal, Slot
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .models import CameraState, FrameResult


STATE_TEXT = {
    CameraState.IDLE: "未启动",
    CameraState.RUNNING: "采集中",
    CameraState.STOPPED: "已停止",
    CameraState.ERROR: "错误",
}


def refresh_style(widget: QWidget) -> None:
    """Re-evaluate stylesheet selectors after a dynamic property changes."""

    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class ImageViewport(QLabel):
    """Aspect-ratio preserving image view that requests after real painting."""

    frame_painted = Signal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageViewport")
        self.setAlignment(Qt.AlignCenter)
        self.setText("等待采集")
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)
        self.setMinimumSize(240, 135)
        self._source_pixmap = QPixmap()
        self._request_after_paint = False

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API name
        return max(135, round(width * 9 / 16))

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return QSize(640, 360)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return QSize(240, 135)

    def set_frame(self, rgb) -> None:
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        # copy() makes QImage own its pixels after the NumPy result is released.
        image = QImage(
            rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()
        self._source_pixmap = QPixmap.fromImage(image)
        self.setText("")
        self._refresh_pixmap()
        self._request_after_paint = True
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._refresh_pixmap()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().paintEvent(event)
        if self._request_after_paint and not self._source_pixmap.isNull():
            self._request_after_paint = False
            self.frame_painted.emit()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)


class CameraPanel(QFrame):
    """View for one camera. It owns all pull requests for that camera."""

    frame_requested = Signal()

    def __init__(self, camera_id: int, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self.setObjectName("cameraPanel")
        self.setMinimumWidth(300)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._header = self._build_header()
        layout.addWidget(self._header)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 12)
        body_layout.setSpacing(12)

        self.viewport = ImageViewport(body)
        self.viewport.frame_painted.connect(self.frame_requested)
        body_layout.addWidget(self.viewport)

        metadata = QWidget(body)
        metadata_layout = QVBoxLayout(metadata)
        metadata_layout.setContentsMargins(4, 0, 4, 0)
        metadata_layout.setSpacing(0)
        self._metadata = metadata

        self.frame_value = self._add_meta_row(metadata_layout, "帧序号", "—")
        metadata_layout.addWidget(self._divider())
        self.resolution_value = self._add_meta_row(metadata_layout, "分辨率", "—")
        metadata_layout.addWidget(self._divider())
        self.error_value = self._add_meta_row(
            metadata_layout,
            "错误信息",
            "—",
            error=True,
        )
        body_layout.addWidget(metadata)
        layout.addWidget(body)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API name
        viewport_width = max(240, width - 20)
        body_height = (
            10
            + self.viewport.heightForWidth(viewport_width)
            + 12
            + self._metadata.sizeHint().height()
            + 12
        )
        return self._header.height() + body_height + 2

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        width = 420
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        width = 300
        return QSize(width, self.heightForWidth(width))

    def _build_header(self) -> QFrame:
        header = QFrame(self)
        header.setObjectName("cameraHeader")
        header.setFixedHeight(64)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(10)

        icon_label = QLabel(header)
        icon_path = Path(__file__).parent / "assets" / "camera.svg"
        icon_label.setPixmap(QIcon(str(icon_path)).pixmap(28, 28))
        layout.addWidget(icon_label)

        title = QLabel("相机 {:02d}".format(self.camera_id), header)
        title.setObjectName("cameraTitle")
        layout.addWidget(title)
        layout.addStretch(1)

        self.state_label = QLabel("● 未启动", header)
        self.state_label.setObjectName("cameraState")
        self.state_label.setProperty("status", CameraState.IDLE.value)
        layout.addWidget(self.state_label)
        return header

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("metaDivider")
        return divider

    @staticmethod
    def _add_meta_row(layout: QVBoxLayout, label: str, value: str, error: bool = False) -> QLabel:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 9, 8, 9)
        row_layout.setSpacing(12)

        label_widget = QLabel(label, row)
        label_widget.setObjectName("metaLabel")
        label_widget.setFixedWidth(64)
        row_layout.addWidget(label_widget)

        value_widget = QLabel(value, row)
        value_widget.setObjectName("metaError" if error else "metaValue")
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_layout.addWidget(value_widget, 1)
        layout.addWidget(row)
        return value_widget

    @Slot(int, object, str)
    def apply_state(self, camera_id: int, state: CameraState, message: str) -> None:
        if camera_id != self.camera_id:
            return
        self.state_label.setText("● {}".format(STATE_TEXT[state]))
        self.state_label.setProperty("status", state.value)
        refresh_style(self.state_label)

        if state is CameraState.RUNNING:
            self.error_value.setText("—")
            # The View initiates the first pull only after entering RUNNING.
            self.frame_requested.emit()
        elif state is CameraState.ERROR and message:
            self.error_value.setText(message)

    @Slot(object)
    def show_result(self, result: FrameResult) -> None:
        if result.camera_id != self.camera_id:
            return

        self.frame_value.setText("{:04d}".format(result.frame_number))
        if result.ok:
            height, width, _ = result.rgb.shape
            self.resolution_value.setText("{} × {}".format(width, height))
            self.error_value.setText("—")
            self.viewport.set_frame(result.rgb)
        else:
            self.error_value.setText(result.error)
            # A failed result has been delivered to the View, so it can pull
            # again immediately without waiting for a paint event.
            self.frame_requested.emit()
