from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

import numpy as np


class CameraState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class GlobalCaptureState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    PARTIAL_ERROR = "partial"
    ERROR = "error"


def summarize_camera_states(states: Iterable[CameraState]) -> GlobalCaptureState:
    camera_states = tuple(states)
    if camera_states and all(state is CameraState.ERROR for state in camera_states):
        return GlobalCaptureState.ERROR
    if any(state is CameraState.ERROR for state in camera_states):
        return GlobalCaptureState.PARTIAL_ERROR
    if any(state is CameraState.RUNNING for state in camera_states):
        return GlobalCaptureState.RUNNING
    if camera_states and all(state is CameraState.STOPPED for state in camera_states):
        return GlobalCaptureState.STOPPED
    return GlobalCaptureState.IDLE


@dataclass(frozen=True)
class FrameResult:
    """单次后台任务的结果。

    ``generation`` 标识启停代次；旧代次结果不得显示，也不得推进游标。
    """

    camera_id: int
    generation: int
    frame_number: int
    rgb: Optional[np.ndarray] = field(default=None, repr=False)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.rgb is not None and not self.error
