from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class VideoRecorder:
    """
    Handles AVI recording using OpenCV.

    The writer is created lazily on the first frame so the
    frame size does not need to be known beforehand.
    """

    def __init__(
        self,
        output_path: Path,
        fps: float = 30.0,
        codec: str = "MJPG",
    ) -> None:

        self.output_path = Path(output_path)
        self.fps = fps
        self.codec = codec

        self._writer: cv2.VideoWriter | None = None
        self._frame_size: tuple[int, int] | None = None

    @property
    def is_open(self) -> bool:
        return self._writer is not None

    def _open(self, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]

        self._frame_size = (width, height)

        fourcc = cv2.VideoWriter_fourcc(*self.codec)

        self._writer = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            self.fps,
            self._frame_size,
            True,
        )

        if not self._writer.isOpened():
            raise RuntimeError(
                "Failed to create AVI file.\n"
                f"Path: {self.output_path}\n"
                f"Codec: {self.codec}"
            )

    def write(self, frame: np.ndarray) -> None:
        """
        Write one BGR frame.
        """

        if self._writer is None:
            self._open(frame)

        height, width = frame.shape[:2]

        if (width, height) != self._frame_size:
            raise ValueError(
                "Frame size changed during recording.\n"
                f"Expected {self._frame_size}, "
                f"received {(width, height)}."
            )

        self._writer.write(frame)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()