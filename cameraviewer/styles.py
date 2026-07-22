from PySide2.QtWidgets import QWidget


def refresh_style(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


LIGHT_PALETTE = {
    "canvas": "#F5F7F9",
    "surface": "#FFFFFF",
    "surface_subtle": "#F8FAFB",
    "surface_hover": "#F2F5F7",
    "surface_pressed": "#E8EEF2",
    "surface_disabled": "#EDF1F4",
    "viewport": "#0B1115",
    "viewport_border": "#26343C",
    "text": "#17212B",
    "text_muted": "#667784",
    "text_disabled": "#8D9AA3",
    "border": "#D9E1E7",
    "border_strong": "#AAB8C2",
    "primary": "#1769E0",
    "primary_hover": "#0E5FCB",
    "primary_pressed": "#0B50AD",
    "focus": "#2F80ED",
    "running": "#0C75D8",
    "stopped": "#9A6500",
    "partial": "#A56300",
    "error": "#C83F4C",
    "error_hover": "#AF333E",
    "error_pressed": "#922933",
    "reset": "#A86A12",
    "reset_hover": "#925A0C",
    "reset_pressed": "#784806",
}


APP_STYLESHEET = r"""
QMainWindow, QWidget#appRoot {
    background: %(canvas)s;
    color: %(text)s;
}

QWidget {
    color: %(text)s;
    font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", "Segoe UI", sans-serif;
    font-size: 13px;
}

QLabel#titleLabel {
    color: %(text)s;
    font-size: 28px;
    font-weight: 700;
}

QLabel#subtitleLabel, QLabel#fieldLabel {
    color: %(text_muted)s;
}

QLabel#subtitleLabel {
    font-size: 14px;
}

QLineEdit {
    min-height: 38px;
    padding: 0 12px;
    color: %(text)s;
    background: %(surface)s;
    border: 1px solid %(border_strong)s;
    border-radius: 6px;
    selection-color: white;
    selection-background-color: %(primary)s;
}

QLineEdit:hover {
    border-color: #82939F;
}

QLineEdit:focus {
    border: 2px solid %(focus)s;
}

QLineEdit:disabled {
    color: %(text_disabled)s;
    background: %(surface_disabled)s;
    border-color: %(border)s;
}

QPushButton {
    min-height: 38px;
    padding: 0 18px;
    color: %(text)s;
    background: %(surface)s;
    border: 1px solid %(border_strong)s;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton:hover {
    background: %(surface_hover)s;
    border-color: #82939F;
}

QPushButton:pressed {
    padding: 1px 18px 0 18px;
    background: %(surface_pressed)s;
    border-color: #758792;
}

QPushButton:focus {
    border: 2px solid %(focus)s;
}

QPushButton:disabled {
    color: %(text_disabled)s;
    background: %(surface_disabled)s;
    border-color: %(border)s;
}

QPushButton#startButton {
    color: white;
    background: %(primary)s;
    border-color: %(primary)s;
    font-size: 14px;
}

QPushButton#startButton:hover {
    background: %(primary_hover)s;
    border-color: %(primary_hover)s;
}

QPushButton#startButton:pressed {
    padding: 1px 18px 0 18px;
    background: %(primary_pressed)s;
    border-color: %(primary_pressed)s;
}

QPushButton#startButton:focus {
    border: 2px solid #0A4FAF;
}

QPushButton#startButton[mode="stop"] {
    background: %(error)s;
    border-color: %(error)s;
}

QPushButton#startButton[mode="stop"]:hover {
    background: %(error_hover)s;
    border-color: %(error_hover)s;
}

QPushButton#startButton[mode="stop"]:pressed {
    padding: 1px 18px 0 18px;
    background: %(error_pressed)s;
    border-color: %(error_pressed)s;
}

QPushButton#startButton[mode="stop"]:focus {
    border: 2px solid #7D1D27;
}

QPushButton#startButton[mode="reset"] {
    background: %(reset)s;
    border-color: %(reset)s;
}

QPushButton#startButton[mode="reset"]:hover {
    background: %(reset_hover)s;
    border-color: %(reset_hover)s;
}

QPushButton#startButton[mode="reset"]:pressed {
    padding: 1px 18px 0 18px;
    background: %(reset_pressed)s;
    border-color: %(reset_pressed)s;
}

QPushButton#startButton[mode="reset"]:focus {
    border: 2px solid #663C00;
}

QPushButton#startButton:disabled {
    color: %(text_disabled)s;
    background: %(surface_disabled)s;
    border-color: %(border)s;
}

QFrame#cameraPanel {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}

QFrame#cameraHeader {
    background: %(surface_subtle)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QLabel#cameraTitle {
    color: %(text)s;
    font-size: 17px;
    font-weight: 700;
}

QLabel#cameraState, QLabel#globalStatus {
    font-weight: 600;
}

QLabel#cameraState[status="idle"], QLabel#globalStatus[status="idle"] {
    color: %(text_muted)s;
}

QLabel#cameraState[status="running"], QLabel#globalStatus[status="running"] {
    color: %(running)s;
}

QLabel#cameraState[status="stopped"], QLabel#globalStatus[status="stopped"] {
    color: %(stopped)s;
}

QLabel#cameraState[status="partial"] , QLabel#globalStatus[status="partial"] {
    color: %(partial)s;
}

QLabel#cameraState[status="error"], QLabel#globalStatus[status="error"] {
    color: %(error)s;
}

QLabel#imageViewport {
    color: #9BAAB2;
    background: %(viewport)s;
    border: 1px solid %(viewport_border)s;
    border-radius: 4px;
    font-size: 15px;
}

QLabel#metaLabel {
    color: %(text_muted)s;
}

QLabel#metaValue {
    color: %(text)s;
}

QLabel#metaError {
    color: %(error)s;
}

QFrame#metaDivider {
    color: %(border)s;
    background: %(border)s;
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QStatusBar {
    color: %(text_muted)s;
    background: %(surface)s;
    border-top: 1px solid %(border)s;
}

QStatusBar::item {
    border: none;
}

QToolTip {
    color: %(text)s;
    background: %(surface)s;
    border: 1px solid %(border_strong)s;
}
""" % LIGHT_PALETTE
