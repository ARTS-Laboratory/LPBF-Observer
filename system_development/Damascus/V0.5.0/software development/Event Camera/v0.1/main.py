"""
Entry point for a standalone recording session.

Wires together a real ArenaCamera, a RecordingSession (which creates
the timestamped output folder), the three writers (video/binary/csv),
a MetadataWriter, a live Display, and RecordingStats into a Recorder,
then runs it until:

    - the user presses 'q' in the preview window,
    - RECORD_SECONDS in config.py elapses (if set), or
    - Ctrl+C is pressed.

Run with:
    python main.py
"""

from __future__ import annotations

import sys

from Functions import config
from Functions.camera import ArenaCamera
from Functions.display import Display
from Functions.metadata import MetadataWriter
from Functions.recorder import Recorder
from Functions.session import RecordingSession  
from Functions.stats import RecordingStats
from Functions.writer_binary import BinaryRecorder
from Functions.writer_csv import CsvRecorder
from Functions.writer_video import VideoRecorder


class DurationLimitedDisplay:
    """
    Wraps a Display so recording also stops once `max_seconds` of
    footage have been captured, in addition to the normal 'q' to quit.

    If `max_seconds` is None, this behaves exactly like the wrapped
    display, i.e. RECORD_SECONDS can be left unset in config.py to
    record indefinitely.
    """

    def __init__(self, display: Display, max_seconds: float | None) -> None:
        self._display = display
        self._max_seconds = max_seconds

    def show(self, frame, stats) -> bool:

        keep_going = self._display.show(frame, stats)

        if (
            self._max_seconds is not None
            and stats.elapsed_seconds >= self._max_seconds
        ):
            return False

        return keep_going

    def close(self) -> None:
        self._display.close()


def build_recorder() -> Recorder:
    """
    Construct every component and wire them into a ready-to-run Recorder.

    The camera is opened here (rather than left for Recorder.run() to
    do it) so its real, device-reported pixel format is known before
    MetadataWriter is constructed. ArenaCamera.open() is idempotent,
    so Recorder.run() opening it again later is a harmless no-op.
    """

    session = RecordingSession(output_folder=config.OUTPUT_FOLDER)

    camera = ArenaCamera()
    camera.open()

    received_format = camera.camera_info.get("pixel_format", "Unknown")

    video = VideoRecorder(
        session.video_path,
        fps=config.VIDEO_FPS,
        codec=config.VIDEO_CODEC,
    )

    binary = BinaryRecorder(session.binary_path)

    csv_writer = CsvRecorder(session.csv_path)

    metadata = MetadataWriter(
        session=session,
        camera_information=camera.camera_info,
        received_format=received_format,
        codec=config.VIDEO_CODEC,
        fps=config.VIDEO_FPS,
    )

    display = DurationLimitedDisplay(
        Display(),
        max_seconds=config.RECORD_SECONDS,
    )

    stats = RecordingStats()

    return Recorder(
        camera=camera,
        session=session,
        video=video,
        binary=binary,
        csv=csv_writer,
        metadata=metadata,
        display=display,
        stats=stats,
    )


def main() -> int:

    try:
        recorder = build_recorder()

    except Exception as exc:
        print(f"Could not start recording: {exc}", file=sys.stderr)
        return 1

    print(f"Recording to: {recorder.session.session_folder}")
    print("Press 'q' in the preview window to stop.")

    if config.RECORD_SECONDS is not None:
        print(f"Recording stops automatically after {config.RECORD_SECONDS:.0f}s.")

    try:
        recorder.run()

    except KeyboardInterrupt:
        print("\nStopping (Ctrl+C)...")

    except Exception as exc:
        print(f"Recording failed: {exc}", file=sys.stderr)
        return 1

    print(recorder.stats)
    print(f"Saved to: {recorder.session.session_folder}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
