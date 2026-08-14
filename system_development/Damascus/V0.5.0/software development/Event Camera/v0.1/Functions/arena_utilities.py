from typing import Any
import ctypes
import cv2
import numpy as np


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