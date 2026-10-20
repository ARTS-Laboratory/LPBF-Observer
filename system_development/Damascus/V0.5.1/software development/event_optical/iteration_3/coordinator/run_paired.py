"""Run one paired event-camera plus post-recording optical-camera experiment.

Edit NAME and DURATION_SECONDS below, then run this file from Visual Studio.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


# Change these values before pressing Run.
NAME = "test_1_lol"
DURATION_SECONDS = 5


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    launcher = root / "coordinator" / "run_experiment.py"

    if not isinstance(NAME, str) or not NAME.strip():
        raise ValueError("NAME must be a non-empty string")
    if not isinstance(DURATION_SECONDS, (int, float)) or isinstance(DURATION_SECONDS, bool):
        raise ValueError("DURATION_SECONDS must be a positive number")
    if DURATION_SECONDS <= 0:
        raise ValueError("DURATION_SECONDS must be greater than zero")
    if not launcher.is_file():
        raise FileNotFoundError(f"Missing paired experiment coordinator: {launcher}")

    print(f"Name: {NAME}", flush=True)
    print(f"Event-camera duration: {DURATION_SECONDS} seconds", flush=True)
    subprocess.run(
        [sys.executable, str(launcher), "--name", NAME, "--duration", str(DURATION_SECONDS)],
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
