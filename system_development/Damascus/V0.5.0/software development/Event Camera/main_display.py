"""
main_display.py

Milestone 1: show Triton2 EVS image/CD-frame data in an OpenCV window.

Run:
    python main_display.py

Optional:
    python main_display.py --serial YOUR_SERIAL_NUMBER
    python main_display.py --buffers 30
    python main_display.py --accumulation-us 5000
"""

from __future__ import annotations

import argparse

from evs_functions import (
    configure_for_display,
    create_device_with_retries,
    destroy_all_devices,
    display_stream,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Display Triton2 EVS data using Arena Python + OpenCV.")
    parser.add_argument("--serial", default=None, help="Optional camera serial number. If omitted, first camera is used.")
    parser.add_argument("--buffers", type=int, default=20, help="Arena stream buffer count.")
    parser.add_argument("--frame-rate", type=float, default=30.0, help="Requested CD-frame/display frame rate if supported.")
    parser.add_argument(
        "--accumulation-us",
        type=int,
        default=1000,
        help="Requested CD-frame event accumulation time in microseconds if supported.",
    )
    parser.add_argument(
        "--no-max-resolution",
        action="store_true",
        help="Do not force Width/Height to max before streaming.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = None

    try:
        device = create_device_with_retries(serial=args.serial)

        configure_for_display(
            device,
            use_max_resolution=not args.no_max_resolution,
            frame_rate_hz=args.frame_rate,
            accumulation_time_us=args.accumulation_us,
        )

        display_stream(
            device,
            number_of_buffers=args.buffers,
        )

    finally:
        # This also closes the device if something errors during setup/display.
        destroy_all_devices()


if __name__ == "__main__":
    main()
