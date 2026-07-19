from pathlib import Path
from typing import Dict, Iterable, Optional

from PySide2.QtCore import QThreadPool, Qt, Slot
from PySide2.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .capture import CameraController
from .models import CameraState
from .source import ImageSequenceSource, SequenceValidationError
from .styles import APP_STYLESHEET
from .widgets import CameraPanel, refresh_style


CAMERA_STARTS = (1, 168, 335)


class MainWindow(QMainWindow):
    def __init__(self, image_directory: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("CameraViewer")
        self.resize(1280, 720)
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(APP_STYLESHEET)
        self._toolbar_compact: Optional[bool] = None

        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(3)

        self.controllers: Dict[int, CameraController] = {}
        self.panels: Dict[int, CameraPanel] = {}
        self._build_ui(image_directory or Path.cwd() / "sample_frames")
        self._build_controllers()
        self._update_global_state()

    def _build_ui(self, image_directory: Path) -> None:
        root = QWidget(self)
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 20, 24, 18)
        root_layout.setSpacing(18)
        root_layout.addWidget(self._build_toolbar(image_directory))

        panel_row = QHBoxLayout()
        panel_row.setSpacing(14)
        for camera_id in range(1, 4):
            panel = CameraPanel(camera_id, root)
            self.panels[camera_id] = panel
            panel_row.addWidget(panel, 1, Qt.AlignTop)
        root_layout.addLayout(panel_row, 1)
        self.setCentralWidget(root)

        status_bar = QStatusBar(self)
        status_bar.setSizeGripEnabled(False)
        self.ready_label = QLabel("● 就绪", status_bar)
        self.thread_label = QLabel("线程池 0/3", status_bar)
        status_bar.addWidget(self.ready_label)
        status_bar.addPermanentWidget(self.thread_label)
        self.setStatusBar(status_bar)

    def _build_toolbar(self, image_directory: Path) -> QWidget:
        toolbar = QWidget(self)
        self._toolbar_grid = QGridLayout(toolbar)
        self._toolbar_grid.setContentsMargins(0, 0, 0, 0)
        self._toolbar_grid.setHorizontalSpacing(16)
        self._toolbar_grid.setVerticalSpacing(10)

        self._brand_widget = QWidget(toolbar)
        title_column = QVBoxLayout(self._brand_widget)
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)
        title = QLabel("CameraViewer", self._brand_widget)
        title.setObjectName("titleLabel")
        subtitle = QLabel("三路异步图像采集演示", self._brand_widget)
        subtitle.setObjectName("subtitleLabel")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        self._controls_widget = QWidget(toolbar)
        controls = QHBoxLayout(self._controls_widget)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(12)

        self.directory_label = QLabel("图像目录", self._controls_widget)
        self.directory_label.setObjectName("fieldLabel")
        controls.addWidget(self.directory_label)

        self.directory_edit = QLineEdit(str(image_directory), self._controls_widget)
        self.directory_edit.setMinimumWidth(220)
        self.directory_edit.setToolTip("包含 frame_0001.jpg 至 frame_0500.jpg 的目录")
        self.directory_label.setBuddy(self.directory_edit)
        controls.addWidget(self.directory_edit, 1)

        self.browse_button = QPushButton("选择目录", self._controls_widget)
        self.browse_button.clicked.connect(self._choose_directory)
        controls.addWidget(self.browse_button)

        self.start_button = QPushButton("启动采集", self._controls_widget)
        self.start_button.setObjectName("startButton")
        self.start_button.setProperty("mode", "start")
        self.start_button.setMinimumWidth(128)
        self.start_button.clicked.connect(self._toggle_capture)
        controls.addWidget(self.start_button)

        self.global_status = QLabel("● 未启动", toolbar)
        self.global_status.setObjectName("globalStatus")
        self.global_status.setProperty("status", "idle")
        self.global_status.setMinimumWidth(88)
        self.global_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.setTabOrder(self.directory_edit, self.browse_button)
        self.setTabOrder(self.browse_button, self.start_button)
        self._apply_toolbar_layout(self.width() < 1200)
        return toolbar

    def _apply_toolbar_layout(self, compact: bool) -> None:
        if self._toolbar_compact is compact:
            return
        self._toolbar_compact = compact

        for widget in (self._brand_widget, self._controls_widget, self.global_status):
            self._toolbar_grid.removeWidget(widget)

        if compact:
            self._toolbar_grid.addWidget(self._brand_widget, 0, 0)
            self._toolbar_grid.addWidget(
                self.global_status,
                0,
                1,
                Qt.AlignRight | Qt.AlignVCenter,
            )
            self._toolbar_grid.addWidget(self._controls_widget, 1, 0, 1, 2)
            self._toolbar_grid.setColumnStretch(0, 1)
            self._toolbar_grid.setColumnStretch(1, 0)
            self._toolbar_grid.setColumnStretch(2, 0)
        else:
            self._toolbar_grid.addWidget(self._brand_widget, 0, 0)
            self._toolbar_grid.addWidget(self._controls_widget, 0, 1)
            self._toolbar_grid.addWidget(
                self.global_status,
                0,
                2,
                Qt.AlignRight | Qt.AlignVCenter,
            )
            self._toolbar_grid.setColumnStretch(0, 0)
            self._toolbar_grid.setColumnStretch(1, 1)
            self._toolbar_grid.setColumnStretch(2, 0)

    def _build_controllers(self) -> None:
        for camera_id, start_cursor in enumerate(CAMERA_STARTS, start=1):
            controller = CameraController(
                camera_id=camera_id,
                start_cursor=start_cursor,
                thread_pool=self.thread_pool,
                parent=self,
            )
            panel = self.panels[camera_id]

            # Connect the View first: it owns the initial and next-frame pulls.
            controller.state_changed.connect(panel.apply_state)
            controller.result_ready.connect(panel.show_result)
            panel.frame_requested.connect(controller.request_frame)

            controller.state_changed.connect(self._on_camera_state_changed)
            controller.activity_changed.connect(self._update_thread_status)
            self.controllers[camera_id] = controller

    @Slot()
    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择图像序列目录",
            self.directory_edit.text(),
        )
        if selected:
            self.directory_edit.setText(selected)

    @Slot()
    def _toggle_capture(self) -> None:
        states = self._states()
        if any(state is CameraState.RUNNING for state in states):
            self.stop_all()
        elif any(state is CameraState.ERROR for state in states):
            # PRD: an errored camera must pass through STOPPED before restart.
            self.stop_all()
        else:
            self.start_all()

    def start_all(self) -> None:
        source = ImageSequenceSource(Path(self.directory_edit.text().strip()))
        try:
            # Validation checks paths only. No image is read or decoded here.
            source.validate()
        except SequenceValidationError as exc:
            for controller in self.controllers.values():
                controller.set_error(str(exc))
            QMessageBox.warning(self, "图像序列不可用", str(exc))
            return

        for controller in self.controllers.values():
            controller.configure_source(source)
        for controller in self.controllers.values():
            controller.start()

    def stop_all(self) -> None:
        for controller in self.controllers.values():
            controller.stop()

    @Slot(int, object, str)
    def _on_camera_state_changed(self, camera_id: int, state: CameraState, message: str) -> None:
        del camera_id, state, message
        self._update_global_state()

    def _states(self) -> Iterable[CameraState]:
        return [controller.state for controller in self.controllers.values()]

    def _update_global_state(self) -> None:
        states = list(self._states())
        has_error = any(state is CameraState.ERROR for state in states)
        has_running = any(state is CameraState.RUNNING for state in states)

        if states and all(state is CameraState.ERROR for state in states):
            text, status = "错误", "error"
        elif has_error:
            text, status = "部分异常", "partial"
        elif has_running:
            text, status = "采集中", "running"
        elif states and all(state is CameraState.STOPPED for state in states):
            text, status = "已停止", "stopped"
        else:
            text, status = "未启动", "idle"

        self.global_status.setText("● {}".format(text))
        self.global_status.setProperty("status", status)
        refresh_style(self.global_status)

        if has_running:
            button_text, mode = "停止采集", "stop"
        elif has_error:
            button_text, mode = "停止并重置", "reset"
        else:
            button_text, mode = "启动采集", "start"
        self.start_button.setText(button_text)
        self.start_button.setProperty("mode", mode)
        refresh_style(self.start_button)

        self.directory_edit.setEnabled(not has_running)
        self.browse_button.setEnabled(not has_running)
        self.ready_label.setText("● {}".format(text if has_running or has_error else "就绪"))
        self._update_thread_status()

    @Slot()
    def _update_thread_status(self) -> None:
        active = sum(controller.in_flight for controller in self.controllers.values())
        self.thread_label.setText("线程池 {}/3".format(active))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        if hasattr(self, "_toolbar_grid"):
            self._apply_toolbar_layout(event.size().width() < 1200)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self.stop_all()
        self.thread_pool.clear()
        self.thread_pool.waitForDone(2500)
        event.accept()
