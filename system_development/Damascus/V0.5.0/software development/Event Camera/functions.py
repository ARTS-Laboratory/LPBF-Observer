"""Helper functions for Triton2 EVS acquisition + TCP streaming.

This module keeps camera acquisition and socket transport separate so the
main script can stay small and easy to modify.
"""
from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
from arena_api.system import system


MAGIC = b"EVS1"
PACKET_TYPE_FRAME_U8 = 1
# < = big-endian, standard sizes, no padding
# magic[4], packet_type[1], frame_number[4], timestamp_us[8], width[2], height[2], payload_len[4]
HEADER = struct.Struct("!IBIQHHI")
# ! = network order / big-endian

@dataclass
class StreamConfig:
    buffers: int = 100
    timeout_ms: int = 1000
    display_scale: float = 1.0
    send_every_n: int = 1
    tcp_nodelay: bool = True


def now_us() -> int:
    return time.perf_counter_ns() // 1000


def connect_camera(serial: Optional[str] = None):
    """Open the first camera or a camera matching the given serial."""
    devices = system.create_device()
    if not devices:
        raise RuntimeError("No camera found")

    if serial is None:
        if len(devices) > 1:
            print("Multiple cameras found; using the first one.")
        device = devices[0]
        print(f"Using device: {device}")
        return device

    for device in devices:
        try:
            # device.__str__ often contains serial, but use the device info when available.
            info = getattr(device, "device_info", None)
            if info is not None and getattr(info, "serial", None) == serial:
                print(f"Using device: {device}")
                return device
        except Exception:
            pass

    raise RuntimeError(f"Could not find camera with serial {serial!r}")


def _set_if_exists(nodemap, name: str, value) -> bool:
    try:
        try:
            node = nodemap.get_node(name)
        except Exception:
            node = nodemap[name]
        node.value = value
        print(f"Set {name} = {value}")
        return True
    except Exception:
        return False


def configure_camera(device, *, newest_only: bool = True, try_auto_packet: bool = True):
    """Apply a minimal stable configuration for CD-frame preview."""
    nodemap = device.nodemap
    tl_stream = device.tl_stream_nodemap

    _set_if_exists(nodemap, "AcquisitionMode", "Continuous")

    if newest_only:
        _set_if_exists(tl_stream, "StreamBufferHandlingMode", "NewestOnly")

    # Helpful on many GigE paths; harmless if unsupported.
    if try_auto_packet:
        _set_if_exists(tl_stream, "StreamAutoNegotiatePacketSize", True)
        _set_if_exists(nodemap, "StreamAutoNegotiatePacketSize", True)

    # If your working ArenaView setup already has EVS Output Frame = CD Frame,
    # keep that setting there. Different firmware versions expose different node names.


def start_stream(device, buffers: int = 100):
    device.start_stream(buffers)
    print(f"Stream started with {buffers} buffers")


def stop_stream(device):
    try:
        device.stop_stream()
        print("Stream stopped")
    except Exception:
        pass


def destroy_device(device):
    try:
        system.destroy_device(device)
        print("Destroyed device")
    except Exception:
        pass


def buffer_to_frame_u8(image_buffer) -> np.ndarray:
    """Convert an Arena buffer into a NumPy image."""
    channels = max(1, int(image_buffer.bits_per_pixel / 8))
    frame = np.ctypeslib.as_array(
        image_buffer.pdata,
        shape=(image_buffer.height, image_buffer.width, channels),
    )
    if channels == 1:
        frame = frame[:, :, 0]
    return np.ascontiguousarray(frame)


def maybe_scale_frame(frame: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return frame
    new_width = max(1, int(frame.shape[1] * scale))
    new_height = max(1, int(frame.shape[0] * scale))
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)


def open_tcp_server(host="0.0.0.0", port=50000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"TCP server listening on {host}:{port}")
    conn, addr = server.accept()
    print(f"LabVIEW connected from {addr}")
    return server, conn


def close_tcp(sock: Optional[socket.socket]):
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass


def send_frame(sock: socket.socket, frame: np.ndarray, frame_number: int):
    """Send a single grayscale frame as a length-prefixed binary packet."""
    if frame.ndim == 3:
        # If a color image ever appears, keep only one plane for now.
        frame = frame[:, :, 0]

    if frame.dtype != np.uint8:
        frame = frame.astype(np.uint8, copy=False)

    height, width = frame.shape[:2]
    payload = frame.tobytes(order="C")
    timestamp_us = now_us()
    header = HEADER.pack(
        MAGIC,
        PACKET_TYPE_FRAME_U8,
        frame_number,
        timestamp_us,
        width,
        height,
        len(payload),
    )
    packet = header + payload
    sock.sendall(struct.pack("!I", len(packet)))
    sock.sendall(packet)


def receive_or_timeout(device, timeout_ms: int):
    """Read one buffer from the camera.

    Returns:
        (frame, buffer)
    Raises:
        TimeoutError / Arena exceptions if get_buffer fails for non-timeout reasons.
    """
    buf = device.get_buffer()
    frame = buffer_to_frame_u8(buf)
    return frame, buf
