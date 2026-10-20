"""Lightweight recorder-side telemetry for Lucid EVS streams.

Write one row every ``sample_interval_s`` seconds while recording.  The CSV is
deliberately separate from the event H5 file so diagnostic writes do not alter
the event dataset or require HDF5 access during plotting.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any


class StreamTelemetry:
    """Periodically record camera, link, and recorder throughput statistics."""

    FIELDNAMES = (
        "elapsed_seconds",
        "camera_event_rate_ev_s",
        "gvsp_frame_rate",
        "link_throughput_B_s",
        "recorded_event_rate_ev_s",
        "total_events",
        "incomplete_buffers",
        "get_buffer_errors",
        "host_payload_rate_B_s",
        "total_payload_bytes",
    )

    def __init__(
        self,
        csv_path: str | Path,
        *,
        sample_interval_s: float = 0.25,
    ) -> None:
        if sample_interval_s <= 0:
            raise ValueError("sample_interval_s must be greater than zero")

        self.path = Path(csv_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDNAMES)
        self._writer.writeheader()
        self._file.flush()

        self.sample_interval_s = float(sample_interval_s)
        self._start_time = time.monotonic()
        self._last_sample_time = self._start_time
        self._last_total_events = 0
        self._last_total_payload_bytes = 0

    @staticmethod
    def _read_node(tl_stream: Any, node_name: str) -> float | None:
        """Return a numeric stream-node value, or None when unavailable."""
        try:
            return float(tl_stream[node_name].value)
        except Exception:
            return None

    def sample(
        self,
        tl_stream: Any,
        *,
        total_events: int,
        incomplete_buffers: int,
        get_buffer_errors: int,
        total_payload_bytes: int,
    ) -> bool:
        """Write a telemetry row when the sampling interval has elapsed.

        Returns True when a row was written and False otherwise.
        """
        now = time.monotonic()
        elapsed_since_last = now - self._last_sample_time

        if elapsed_since_last < self.sample_interval_s:
            return False

        elapsed_seconds = now - self._start_time
        recorded_event_rate = (
            (int(total_events) - self._last_total_events) / elapsed_since_last
        )

        host_payload_rate = (
            int(total_payload_bytes) - self._last_total_payload_bytes
        ) / elapsed_since_last

        self._writer.writerow(
            {
                "elapsed_seconds": f"{elapsed_seconds:.6f}",
                "camera_event_rate_ev_s": self._read_node(
                    tl_stream, "StreamEvsEventRate"
                ),
                "gvsp_frame_rate": self._read_node(
                    tl_stream, "StreamEvsGvspFrameRate"
                ),
                "link_throughput_B_s": self._read_node(
                    tl_stream, "StreamEvsLinkThroughput"
                ),
                "recorded_event_rate_ev_s": f"{recorded_event_rate:.6f}",
                "total_events": int(total_events),
                "incomplete_buffers": int(incomplete_buffers),
                "get_buffer_errors": int(get_buffer_errors),
                "host_payload_rate_B_s": f"{host_payload_rate:.6f}",
                "total_payload_bytes": int(total_payload_bytes),
            }
        )
        self._file.flush()

        self._last_sample_time = now
        self._last_total_payload_bytes = int(total_payload_bytes)
        self._last_total_events = int(total_events)
        return True

    def close(self) -> None:
        """Close the telemetry CSV safely."""
        if not self._file.closed:
            self._file.close()
