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
import numpy as np
from Functions.frame import Frame


class UDPStreamer:
        """
        Sends JPEG-compressed preview frames over UDP.

        Packet format
        -------------

        4 bytes : JPEG size (unsigned int, big endian)

        N bytes : JPEG image

        Notes
        -----
        JPEG frames must fit inside one UDP datagram.

        If larger previews are needed later, this class
        can be extended to fragment frames into multiple
        packets.
        """

        def __init__(
                self,
                host: str = "127.0.0.1",
                port: int = 5100,
                jpeg_quality: int = 80,
                ):

                self.address = (host, port)

                self.jpeg_quality = int(jpeg_quality)
                
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

                Parameters
                ----------
                frame
                        Frame object received from the recorder.
                """

                if frame is None:
                        return

                if frame.image is None:
                        return

                success, encoded = cv2.imencode(
                        ".jpg",
                        frame.image,
                        (
                        cv2.IMWRITE_JPEG_QUALITY,
                        self.jpeg_quality,
                        ),
                )

                if not success:
                        return

                payload = encoded.tobytes()

                #
                # UDP packets larger than about 65 kB are invalid.
                #
                if len(payload) > 65000:
                        raise RuntimeError(
                        "JPEG preview exceeds UDP packet size."
                        )

                packet = (
                        struct.pack(">I", len(payload))
                        + payload
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