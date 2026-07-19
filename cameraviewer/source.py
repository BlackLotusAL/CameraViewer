from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import cv2
import numpy as np


class SequenceValidationError(ValueError):
    """Raised when the configured image sequence is incomplete."""


class FrameSource(ABC):
    """Replaceable image source used by the capture scheduler."""

    frame_count: int

    @abstractmethod
    def validate(self) -> None:
        """Validate source configuration without decoding a frame."""

    @abstractmethod
    def load_rgb(self, frame_number: int) -> np.ndarray:
        """Read, decode and process one frame in a worker thread."""


class ImageSequenceSource(FrameSource):
    """Local JPEG sequence source with Unicode-path support."""

    def __init__(self, directory: Path, frame_count: int = 500) -> None:
        self.directory = Path(directory).expanduser()
        self.frame_count = frame_count

    def frame_path(self, frame_number: int) -> Path:
        return self.directory / "frame_{:04d}.jpg".format(frame_number)

    def validate(self) -> None:
        if not self.directory.is_dir():
            raise SequenceValidationError("图像目录不存在或不是文件夹：{}".format(self.directory))

        missing: List[int] = [
            number
            for number in range(1, self.frame_count + 1)
            if not self.frame_path(number).is_file()
        ]
        if missing:
            sample = "、".join("{:04d}".format(number) for number in missing[:5])
            suffix = " 等" if len(missing) > 5 else ""
            raise SequenceValidationError(
                "图像序列不完整，缺少 {} 帧（{}{}）".format(len(missing), sample, suffix)
            )

    def load_rgb(self, frame_number: int) -> np.ndarray:
        path = self.frame_path(frame_number)

        # np.fromfile + cv2.imdecode works with Chinese and other non-ASCII
        # paths on Windows, unlike some cv2.imread builds.
        encoded = np.fromfile(str(path), dtype=np.uint8)
        if encoded.size == 0:
            raise IOError("无法读取图像文件：{}".format(path.name))

        bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("图像解码失败：{}".format(path.name))

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return np.ascontiguousarray(rgb)
