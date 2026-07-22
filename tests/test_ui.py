from pathlib import Path

import numpy as np
import pytest

from cameraviewer.controls import CaptureStatusBar, CaptureToolbar
from cameraviewer.main_window import MainWindow
from cameraviewer.models import CameraState, FrameResult, GlobalCaptureState
from cameraviewer.styles import APP_STYLESHEET
from cameraviewer.widgets import CameraPanel


def test_light_ui_geometry_focus_and_responsive_toolbar(qtbot, tmp_path: Path) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.show()

    window.resize(1280, 720)
    qtbot.waitUntil(
        lambda: window.toolbar.controls_widget.y()
        == window.toolbar.brand_widget.y()
    )
    assert window.toolbar.directory_label.buddy() is window.toolbar.directory_edit
    assert (
        window.toolbar.directory_edit.nextInFocusChain()
        is window.toolbar.browse_button
    )
    assert (
        window.toolbar.browse_button.nextInFocusChain()
        is window.toolbar.capture_button
    )

    for panel in window.panels.values():
        expected_height = round(panel.viewport.width() * 9 / 16)
        assert abs(panel.viewport.height() - expected_height) <= 1

    window.resize(1080, 680)
    qtbot.waitUntil(
        lambda: window.toolbar.controls_widget.y()
        > window.toolbar.brand_widget.y()
    )
    assert (
        window.toolbar.controls_widget.width()
        > window.toolbar.brand_widget.width()
    )

    assert 'QPushButton#startButton[mode="stop"]:hover' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="stop"]:pressed' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="reset"]:hover' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="reset"]:pressed' in APP_STYLESHEET
    assert "QLineEdit:disabled" in APP_STYLESHEET


@pytest.mark.parametrize(
    ("state", "status_text", "button_text", "mode", "directory_enabled"),
    [
        (GlobalCaptureState.IDLE, "未启动", "启动采集", "start", True),
        (GlobalCaptureState.RUNNING, "采集中", "停止采集", "stop", False),
        (GlobalCaptureState.STOPPED, "已停止", "启动采集", "start", True),
        (
            GlobalCaptureState.PARTIAL_ERROR,
            "部分异常",
            "停止采集",
            "stop",
            False,
        ),
        (GlobalCaptureState.ERROR, "错误", "停止并重置", "reset", True),
    ],
)
def test_toolbar_presents_global_state(
    qtbot,
    tmp_path: Path,
    state: GlobalCaptureState,
    status_text: str,
    button_text: str,
    mode: str,
    directory_enabled: bool,
) -> None:
    toolbar = CaptureToolbar(tmp_path)
    qtbot.addWidget(toolbar)

    toolbar.apply_state(state)

    assert toolbar.global_status.text() == "● {}".format(status_text)
    assert toolbar.global_status.property("status") == state.value
    assert toolbar.capture_button.text() == button_text
    assert toolbar.capture_button.property("mode") == mode
    assert toolbar.directory_edit.isEnabled() is directory_enabled
    assert toolbar.browse_button.isEnabled() is directory_enabled


def test_status_bar_presents_state_and_thread_activity(qtbot) -> None:
    status_bar = CaptureStatusBar(capacity=3)
    qtbot.addWidget(status_bar)

    status_bar.apply_state(GlobalCaptureState.PARTIAL_ERROR)
    status_bar.set_activity(active=2, capacity=3)

    assert status_bar.state_label.text() == "● 部分异常"
    assert status_bar.activity_label.text() == "线程池 2/3"


def test_camera_panel_owns_initial_and_follow_up_pull(qtbot) -> None:
    panel = CameraPanel(camera_id=1)
    qtbot.addWidget(panel)
    panel.show()

    with qtbot.waitSignal(panel.frame_requested):
        panel.apply_state(1, CameraState.RUNNING, "")

    successful_result = FrameResult(
        camera_id=1,
        generation=1,
        frame_number=1,
        rgb=np.zeros((90, 160, 3), dtype=np.uint8),
    )
    with qtbot.waitSignal(panel.frame_requested, timeout=1000):
        panel.show_result(successful_result)

    failed_result = FrameResult(
        camera_id=1,
        generation=1,
        frame_number=2,
        error="读取失败",
    )
    with qtbot.waitSignal(panel.frame_requested):
        panel.show_result(failed_result)

    assert panel.frame_value.text() == "0002"
    assert panel.error_value.text() == "读取失败"
