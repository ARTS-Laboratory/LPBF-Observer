import socket
import struct
import threading

import cv2
import numpy as np

HOST = "localhost"

COMMAND_PORT = 5000
STREAM_PORT = 5100


def recvall(sock, size):
    """Receive exactly size bytes."""

    data = b""

    while len(data) < size:

        packet = sock.recv(size - len(data))

        if not packet:
            return None

        data += packet

    return data


# ----------------------------------------------------
# Image Stream Thread
# ----------------------------------------------------

def stream_thread():

    with socket.create_connection((HOST, STREAM_PORT)) as stream:

        print(f"Connected to image stream ({HOST}:{STREAM_PORT})")

        while True:

            #
            # Read the 4-byte JPEG length.
            #
            header = recvall(stream, 4)

            if header is None:
                print("Image stream disconnected.")
                break

            frame_len = struct.unpack(">I", header)[0]

            #
            # Read the JPEG image.
            #
            payload = recvall(stream, frame_len)

            if payload is None:
                print("Failed to receive image.")
                break

            image = cv2.imdecode(
                np.frombuffer(payload, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )

            if image is None:
                print("Could not decode frame.")
                continue

            cv2.imshow("Live Preview", image)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()


# ----------------------------------------------------
# Command Connection
# ----------------------------------------------------

with socket.create_connection((HOST, COMMAND_PORT)) as command:

    print(f"Connected to command server ({HOST}:{COMMAND_PORT})")

    thread = threading.Thread(
        target=stream_thread,
        daemon=True,
    )

    thread.start()

    print()
    print("Commands")
    print("--------")
    print("START")
    print("STOP")
    print("QUIT")
    print()

    while True:

        cmd = input("> ").strip()

        if not cmd:
            continue

        command.sendall((cmd + "\n").encode("ascii"))

        reply = command.recv(1024).decode().strip()

        print(f"Server: {reply}")

        if cmd.upper() == "QUIT":
            break

cv2.destroyAllWindows()