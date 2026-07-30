from __future__ import annotations

import cv2

from Functions.frame import Frame
from Functions.stats import RecordingStats


class Display:
    """
    Handles the live preview window.

    The displayed image is independent of the recorded video.
    Overlays are added only to the preview.
    """

    WINDOW_NAME = "LUCID Triton2 EVS - Combined Recording"

    def __init__(self) -> None:
        self._window_created = False

    def show(
        self,
        frame: Frame,
        stats: RecordingStats,
    ) -> bool:
        """
        Display the current frame.

        Returns
        -------
        bool
            True to continue recording.
            False if the user pressed Q.
        """

        display_frame = frame.image.copy()

        cv2.putText(
            display_frame,
            f"REC  {stats.elapsed_seconds:.1f} s",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            display_frame,
            f"Frames: {stats.frame_count}",
            (15, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow(
            self.WINDOW_NAME,
            display_frame,
        )

        self._window_created = True

        return (cv2.waitKey(1) & 0xFF) != ord("q")

    def close(self) -> None:

        if self._window_created:
            cv2.destroyWindow(self.WINDOW_NAME)
            self._window_created = False