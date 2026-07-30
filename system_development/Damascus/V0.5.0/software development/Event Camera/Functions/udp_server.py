"""
udp_streamer.py

Streams preview frames to LabVIEW over UDP.

Only the live preview is streamed.

The recorder remains responsible for recording the
AVI/BIN/CSV files.
"""

from __future__ import annotations

import socket
import struct

import cv2
from Functions.frame import Frame


class UDPStreamer:
    """
    Sends JPEG-compressed preview frames over UDP.

    Packet format
    -------------

    4 bytes : JPEG size (unsigned int, big endian)

    N bytes : JPEG image
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5100,
        jpeg_quality: int = 80,
        preview_width: int = 640,
        preview_height: int = 480,
    ):

        self.address = (host, port)

        self.jpeg_quality = int(jpeg_quality)

        self.preview_width = int(preview_width)
        self.preview_height = int(preview_height)

        self.socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        self.frames_sent = 0

    # ------------------------------------------------------

    def send(
        self,
        frame: Frame | None,
    ) -> None:
        """
        Send one preview frame to LabVIEW.
        """

        if frame is None:
            return

        if frame.image is None:
            return

        #
        # Resize preview for UDP streaming.
        # The original frame remains untouched for recording.
        #
        preview = cv2.resize(
            frame.image,
            (self.preview_width, self.preview_height),
            interpolation=cv2.INTER_AREA,
        )

        success, encoded = cv2.imencode(
            ".jpg",
            preview,
            (
                cv2.IMWRITE_JPEG_QUALITY,
                self.jpeg_quality,
            ),
        )

        if not success:
            return

        payload = encoded.tobytes()

        #
        # UDP packets larger than ~65 kB are invalid.
        # Skip the preview instead of crashing the recorder.
        #
        if len(payload) > 65000:
            print(
                f"Skipping preview frame "
                f"({len(payload)} bytes exceeds UDP limit)"
            )
            return

        packet = (
            struct.pack(">I", len(payload))
            + payload
        )

        print(
            f"Sending frame {self.frames_sent} "
            f"({len(payload)} bytes) "
            f"to {self.address}"
        )

        self.socket.sendto(
            packet,
            self.address,
        )

        self.frames_sent += 1

    # ------------------------------------------------------

    def close(self):

        self.socket.close()

    # ------------------------------------------------------

    def __enter__(self):

        return self

    # ------------------------------------------------------

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):

        self.close()