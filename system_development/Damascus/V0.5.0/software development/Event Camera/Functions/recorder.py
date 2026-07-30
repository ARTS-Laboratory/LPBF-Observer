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

from Functions.streaming_server import StreamingServer


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
        streaming_server: Optional[StreamingServer] = None,
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
        self.streaming_server = streaming_server

        self.stats = stats

        self.metadata_update_interval = metadata_update_interval

        self.running = False

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def run(self) -> None:

        print("Recorder.run() started")

        self.running = True

        self.before_recording()

        self.metadata.update(
            status="initializing",
            stats=self.stats,
        )

        try:

            print("Opening camera...")
            self.camera.open()
            print("Camera opened.")

            self.metadata.update(
                status="recording",
                stats=self.stats,
            )

            print("Entering acquisition loop...")

            for frame in self.camera:

                if not self.running:
                    print("Recording stopped (running == False)")
                    break

                self.on_frame(frame)

                keep_going = self._process_frame(frame)


                if not keep_going:
                    print("Recorder requested to stop.")
                    break

            print("Exited acquisition loop.")

        except Exception as exc:

            print(f"Exception inside Recorder.run(): {exc}")
            raise

        finally:

            print("Running shutdown()")
            self.shutdown()

            print("Running after_recording()")
            self.after_recording()

            print("Recorder.run() finished")

    '''def run(self) -> None:

        self.running = True

        self.before_recording()

        self.metadata.update(
            status="initializing",
            stats=self.stats,
        )

        try:

            self.camera.open()
            print("Camera opened")

            self.metadata.update(
                status="recording",
                stats=self.stats,
            )

            print("Starting acquisition loop")
            for frame in self.camera:
                print(f"Frame {frame.number}")
                if not self.running:
                    break

                self.on_frame(frame)

                if not self._process_frame(frame):
                    break

        finally:

            self.shutdown()

            self.after_recording()'''

    def stop(self) -> None:
        """
        Stops recording from another thread.
        """

        self.running = False

    # ----------------------------------------------------------
    # Frame processing
    # ----------------------------------------------------------

    def _process_frame(
        self,
        frame: Frame,
    ) -> bool:

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
        # Send preview over TCP.
        #
        if (
            self.streaming_server is not None
            and self.stats.frame_count % 0.05 == 0
        ):
            self.streaming_server.send(frame)

        #
        # Local OpenCV preview
        #
        if self.display is not None:
            return self.display.show(
                frame,
                self.stats,
            )

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

        if self.streaming_server is not None:
            try:
                self.streaming_server.close()
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

    def on_frame(
        self,
        frame: Frame,
    ) -> None:
        pass