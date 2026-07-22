from typing import Dict, Iterable, Optional, Tuple

from PySide2.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .models import (
    CameraState,
    FrameResult,
    GlobalCaptureState,
    summarize_camera_states,
)
from .source import FrameSource, SequenceValidationError


DEFAULT_CAMERA_STARTS: Tuple[Tuple[int, int], ...] = (
    (1, 1),
    (2, 168),
    (3, 335),
)
DEFAULT_SHUTDOWN_TIMEOUT_MS = 2500


class _WorkerSignals(QObject):
    finished = Signal(object)


class _FrameWorker(QRunnable):
    """在工作线程中读取并处理一帧。"""

    def __init__(
        self,
        source: FrameSource,
        camera_id: int,
        generation: int,
        frame_number: int,
    ) -> None:
        super().__init__()
        self.source = source
        self.camera_id = camera_id
        self.generation = generation
        self.frame_number = frame_number
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            rgb = self.source.load_rgb(self.frame_number)
            result = FrameResult(
                camera_id=self.camera_id,
                generation=self.generation,
                frame_number=self.frame_number,
                rgb=rgb,
            )
        except Exception as exc:
            # 单帧异常作为采集结果返回，不能让工作线程终止应用。
            result = FrameResult(
                camera_id=self.camera_id,
                generation=self.generation,
                frame_number=self.frame_number,
                error="{}: {}".format(type(exc).__name__, exc),
            )
        self.signals.finished.emit(result)


