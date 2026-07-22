from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtGui import QResizeEvent
from PySide2.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .models import GlobalCaptureState
from .styles import refresh_style


TOOLBAR_COMPACT_WIDTH = 1200


@dataclass(frozen=True)
class _ToolbarPresentation:
    status_text: str
    button_text: str
    button_mode: str
    directory_enabled: bool


_TOOLBAR_PRESENTATIONS: Dict[GlobalCaptureState, _ToolbarPresentation] = {
    GlobalCaptureState.IDLE: _ToolbarPresentation(
        status_text="未启动",
        button_text="启动采集",
        button_mode="start",
        directory_enabled=True,
    ),
    GlobalCaptureState.RUNNING: _ToolbarPresentation(
        status_text="采集中",
        button_text="停止采集",
        button_mode="stop",
        directory_enabled=False,
    ),
    GlobalCaptureState.STOPPED: _ToolbarPresentation(
        status_text="已停止",
        button_text="启动采集",
        button_mode="start",
        directory_enabled=True,
    ),
    GlobalCaptureState.PARTIAL_ERROR: _ToolbarPresentation(
        status_text="部分异常",
        button_text="停止采集",
        button_mode="stop",
        directory_enabled=False,
    ),
    GlobalCaptureState.ERROR: _ToolbarPresentation(
        status_text="错误",
        button_text="停止并重置",
        button_mode="reset",
        directory_enabled=True,
    ),
}


_STATUS_TEXT = {
    GlobalCaptureState.IDLE: "就绪",
    GlobalCaptureState.RUNNING: "采集中",
    GlobalCaptureState.STOPPED: "就绪",
    GlobalCaptureState.PARTIAL_ERROR: "部分异常",
    GlobalCaptureState.ERROR: "错误",
}


class CaptureToolbar(QWidget):
    browse_requested = Signal()
    capture_requested = Signal()

    def __init__(
        self,
        image_directory: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._is_compact: Optional[bool] = None
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(10)

        self.brand_widget = self._build_brand()
        self.controls_widget = self._build_controls(image_directory)
        self.global_status = QLabel("● 未启动", self)
        self.global_status.setObjectName("globalStatus")
        self.global_status.setProperty("status", GlobalCaptureState.IDLE.value)
        self.global_status.setMinimumWidth(88)
        self.global_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._apply_layout(self.width() < TOOLBAR_COMPACT_WIDTH)

    @property
    def image_directory(self) -> Path:
        return Path(self.directory_edit.text().strip())

    def set_image_directory(self, directory: Path) -> None:
        self.directory_edit.setText(str(directory))

    def apply_state(self, state: GlobalCaptureState) -> None:
        presentation = _TOOLBAR_PRESENTATIONS[state]
        self.global_status.setText("● {}".format(presentation.status_text))
        self.global_status.setProperty("status", state.value)
        refresh_style(self.global_status)

        self.capture_button.setText(presentation.button_text)
        self.capture_button.setProperty("mode", presentation.button_mode)
        refresh_style(self.capture_button)

        self.directory_edit.setEnabled(presentation.directory_enabled)
        self.browse_button.setEnabled(presentation.directory_enabled)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt 接口命名
        super().resizeEvent(event)
        self._apply_layout(event.size().width() < TOOLBAR_COMPACT_WIDTH)

    def _build_brand(self) -> QWidget:
        brand = QWidget(self)
        layout = QVBoxLayout(brand)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel("CameraViewer", brand)
        title.setObjectName("titleLabel")
        subtitle = QLabel("三路异步图像采集演示", brand)
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return brand

    def _build_controls(self, image_directory: Path) -> QWidget:
        controls_widget = QWidget(self)
        layout = QHBoxLayout(controls_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.directory_label = QLabel("图像目录", controls_widget)
        self.directory_label.setObjectName("fieldLabel")
        layout.addWidget(self.directory_label)

        self.directory_edit = QLineEdit(str(image_directory), controls_widget)
        self.directory_edit.setMinimumWidth(220)
        self.directory_edit.setToolTip("包含 frame_0001.jpg 至 frame_0500.jpg 的目录")
        self.directory_label.setBuddy(self.directory_edit)
        layout.addWidget(self.directory_edit, 1)

        self.browse_button = QPushButton("选择目录", controls_widget)
        self.browse_button.clicked.connect(self.browse_requested.emit)
        layout.addWidget(self.browse_button)

        self.capture_button = QPushButton("启动采集", controls_widget)
        self.capture_button.setObjectName("startButton")
        self.capture_button.setProperty("mode", "start")
        self.capture_button.setMinimumWidth(128)
        self.capture_button.clicked.connect(self.capture_requested.emit)
        layout.addWidget(self.capture_button)

        self.setTabOrder(self.directory_edit, self.browse_button)
        self.setTabOrder(self.browse_button, self.capture_button)
        return controls_widget

    def _apply_layout(self, compact: bool) -> None:
        if self._is_compact is compact:
            return
        self._is_compact = compact

        for widget in (self.brand_widget, self.controls_widget, self.global_status):
            self._grid.removeWidget(widget)

        if compact:
            self._grid.addWidget(self.brand_widget, 0, 0)
            self._grid.addWidget(
                self.global_status,
                0,
                1,
                Qt.AlignRight | Qt.AlignVCenter,
            )
            self._grid.addWidget(self.controls_widget, 1, 0, 1, 2)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 0)
            self._grid.setColumnStretch(2, 0)
            return

        self._grid.addWidget(self.brand_widget, 0, 0)
        self._grid.addWidget(self.controls_widget, 0, 1)
        self._grid.addWidget(
            self.global_status,
            0,
            2,
            Qt.AlignRight | Qt.AlignVCenter,
        )
        self._grid.setColumnStretch(0, 0)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 0)


class CaptureStatusBar(QStatusBar):
    def __init__(self, capacity: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.state_label = QLabel("● 就绪", self)
        self.activity_label = QLabel("线程池 0/{}".format(capacity), self)
        self.addWidget(self.state_label)
        self.addPermanentWidget(self.activity_label)

    def apply_state(self, state: GlobalCaptureState) -> None:
        self.state_label.setText("● {}".format(_STATUS_TEXT[state]))

    def set_activity(self, active: int, capacity: int) -> None:
        self.activity_label.setText("线程池 {}/{}".format(active, capacity))
