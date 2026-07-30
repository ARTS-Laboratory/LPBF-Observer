from __future__ import annotations

from typing import Optional

from camera import ArenaCamera
from display import Display
from frame import Frame
from metadata import MetadataWriter
from session import RecordingSession
from stats import RecordingStats
from writer_binary import BinaryRecorder
from writer_csv import CsvRecorder
from writer_video import VideoRecorder


class Recorder:
    """
    Coordinates the recording process.

    Responsibilities
    ----------------
    - Acquire frames from the camera
    - Send frames to all writers
    - Update recording statistics
    - Update metadata periodically
    - Display the live preview
    - Handle startup and shutdown

    This class intentionally contains very little implementation
    logic. Individual modules are responsible for their own work.
    """

    def __init__(
        self,
        *,
        camera: ArenaCamera,
        session: RecordingSession,
        video: VideoRecorder,
        binary: BinaryRecorder,
        csv: CsvRecorder,
        metadata: MetadataWriter,
        display: Display,
        stats: RecordingStats,
        metadata_update_interval: int = 100,
    ) -> None:

        self.camera = camera
        self.session = session

        self.video = video
        self.binary = binary
        self.csv = csv

        self.metadata = metadata
        self.display = display
        self.stats = stats

        self.metadata_update_interval = metadata_update_interval

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def run(self) -> None:
        """
        Execute the recording session.
        """

        self.before_recording()

        self.metadata.update(
            status="initializing",
            stats=self.stats,
        )

        try:

            self.camera.open()

            self.metadata.update(
                status="recording",
                stats=self.stats,
            )

            for frame in self.camera:

                self.on_frame(frame)

                if not self._process_frame(frame):
                    break

        finally:

            self.shutdown()

            self.after_recording()

    # ----------------------------------------------------------
    # Frame processing
    # ----------------------------------------------------------

    def _process_frame(self, frame: Frame) -> bool:
        """
        Process one acquired frame.

        Returns
        -------
        bool
            True to continue recording.
            False to stop.
        """

        if frame.incomplete:

            self.stats.drop(frame)

            self.csv.write(frame)

            return True

        payload_offset = self.binary.write(frame)

        self.video.write(frame.image)

        self.csv.write(
            frame,
            payload_offset,
        )

        self.stats.update(frame)

        if (
            self.stats.frame_count
            % self.metadata_update_interval
            == 0
        ):
            self.metadata.update(
                status="recording",
                stats=self.stats,
            )

        continue_recording = self.display.show(
            frame,
            self.stats,
        )

        return continue_recording

    # ----------------------------------------------------------
    # Shutdown
    # ----------------------------------------------------------

    def shutdown(self) -> None:
        """
        Close all resources.
        """

        try:
            self.video.close()
        except Exception:
            pass

        try:
            self.binary.close()
        except Exception:
            pass

        try:
            self.csv.close()
        except Exception:
            pass

        try:
            self.display.close()
        except Exception:
            pass

        try:
            self.camera.close()
        except Exception:
            pass

        self.stats.finish()

        self.metadata.update(
            status="completed",
            stats=self.stats,
        )

    # ----------------------------------------------------------
    # Hooks
    # ----------------------------------------------------------

    def before_recording(self) -> None:
        """
        Called before recording begins.

        Override in subclasses if needed.
        """
        pass

    def after_recording(self) -> None:
        """
        Called after recording ends.

        Override in subclasses if needed.
        """
        pass

    def on_frame(self, frame: Frame) -> None:
        """
        Called immediately after a frame is acquired.

        Override in subclasses to implement custom
        behavior (TCP streaming, ROS publishing,
        triggering, etc.).
        """
        pass