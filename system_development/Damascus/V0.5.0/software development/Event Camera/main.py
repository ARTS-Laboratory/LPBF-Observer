from __future__ import annotations

import argparse
import sys
import time

import cv2

from functions import (
    connect_camera,
    configure_camera,
    destroy_device,
    close_tcp,
    maybe_scale_frame,
    open_tcp_server,
    receive_or_timeout,
    send_frame,
    start_stream,
    stop_stream,
)


def parse_args():
    p = argparse.ArgumentParser(description="Triton2 EVS camera preview + TCP sender")
    p.add_argument("--serial", type=str, default=None, help="Camera serial number")
    p.add_argument(
        "--bind-host",
        type=str,
        default="0.0.0.0",
        help="TCP bind host for Python server",
    )
    p.add_argument("--port", type=int, default=50000, help="TCP port for LabVIEW client")
    p.add_argument("--buffers", type=int, default=100, help="Arena stream buffers")
    p.add_argument("--timeout-ms", type=int, default=1000, help="Buffer wait timeout")
    p.add_argument("--display-scale", type=float, default=1.0, help="Display scaling factor")
    p.add_argument("--send-every-n", type=int, default=1, help="Send every Nth frame to TCP")
    p.add_argument("--no-tcp", action="store_true", help="Run camera preview only")
    return p.parse_args()


def main():
    args = parse_args()

    device = None
    server = None
    conn = None
    frame_number = 0
    last_timeout_print = 0.0

    try:
        device = connect_camera(args.serial)
        configure_camera(device)
        start_stream(device, args.buffers)

        if not args.no_tcp:
            print(f"Waiting for LabVIEW to connect on {args.bind_host}:{args.port} ...")
            server, conn = open_tcp_server(args.bind_host, args.port)
            print("LabVIEW connected")

        while True:
            try:
                frame, buf = receive_or_timeout(device, args.timeout_ms)
            except Exception as exc:
                now = time.time()
                if now - last_timeout_print > 2.0:
                    print(f"Buffer wait issue: {exc}")
                    last_timeout_print = now
                continue

            try:
                preview = maybe_scale_frame(frame, args.display_scale)
                cv2.imshow("Triton2 EVS", preview)

                if conn is not None and (frame_number % max(1, args.send_every_n) == 0):
                    send_frame(conn, frame, frame_number)
                    print(f"sent frame {frame_number}")

                frame_number += 1

                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
            finally:
                device.requeue_buffer(buf)

    finally:
        stop_stream(device)
        close_tcp(conn)
        close_tcp(server)
        destroy_device(device)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())