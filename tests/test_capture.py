import threading

import numpy as np
import pytest
from PySide2.QtCore import QThreadPool

from cameraviewer.capture import CameraController, CaptureCoordinator
from cameraviewer.models import CameraState, GlobalCaptureState
from cameraviewer.source import FrameSource, SequenceValidationError


class SuccessfulSource(FrameSource):
    def __init__(self, frame_count: int = 5) -> None:
        self.frame_count = frame_count
        self.calls = []
        self.validation_count = 0

    def validate(self) -> None:
        self.validation_count += 1

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


class InvalidSource(FrameSource):
    frame_count = 5

    def validate(self) -> None:
        raise SequenceValidationError("图像序列不可用")

    def load_rgb(self, frame_number: int) -> np.ndarray:
        raise AssertionError("验证失败后不应读取图像")


def make_controller():
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    return CameraController(1, 1, pool), pool


def test_success_advances_cursor(qtbot) -> None:
    source = SuccessfulSource()
    controller, pool = make_controller()
    results = []
    controller.result_ready.connect(results.append)

    controller.start(source)
    controller.request_frame()
    qtbot.waitUntil(lambda: len(results) == 1)

    assert results[0].ok
    assert controller.cursor == 2
    assert source.calls == [1]
    assert pool.waitForDone(1000)


def test_repeated_demand_is_merged_into_one_pending_request(qtbot) -> None:
    source = BlockingFirstSource()
    controller, pool = make_controller()
    results = []
    controller.result_ready.connect(results.append)

    controller.start(source)
    controller.request_frame()
    assert source.first_started.wait(1)

    for _ in range(5):
        controller.request_frame()
    assert controller.pending

    source.release_first.set()
    qtbot.waitUntil(lambda: len(results) == 2, timeout=2000)

    assert source.calls == [1, 2]
    assert not controller.pending
    assert pool.waitForDone(1000)


def test_stop_restart_discards_late_result_and_preserves_new_demand(qtbot) -> None:
    source = BlockingFirstSource()
    controller, pool = make_controller()
    results = []
    controller.result_ready.connect(results.append)

    controller.start(source)
    controller.request_frame()
    assert source.first_started.wait(1)

    controller.stop()
    controller.start(source)
    controller.request_frame()
    assert controller.pending

    source.release_first.set()
    qtbot.waitUntil(lambda: len(results) == 1, timeout=2000)

    assert results[0].frame_number == 1
    assert source.calls == [1, 1]
    assert controller.cursor == 2
    assert pool.waitForDone(1000)


def test_consecutive_failures_only_error_that_camera(qtbot) -> None:
    source = FailingSource(frame_count=2)
    controller, pool = make_controller()
    results = []
    controller.result_ready.connect(results.append)

    controller.start(source)
    controller.request_frame()
    qtbot.waitUntil(lambda: len(results) == 1)
    assert controller.state is CameraState.RUNNING
    assert controller.cursor == 2

    controller.request_frame()
    qtbot.waitUntil(lambda: controller.state is CameraState.ERROR)
    assert len(results) == 2
    assert controller.cursor == 1
    assert pool.waitForDone(1000)


def test_coordinator_validates_once_and_starts_all_cameras() -> None:
    source = SuccessfulSource()
    coordinator = CaptureCoordinator()

    coordinator.start(source)

    assert source.validation_count == 1
    assert coordinator.state is GlobalCaptureState.RUNNING
    assert [controller.cursor for controller in coordinator.controllers.values()] == [
        1,
        168,
        335,
    ]
    assert all(
        controller.state is CameraState.RUNNING
        for controller in coordinator.controllers.values()
    )
    assert coordinator.shutdown(1000)


def test_coordinator_sets_all_cameras_to_error_when_validation_fails() -> None:
    coordinator = CaptureCoordinator()

    with pytest.raises(SequenceValidationError, match="图像序列不可用"):
        coordinator.start(InvalidSource())

    assert coordinator.state is GlobalCaptureState.ERROR
    assert all(
        controller.state is CameraState.ERROR
        for controller in coordinator.controllers.values()
    )
    assert coordinator.shutdown(1000)


def test_coordinator_survives_fifty_start_stop_cycles(qtbot) -> None:
    source = SuccessfulSource(frame_count=500)
    coordinator = CaptureCoordinator()

    for _ in range(50):
        coordinator.start(source)
        for controller in coordinator.controllers.values():
            controller.request_frame()
        qtbot.waitUntil(lambda: coordinator.active_tasks == 0, timeout=2000)
        coordinator.stop()

    assert coordinator.state is GlobalCaptureState.STOPPED
    assert all(
        not controller.in_flight and not controller.pending
        for controller in coordinator.controllers.values()
    )
    assert coordinator.shutdown(1000)
