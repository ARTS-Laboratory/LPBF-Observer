"""
streaming_server.py

Streams preview frames to a TCP client.

Packet format
-------------

1 byte  : Packet type
4 bytes : Payload size (big-endian uint32)
N bytes : JPEG image

Packet types
------------

2 : JPEG preview image
"""

from __future__ import annotations

import socket
import struct
import threading

import cv2

from Functions.frame import Frame


PACKET_IMAGE = 2


class StreamingServer:

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        jpeg_quality: int = 80,
        preview_width: int = 640,
        preview_height: int = 480,
    ):

        self.host = host
        self.port = port

        self.jpeg_quality = jpeg_quality

        self.preview_width = preview_width
        self.preview_height = preview_height

        self.server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        self.server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        self.server.bind((host, port))
        self.server.listen(1)

        self.client = None
        self.client_lock = threading.Lock()

        self.frames_sent = 0

        self.running = False

    # --------------------------------------------------

    @property
    def is_connected(self):

        return self.client is not None

    # --------------------------------------------------

    def wait_for_client(self):

        print(f"Waiting for client on {self.host}:{self.port}")

        client, address = self.server.accept()

        print(f"Client connected: {address}")

        with self.client_lock:
            self.client = client

    # --------------------------------------------------

    def send(self, frame: Frame | None):

        if frame is None:
            return

        if frame.image is None:
            return

        with self.client_lock:

            if self.client is None:
                return

            preview = cv2.resize(
                frame.image,
                (
                    self.preview_width,
                    self.preview_height,
                ),
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

            jpeg = encoded.tobytes()

            try:

                #
                # Send the frame length first (4 bytes),
                # then send the JPEG image.
                #
                header = struct.pack(">I", len(jpeg))

                self.client.sendall(header)
                self.client.sendall(jpeg)

                self.frames_sent += 1

            except (
                BrokenPipeError,
                ConnectionResetError,
                OSError,
            ):

                print("Client disconnected.")

                self._disconnect_client()

    # --------------------------------------------------

    def _disconnect_client(self):

        if self.client is not None:

            try:
                self.client.close()

            except Exception:
                pass

            self.client = None

    # --------------------------------------------------

    def close(self):

        self.running = False

        with self.client_lock:
            self._disconnect_client()

        self.server.close()