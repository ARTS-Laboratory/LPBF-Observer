from __future__ import annotations

from typing import Optional

from Functions.camera import ArenaCamera
from Functions.display import Display
from Functions.frame import Frame
from Functions.metadata import MetadataWriter
from Functions.session import RecordingSession
from Functions.stats import RecordingStats
from Functions.writer_binary import BinaryRecorder
from Functions.writer_csv import CsvRecorder
from Functions.writer_video import VideoRecorder

from Functions.udp_server import UDPStreamer


class Recorder:
    """
    Coordinates the recording process.
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
        display: Optional[Display] = None,
        udp_streamer: Optional[UDPStreamer] = None,
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
        self.udp_streamer = udp_streamer

        self.stats = stats

        self.metadata_update_interval = metadata_update_interval

        self.running = False

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def run(self) -> None:

        self.running = True

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

                if not self.running:
                    break

                self.on_frame(frame)

                if not self._process_frame(frame):
                    break

        finally:

            self.shutdown()

            self.after_recording()

    def stop(self) -> None:
        """
        Stops recording from another thread.
        Used by the TCP server.
        """

        self.running = False

    # ----------------------------------------------------------
    # Frame processing
    # ----------------------------------------------------------

    def _process_frame(self, frame: Frame) -> bool:

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

        #
        # Send only every 10th frame for the live UDP preview.
        #
        if (
            self.udp_streamer is not None
            and self.stats.frame_count % 10 == 0
        ):
            self.udp_streamer.send(frame)

        #
        # Local OpenCV preview
        #
        if self.display is not None:
            return self.display.show(
                frame,
                self.stats,
            )

        #
        # Headless mode
        #
        return True

    # ----------------------------------------------------------
    # Shutdown
    # ----------------------------------------------------------

    def shutdown(self) -> None:

        self.running = False

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

        if self.display is not None:
            try:
                self.display.close()
            except Exception:
                pass

        if self.udp_streamer is not None:
            try:
                self.udp_streamer.close()
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
        pass

    def after_recording(self) -> None:
        pass

    def on_frame(self, frame: Frame) -> None:
        pass