from __future__ import annotations

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
from Functions.streaming_server import StreamingServer


# -------------------------------------------------------
# Network configuration
# -------------------------------------------------------

HOST = "localhost"

COMMAND_PORT = 5000
STREAM_PORT = 5100


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

    #
    # Image streaming server
    #
    streaming_server = StreamingServer(
        host=HOST,
        port=STREAM_PORT,
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
        streaming_server=streaming_server,
    )

    #
    # Command server. Its "START"/"STOP" handlers must call
    # recorder.begin_recording() / recorder.end_recording() —
    # NOT recorder.run(), which is already running continuously
    # below, and NOT recorder.stop(), which is a full shutdown.
    #
    tcp_server = TCPServer(
        recorder=recorder,
        host=HOST,
        port=COMMAND_PORT,
    )

    return recorder, tcp_server, streaming_server


# -------------------------------------------------------
# Main
# -------------------------------------------------------

def main():

    try:

        recorder, tcp_server, streaming_server = build_recorder()

    except Exception as exc:

        print(
            f"Could not initialize recorder:\n{exc}",
            file=sys.stderr,
        )

        return 1

    #
    # Acquisition + live streaming starts immediately, independent
    # of any command. Recording only begins once "START" is
    # received on the command port.
    #
    recorder_thread = threading.Thread(
        target=recorder.run,
        daemon=True,
    )

    recorder_thread.start()

    #
    # Wait for image-stream client in the background.
    #
    stream_thread = threading.Thread(
        target=streaming_server.wait_for_client,
        daemon=True,
    )

    stream_thread.start()

    #
    # Start command server.
    #
    command_thread = threading.Thread(
        target=tcp_server.run,
        daemon=True,
    )

    command_thread.start()

    print()
    print("----------------------------------------")
    print(" Event Camera Server")
    print("----------------------------------------")
    print(f"Host          : {HOST}")
    print(f"Command Port  : {COMMAND_PORT}")
    print(f"Stream Port   : {STREAM_PORT}")
    print("Streaming now. Send START to begin recording.")
    print()

    try:

        command_thread.join()

    except KeyboardInterrupt:

        print("\nStopping...")

    finally:

        try:
            recorder.stop()
        except Exception:
            pass

        try:
            streaming_server.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
