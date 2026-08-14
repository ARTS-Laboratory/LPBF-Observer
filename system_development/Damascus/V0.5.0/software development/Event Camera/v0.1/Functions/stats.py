from __future__ import annotations

from dataclasses import dataclass, field
import time

from Functions.frame import Frame


@dataclass(slots=True)
class RecordingStats:
    """
    Tracks statistics for a recording session.

    This class owns all recording-related counters and timing.
    Writers and the recorder should read from this object instead
    of maintaining their own counters.
    """

    # ----------------------------------------------------------
    # Session timing
    # ----------------------------------------------------------

    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None

    # ----------------------------------------------------------
    # Frame statistics
    # ----------------------------------------------------------

    frame_count: int = 0
    dropped_frames: int = 0

    # ----------------------------------------------------------
    # Payload statistics
    # ----------------------------------------------------------

    total_payload_bytes: int = 0

    # ----------------------------------------------------------
    # Frame updates
    # ----------------------------------------------------------

    def update(self, frame: Frame) -> None:
        """
        Update statistics after successfully recording a frame.
        """

        self.frame_count += 1
        self.total_payload_bytes += len(frame.payload)

    def drop(self, frame: Frame | None = None) -> None:
        """
        Record an incomplete or dropped frame.
        """

        self.dropped_frames += 1

    def finish(self) -> None:
        """
        Mark the recording as complete.
        """

        if self.end_time is None:
            self.end_time = time.perf_counter()

    # ----------------------------------------------------------
    # Time properties
    # ----------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        """
        Recording duration in seconds.
        """

        end = self.end_time or time.perf_counter()
        return end - self.start_time

    # ----------------------------------------------------------
    # Throughput
    # ----------------------------------------------------------

    @property
    def fps(self) -> float:
        """
        Average recorded frames per second.
        """

        elapsed = self.elapsed_seconds

        if elapsed <= 0:
            return 0.0

        return self.frame_count / elapsed

    @property
    def payload_megabytes(self) -> float:
        """
        Total payload written in MB.
        """

        return self.total_payload_bytes / (1024 * 1024)

    @property
    def payload_megabytes_per_second(self) -> float:
        """
        Average payload throughput.
        """

        elapsed = self.elapsed_seconds

        if elapsed <= 0:
            return 0.0

        return self.payload_megabytes / elapsed

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------

    def summary(self) -> dict:
        """
        Return a summary suitable for metadata.json.
        """

        return {
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "frames_recorded": self.frame_count,
            "frames_dropped": self.dropped_frames,
            "average_fps": round(self.fps, 3),
            "payload_bytes": self.total_payload_bytes,
            "payload_megabytes": round(
                self.payload_megabytes,
                3,
            ),
            "payload_megabytes_per_second": round(
                self.payload_megabytes_per_second,
                3,
            ),
        }

    def __str__(self) -> str:
        return (
            f"RecordingStats("
            f"frames={self.frame_count}, "
            f"dropped={self.dropped_frames}, "
            f"fps={self.fps:.2f}, "
            f"MB={self.payload_megabytes:.2f}, "
            f"time={self.elapsed_seconds:.2f}s)"
        )