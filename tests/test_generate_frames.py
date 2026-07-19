from pathlib import Path

import cv2
import numpy as np

from scripts.generate_frames import build_frame, generate_sequence


def test_build_frame_and_sequence_names(tmp_path: Path) -> None:
    frame = build_frame(7, width=320, height=180)
    assert frame.shape == (180, 320, 3)
    assert frame.dtype == np.uint8

    generate_sequence(tmp_path, count=3, width=320, height=180, quality=75)
    assert [path.name for path in sorted(tmp_path.glob("*.jpg"))] == [
        "frame_0001.jpg",
        "frame_0002.jpg",
        "frame_0003.jpg",
    ]

    encoded = np.fromfile(str(tmp_path / "frame_0002.jpg"), dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    assert decoded.shape == (180, 320, 3)
