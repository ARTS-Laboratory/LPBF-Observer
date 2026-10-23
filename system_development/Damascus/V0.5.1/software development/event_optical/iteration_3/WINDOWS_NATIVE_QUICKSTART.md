# Native Windows acquisition

These launchers use the existing camera programs in separate native Python processes. The event program records RAW files; the optical program supports single images, image sequences, and command-driven capture. Only the coordinator decides to take a post-recording image. Docker remains available for offline analysis and reconstruction.

## Install into the existing project

Extract `windows-native-launchers.zip` **into `iteration_3`**, alongside `compose.yaml`. The ZIP contains `event_camera`, `coordinator`, `tests_windows`, and this guide; it does not contain an extra wrapping directory. Existing Linux launchers and camera configurations are not replaced.

From PowerShell at the project root, run once:

```powershell
py -3.12 .\coordinator\install_windows_support.py
```

This patches only the optical `serve` stdin reader: Windows cannot use `select()` on a stdin pipe, so a reader thread supplies commands through a queue. The original bytes are saved as `optical_camera/capture.py.before-windows-pipes.bak`. If the expected source block is absent, the installer stops without changing the file. Do not run paired capture until the patch succeeds.

The optical camera's existing `config/camera.toml` is used unchanged. For the tested Blackfly, use `exposure_us = 1010.0`; requesting 1000.0 previously read back 1010.0 and correctly failed verification. This package does not change exposure automatically.

## SDK paths

`coordinator/windows_settings.py` supplies paths for both launchers. Defaults match the tested setup:

- Event Python: `~/Documents/camera-sdks/openeb-4.6.2/.venv-py312/Scripts/python.exe` (Python 3.12, NumPy 1.26.4, compiled OpenEB 4.6.2 bindings).
- OpenEB DLLs: `~/Documents/camera-sdks/openeb-4.6.2-py312/bin`.
- Dependency DLLs: `~/Documents/camera-sdks/openeb-4.6.2-deps/vcpkg_installed/x64-windows-v143/bin`.
- Arena DLLs/plugin: `C:\Program Files\Lucid Vision Labs\Arena SDK\x64Release`.
- Optical Python: `optical_camera/.venv/Scripts/python.exe` with the working native PySpin installation.
- Event source: `:lucid_imx63x_plugin:250200198`.
- Optical serial: `19328838`.

No environment activation, administrator terminal, WSL, Docker, or Developer Command Prompt is required for **acquisition**. SDK compilation and installation must already be complete. Close ArenaView and SpinView before capture. Keep the SDK source virtual environment and installed DLL folders in place.

## Event camera only: press Run

Open `event_camera/run_windows.py` in VS Code and edit:

```python
NAME = "event-recording"
DURATION_SECONDS = 5
```

Press **Run Python File**. Any normal Windows Python 3.12 interpreter can launch this file; it starts the configured event Python itself. Relative paths resolve from the file's location, so the terminal's current directory does not matter.

Command-line equivalent from PowerShell at `iteration_3`:

```powershell
py -3.12 .\event_camera\run_windows.py
```

Each capture creates a new session under `event_camera/data/recordings`, with `events.raw`, `metadata.json`, and telemetry. `event_camera/config/recorder-windows.toml` is a separate Windows configuration: omitted bias/ERC settings leave camera settings unchanged. Add settings only after checking the camera's supported ranges/readback.

The existing telemetry collector's NIC and UDP counters use Linux `/sys` and `/proc`; those fields remain unavailable on Windows. Payload/buffer rates and optional decoder statistics remain available. This package does not claim Windows packet-loss telemetry.

## Event + optical: press Run

Open `coordinator/run_paired_windows.py`, edit the same two variables, and press **Run Python File**:

```python
NAME = "paired-experiment"
DURATION_SECONDS = 5
```

Or from PowerShell:

```powershell
py -3.12 .\coordinator\run_paired_windows.py
```

The coordinator:

1. Checks both Python environments before making a run directory.
2. Opens the optical worker and waits for `ready`; no photo is requested yet.
3. Runs the event recorder for the chosen duration.
4. Requires a zero exit status, `capture_stopped` metadata, no recorded cleanup errors, and a nonempty RAW file.
5. Requests exactly one new software-triggered optical photo.
6. Stops the optical worker and verifies exactly one saved, nonempty photo before reporting `complete`.

