from __future__ import annotations

import csv
from pathlib import Path

from frame import Frame


class CsvRecorder:
    """
    Writes one CSV row per acquired frame.
    """

    HEADER = (
        "frame_number",
        "frame_id",
        "device_timestamp",
        "host_timestamp_ns",
        "elapsed_seconds",
        "binary_payload_offset",
        "payload_size_bytes",
        "width",
        "height",
        "bits_per_pixel",
        "pixel_format",
        "incomplete",
    )

    def __init__(
        self,
        output_path: Path,
    ) -> None:

        self._file = output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        )

        self._writer = csv.writer(self._file)
        self._writer.writerow(self.HEADER)

    def write(
        self,
        frame: Frame,
        payload_offset: int | None,
    ) -> None:

        self._writer.writerow(
            (
                frame.number,
                frame.frame_id,
                frame.device_timestamp,
                frame.host_timestamp_ns,
                frame.elapsed_seconds,
                "" if payload_offset is None else payload_offset,
                len(frame.payload),
                frame.width,
                frame.height,
                frame.bits_per_pixel,
                frame.pixel_format,
                frame.incomplete,
            )
        )

    def flush(self) -> None:
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()