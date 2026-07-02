"""
evs_functions.py

Starter helper functions for displaying a LUCID Triton2 EVS stream in Python.

Goal for milestone 1:
    Triton2 EVS -> Arena Python -> OpenCV display window

No LabVIEW TCP is included here yet. Once this displays reliably, the next step
is to replace or parallel the OpenCV display with a TCP sender.
"""

from __future__ import annotations

import time
from typing import Any, Iterable, Optional

import cv2
import numpy as np
from arena_api.system import system


# -----------------------------
# Device discovery / connection
# -----------------------------

def list_devices() -> list[dict[str, Any]]:
    """Return the current Arena device info list and print a short summary."""
    infos = system.device_infos
    print(f"Found {len(infos)} device(s).")
    for i, info in enumerate(infos):
        print(
            f"  [{i}] model={info.get('model')}  "
            f"serial={info.get('serial')}  "
            f"ip={info.get('ip')}  "
            f"mac={info.get('mac')}"
        )
    return infos


def create_device_with_retries(
    serial: Optional[str] = None,
    tries_max: int = 6,
    sleep_time_s: float = 5.0,
):
    """
    Create one Arena device.

    If serial is None, the first detected device is used.
    If serial is supplied, the matching device is opened.
    """
    for attempt in range(1, tries_max + 1):
        infos = list_devices()

        selected_info = None
        if serial is None:
            if infos:
                selected_info = infos[0]
        else:
            for info in infos:
                if str(info.get("serial")) == str(serial):
                    selected_info = info
                    break

        if selected_info is not None:
            print(f"Creating device: {selected_info.get('model')} serial={selected_info.get('serial')}")
            devices = system.create_device(selected_info)
            if not devices:
                raise RuntimeError("Arena returned no device after selecting a valid device_info.")
            return devices[0]

        print(f"Attempt {attempt}/{tries_max}: no matching device yet. Waiting {sleep_time_s:.1f} s...")
        time.sleep(sleep_time_s)

    if serial is None:
        raise RuntimeError("No Arena device found. Check power, Ethernet/IP settings, and close ArenaView.")
    raise RuntimeError(f"No Arena device found with serial {serial!r}.")


def destroy_all_devices() -> None:
    """Destroy all Arena devices opened by this process."""
    try:
        system.destroy_device()
        print("Destroyed all created Arena devices.")
    except Exception as exc:
        print(f"Warning: system.destroy_device() failed or no devices were open: {exc}")


# -----------------------------
# Node helpers
# -----------------------------

def _get_node(nodemap, node_name: str):
    """Return a GenICam node or None if it does not exist / cannot be accessed."""
    try:
        return nodemap.get_node(node_name)
    except Exception:
        try:
            return nodemap[node_name]
        except Exception:
            return None


def try_set_node_value(nodemap, node_name: str, value: Any) -> bool:
    """Try to set one node. Return True if successful, False otherwise."""
    node = _get_node(nodemap, node_name)
    if node is None:
        return False
    try:
        old_value = getattr(node, "value", None)
        node.value = value
        print(f"  set {node_name}: {old_value!r} -> {value!r}")
        return True
    except Exception as exc:
        print(f"  could not set {node_name}={value!r}: {exc}")
        return False


def try_set_first_available(nodemap, node_names: Iterable[str], values: Iterable[Any]) -> bool:
    """
    Try several possible node names and values.

    This is useful for EVS/CD-frame nodes because exact names can differ between
    SDK/camera firmware versions. The first successful set returns True.
    """
    for node_name in node_names:
        for value in values:
            if try_set_node_value(nodemap, node_name, value):
                return True
    return False


def print_basic_camera_nodes(device) -> None:
    """Print a few useful nodes for debugging."""
    nodemap = device.nodemap
    tl_stream_nodemap = device.tl_stream_nodemap

    for name in [
        "DeviceModelName",
        "DeviceSerialNumber",
        "Width",
        "Height",
        "PixelFormat",
        "AcquisitionMode",
        "GevCurrentIPAddress",
    ]:
        node = _get_node(nodemap, name)
        if node is not None:
            try:
                print(f"{name}: {node.value}")
            except Exception:
                pass

    for name in ["StreamBufferHandlingMode"]:
        node = _get_node(tl_stream_nodemap, name)
        if node is not None:
            try:
                print(f"TL stream {name}: {node.value}")
            except Exception:
                pass


