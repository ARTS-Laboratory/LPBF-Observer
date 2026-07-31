"""
tcp_server.py

Simple TCP command server for LabVIEW.

Supported commands
------------------
CONNECT
START
STOP
QUIT

All commands are ASCII strings terminated by '\n'.
"""

from __future__ import annotations

import socket
import threading


class TCPServer:

    def __init__(
        self,
        recorder,
        host: str = "0.0.0.0",
        port: int = 5000,
    ):

        self.recorder = recorder

        self.host = host
        self.port = port

        self.running = False

    # ---------------------------------------------------------

    def run(self):

        self.running = True

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as server:

            server.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )

            server.bind(
                (
                    self.host,
                    self.port,
                )
            )

            server.listen(1)

            print(
                f"TCP Server listening on "
                f"{self.host}:{self.port}"
            )

            while self.running:

                connection, address = server.accept()

                print(
                    f"Client connected: {address}"
                )

                thread = threading.Thread(
                    target=self.handle_client,
                    args=(connection,),
                    daemon=True,
                )

                thread.start()

    # ---------------------------------------------------------

    def handle_client(
        self,
        connection,
    ):

        with connection:

            while self.running:

                data = connection.recv(1024)

                if not data:
                    break

                command = (
                    data.decode()
                    .strip()
                    .upper()
                )

                print(
                    "Received:",
                    command,
                )

                if command == "CONNECT":

                    self.connect_camera(connection)

                elif command == "START":

                    self.start_recording(connection)

                elif command == "STOP":

                    self.stop_recording(connection)

                elif command == "QUIT":

                    self.quit(connection)

                    break

                else:

                    self.unknown(connection)

    # ---------------------------------------------------------

    def connect_camera(
        self,
        connection,
    ):

        try:

            self.recorder.camera.open()

            connection.sendall(
                b"OK CONNECTED\n"
            )

        except Exception as exc:

            connection.sendall(
                f"ERROR {exc}\n".encode()
            )

    # ---------------------------------------------------------

    def start_recording(
        self,
        connection,
    ):

        try:

            thread = threading.Thread(
                target=self.recorder.run,
                daemon=True,
            )

            thread.start()

            connection.sendall(
                b"OK RECORDING\n"
            )

        except Exception as exc:

            connection.sendall(
                f"ERROR {exc}\n".encode()
            )

    # ---------------------------------------------------------

    def stop_recording(
        self,
        connection,
    ):

        try:

            #
            # We'll add Recorder.stop()
            # later.
            #

            self.recorder.stop()

            connection.sendall(
                b"OK STOPPED\n"
            )

        except Exception as exc:

            connection.sendall(
                f"ERROR {exc}\n".encode()
            )

    # ---------------------------------------------------------

    def quit(
        self,
        connection,
    ):

        self.running = False

        try:

            self.recorder.stop()

        except Exception:

            pass

        connection.sendall(
            b"OK QUIT\n"
        )

    # ---------------------------------------------------------

    def unknown(
        self,
        connection,
    ):

        connection.sendall(
            b"UNKNOWN COMMAND\n"
        )