import pytest

from cameraviewer.models import (
    CameraState,
    GlobalCaptureState,
    summarize_camera_states,
)


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ([], GlobalCaptureState.IDLE),
        ([CameraState.IDLE] * 3, GlobalCaptureState.IDLE),
        ([CameraState.STOPPED] * 3, GlobalCaptureState.STOPPED),
        ([CameraState.RUNNING] * 3, GlobalCaptureState.RUNNING),
        (
            [CameraState.ERROR, CameraState.RUNNING, CameraState.RUNNING],
            GlobalCaptureState.PARTIAL_ERROR,
        ),
        ([CameraState.ERROR] * 3, GlobalCaptureState.ERROR),
    ],
)
def test_summarize_camera_states(states, expected) -> None:
    assert summarize_camera_states(states) is expected