# -----------------------------
# Stream configuration
# -----------------------------

def configure_for_display(
    device,
    use_max_resolution: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    stream_buffer_mode: str = "NewestOnly",
    frame_rate_hz: float = 30.0,
    accumulation_time_us: int = 1000,
) -> None:
    """
    Configure the camera for first-pass live display.

    For a normal area-scan camera this usually gives a normal image stream.
    For the Triton2 EVS, the desired display output is a CD frame: an accumulated
    event image. The exact CD-frame node names can vary, so this function tries
    several common names and simply skips any nodes that are not present.
    """
    nodemap = device.nodemap
    tl_stream_nodemap = device.tl_stream_nodemap

    print("Configuring stream for display...")

    try_set_node_value(nodemap, "AcquisitionMode", "Continuous")
    try_set_node_value(tl_stream_nodemap, "StreamBufferHandlingMode", stream_buffer_mode)

    # Width/height should be set before streaming. For the TRT009S-EC this is
    # expected to be 1280 x 720 at full resolution.
    if use_max_resolution:
        width_node = _get_node(nodemap, "Width")
        height_node = _get_node(nodemap, "Height")
        if width_node is not None:
            try:
                width_node.value = width_node.max
                print(f"  set Width to max: {width_node.value}")
            except Exception as exc:
                print(f"  could not set Width to max: {exc}")
        if height_node is not None:
            try:
                height_node.value = height_node.max
                print(f"  set Height to max: {height_node.value}")
            except Exception as exc:
                print(f"  could not set Height to max: {exc}")
    else:
        if width is not None:
            try_set_node_value(nodemap, "Width", int(width))
        if height is not None:
            try_set_node_value(nodemap, "Height", int(height))

    # Prefer a displayable CD frame / image output if the camera exposes nodes
    # for it. These names are intentionally broad; unsupported names are ignored.
    print("Trying EVS/CD-frame display nodes if present...")
    try_set_first_available(
        nodemap,
        node_names=[
            "FrameGeneratorEnable",
            "CDFrameGeneratorEnable",
            "CdFrameGeneratorEnable",
            "EVSFrameGeneratorEnable",
            "EvsFrameGeneratorEnable",
            "EventFrameGeneratorEnable",
        ],
        values=[True, "True", "On", "Enable", "Enabled"],
    )

    try_set_first_available(
        nodemap,
        node_names=[
            "FrameGeneratorMode",
            "CDFrameGeneratorMode",
            "CdFrameGeneratorMode",
            "EVSOutputMode",
            "EvsOutputMode",
            "EventOutputMode",
            "EventDataOutputMode",
            "DeviceStreamOutput",
        ],
        values=["CDFrame", "CdFrame", "CDFrames", "Frame", "Image", "Processed"],
    )

    try_set_first_available(
        nodemap,
        node_names=[
            "FrameGeneratorFrameRate",
            "CDFrameFrameRate",
            "CdFrameFrameRate",
            "EVSFrameRate",
            "EvsFrameRate",
        ],
        values=[float(frame_rate_hz)],
    )

    try_set_first_available(
        nodemap,
        node_names=[
            "AccumulationTime",
            "CDFrameAccumulationTime",
            "CdFrameAccumulationTime",
            "FrameGeneratorAccumulationTime",
            "EventAccumulationTime",
            "EVSAccumulationTime",
            "EvsAccumulationTime",
        ],
        values=[int(accumulation_time_us), float(accumulation_time_us)],
    )

    # If Mono8 is available, it is easiest to display and later TCP to LabVIEW.
    # This may fail on raw EVT output, which is fine for now.
    try_set_first_available(
        nodemap,
        node_names=["PixelFormat"],
        values=["Mono8", "BGR8", "RGB8"],
    )

    print("Configuration attempt complete.")
    print_basic_camera_nodes(device)


