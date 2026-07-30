"""
Exercises the full Recorder pipeline with a fake camera and a fake
display, standing in for the real ArenaCamera (needs hardware + the
proprietary arena_api package) and the real cv2.imshow preview window
(needs a display).

Everything else (Frame, session, stats, all three writers, metadata,
and Recorder itself) runs for real.
"""

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np

from frame import Frame
from session import RecordingSession
from stats import RecordingStats
from writer_binary import BinaryRecorder
from writer_csv import CsvRecorder
from writer_video import VideoRecorder
from metadata import MetadataWriter
from recorder import Recorder


class FakeCamera:
    """Mimics ArenaCamera's interface using synthetic frames."""

    def __init__(self, num_good=8, num_bad=2):
        self.num_good = num_good
        self.num_bad = num_bad
        self._counter = 0
        self._emitted = 0
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def __iter__(self):
        return self

    def __next__(self):
        total = self.num_good + self.num_bad
        if self._emitted >= total:
            raise StopIteration

        self._counter += 1
        self._emitted += 1

        # Every 4th frame is "incomplete" to exercise that path too.
        incomplete = (self._emitted % 4 == 0) and (
            self._emitted <= self.num_bad * 4
        )

        if incomplete:
            frame = Frame(
                image=None,
                payload=b"",
                frame_id=self._counter,
                number=self._counter,
                device_timestamp=self._counter * 1000,
                host_timestamp_ns=self._counter * 1_000_000_000,
                width=64,
                height=48,
                bits_per_pixel=24,
                pixel_format="BGR8",
                incomplete=True,
            )
        else:
            image = np.full((48, 64, 3), fill_value=self._counter % 255, dtype=np.uint8)
            frame = Frame(
                image=image,
                payload=image.tobytes(),
                frame_id=self._counter,
                number=self._counter,
                device_timestamp=self._counter * 1000,
                host_timestamp_ns=self._counter * 1_000_000_000,
                width=64,
                height=48,
                bits_per_pixel=24,
                pixel_format="BGR8",
                incomplete=False,
            )

        return frame


class FakeDisplay:
    """Stands in for the real cv2-window based Display."""

    def __init__(self):
        self.shown = 0
        self.closed = False

    def show(self, frame, stats):
        self.shown += 1
        return True  # never request an early stop

    def close(self):
        self.closed = True


def main():
    tmp_dir = Path(tempfile.mkdtemp(prefix="recorder_test_"))

    try:
        session = RecordingSession(output_folder=tmp_dir)

        camera = FakeCamera(num_good=8, num_bad=2)

        video = VideoRecorder(session.video_path, fps=10.0, codec="MJPG")
        binary = BinaryRecorder(session.binary_path)
        csv_writer = CsvRecorder(session.csv_path)

        metadata = MetadataWriter(
            session=session,
            camera_information={"vendor": "Fake", "model": "TestCam"},
            received_format="BGR8",
            codec="MJPG",
            fps=10.0,
        )

        display = FakeDisplay()
        stats = RecordingStats()

        recorder = Recorder(
            camera=camera,
            session=session,
            video=video,
            binary=binary,
            csv=csv_writer,
            metadata=metadata,
            display=display,
            stats=stats,
            metadata_update_interval=3,
        )

        recorder.run()

        # ---- Assertions ----

        assert camera.opened and camera.closed, "camera lifecycle broken"
        assert display.closed, "display was not closed"

        assert stats.frame_count == 8, f"expected 8 good frames, got {stats.frame_count}"
        assert stats.dropped_frames == 2, f"expected 2 dropped frames, got {stats.dropped_frames}"

        assert session.video_path.exists(), "video file missing"
        assert session.binary_path.exists(), "binary file missing"
        assert session.csv_path.exists(), "csv file missing"
        assert session.metadata_path.exists(), "metadata file missing"

        csv_text = session.csv_path.read_text()
        rows = csv_text.strip().splitlines()
        assert len(rows) == 1 + 10, f"expected header + 10 rows, got {len(rows)}"

        meta = json.loads(session.metadata_path.read_text())
        assert meta["status"] == "completed"
        assert meta["stats"]["frames_recorded"] == 8
        assert meta["stats"]["frames_dropped"] == 2
        assert meta["camera"]["model"] == "TestCam"

        print("ALL CHECKS PASSED")
        print(json.dumps(meta, indent=2))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
