"""Reconstruct one saved RAW recording by its numbered file entry.

Edit FILE_NUMBER below, then run this file from Visual Studio or with Python.
Recordings are discovered recursively under ``data/recordings`` and sorted by
their path, so the printed number is stable until new recordings are added.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


# Change this number before pressing Run.
FILE_NUMBER = 1

# The normal reconstruction settings are read from this file.
CONFIG_FILE = Path("config/reconstruction.toml")


def project_root() -> Path:
    """Return the event-camera component directory containing this script."""

    return Path(__file__).resolve().parents[1]


def recording_files(root: Path) -> list[Path]:
    """Return numbered RAW recordings in deterministic order."""

    return sorted(
        path for path in (root / "data" / "recordings").rglob("*.raw")
        if path.is_file()
    )


def choose_recording(root: Path, number: int) -> Path:
    files = recording_files(root)
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError("FILE_NUMBER must be a positive integer")
    if not files:
        raise FileNotFoundError(f"No .raw recordings found under {root / 'data' / 'recordings'}")
    if number > len(files):
        listing = "\n".join(f"  {index}: {path}" for index, path in enumerate(files, 1))
        raise IndexError(f"FILE_NUMBER={number} is out of range. Available files:\n{listing}")
    return files[number - 1]


def main() -> int:
    root = project_root()
    source = choose_recording(root, FILE_NUMBER)
    config = (root / CONFIG_FILE).resolve()
    launcher = root / "scripts" / "run_reconstruction.sh"

    if not config.is_file():
        raise FileNotFoundError(f"Missing reconstruction config: {config}")
    if not launcher.is_file():
        raise FileNotFoundError(f"Missing reconstruction launcher: {launcher}")

    print(f"File {FILE_NUMBER}: {source}", flush=True)
    print(f"Config: {config}", flush=True)
    subprocess.run(
        ["bash", str(launcher), str(source), "--config", str(config)],
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
