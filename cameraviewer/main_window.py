from pathlib import Path
from typing import Dict, Optional

from PySide2.QtCore import Qt, Slot
from PySide2.QtGui import QCloseEvent
from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureCoordinator
from .controls import CaptureStatusBar, CaptureToolbar
from .models import GlobalCaptureState
from .source import ImageSequenceSource, SequenceValidationError
from .styles import APP_STYLESHEET
from .widgets import CameraPanel


class MainWindow(QMainWindow):
    def __init__(self, image_directory: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("CameraViewer")
        self.resize(1280, 720)
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(APP_STYLESHEET)

        directory = image_directory or Path.cwd() / "sample_frames"
        self.coordinator = CaptureCoordinator(parent=self)
        self.toolbar = CaptureToolbar(directory, self)
        self.capture_status = CaptureStatusBar(self.coordinator.capacity, self)
        self.panels: Dict[int, CameraPanel] = {}

        self._build_ui()
        self._connect_signals()
        self._apply_global_state(self.coordinator.state)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 20, 24, 18)
        root_layout.setSpacing(18)
        root_layout.addWidget(self.toolbar)

        panel_row = QHBoxLayout()
        panel_row.setSpacing(14)
        for camera_id in self.coordinator.controllers:
            panel = CameraPanel(camera_id, root)
            self.panels[camera_id] = panel
            panel_row.addWidget(panel, 1, Qt.AlignTop)
        root_layout.addLayout(panel_row, 1)

        self.setCentralWidget(root)
        self.setStatusBar(self.capture_status)

    def _connect_signals(self) -> None:
        self.toolbar.browse_requested.connect(self._choose_directory)
        self.toolbar.capture_requested.connect(self._toggle_capture)
        self.coordinator.state_changed.connect(self._apply_global_state)
        self.coordinator.activity_changed.connect(self.capture_status.set_activity)

        for camera_id, controller in self.coordinator.controllers.items():
            panel = self.panels[camera_id]

            # View 直接监听运行态，并负责发起该路首帧 Pull。
            controller.state_changed.connect(panel.apply_state)
            controller.result_ready.connect(panel.show_result)
            panel.frame_requested.connect(controller.request_frame)

    @Slot()
    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择图像序列目录",
            str(self.toolbar.image_directory),
        )
        if selected:
            self.toolbar.set_image_directory(Path(selected))

    @Slot()
    def _toggle_capture(self) -> None:
        if self.coordinator.state in (
            GlobalCaptureState.RUNNING,
            GlobalCaptureState.PARTIAL_ERROR,
            GlobalCaptureState.ERROR,
        ):
            self.stop_all()
            return
        self.start_all()

    def start_all(self) -> None:
        source = ImageSequenceSource(self.toolbar.image_directory)
        try:
            self.coordinator.start(source)
        except SequenceValidationError as exc:
            QMessageBox.warning(self, "图像序列不可用", str(exc))

    def stop_all(self) -> None:
        self.coordinator.stop()

    @Slot(object)
    def _apply_global_state(self, state: GlobalCaptureState) -> None:
        self.toolbar.apply_state(state)
        self.capture_status.apply_state(state)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt 接口命名
        self.coordinator.shutdown()
        event.accept()
