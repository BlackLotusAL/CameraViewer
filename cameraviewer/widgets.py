from pathlib import Path
from typing import Optional

import numpy as np

from PySide2.QtCore import QSize, Qt, Signal, Slot
from PySide2.QtGui import QIcon, QImage, QPaintEvent, QPixmap, QResizeEvent
from PySide2.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .models import CameraState, FrameResult
from .styles import refresh_style


STATE_TEXT = {
    CameraState.IDLE: "未启动",
    CameraState.RUNNING: "采集中",
    CameraState.STOPPED: "已停止",
    CameraState.ERROR: "错误",
}


class ImageViewport(QLabel):
    """保持图像宽高比，并在新帧真正绘制后通知 View 继续 Pull。"""

    frame_painted = Signal()
    ASPECT_WIDTH = 16
    ASPECT_HEIGHT = 9
    MINIMUM_WIDTH = 240
    MINIMUM_HEIGHT = 135

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageViewport")
        self.setAlignment(Qt.AlignCenter)
        self.setText("等待采集")
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)
        self.setMinimumSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT)
        self._source_pixmap = QPixmap()
        self._request_after_paint = False

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt 接口命名
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt 接口命名
        return max(
            self.MINIMUM_HEIGHT,
            round(width * self.ASPECT_HEIGHT / self.ASPECT_WIDTH),
        )

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt 接口命名
        return QSize(640, 360)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt 接口命名
        return QSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT)

    def set_frame(self, rgb: np.ndarray) -> None:
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        # copy() 让 QImage 独立持有像素，避免 NumPy 结果释放后引用失效。
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

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt 接口命名
        super().resizeEvent(event)
        self._refresh_pixmap()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt 接口命名
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
    """单路相机视图，负责发起该路的全部 Pull 请求。"""

    frame_requested = Signal()

    def __init__(self, camera_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self._configure_panel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._header = self._build_header()
        layout.addWidget(self._header)
        layout.addWidget(self._build_body())

    def _configure_panel(self) -> None:
        self.setObjectName("cameraPanel")
        self.setMinimumWidth(300)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)

    def _build_body(self) -> QWidget:
        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 12)
        body_layout.setSpacing(12)

        self.viewport = ImageViewport(body)
        self.viewport.frame_painted.connect(self.frame_requested)
        body_layout.addWidget(self.viewport)

        self._metadata = self._build_metadata(body)
        body_layout.addWidget(self._metadata)
        return body

    def _build_metadata(self, parent: QWidget) -> QWidget:
        metadata = QWidget(parent)
        metadata_layout = QVBoxLayout(metadata)
        metadata_layout.setContentsMargins(4, 0, 4, 0)
        metadata_layout.setSpacing(0)

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
        return metadata

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt 接口命名
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt 接口命名
        viewport_width = max(240, width - 20)
        body_height = (
            10
            + self.viewport.heightForWidth(viewport_width)
            + 12
            + self._metadata.sizeHint().height()
            + 12
        )
        return self._header.height() + body_height + 2

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt 接口命名
        width = 420
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt 接口命名
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
    def _add_meta_row(
        layout: QVBoxLayout,
        label: str,
        value: str,
        error: bool = False,
    ) -> QLabel:
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
            # View 仅在进入运行态后发起首帧 Pull。
            self.frame_requested.emit()
        elif state is CameraState.ERROR and message:
            self.error_value.setText(message)

    @Slot(object)
    def show_result(self, result: FrameResult) -> None:
        if result.camera_id != self.camera_id:
            return

        self.frame_value.setText("{:04d}".format(result.frame_number))
        rgb = result.rgb
        if rgb is not None and not result.error:
            height, width, _ = rgb.shape
            self.resolution_value.setText("{} × {}".format(width, height))
            self.error_value.setText("—")
            self.viewport.set_frame(rgb)
        else:
            self.error_value.setText(result.error)
            # 失败结果交付 View 后立即继续 Pull，无需等待绘制事件。
            self.frame_requested.emit()
