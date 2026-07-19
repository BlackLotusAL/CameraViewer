from pathlib import Path

import cv2
import numpy as np
import pytest

from cameraviewer.source import ImageSequenceSource, SequenceValidationError


def write_test_jpeg(path: Path, bgr: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".jpg", bgr)
    assert ok
    encoded.tofile(str(path))


def test_unicode_directory_validates_and_loads_rgb(tmp_path: Path) -> None:
    directory = tmp_path / "中文 图像_é"
    directory.mkdir()
    bgr = np.zeros((12, 20, 3), dtype=np.uint8)
    bgr[:, :] = (10, 30, 220)
    for frame_number in range(1, 4):
        write_test_jpeg(directory / "frame_{:04d}.jpg".format(frame_number), bgr)

    source = ImageSequenceSource(directory, frame_count=3)
    source.validate()
    rgb = source.load_rgb(2)

    assert rgb.shape == (12, 20, 3)
    assert rgb.flags.c_contiguous
    assert int(rgb[0, 0, 0]) > int(rgb[0, 0, 2])


def test_validate_reports_incomplete_sequence(tmp_path: Path) -> None:
    write_test_jpeg(
        tmp_path / "frame_0001.jpg",
        np.zeros((4, 4, 3), dtype=np.uint8),
    )
    source = ImageSequenceSource(tmp_path, frame_count=3)

    with pytest.raises(SequenceValidationError, match="缺少 2 帧"):
        source.validate()
