"""Edit FILE_NUMBER, save, then press Run Python File in VS Code.

Place this file inside iteration_3/event_camera. Python launches the existing
Docker reconstruction; no native Metavision or NumPy imports are needed here.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

# ----- Change these settings before pressing Run -----
FILE_NUMBER = 20
LIST_ONLY = False  # True prints the numbered recordings without reconstructing.

# Optional: paste a full events.raw path here to override FILE_NUMBER.
INPUT_FILE = None  # Example: Path(r"C:\Users\THIENAN\lpbf-data\...\events.raw")

COMPONENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = COMPONENT_ROOT.parent
RECORDING_ROOTS = [
    COMPONENT_ROOT / "data" / "recordings",
    Path.home() / "documents" / "lpbf-data" / "event_camera" / "recordings",
]
CONFIG_FILE = COMPONENT_ROOT / "config" / "reconstruction.toml"
OUTPUT_ROOT = Path.home() / "documents" / "lpbf-data" / "reconstructions"
DOCKER_IMAGE = "lpbf-event-optical:0.1"

# None uses the value in reconstruction.toml (or the reconstruction default).
START_S = None
END_S = None
WINDOW_US = None
# ----------------------------------------------------


def recording_files(roots):
    files = {
        path.resolve()
        for root in roots
        for path in Path(root).rglob("*.raw")
        if path.is_file()
    }
    return sorted(files, key=lambda path: str(path).casefold())


def choose_recording(files, number, explicit):
    if explicit is not None:
        source = Path(explicit).expanduser()
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"RAW file not found: {source}")
        return source
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("FILE_NUMBER must be a positive integer")
    if not files:
        raise FileNotFoundError("No RAW recordings found. Set INPUT_FILE or edit RECORDING_ROOTS.")
    if number > len(files):
        raise ValueError(f"FILE_NUMBER={number}; choose a number from 1 to {len(files)}")
    return files[number - 1]


def docker_command(docker, source, config, output):
    # Argument lists preserve spaces in Windows paths. Mount the whole session
    # read-only so reconstruction can also read its adjacent metadata.json.
    for path in (source.parent, config, output):
        if "," in str(path):
            raise ValueError(f"Docker --mount cannot use this comma-containing path: {path}")
    command = [
        docker, "run", "--rm", "--pull=never",
        "--mount", f"type=bind,source={source.parent},target=/input,readonly",
        "--mount", f"type=bind,source={config},target=/settings/reconstruction.toml,readonly",
        "--mount", f"type=bind,source={output},target=/data",
        DOCKER_IMAGE, "reconstruct", f"/input/{source.name}",
        "--config", "/settings/reconstruction.toml", "--output-root", "/data",
    ]
    for option, value in (("--start-s", START_S), ("--end-s", END_S), ("--window-us", WINDOW_US)):
        if value is not None:
            command.extend([option, str(value)])
    return command


def main():
    files = recording_files(RECORDING_ROOTS)
    print("Available recordings (numbers can change when files are added):", flush=True)
    for number, path in enumerate(files, 1):
        print(f"  {number}: {path}", flush=True)
    if LIST_ONLY:
        return 0
    source = choose_recording(files, FILE_NUMBER, INPUT_FILE)
    config = CONFIG_FILE.resolve()
    if not config.is_file():
        raise FileNotFoundError(f"Config not found: {config}. Place this script in event_camera.")
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker was not found. Start Docker Desktop and reopen VS Code.")
    if subprocess.run([docker, "info"], capture_output=True).returncode:
        raise RuntimeError("Docker engine is unavailable. Start Docker Desktop, then retry.")
    if subprocess.run([docker, "image", "inspect", DOCKER_IMAGE], capture_output=True).returncode:
        raise RuntimeError(f"Local Docker image {DOCKER_IMAGE} is missing. Build or load it first.")
    output = OUTPUT_ROOT.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    print(f"Selected RAW: {source}\nConfig: {config}\nOutput folder: {output}", flush=True)
    result = subprocess.run(docker_command(docker, source, config, output))
    print(f"Reconstruction exit code: {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Reconstruction launcher: {error}", file=sys.stderr)
        raise SystemExit(1)
