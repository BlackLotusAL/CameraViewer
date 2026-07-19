import threading

import numpy as np
from PySide2.QtCore import QThreadPool

from cameraviewer.capture import CameraController
from cameraviewer.models import CameraState
from cameraviewer.source import FrameSource


class SuccessfulSource(FrameSource):
    def __init__(self, frame_count: int = 5) -> None:
        self.frame_count = frame_count
        self.calls = []

    def validate(self) -> None:
        return None

    def load_rgb(self, frame_number: int) -> np.ndarray:
        self.calls.append(frame_number)
        return np.zeros((8, 12, 3), dtype=np.uint8)


class BlockingFirstSource(SuccessfulSource):
    def __init__(self) -> None:
        super().__init__(frame_count=5)
        self.first_started = threading.Event()
        self.release_first = threading.Event()

    def load_rgb(self, frame_number: int) -> np.ndarray:
        self.calls.append(frame_number)
        if len(self.calls) == 1:
            self.first_started.set()
            assert self.release_first.wait(2)
        return np.zeros((8, 12, 3), dtype=np.uint8)


class FailingSource(FrameSource):
    def __init__(self, frame_count: int = 2) -> None:
        self.frame_count = frame_count

    def validate(self) -> None:
        return None

    def load_rgb(self, frame_number: int) -> np.ndarray:
        raise IOError("broken {:04d}".format(frame_number))


def make_controller(source: FrameSource):
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    controller = CameraController(1, 1, pool)
    controller.configure_source(source)
    return controller, pool


def test_success_advances_cursor(qtbot) -> None:
    source = SuccessfulSource()
    controller, pool = make_controller(source)
    results = []
    controller.result_ready.connect(results.append)

    controller.start()
    controller.request_frame()
    qtbot.waitUntil(lambda: len(results) == 1)

    assert results[0].ok
    assert controller.cursor == 2
    assert source.calls == [1]
    assert pool.waitForDone(1000)


def test_stop_restart_discards_late_result_and_preserves_new_demand(qtbot) -> None:
    source = BlockingFirstSource()
    controller, pool = make_controller(source)
    results = []
    controller.result_ready.connect(results.append)

    controller.start()
    controller.request_frame()
    assert source.first_started.wait(1)

    controller.stop()
    controller.start()
    controller.request_frame()
    assert controller.pending

    source.release_first.set()
    qtbot.waitUntil(lambda: len(results) == 1, timeout=2000)

    assert results[0].frame_number == 1
    assert source.calls == [1, 1]
    assert controller.cursor == 2
    assert pool.waitForDone(1000)


def test_consecutive_failures_only_error_that_camera(qtbot) -> None:
    controller, pool = make_controller(FailingSource(frame_count=2))
    results = []
    controller.result_ready.connect(results.append)

    controller.start()
    controller.request_frame()
    qtbot.waitUntil(lambda: len(results) == 1)
    assert controller.state is CameraState.RUNNING
    assert controller.cursor == 2

    controller.request_frame()
    qtbot.waitUntil(lambda: controller.state is CameraState.ERROR)
    assert len(results) == 2
    assert controller.cursor == 1
    assert pool.waitForDone(1000)
