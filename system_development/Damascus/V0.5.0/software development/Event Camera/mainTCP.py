from __future__ import annotations

import socket
import threading
import sys

from Functions import config

from Functions.camera import ArenaCamera
from Functions.session import RecordingSession
from Functions.stats import RecordingStats
from Functions.metadata import MetadataWriter

from Functions.writer_binary import BinaryRecorder
from Functions.writer_csv import CsvRecorder
from Functions.writer_video import VideoRecorder

from Functions.recorder import Recorder

from Functions.tcp_server import TCPServer
from Functions.udp_server import UDPStreamer


# -------------------------------------------------------
# Network configuration
# -------------------------------------------------------

HOST = "localhost"

COMMAND_PORT = 5000
VIDEO_PORT = 5100


# -------------------------------------------------------
# Build recorder
# -------------------------------------------------------

def build_recorder():

    session = RecordingSession(
        output_folder=config.OUTPUT_FOLDER
    )

    camera = ArenaCamera()
    camera.open()

    video = VideoRecorder(
        session.video_path,
        fps=config.VIDEO_FPS,
        codec=config.VIDEO_CODEC,
    )

    binary = BinaryRecorder(
        session.binary_path,
    )

    csv = CsvRecorder(
        session.csv_path,
    )

    metadata = MetadataWriter(
        session=session,
        camera_information=camera.camera_info,
        received_format=camera.camera_info.get(
            "pixel_format",
            "Unknown",
        ),
        codec=config.VIDEO_CODEC,
        fps=config.VIDEO_FPS,
    )

    stats = RecordingStats()

    udp_streamer = UDPStreamer(
        host=HOST,
        port=VIDEO_PORT,
    )

    recorder = Recorder(
        camera=camera,
        session=session,
        video=video,
        binary=binary,
        csv=csv,
        metadata=metadata,
        display=None,
        stats=stats,
        udp_streamer=udp_streamer,
    )

    return recorder


# -------------------------------------------------------
# Main
# -------------------------------------------------------

def main():

    try:

        recorder = build_recorder()

    except Exception as exc:

        print(
            f"Could not initialize recorder:\n{exc}",
            file=sys.stderr,
        )

        return 1

    tcp_server = TCPServer(
        recorder=recorder,
        host=HOST,
        port=COMMAND_PORT,
    )

    socket_thread = threading.Thread(
        target=tcp_server.run,
        daemon=True,
    )

    socket_thread.start()

    print()
    print("----------------------------------------")
    print(" Event Camera Server")
    print("----------------------------------------")
    print(f"Host          : {HOST}")
    print(f"Command Port  : {COMMAND_PORT}")
    print(f"Preview Port  : {VIDEO_PORT}")
    print("Waiting for LabVIEW...")
    print()

    socket_thread.join()

    recorder.camera.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())