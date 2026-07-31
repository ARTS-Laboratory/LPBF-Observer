from __future__ import annotations

import csv
import ctypes
import json
import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from arena_api.system import system


# ------------------------------------------------------------------
# USER SETTINGS
# ------------------------------------------------------------------
current_dir = Path(__file__).resolve().parent
OUTPUT_FOLDER = Path(
    current_dir / "Recordings"
)

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# Match the CD-frame output rate configured in ArenaView.
VIDEO_FPS = 30.0

# Set to None to record until Q or Ctrl+C is pressed.
# Example: RECORD_SECONDS = 20.0
RECORD_SECONDS: float | None = None

VIDEO_CODEC = "MJPG"

STREAM_BUFFER_COUNT = 50


# ------------------------------------------------------------------
# BINARY FILE FORMAT
# ------------------------------------------------------------------

# File header:
#   magic:   8 bytes
#   version: uint32
FILE_HEADER = struct.Struct("<8sI")

# Block header before every Arena buffer:
#   frame_id:          uint64
#   device_timestamp:  uint64
#   host_timestamp_ns: uint64
#   payload_size:      uint64
#   width:             uint32
#   height:            uint32
#   bits_per_pixel:    uint32
BLOCK_HEADER = struct.Struct("<QQQQIII")

FILE_MAGIC = b"LUCDBUF1"
FILE_VERSION = 1


def get_integer_attribute(
    obj: Any,
    names: tuple[str, ...],
    default: int = 0,
) -> int:
    """Read the first available integer attribute."""

    for name in names:
        try:
            value = getattr(obj, name)

            if callable(value):
                value = value()

            return int(value)

        except (AttributeError, TypeError, ValueError):
            continue

    return default


def get_pixel_format_name(image_buffer: Any) -> str:
    """Return the buffer pixel-format name reported by Arena."""

    pixel_format = getattr(image_buffer, "pixel_format", None)

    if pixel_format is None:
        return "Unknown"

    for attribute_name in ("name", "symbolic"):
        try:
            value = getattr(pixel_format, attribute_name)

            if value is not None:
                return str(value)

        except Exception:
            continue

    return str(pixel_format)


