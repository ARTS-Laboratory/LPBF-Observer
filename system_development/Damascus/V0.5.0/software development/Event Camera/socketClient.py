import socket
import struct
import threading

import cv2
import numpy as np

HOST = "localhost"

COMMAND_PORT = 5000
VIDEO_PORT = 5100


# ----------------------------------------------------
# UDP Preview Thread
# ----------------------------------------------------

def preview_thread():

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("", VIDEO_PORT))

    print(f"Listening for preview frames on UDP port {VIDEO_PORT}")

    while True:

        packet, addr = udp.recvfrom(65535)

        if len(packet) < 4:
            continue

        frame_size = struct.unpack(">I", packet[:4])[0]
        jpeg = packet[4:]

        if len(jpeg) != frame_size:
            print("Incomplete packet received.")
            continue

        image = cv2.imdecode(
            np.frombuffer(jpeg, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        if image is None:
            continue

        cv2.imshow("Live Preview", image)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    udp.close()
    cv2.destroyAllWindows()


# ----------------------------------------------------
# TCP Command Console
# ----------------------------------------------------

with socket.create_connection((HOST, COMMAND_PORT)) as tcp:

    print("Connected to TCP server.")
    print()
    print("Commands:")
    print("  CONNECT")
    print("  START")
    print("  STOP")
    print("  QUIT")
    print()

    #
    # Start the preview thread.
    #
    thread = threading.Thread(
        target=preview_thread,
        daemon=True,
    )

    thread.start()

    #
    # Interactive command loop.
    #
    while True:

        command = input("> ").strip()

        if not command:
            continue

        tcp.sendall((command + "\n").encode("ascii"))

        reply = tcp.recv(1024).decode().strip()

        print(f"Server: {reply}")

        if command.upper() == "QUIT":
            break