# -----------------------------
# Buffer conversion / display
# -----------------------------

def buffer_to_numpy_image(image_buffer) -> np.ndarray:
    """
    Convert an Arena image buffer into a numpy image array.

    This follows LUCID's published Arena Python/OpenCV pattern using
    image_buffer.pdata and image_buffer.bits_per_pixel. The result is copied so
    it remains valid after the Arena buffer is requeued.
    """
    pixel_format_name = ""
    try:
        pixel_format_name = image_buffer.pixel_format.name
    except Exception:
        pass

    if any(token in pixel_format_name.upper() for token in ["EVT", "EVENT"]):
        raise RuntimeError(
            f"Buffer pixel format looks like raw event data ({pixel_format_name}), "
            "not a displayable image. Enable CD-frame/image output in ArenaView "
            "or update the CD-frame node names in configure_for_display()."
        )

    width = int(image_buffer.width)
    height = int(image_buffer.height)
    bits_per_pixel = int(image_buffer.bits_per_pixel)

    if bits_per_pixel % 8 != 0:
        raise RuntimeError(
            f"Unsupported packed/non-byte-aligned pixel format: "
            f"{pixel_format_name}, bits_per_pixel={bits_per_pixel}. "
            "For this first milestone, use Mono8/BGR8/RGB8 CD-frame output."
        )

    bytes_per_pixel = bits_per_pixel // 8
    if bytes_per_pixel < 1:
        raise RuntimeError(f"Invalid bytes_per_pixel={bytes_per_pixel}.")

    array = np.ctypeslib.as_array(
        image_buffer.pdata,
        shape=(height, width, bytes_per_pixel),
    ).reshape(height, width, bytes_per_pixel)

    # Squeeze Mono8 from H x W x 1 to H x W for OpenCV display.
    if bytes_per_pixel == 1:
        array = array[:, :, 0]

    return array.copy()


def print_buffer_info(image_buffer, prefix: str = "buffer") -> None:
    """Print one line describing an Arena buffer."""
    try:
        pixel_format_name = image_buffer.pixel_format.name
    except Exception:
        pixel_format_name = "unknown"

    attrs = {
        "width": getattr(image_buffer, "width", None),
        "height": getattr(image_buffer, "height", None),
        "bits_per_pixel": getattr(image_buffer, "bits_per_pixel", None),
        "pixel_format": pixel_format_name,
    }
    print(f"{prefix}: " + ", ".join(f"{k}={v}" for k, v in attrs.items()))


def display_stream(
    device,
    window_name: str = "Triton2 EVS display",
    number_of_buffers: int = 20,
    print_every_n_frames: int = 30,
) -> None:
    """
    Start the stream and display frames until q or Esc is pressed.

    The loop intentionally does only three things:
        1. get Arena buffer
        2. convert to numpy/OpenCV image
        3. display image

    Keeping this simple makes it easy to swap the display step for TCP later.
    """
    print(f"Starting stream with {number_of_buffers} buffers...")
    device.start_stream(number_of_buffers)
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    frame_count = 0
    t0 = time.perf_counter()

    try:
        while True:
            image_buffer = None
            try:
                image_buffer = device.get_buffer()

                if frame_count == 0:
                    print_buffer_info(image_buffer, "first buffer")

                image = buffer_to_numpy_image(image_buffer)

            finally:
                if image_buffer is not None:
                    device.requeue_buffer(image_buffer)

            frame_count += 1

            if frame_count % print_every_n_frames == 0:
                elapsed = time.perf_counter() - t0
                fps = frame_count / elapsed if elapsed > 0 else 0.0
                print(f"Displayed {frame_count} frames, approx {fps:.1f} FPS")

            cv2.imshow(window_name, image)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):  # Esc or q
                print("Display stopped by user.")
                break

    finally:
        print("Stopping stream...")
        try:
            device.stop_stream()
        finally:
            cv2.destroyWindow(window_name)
