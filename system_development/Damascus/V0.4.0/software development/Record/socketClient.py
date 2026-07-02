import socket
import struct
import cv2
import numpy as np

HOST = socket.gethostbyname(socket.gethostname())
videoPort = 5100

def recvall(sock, n):
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.connect((HOST, videoPort))
    print(f"Connected to video stream on {HOST}:{videoPort}")

    while True:
        header = recvall(client, 4)
        if not header:
            print("Server closed connection.")
            break

        frame_len = struct.unpack(">I", header)[0]
        payload = recvall(client, frame_len)
        if not payload:
            print("Failed to receive frame.")
            break

        frame_array = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

        if image is None:
            print("Could not decode frame.")
            continue

        cv2.imshow("Video Test", image)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cv2.destroyAllWindows()