import argparse
from pathlib import Path
from typing import Optional, Sequence

import cv2
import numpy as np


DEFAULT_FRAME_COUNT = 500
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_JPEG_QUALITY = 90
GRID_STEP = 120


def build_frame(
    index: int,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> np.ndarray:
    phase = (index - 1) / DEFAULT_FRAME_COUNT
    frame = _build_gradient(width, height, phase)
    _draw_test_pattern(frame, phase)
    _draw_labels(frame, index)
    return frame


def _build_gradient(width: int, height: int, phase: float) -> np.ndarray:
    y, x = np.mgrid[0:height, 0:width]
    blue = 42 + 48 * (x / width) + 30 * np.sin(phase * np.pi * 2)
    green = 24 + 52 * (y / height) + 25 * np.sin((phase + 0.33) * np.pi * 2)
    red = 18 + 36 * ((x + y) / (width + height)) + 22 * np.sin(
        (phase + 0.66) * np.pi * 2
    )
    return np.dstack((blue, green, red)).clip(0, 255).astype(np.uint8)


def _draw_test_pattern(frame: np.ndarray, phase: float) -> None:
    height, width, _ = frame.shape
    grid_color = (72, 116, 142)
    for grid_x in range(0, width, GRID_STEP):
        cv2.line(frame, (grid_x, 0), (grid_x, height), grid_color, 1, cv2.LINE_AA)
    for grid_y in range(0, height, GRID_STEP):
        cv2.line(frame, (0, grid_y), (width, grid_y), grid_color, 1, cv2.LINE_AA)

    center = (width // 2, height // 2)
    radius = min(width, height) // 3
    accent = (
        int(150 + 80 * np.sin(phase * np.pi * 2)),
        int(170 + 70 * np.sin((phase + 0.33) * np.pi * 2)),
        int(190 + 60 * np.sin((phase + 0.66) * np.pi * 2)),
    )
    cv2.circle(frame, center, radius, accent, 4, cv2.LINE_AA)
    cv2.line(
        frame,
        (center[0] - radius, center[1]),
        (center[0] + radius, center[1]),
        accent,
        2,
    )
    cv2.line(
        frame,
        (center[0], center[1] - radius),
        (center[0], center[1] + radius),
        accent,
        2,
    )

    orbit_angle = phase * np.pi * 6
    marker = (
        int(center[0] + np.cos(orbit_angle) * radius * 0.72),
        int(center[1] + np.sin(orbit_angle) * radius * 0.72),
    )
    cv2.circle(frame, marker, 24, (235, 245, 255), -1, cv2.LINE_AA)

    bar_width = width // 10
    colors = [
        (235, 220, 60),
        (220, 80, 60),
        (70, 205, 90),
        (70, 180, 235),
        (210, 85, 220),
        (70, 70, 230),
    ]
    start_x = center[0] - len(colors) * bar_width // 2
    for offset, color in enumerate(colors):
        x1 = start_x + offset * bar_width
        cv2.rectangle(
            frame,
            (x1, height - 165),
            (x1 + bar_width, height - 95),
            color,
            -1,
        )

    cv2.rectangle(frame, (48, 42), (width - 48, height - 42), accent, 3)


def _draw_labels(frame: np.ndarray, index: int) -> None:
    height, width, _ = frame.shape
    text_color = (230, 240, 246)
    cv2.putText(
        frame,
        "CAMERAVIEWER / SIMULATED SOURCE",
        (78, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.25,
        text_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "FRAME {:04d}    {} x {}".format(index, width, height),
        (78, height - 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        text_color,
        2,
        cv2.LINE_AA,
    )


def write_jpeg(path: Path, frame: np.ndarray, quality: int) -> None:
    """通过 imencode 写入 JPEG，确保 Windows Unicode 路径可靠。"""

    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG 编码失败：{}".format(path))
    encoded.tofile(str(path))


def generate_sequence(
    output: Path,
    count: int = DEFAULT_FRAME_COUNT,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        path = output / "frame_{:04d}.jpg".format(index)
        write_jpeg(path, build_frame(index, width, height), quality)
        if index == 1 or index % 50 == 0 or index == count:
            print("已生成 {}/{}：{}".format(index, count, path.name), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 CameraViewer 本地图像序列")
    parser.add_argument("output", nargs="?", type=Path, default=Path("sample_frames"))
    parser.add_argument("--count", type=int, default=DEFAULT_FRAME_COUNT)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--quality", type=int, default=DEFAULT_JPEG_QUALITY)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    options = build_parser().parse_args(argv)
    if options.count <= 0 or options.width <= 0 or options.height <= 0:
        raise SystemExit("count、width 和 height 必须为正数")
    generate_sequence(
        output=options.output,
        count=options.count,
        width=options.width,
        height=options.height,
        quality=options.quality,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
