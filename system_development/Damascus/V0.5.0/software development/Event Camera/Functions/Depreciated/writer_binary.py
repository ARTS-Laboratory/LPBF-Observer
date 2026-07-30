from __future__ import annotations

import struct
from pathlib import Path

from frame import Frame


# ------------------------------------------------------------------
# Binary File Format
# ------------------------------------------------------------------

FILE_MAGIC = b"LUCDBUF1"
FILE_VERSION = 1

# File header
FILE_HEADER = struct.Struct("<8sI")

# Per-frame header
BLOCK_HEADER = struct.Struct("<QQQQIII")


class BinaryWriter:
    """
    Writes Arena frame payloads into a custom binary file.

    File layout:

        [File Header]

        Repeated:
            [Block Header]
            [Payload Bytes]
    """

    def __init__(self, path: Path):

        self.path = Path(path)

        self.file = self.path.open("wb")

        self.file.write(
            FILE_HEADER.pack(
                FILE_MAGIC,
                FILE_VERSION,
            )
        )

        self.frames_written = 0
        self.total_payload_bytes = 0

    # --------------------------------------------------------------

    def write(self, frame: Frame) -> int:
        """
        Write one frame.

        Returns
        -------
        int
            Byte offset where the payload begins.
        """

        if frame.incomplete:
            raise ValueError(
                "Cannot write an incomplete frame."
            )

        self.file.write(
            BLOCK_HEADER.pack(
                frame.frame_id,
                frame.device_timestamp,
                frame.host_timestamp_ns,
                len(frame.payload),
                frame.width,
                frame.height,
                frame.bits_per_pixel,
            )
        )

        payload_offset = self.file.tell()

        self.file.write(frame.payload)

        self.frames_written += 1
        self.total_payload_bytes += len(frame.payload)

        return payload_offset

    # --------------------------------------------------------------

    def flush(self):

        self.file.flush()

    # --------------------------------------------------------------

    def close(self):

        if not self.file.closed:
            self.file.close()

    # --------------------------------------------------------------

    @property
    def bytes_written(self) -> int:

        return self.total_payload_bytes

    # --------------------------------------------------------------

    @property
    def payload_megabytes(self) -> float:

        return self.total_payload_bytes / (1024 * 1024)

    # --------------------------------------------------------------

    def __enter__(self):

        return self

    # --------------------------------------------------------------

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.close()