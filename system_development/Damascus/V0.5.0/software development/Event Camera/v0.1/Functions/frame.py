from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Frame:
    """
    Represents a single frame acquired from the camera.

    This object is passed to every recorder (video, binary, CSV,
    display, metadata, etc.) so each module operates on the same
    source of truth.
    """

    # ------------------------------------------------------------------
    # Image data
    # ------------------------------------------------------------------

    image: np.ndarray | None
    payload: bytes

    # ------------------------------------------------------------------
    # Camera metadata
    # ------------------------------------------------------------------

    frame_id: int
    device_timestamp: int
    host_timestamp_ns: int

    # ------------------------------------------------------------------
    # Recording sequence
    # ------------------------------------------------------------------
    #
    # A running count assigned by the recorder/camera for every frame
    # it hands off (including incomplete/dropped ones). Unlike
    # `frame_id` (assigned by the device and not guaranteed gap-free),
    # this is always sequential, which is what the CSV log relies on.

    number: int

    # ------------------------------------------------------------------
    # Image information
    # ------------------------------------------------------------------

    width: int
    height: int
    bits_per_pixel: int
    pixel_format: str

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    incomplete: bool = False

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def payload_size(self) -> int:
        """Return the payload size in bytes."""
        return len(self.payload)

    @property
    def resolution(self) -> tuple[int, int]:
        """Return (width, height)."""
        return (self.width, self.height)

    @property
    def megapixels(self) -> float:
        """Return the image resolution in megapixels."""
        return (self.width * self.height) / 1_000_000

    @property
    def has_image(self) -> bool:
        """True if a decoded image is available."""
        return self.image is not None

    @property
    def is_complete(self) -> bool:
        """True if the frame is valid."""
        return not self.incomplete

    def __str__(self) -> str:
        return (
            f"Frame("
            f"number={self.number}, "
            f"id={self.frame_id}, "
            f"{self.width}x{self.height}, "
            f"{self.pixel_format}, "
            f"{self.bits_per_pixel} bpp, "
            f"payload={self.payload_size} bytes, "
            f"incomplete={self.incomplete})"
        )