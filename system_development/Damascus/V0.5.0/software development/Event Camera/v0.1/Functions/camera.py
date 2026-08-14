from __future__ import annotations

import time

from arena_api.system import system

from Functions import config
from Functions.arena_utilities import (
    arena_buffer_to_bgr,
    copy_buffer_payload,
    get_integer_attribute,
    get_pixel_format_name,
    is_incomplete_buffer,
)
from Functions.frame import Frame


# --------------------------------------------------------
# Camera object
# --------------------------------------------------------

class ArenaCamera:

    def __init__(self):

        self.device = None
        self.streaming = False
        self.camera_info = {}
        self._frame_counter = 0

    # ----------------------------------------------------

    def open(self):

        if self.device is not None:
            return

        # Discover all GigE Vision devices
        device_infos = system.device_infos

        if not device_infos:
            raise RuntimeError("No GigE Vision devices found.")

        # Find the configured camera
        camera_info = next(
            (
                info
                for info in device_infos
                if info.get("serial") == config.CAMERA_SERIAL
            ),
            None,
        )

        if camera_info is None:

            available = "\n".join(
                f"{d.get('vendor')} | "
                f"{d.get('model')} | "
                f"{d.get('serial')}"
                for d in device_infos
            )

            raise RuntimeError(
                f"Camera with serial "
                f"{config.CAMERA_SERIAL} was not found.\n\n"
                f"Detected devices:\n{available}"
            )

        # Open ONLY the selected camera
        devices = system.create_device(camera_info)

        if not devices:
            raise RuntimeError(
                f"Unable to open camera "
                f"{config.CAMERA_SERIAL}."
            )

        self.device = devices[0]

        # Verify we opened the expected camera
        serial = str(
            self.device.nodemap[
                "DeviceSerialNumber"
            ].value
        )

        if serial != config.CAMERA_SERIAL:
            raise RuntimeError(
                f"Opened the wrong camera "
                f"({serial})."
            )

        self._frame_counter = 0

        self.camera_info = self._read_camera_information()

    # ----------------------------------------------------

    def close(self):

        if self.streaming:

            try:
                self.stop()

            except Exception:
                pass

        if self.device is not None:

            try:
                system.destroy_device(self.device)

            finally:
                self.device = None
                self.streaming = False

    # ----------------------------------------------------

    def start(self):

        if self.streaming:
            return

        self.device.start_stream(
            config.STREAM_BUFFER_COUNT
        )

        self.streaming = True

    # ----------------------------------------------------

    def stop(self):

        if not self.streaming:
            return

        self.device.stop_stream()

        self.streaming = False

    # ----------------------------------------------------

    def __iter__(self):

        if not self.streaming:
            self.start()

        return self

    # ----------------------------------------------------

    def __next__(self) -> Frame:

        if not self.streaming:
            raise StopIteration

        return self.get_frame()

    # ----------------------------------------------------

    def get_frame(self) -> Frame:

        image_buffer = self.device.get_buffer()

        try:

            width = int(image_buffer.width)
            height = int(image_buffer.height)

            bits = int(image_buffer.bits_per_pixel)

            pixel_format = get_pixel_format_name(
                image_buffer
            )

            frame_id = get_integer_attribute(
                image_buffer,
                ("frame_id", "frameid"),
            )

            device_timestamp = get_integer_attribute(
                image_buffer,
                ("timestamp_ns", "timestamp"),
            )

            host_timestamp = time.time_ns()

            incomplete = is_incomplete_buffer(
                image_buffer
            )

            self._frame_counter += 1
            frame_number = self._frame_counter

            if incomplete:

                return Frame(
                    image=None,
                    payload=b"",
                    frame_id=frame_id,
                    number=frame_number,
                    device_timestamp=device_timestamp,
                    host_timestamp_ns=host_timestamp,
                    width=width,
                    height=height,
                    bits_per_pixel=bits,
                    pixel_format=pixel_format,
                    incomplete=True,
                )

            payload = copy_buffer_payload(
                image_buffer
            )

            image = arena_buffer_to_bgr(
                image_buffer
            )

            return Frame(
                image=image,
                payload=payload,
                frame_id=frame_id,
                number=frame_number,
                device_timestamp=device_timestamp,
                host_timestamp_ns=host_timestamp,
                width=width,
                height=height,
                bits_per_pixel=bits,
                pixel_format=pixel_format,
                incomplete=False,
            )

        finally:

            self.device.requeue_buffer(
                image_buffer
            )

    # ----------------------------------------------------

    def _read_camera_information(self):

        node_names = {
            "vendor": "DeviceVendorName",
            "model": "DeviceModelName",
            "serial_number": "DeviceSerialNumber",
            "firmware_version": "DeviceFirmwareVersion",
            "pixel_format": "PixelFormat",
            "event_format": "EventFormat",
            "event_format_size": "EventFormatSize",
            "acquisition_frame_rate": "AcquisitionFrameRate",
        }

        info = {}

        for key, node in node_names.items():

            try:
                info[key] = str(
                    self.device.nodemap[node].value
                )

            except Exception:
                info[key] = "Unavailable"

        return info

    # ----------------------------------------------------

    def __enter__(self):

        self.open()
        self.start()

        return self

    # ----------------------------------------------------

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.close()