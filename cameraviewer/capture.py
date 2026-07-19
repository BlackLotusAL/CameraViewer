from typing import Optional

from PySide2.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .models import CameraState, FrameResult
from .source import FrameSource


class _WorkerSignals(QObject):
    finished = Signal(object)


class FrameWorker(QRunnable):
    """Read and process exactly one frame outside the GUI thread."""

    def __init__(
        self,
        source: FrameSource,
        camera_id: int,
        generation: int,
        cursor: int,
    ) -> None:
        super().__init__()
        self.source = source
        self.camera_id = camera_id
        self.generation = generation
        self.cursor = cursor
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            rgb = self.source.load_rgb(self.cursor)
            result = FrameResult(
                camera_id=self.camera_id,
                generation=self.generation,
                cursor=self.cursor,
                frame_number=self.cursor,
                rgb=rgb,
            )
        except Exception as exc:  # A bad frame is data, not an app crash.
            result = FrameResult(
                camera_id=self.camera_id,
                generation=self.generation,
                cursor=self.cursor,
                frame_number=self.cursor,
                error="{}: {}".format(type(exc).__name__, exc),
            )
        self.signals.finished.emit(result)


class CameraController(QObject):
    """Single-camera pull scheduler.

    There is never more than one active worker. Repeated demand while a worker
    is active is merged into one ``pending`` flag.
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
        self._active_worker: Optional[FrameWorker] = None

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    @property
    def pending(self) -> bool:
        return self._pending

    def configure_source(self, source: FrameSource) -> None:
        self.source = source

    def start(self) -> None:
        if self.source is None:
            raise RuntimeError("尚未配置图像源")
        if self.state is CameraState.ERROR:
            raise RuntimeError("错误相机必须先停止再重新启动")
        if self.state is CameraState.RUNNING:
            return

        self._generation += 1
        self.consecutive_failures = 0
        self.error_message = ""
        self._set_state(CameraState.RUNNING)

    def stop(self) -> None:
        # Changing generation invalidates a late worker result. The running
        # worker is allowed to finish; its result will be silently discarded.
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
        if self.source is None or self.state is not CameraState.RUNNING:
            return

        self._pending = False
        self._in_flight = True
        worker = FrameWorker(
            source=self.source,
            camera_id=self.camera_id,
            generation=self._generation,
            cursor=self.cursor,
        )
        self._active_worker = worker
        worker.signals.finished.connect(self._on_worker_finished)
        self.thread_pool.start(worker)
        self.activity_changed.emit()

    @Slot(object)
    def _on_worker_finished(self, result: FrameResult) -> None:
        self._in_flight = False
        self._active_worker = None
        self.activity_changed.emit()

        is_current = (
            result.generation == self._generation
            and self.state is CameraState.RUNNING
        )
        if not is_current:
            # A stop/start may have queued fresh demand while an old worker was
            # still settling. Preserve that demand and submit it now.
            self._submit_pending_if_needed()
            return

        self.cursor = result.cursor % self.source.frame_count + 1  # type: ignore[union-attr]
        if result.ok:
            self.consecutive_failures = 0
            self.error_message = ""
        else:
            self.consecutive_failures += 1
            self.error_message = result.error
            if self.consecutive_failures >= self.source.frame_count:  # type: ignore[union-attr]
                self._pending = False
                self._set_state(CameraState.ERROR, result.error)

        # Slots update the View synchronously in the GUI thread. A successful
        # frame requests again from paintEvent; a failure requests immediately.
        self.result_ready.emit(result)
        self._submit_pending_if_needed()

    def _submit_pending_if_needed(self) -> None:
        if self._pending and not self._in_flight and self.state is CameraState.RUNNING:
            self._submit()

    def _set_state(self, state: CameraState, message: str = "") -> None:
        self.state = state
        self.state_changed.emit(self.camera_id, state, message)