def normalize_format_name(format_name: str) -> str:
    return (
        format_name.lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def is_incomplete_buffer(image_buffer: Any) -> bool:
    """Check whether Arena marked the buffer as incomplete."""

    value = getattr(image_buffer, "is_incomplete", False)

    try:
        if callable(value):
            value = value()

        return bool(value)

    except Exception:
        return False


def copy_buffer_payload(image_buffer: Any) -> bytes:
    """
    Copy the complete Arena buffer before requeueing it.

    Arena reuses the memory after requeue_buffer(), so a copy is required.
    """

    payload_size = get_integer_attribute(
        image_buffer,
        (
            "size_filled",
            "data_size",
            "payload_size",
            "size",
        ),
    )

    if payload_size <= 0:
        width = int(image_buffer.width)
        height = int(image_buffer.height)
        bits_per_pixel = int(image_buffer.bits_per_pixel)

        payload_size = (
            width * height * bits_per_pixel
        ) // 8

    if payload_size <= 0:
        raise RuntimeError(
            "Could not determine the Arena buffer payload size."
        )

    data_pointer = getattr(image_buffer, "pdata", None)

    if data_pointer is None:
        raise RuntimeError(
            "The Arena buffer does not expose a pdata pointer."
        )

    return ctypes.string_at(
        data_pointer,
        payload_size,
    )


def arena_buffer_to_bgr(image_buffer: Any) -> np.ndarray:
    """
    Convert an Arena CD/image buffer to an OpenCV BGR image.

    Supports:
        8-bit single-channel images
        24-bit three-channel images
        32-bit four-channel images
    """

    width = int(image_buffer.width)
    height = int(image_buffer.height)
    bits_per_pixel = int(image_buffer.bits_per_pixel)

    if bits_per_pixel % 8 != 0:
        raise RuntimeError(
            f"Unsupported packed image format: "
            f"{bits_per_pixel} bits per pixel."
        )

    bytes_per_pixel = bits_per_pixel // 8
    total_values = width * height * bytes_per_pixel

    raw_array = np.ctypeslib.as_array(
        image_buffer.pdata,
        shape=(total_values,),
    )

    if bytes_per_pixel == 1:
        grayscale_frame = raw_array.reshape(
            height,
            width,
        )

        return cv2.cvtColor(
            grayscale_frame,
            cv2.COLOR_GRAY2BGR,
        )

    if bytes_per_pixel == 3:
        return raw_array.reshape(
            height,
            width,
            3,
        ).copy()

    if bytes_per_pixel == 4:
        four_channel_frame = raw_array.reshape(
            height,
            width,
            4,
        )

        return cv2.cvtColor(
            four_channel_frame,
            cv2.COLOR_BGRA2BGR,
        )

    raise RuntimeError(
        f"The received buffer has {bytes_per_pixel} "
        "bytes per pixel and cannot be written to AVI directly."
    )


def get_camera_information(device: Any) -> dict[str, str]:
    """Read available camera identification and event settings."""

    node_names = {
        "vendor": "DeviceVendorName",
        "model": "DeviceModelName",
        "serial_number": "DeviceSerialNumber",
        "firmware_version": "DeviceFirmwareVersion",
        "event_format": "EventFormat",
        "event_format_size": "EventFormatSize",
        "acquisition_frame_rate": "AcquisitionFrameRate",
    }

    camera_information: dict[str, str] = {}

    for output_name, node_name in node_names.items():
        try:
            camera_information[output_name] = str(
                device.nodemap[node_name].value
            )
        except Exception:
            camera_information[output_name] = "Unavailable"

    return camera_information


def write_metadata(
    metadata_path: Path,
    *,
    status: str,
    timestamp: str,
    video_path: Path,
    binary_path: Path,
    csv_path: Path,
    camera_information: dict[str, str],
    received_format: str,
    frame_count: int,
    incomplete_buffer_count: int,
    total_payload_bytes: int,
    elapsed_seconds: float,
) -> None:
    """Write or update the recording metadata JSON file."""

    normalized_format = normalize_format_name(
        received_format
    )

    original_event_data = any(
        event_format in normalized_format
        for event_format in (
            "xytpframe",
            "xyptframe",
            "rawframeencoded",
        )
    )

    metadata = {
        "status": status,
        "recording_timestamp": timestamp,
        "output_folder": str(OUTPUT_FOLDER),
        "files": {
            "avi_video": video_path.name,
            "arena_buffer_binary": binary_path.name,
            "frame_index_csv": csv_path.name,
            "metadata_json": metadata_path.name,
        },
        "received_buffer_format": received_format,
        "binary_contains_original_event_data": (
            original_event_data
        ),
        "important_note": (
            "If received_buffer_format is a CD-frame, Mono8, "
            "BGR8, or other image format, the binary file contains "
            "the exact image-buffer bytes but not the original XYPT "
            "event stream."
        ),
        "video": {
            "codec": VIDEO_CODEC,
            "declared_fps": VIDEO_FPS,
        },
        "statistics": {
            "frames_recorded": frame_count,
            "incomplete_buffers": incomplete_buffer_count,
            "payload_bytes": total_payload_bytes,
            "payload_megabytes": (
                total_payload_bytes / (1024 * 1024)
            ),
            "elapsed_seconds": elapsed_seconds,
            "measured_frame_rate": (
                frame_count / elapsed_seconds
                if elapsed_seconds > 0
                else 0.0
            ),
        },
        "camera": camera_information,
        "binary_file_structure": {
            "file_header": {
                "struct_format": "<8sI",
                "fields": [
                    "magic",
                    "version",
                ],
            },
            "buffer_header": {
                "struct_format": "<QQQQIII",
                "fields": [
                    "frame_id",
                    "device_timestamp",
                    "host_timestamp_ns",
                    "payload_size",
                    "width",
                    "height",
                    "bits_per_pixel",
                ],
            },
        },
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def record_all_formats() -> None:
    """
    Record the current Arena stream simultaneously as:

        1. AVI visualization
        2. Exact Arena buffer payloads
        3. Frame/buffer index CSV
        4. Metadata JSON
    """

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    base_name = f"lucid_recording_{timestamp}"

    video_path = (
        OUTPUT_FOLDER
        / f"{base_name}.avi"
    )

    binary_path = (
        OUTPUT_FOLDER
        / f"{base_name}.bufferbin"
    )

    csv_path = (
        OUTPUT_FOLDER
        / f"{base_name}_frame_index.csv"
    )

    metadata_path = (
        OUTPUT_FOLDER
        / f"{base_name}.json"
    )

    devices = system.create_device()

    if not devices:
        raise RuntimeError(
            "No LUCID camera was detected.\n"
            "Check camera power, Ethernet connection, IP address, "
            "Arena SDK installation, and ensure ArenaView is closed."
        )

    device = devices[0]

    camera_information = get_camera_information(
        device
    )

    video_writer: cv2.VideoWriter | None = None
    stream_started = False

    frame_count = 0
    incomplete_buffer_count = 0
    total_payload_bytes = 0
    received_format = "Unknown"

    recording_start = time.perf_counter()

    print("\nCamera information:")

    for key, value in camera_information.items():
        print(f"  {key}: {value}")

    write_metadata(
        metadata_path,
        status="initializing",
        timestamp=timestamp,
        video_path=video_path,
        binary_path=binary_path,
        csv_path=csv_path,
        camera_information=camera_information,
        received_format=received_format,
        frame_count=frame_count,
        incomplete_buffer_count=(
            incomplete_buffer_count
        ),
        total_payload_bytes=total_payload_bytes,
        elapsed_seconds=0.0,
    )

    try:
        with (
            binary_path.open("wb") as binary_file,
            csv_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as csv_file,
        ):
            binary_file.write(
                FILE_HEADER.pack(
                    FILE_MAGIC,
                    FILE_VERSION,
                )
            )

            csv_writer = csv.writer(csv_file)

            csv_writer.writerow(
                [
                    "frame_number",
                    "frame_id",
                    "device_timestamp",
                    "host_timestamp_ns",
                    "elapsed_seconds",
                    "binary_payload_offset",
                    "payload_size_bytes",
                    "width",
                    "height",
                    "bits_per_pixel",
                    "pixel_format",
                    "incomplete",
                ]
            )

            device.start_stream(
                STREAM_BUFFER_COUNT
            )

            stream_started = True

            print("\nRecording started.")
            print(f"AVI file   : {video_path}")
            print(f"Buffer file: {binary_path}")
            print(f"CSV file   : {csv_path}")
            print(f"JSON file  : {metadata_path}")
            print("\nPress Q in the video window to stop.")

            while True:
                image_buffer = device.get_buffer()

                try:
                    host_timestamp_ns = time.time_ns()
                    elapsed_seconds = (
                        time.perf_counter()
                        - recording_start
                    )

                    width = int(
                        image_buffer.width
                    )

                    height = int(
                        image_buffer.height
                    )

                    bits_per_pixel = int(
                        image_buffer.bits_per_pixel
                    )

                    current_format = (
                        get_pixel_format_name(
                            image_buffer
                        )
                    )

                    frame_id = get_integer_attribute(
                        image_buffer,
                        (
                            "frame_id",
                            "frameid",
                        ),
                    )

                    device_timestamp = (
                        get_integer_attribute(
                            image_buffer,
                            (
                                "timestamp_ns",
                                "timestamp",
                            ),
                        )
                    )

                    incomplete = is_incomplete_buffer(
                        image_buffer
                    )

                    if incomplete:
                        incomplete_buffer_count += 1

                        csv_writer.writerow(
                            [
                                frame_count,
                                frame_id,
                                device_timestamp,
                                host_timestamp_ns,
                                elapsed_seconds,
                                "",
                                0,
                                width,
                                height,
                                bits_per_pixel,
                                current_format,
                                True,
                            ]
                        )

                        continue

                    # Copy both representations before returning
                    # the Arena buffer:
                    #   1. exact buffer bytes;
                    #   2. image for AVI.
                    payload = copy_buffer_payload(
                        image_buffer
                    )

                    frame_bgr = arena_buffer_to_bgr(
                        image_buffer
                    )

                finally:
                    device.requeue_buffer(
                        image_buffer
                    )

                if frame_count == 0:
                    received_format = current_format

                    print(
                        "\nFirst received buffer:"
                    )
                    print(
                        f"  Format: {received_format}"
                    )
                    print(
                        f"  Resolution: "
                        f"{width} x {height}"
                    )
                    print(
                        f"  Bits per pixel: "
                        f"{bits_per_pixel}"
                    )

                    normalized_format = (
                        normalize_format_name(
                            received_format
                        )
                    )

                    if any(
                        value in normalized_format
                        for value in (
                            "xytpframe",
                            "xyptframe",
                            "rawframeencoded",
                        )
                    ):
                        print(
                            "  The binary file contains "
                            "original event data."
                        )
                    else:
                        print(
                            "  The binary file contains "
                            "CD/image-buffer data, not "
                            "original XYPT events."
                        )

                if video_writer is None:
                    fourcc = (
                        cv2.VideoWriter_fourcc(
                            *VIDEO_CODEC
                        )
                    )

                    video_writer = cv2.VideoWriter(
                        str(video_path),
                        fourcc,
                        VIDEO_FPS,
                        (width, height),
                        True,
                    )

                    if not video_writer.isOpened():
                        raise RuntimeError(
                            "OpenCV could not create the AVI file.\n"
                            f"Path: {video_path}\n"
                            f"Codec: {VIDEO_CODEC}"
                        )

                # --------------------------------------------------
                # 1. Save exact Arena buffer payload
                # --------------------------------------------------

                binary_file.write(
                    BLOCK_HEADER.pack(
                        frame_id,
                        device_timestamp,
                        host_timestamp_ns,
                        len(payload),
                        width,
                        height,
                        bits_per_pixel,
                    )
                )

                payload_offset = binary_file.tell()

                binary_file.write(payload)

                total_payload_bytes += len(payload)

                # --------------------------------------------------
                # 2. Write frame to AVI
                # --------------------------------------------------

                video_writer.write(frame_bgr)

                # --------------------------------------------------
                # 3. Write frame metadata to CSV
                # --------------------------------------------------

                csv_writer.writerow(
                    [
                        frame_count,
                        frame_id,
                        device_timestamp,
                        host_timestamp_ns,
                        elapsed_seconds,
                        payload_offset,
                        len(payload),
                        width,
                        height,
                        bits_per_pixel,
                        current_format,
                        False,
                    ]
                )

                frame_count += 1

                # Display overlay is not written into the AVI.
                display_frame = frame_bgr.copy()

                cv2.putText(
                    display_frame,
                    f"REC  {elapsed_seconds:0.1f} s",
                    (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

                cv2.putText(
                    display_frame,
                    f"Frames: {frame_count}",
                    (15, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

                cv2.imshow(
                    "LUCID Triton2 EVS - Combined Recording",
                    display_frame,
                )

                if frame_count % 100 == 0:
                    binary_file.flush()
                    csv_file.flush()

                    write_metadata(
                        metadata_path,
                        status="recording",
                        timestamp=timestamp,
                        video_path=video_path,
                        binary_path=binary_path,
                        csv_path=csv_path,
                        camera_information=(
                            camera_information
                        ),
                        received_format=received_format,
                        frame_count=frame_count,
                        incomplete_buffer_count=(
                            incomplete_buffer_count
                        ),
                        total_payload_bytes=(
                            total_payload_bytes
                        ),
                        elapsed_seconds=(
                            elapsed_seconds
                        ),
                    )

                    print(
                        f"\rFrames: {frame_count:,} | "
                        f"Data: "
                        f"{total_payload_bytes / (1024 * 1024):,.1f} MB | "
                        f"Time: {elapsed_seconds:.1f} s",
                        end="",
                        flush=True,
                    )

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print(
                        "\nQ pressed. Stopping recording."
                    )
                    break

                if (
                    RECORD_SECONDS is not None
                    and elapsed_seconds
                    >= RECORD_SECONDS
                ):
                    print(
                        f"\nRecording duration of "
                        f"{RECORD_SECONDS} seconds completed."
                    )
                    break

    except KeyboardInterrupt:
        print(
            "\nRecording interrupted with Ctrl+C."
        )

    finally:
        elapsed_seconds = (
            time.perf_counter()
            - recording_start
        )

        if video_writer is not None:
            video_writer.release()

        if stream_started:
            try:
                device.stop_stream()
            except Exception as exc:
                print(
                    "\nWarning while stopping stream: "
                    f"{exc}"
                )

        system.destroy_device()
        cv2.destroyAllWindows()

        write_metadata(
            metadata_path,
            status="completed",
            timestamp=timestamp,
            video_path=video_path,
            binary_path=binary_path,
            csv_path=csv_path,
            camera_information=camera_information,
            received_format=received_format,
            frame_count=frame_count,
            incomplete_buffer_count=(
                incomplete_buffer_count
            ),
            total_payload_bytes=(
                total_payload_bytes
            ),
            elapsed_seconds=elapsed_seconds,
        )

    if frame_count == 0:
        print("\nNo complete frames were recorded.")
        return

    measured_frame_rate = (
        frame_count
        / max(elapsed_seconds, 0.001)
    )

    print("\n\nRecording completed.")
    print(f"Received format: {received_format}")
    print(f"Frames recorded: {frame_count:,}")
    print(
        f"Incomplete buffers: "
        f"{incomplete_buffer_count:,}"
    )
    print(
        f"Elapsed time: "
        f"{elapsed_seconds:.2f} seconds"
    )
    print(
        f"Measured frame rate: "
        f"{measured_frame_rate:.2f} FPS"
    )
    print(
        f"Raw payload size: "
        f"{total_payload_bytes / (1024 * 1024):,.2f} MB"
    )

    print("\nSaved files:")
    print(f"  AVI   : {video_path.resolve()}")
    print(f"  Binary: {binary_path.resolve()}")
    print(f"  CSV   : {csv_path.resolve()}")
    print(f"  JSON  : {metadata_path.resolve()}")


if __name__ == "__main__":
    record_all_formats()