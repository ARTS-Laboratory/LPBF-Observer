"""Event camera only: change NAME and DURATION_SECONDS, then press Run in VS Code."""
from pathlib import Path
import subprocess
import sys

NAME = "event-recording"
DURATION_SECONDS = 5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "coordinator"))
import windows_settings as settings
from windows_runtime import check_paths, event_command, validate_settings, stop_event


def main():
    if sys.platform != "win32":
        raise RuntimeError("Use the Linux launcher on Linux; this file is for native Windows.")
    validate_settings(NAME, DURATION_SECONDS)
    check_paths(settings.EVENT_PYTHON, settings.EVENT_CONFIG)
    print(f"Name: {NAME}\nEvent-camera duration: {DURATION_SECONDS} seconds", flush=True)
    process = subprocess.Popen(event_command([
        "--config", settings.EVENT_CONFIG, "--serial", settings.EVENT_SERIAL,
        "--name", NAME, "--duration", DURATION_SECONDS,
        "--output-dir", ROOT / "event_camera" / "data" / "recordings",
    ]), cwd=ROOT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        return process.wait()
    except KeyboardInterrupt:
        print("Stopping event recording gracefully...", flush=True)
        try:
            return stop_event(process)
        except BaseException:
            process.kill()
            process.wait(timeout=10)
            raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Cannot start event recording: {error}", file=sys.stderr)
        raise SystemExit(1)
