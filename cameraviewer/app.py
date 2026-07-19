import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from PySide2.QtCore import QCoreApplication, Qt
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QApplication

from .main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CameraViewer 三路异步采集 Demo")
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=Path.cwd() / "sample_frames",
        help="包含 frame_0001.jpg 至 frame_0500.jpg 的目录",
    )
    return parser


def create_application(argv: Sequence[str]) -> QApplication:
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(list(argv))
    app.setApplicationName("CameraViewer")
    app.setOrganizationName("CameraViewer Demo")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    return app


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    options = build_parser().parse_args(arguments)

    app = create_application([sys.argv[0]] + arguments)
    window = MainWindow(options.image_dir)
    window.show()
    return app.exec_()
