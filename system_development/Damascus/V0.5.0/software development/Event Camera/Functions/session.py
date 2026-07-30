from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class RecordingSession:
    """
    Represents one recording session.

    Creates a timestamped recording directory and provides
    convenient access to all output file paths.
    """

    output_folder: Path

    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
    )

    session_folder: Path = field(init=False)

    video_path: Path = field(init=False)
    binary_path: Path = field(init=False)
    csv_path: Path = field(init=False)
    metadata_path: Path = field(init=False)

    def __post_init__(self) -> None:

        self.output_folder = Path(self.output_folder)

        self.session_folder = (
            self.output_folder / self.timestamp
        )

        self.session_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.video_path = (
            self.session_folder / "recording.avi"
        )

        self.binary_path = (
            self.session_folder / "recording.bin"
        )

        self.csv_path = (
            self.session_folder / "recording.csv"
        )

        self.metadata_path = (
            self.session_folder / "metadata.json"
        )

    @property
    def files(self) -> dict[str, Path]:
        """
        Return all output file paths.
        """

        return {
            "video": self.video_path,
            "binary": self.binary_path,
            "csv": self.csv_path,
            "metadata": self.metadata_path,
        }

    def __str__(self) -> str:

        return (
            f"RecordingSession("
            f"folder='{self.session_folder.name}')"
        )