class CameraController(QObject):
    """单路相机的 Pull 调度器。

    同一时刻最多存在一个在途任务；在途期间的重复需求合并为一个待提交请求。
    """

    state_changed = Signal(int, object, str)
    result_ready = Signal(object)
    activity_changed = Signal()

    def __init__(
        self,
        camera_id: int,
        start_cursor: int,
        thread_pool: QThreadPool,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self.start_cursor = start_cursor
        self.cursor = start_cursor
        self.thread_pool = thread_pool
        self.source: Optional[FrameSource] = None
        self.state = CameraState.IDLE
        self.error_message = ""
        self.consecutive_failures = 0

        self._generation = 0
        self._in_flight = False
        self._pending = False
        self._active_worker: Optional[_FrameWorker] = None

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    @property
    def pending(self) -> bool:
        return self._pending

    def start(self, source: FrameSource) -> None:
        if self.state is CameraState.ERROR:
            raise RuntimeError("错误相机必须先停止再重新启动")
        if self.state is CameraState.RUNNING:
            return

        self.source = source
        self._generation += 1
        self.consecutive_failures = 0
        self.error_message = ""
        self._set_state(CameraState.RUNNING)

    def stop(self) -> None:
        # 增加代次会作废迟到结果；在途任务仍可结束，但结果会被静默丢弃。
        self._generation += 1
        self._pending = False
        self.error_message = ""
        if self.state is not CameraState.STOPPED:
            self._set_state(CameraState.STOPPED)

    def set_error(self, message: str) -> None:
        self._generation += 1
        self._pending = False
        self.error_message = message
        self._set_state(CameraState.ERROR, message)

    @Slot()
    def request_frame(self) -> None:
        if self.state is not CameraState.RUNNING:
            return
        if self._in_flight:
            self._pending = True
            return
        self._submit()

    def _submit(self) -> None:
        source = self.source
        if source is None or self.state is not CameraState.RUNNING:
            return

        self._pending = False
        self._in_flight = True
        worker = _FrameWorker(
            source=source,
            camera_id=self.camera_id,
            generation=self._generation,
            frame_number=self.cursor,
        )
        self._active_worker = worker
        worker.signals.finished.connect(self._on_worker_finished)
        self.thread_pool.start(worker)
        self.activity_changed.emit()

    @Slot(object)
    def _on_worker_finished(self, result: FrameResult) -> None:
        self._release_worker()

        if not self._is_current_result(result):
            # 停止后立即重启时，新代次需求会等待旧任务结算后再提交。
            self._submit_pending_if_needed()
            return

        self._settle_current_result(result)

        # 成功帧由绘制事件请求下一帧，失败帧在结果交付后立即继续。
        self.result_ready.emit(result)
        self._submit_pending_if_needed()

    def _release_worker(self) -> None:
        self._in_flight = False
        self._active_worker = None
        self.activity_changed.emit()

    def _is_current_result(self, result: FrameResult) -> bool:
        return (
            result.generation == self._generation
            and self.state is CameraState.RUNNING
        )

    def _settle_current_result(self, result: FrameResult) -> None:
        source = self.source
        assert source is not None

        self.cursor = result.frame_number % source.frame_count + 1
        if result.ok:
            self.consecutive_failures = 0
            self.error_message = ""
        else:
            self.consecutive_failures += 1
            self.error_message = result.error
            if self.consecutive_failures >= source.frame_count:
                self._pending = False
                self._set_state(CameraState.ERROR, result.error)

    def _submit_pending_if_needed(self) -> None:
        if self._pending and not self._in_flight and self.state is CameraState.RUNNING:
            self._submit()

    def _set_state(self, state: CameraState, message: str = "") -> None:
        self.state = state
        self.state_changed.emit(self.camera_id, state, message)


class CaptureCoordinator(QObject):
    """统一管理三路控制器、线程池和全局采集状态。"""

    state_changed = Signal(object)
    activity_changed = Signal(int, int)

    def __init__(
        self,
        camera_starts: Iterable[Tuple[int, int]] = DEFAULT_CAMERA_STARTS,
        parent: Optional[QObject] = None,
        thread_pool: Optional[QThreadPool] = None,
    ) -> None:
        super().__init__(parent)
        starts = tuple(camera_starts)
        if not starts:
            raise ValueError("至少需要配置一路相机")

        self.thread_pool = thread_pool or QThreadPool(self)
        self.thread_pool.setMaxThreadCount(len(starts))
        self.controllers: Dict[int, CameraController] = {}

        for camera_id, start_cursor in starts:
            if camera_id in self.controllers:
                raise ValueError("相机 ID 不能重复：{}".format(camera_id))
            controller = CameraController(
                camera_id=camera_id,
                start_cursor=start_cursor,
                thread_pool=self.thread_pool,
                parent=self,
            )
            controller.state_changed.connect(self._on_controller_state_changed)
            controller.activity_changed.connect(self._emit_activity)
            self.controllers[camera_id] = controller

        self._state = self._summarize_state()

    @property
    def state(self) -> GlobalCaptureState:
        return self._state

    @property
    def capacity(self) -> int:
        return self.thread_pool.maxThreadCount()

    @property
    def active_tasks(self) -> int:
        return sum(controller.in_flight for controller in self.controllers.values())

    def start(self, source: FrameSource) -> None:
        try:
            source.validate()
        except SequenceValidationError as exc:
            self._set_all_error(str(exc))
            raise

        for controller in self.controllers.values():
            controller.start(source)

    def stop(self) -> None:
        for controller in self.controllers.values():
            controller.stop()

    def shutdown(self, timeout_ms: int = DEFAULT_SHUTDOWN_TIMEOUT_MS) -> bool:
        self.stop()
        self.thread_pool.clear()
        return self.thread_pool.waitForDone(timeout_ms)

    def _set_all_error(self, message: str) -> None:
        for controller in self.controllers.values():
            controller.set_error(message)

    def _summarize_state(self) -> GlobalCaptureState:
        return summarize_camera_states(
            controller.state for controller in self.controllers.values()
        )

    @Slot(int, object, str)
    def _on_controller_state_changed(
        self,
        camera_id: int,
        state: CameraState,
        message: str,
    ) -> None:
        del camera_id, state, message
        current_state = self._summarize_state()
        if current_state is self._state:
            return
        self._state = current_state
        self.state_changed.emit(current_state)

    @Slot()
    def _emit_activity(self) -> None:
        self.activity_changed.emit(self.active_tasks, self.capacity)