A failed event capture never requests a photo. A failed or missing optical photo makes the experiment `error`. Ctrl+C during event recording asks the event process to stop gracefully; if that stop succeeds and the RAW session is clean, the photo follows. If you stop the coordinator before the optical worker is ready, the run ends in error without a photo. Avoid using VS Code's force-stop button when a graceful shutdown is needed.

This is software sequencing after event finalization, **not hardware synchronization or a weld-completion sensor**. The optical camera is already open to reduce delay, but the delay is not guaranteed and must be measured on Windows.

Paired outputs use the short directory `C:\Users\THIENAN\lpbf-data` by default (`Path.home() / "lpbf-data"`). The project can remain in its current location. This avoids Windows/vendor SDK path-length failures caused by nested session folders. Change `PAIRED_DATA_ROOT` in `coordinator/windows_settings.py` if another short directory is needed. Event-only captures continue using `event_camera/data/recordings`.

Paired outputs share one run ID; these locations are relative to `PAIRED_DATA_ROOT`:

| Output | Location |
| --- | --- |
| Event RAW and metadata | `event_camera/recordings/<run-id>/events-…/` |
| Optical image, frame CSV, metadata | `optical_camera/recordings/<run-id>/optical-…/` |
| Experiment manifest and optical worker log | `runs/<run-id>/` |

The manifest stores its absolute `data_root`, file paths relative to that root, event stop time, photo request time, optical frame timestamps, and failure details. Output folders always receive a UTC timestamp and random suffix. Edit `NAME` to set the human-readable label. Paired run timestamps are formatted in `coordinator/native_experiment.py` at `run_id`; camera session timestamps remain controlled by each camera's own program.

## First verification

Run event-only once, then paired once. For paired capture, expect `State: complete` and one optical image. Confirm timing from PowerShell (selects the newest Windows-native run):

```powershell
@'
import json
from datetime import datetime
from pathlib import Path
runs = []
for path in (Path.home() / "lpbf-data" / "runs").glob("*/manifest.json"):
    data = json.loads(path.read_text())
    if data.get("backend") == "windows-native":
        runs.append((path, data))
if not runs:
    raise SystemExit("No native Windows runs found")
path, data = max(runs, key=lambda item: item[0].stat().st_mtime_ns)
print("Manifest:", path)
print("State:", data["state"])
if data["state"] != "complete":
    raise SystemExit(data.get("error", "Run did not complete"))
a = datetime.fromisoformat(data["timing"]["event_stopped_utc"])
b = datetime.fromisoformat(data["optical_capture"]["frame"]["trigger_issued_utc"])
print("Trigger delay after event finalization:", (b-a).total_seconds(), "seconds")
print("Photo:", Path(data["data_root"]) / data["optical_image"])
'@ | py -3.12 -
```

For paired outputs, mount the short output root explicitly for offline Docker analysis. From PowerShell, replace the example RAW path with the one from the manifest:

```powershell
docker run --rm `
  --mount "type=bind,source=$HOME\lpbf-data,target=/data" `
  lpbf-event-optical:0.1 analyze `
  /data/event_camera/recordings/<run-id>/<event-session>/events.raw `
  --bin-us 250000 --plot
```

Use `reconstruct` instead of `analyze` and `--config /app/config/reconstruction.toml` for reconstruction using the image's built-in configuration, or additionally mount your project `event_camera/config` at `/settings` to use edited settings. The original Compose file still mounts the project's event-camera data directory; it cannot see the new paired outputs unless its mount is changed. Event-only outputs still use the original Compose mount. Native acquisition does not set Compose variables in your terminal.

## Hardware-free checks

After applying the stdin patch:

```powershell
py -3.12 -m unittest discover -s tests_windows -v
```

The optical pipe tests use the existing `optical_camera/tests/test_capture.py` fixtures. Tests cover photo ordering, failed event captures, missing photos, optical failures, response IDs, stdin EOF, cleanup commands, and the guarded patch. They do not prove SDK ABI compatibility, actual packet completeness, or physical trigger timing. A live paired Windows run remains required.

For single optical images and continuous sequences, continue using the existing `optical_camera/capture.py` modes with its native `.venv`. The event camera's general recorder and optical acquisition policy remain independent of the experiment coordinator.
