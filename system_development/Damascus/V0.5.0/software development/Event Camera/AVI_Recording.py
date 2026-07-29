from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time

import cv2
import numpy as np
from arena_api.system import system


# ------------------------------------------------------------------
# USER SETTINGS
# ------------------------------------------------------------------

OUTPUT_FOLDER = Path(r"C:\Users\killedar\OneDrive - University of South Carolina\Documents\GitHub\LPBF-Observer\system_development\Damascus\V0.5.0\software development\Event Camera\recordings")

# Use the same value configured for the CD-frame output rate
# in ArenaView.
VIDEO_FPS = 30.0

# Set to None to record until Q is pressed.
# Example: RECORD_SECONDS = 20.0 records for 20 seconds.
RECORD_SECONDS: float | None = None

# MJPG + AVI is normally reliable on Windows.
VIDEO_CODEC = "MJPG"


def arena_buffer_to_bgr(image_buffer) -> np.ndarray:
    """
    Convert an Arena image buffer to an OpenCV BGR image.

    Supports:
        8-bit grayscale
        24-bit three-channel images
        32-bit four-channel images
    """

    width = int(image_buffer.width)
    height = int(image_buffer.height)
    bits_per_pixel = int(image_buffer.bits_per_pixel)

    if bits_per_pixel % 8 != 0:
        raise RuntimeError(
            f"Unsupported packed pixel format: {bits_per_pixel} bits/pixel.\n"
            "Set the camera CD-frame output to Mono8 or BGR8."
        )

    bytes_per_pixel = bits_per_pixel // 8
    total_values = width * height * bytes_per_pixel

    # Create a NumPy view of the Arena buffer.
    raw_array = np.ctypeslib.as_array(
        image_buffer.pdata,
        shape=(total_values,),
    )

    if bytes_per_pixel == 1:
        gray_frame = raw_array.reshape(height, width)

        # VideoWriter is configured for three-channel color frames.
        bgr_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)

    elif bytes_per_pixel == 3:
        frame = raw_array.reshape(height, width, 3)

        # Copy the data before returning the Arena buffer.
        bgr_frame = frame.copy()

    elif bytes_per_pixel == 4:
        frame = raw_array.reshape(height, width, 4)
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    else:
        raise RuntimeError(
            f"Unsupported image format: {bits_per_pixel} bits/pixel."
        )

    return bgr_frame


def record_lucid_stream() -> None:
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = OUTPUT_FOLDER / f"lucid_cd_stream_{timestamp}.avi"

    devices = system.create_device()

    if not devices:
        raise RuntimeError(
            "No LUCID camera was detected.\n"
            "Check the camera power, Ethernet connection, IP address, "
            "and Arena SDK installation."
        )

    device = devices[0]
    video_writer: cv2.VideoWriter | None = None

    frame_count = 0
    recording_start = time.perf_counter()

    try:
        # Using more acquisition buffers can help during recording.
        device.start_stream(20)

        print("Camera stream started.")
        print(f"Recording file: {video_path}")
        print("Press Q in the video window to stop recording.")

        while True:
            image_buffer = device.get_buffer()

            try:
                # Make an independent copy before requeueing the buffer.
                frame_bgr = arena_buffer_to_bgr(image_buffer)

            finally:
                device.requeue_buffer(image_buffer)

            height, width = frame_bgr.shape[:2]

            # Initialize VideoWriter after receiving the first frame,
            # because its width and height are then known.
            if video_writer is None:
                fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)

                video_writer = cv2.VideoWriter(
                    str(video_path),
                    fourcc,
                    VIDEO_FPS,
                    (width, height),
                    True,
                )

                if not video_writer.isOpened():
                    raise RuntimeError(
                        "OpenCV could not open the video output file.\n"
                        f"Output path: {video_path}\n"
                        f"Codec: {VIDEO_CODEC}"
                    )

                print(f"Resolution: {width} x {height}")
                print(f"Video FPS setting: {VIDEO_FPS}")

            # Write the current camera frame into the AVI file.
            video_writer.write(frame_bgr)
            frame_count += 1

            elapsed_seconds = time.perf_counter() - recording_start

            # Make a separate display frame so the recording itself
            # does not contain the REC text.
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

            cv2.imshow(
                "LUCID Triton2 EVS - Recording",
                display_frame,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("Q pressed. Stopping recording.")
                break

            if (
                RECORD_SECONDS is not None
                and elapsed_seconds >= RECORD_SECONDS
            ):
                print(
                    f"Recording duration of "
                    f"{RECORD_SECONDS} seconds completed."
                )
                break

    except KeyboardInterrupt:
        print("\nRecording interrupted with Ctrl+C.")

    finally:
        elapsed_seconds = time.perf_counter() - recording_start

        if video_writer is not None:
            video_writer.release()

        try:
            device.stop_stream()
        except Exception:
            pass

        system.destroy_device()
        cv2.destroyAllWindows()

    if frame_count == 0:
        print("No frames were recorded.")
        return

    measured_capture_rate = frame_count / max(elapsed_seconds, 0.001)

    print("\nRecording completed.")
    print(f"Frames recorded: {frame_count}")
    print(f"Elapsed time: {elapsed_seconds:.2f} seconds")
    print(
        f"Measured acquisition rate: "
        f"{measured_capture_rate:.2f} frames/second"
    )
    print(f"Video saved to: {video_path.resolve()}")


if __name__ == "__main__":
    record_lucid_stream()