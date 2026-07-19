from pathlib import Path

from cameraviewer.main_window import MainWindow
from cameraviewer.styles import APP_STYLESHEET


def test_light_ui_geometry_focus_and_button_states(qtbot, tmp_path: Path) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.show()

    window.resize(1280, 720)
    qtbot.waitUntil(lambda: window._controls_widget.y() == 0)
    assert window.directory_label.buddy() is window.directory_edit
    assert window.directory_edit.nextInFocusChain() is window.browse_button
    assert window.browse_button.nextInFocusChain() is window.start_button

    for panel in window.panels.values():
        expected_height = round(panel.viewport.width() * 9 / 16)
        assert abs(panel.viewport.height() - expected_height) <= 1

    window.resize(1080, 680)
    qtbot.waitUntil(
        lambda: window._controls_widget.y() > window._brand_widget.y()
    )
    assert window._controls_widget.width() > window._brand_widget.width()

    assert 'QPushButton#startButton[mode="stop"]:hover' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="stop"]:pressed' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="reset"]:hover' in APP_STYLESHEET
    assert 'QPushButton#startButton[mode="reset"]:pressed' in APP_STYLESHEET
    assert "QLineEdit:disabled" in APP_STYLESHEET
