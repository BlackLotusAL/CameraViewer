from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class CameraState(str, Enum):
    """A single camera's user-visible state."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class FrameResult:
    """Result produced by one worker task.

    ``generation`` identifies the current start/stop cycle. A result from an
    older generation is stale and must not be displayed or advance the cursor.
    """

    camera_id: int
    generation: int
    cursor: int
    frame_number: int
    rgb: Optional[np.ndarray] = field(default=None, repr=False)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.rgb is not None and not self.error
