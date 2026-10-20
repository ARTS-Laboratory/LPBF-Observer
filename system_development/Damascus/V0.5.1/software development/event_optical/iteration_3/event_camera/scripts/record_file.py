"""Start one event-camera recording with editable Run settings.

Edit NAME and DURATION_SECONDS below, then run this file from Visual Studio.
The existing recorder shell launcher remains responsible for SDK paths,
camera controls, telemetry, graceful shutdown, and metadata.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


# Change these values before pressing Run.
NAME = "event-recording"
DURATION_SECONDS = 5

# The qualified camera identifier discovered by the Arena/Lucid SDK.
SERIAL = "Lucid Vision Labs:lucid_imx63x_plugin5:250200198"

CONFIG_FILE = Path("config/recorder.toml")


def project_root() -> Path:
    """Return the event-camera component directory containing this script."""

    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = project_root()
    config = (root / CONFIG_FILE).resolve()
    launcher = root / "scripts" / "run_recorder.sh"

    if not isinstance(NAME, str) or not NAME.strip():
        raise ValueError("NAME must be a non-empty string")
    if not isinstance(DURATION_SECONDS, (int, float)) or isinstance(DURATION_SECONDS, bool):
        raise ValueError("DURATION_SECONDS must be a positive number")
    if DURATION_SECONDS <= 0:
        raise ValueError("DURATION_SECONDS must be greater than zero")
    if not config.is_file():
        raise FileNotFoundError(f"Missing recorder config: {config}")
    if not launcher.is_file():
        raise FileNotFoundError(f"Missing recorder launcher: {launcher}")

    print(f"Name: {NAME}", flush=True)
    print(f"Duration: {DURATION_SECONDS} seconds", flush=True)
    subprocess.run(
        [
            "bash",
            str(launcher),
            "--config",
            str(config),
            "--serial",
            SERIAL,
            "--name",
            NAME,
            "--duration",
            str(DURATION_SECONDS),
        ],
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
