"""Load Windows HAL DLLs, then run the existing general event recorder."""
from __future__ import annotations
import os
from pathlib import Path
import signal
import sys
import ctypes
import windows_settings as settings

# Keep SDK lookup paths registered through interpreter/native module finalization.
# Removing them does not unload DLLs, but can prevent late dependency loads.
_DLL_DIRECTORY_HANDLES = []
_ARENA_LIBRARIES = []

def check_paths(*paths):
    for path in paths:
        if not Path(path).exists():
            raise FileNotFoundError(f"Missing: {path}. Check coordinator/windows_settings.py.")


def event_command(arguments):
    return [str(settings.EVENT_PYTHON), str(Path(__file__).resolve()), *map(str, arguments)]


def validate_settings(name, duration):
    import math
    import re
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise ValueError("NAME must start with a letter/digit and contain 1–64 letters, digits, dots, underscores or hyphens")
    if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("DURATION_SECONDS must be a positive finite number")


def stop_event(process, timeout=40):
    if process.poll() is None:
        process.send_signal(signal.CTRL_BREAK_EVENT)
    return process.wait(timeout=timeout)


def main(arguments=None):
    if sys.platform != "win32":
        raise RuntimeError("This launcher is for native Windows. Use the existing Linux launchers on Linux.")
    directories = [settings.DEPENDENCY_BIN, settings.ARENA_BIN, settings.OPENEB_INSTALL / "bin"]
    check_paths(*directories, settings.ROOT / "event_camera" / "src" / "event_optical" / "recorder.py")
    # Retain handles throughout recording; releasing one removes that DLL directory.
    _DLL_DIRECTORY_HANDLES.extend(os.add_dll_directory(str(path)) for path in directories)
    os.environ["PATH"] = os.pathsep.join(map(str, directories)) + os.pathsep + os.environ.get("PATH", "")
    plugin_directory = (
        Path.home() / "Documents" / "camera-sdks" / "lucid-hal-only"
    )
    check_paths(plugin_directory / "lucid_imx63x_plugin.dll")

    # Retain Arena before Metavision loads and later releases its plugin.
    _ARENA_LIBRARIES.append(
        ctypes.WinDLL(str(settings.ARENA_BIN / "ArenaC_v140.dll"))
    )
    os.environ["MV_HAL_PLUGIN_PATH"] = str(plugin_directory)
    sys.path.insert(0, str(settings.ROOT / "event_camera" / "src"))
    # The coordinator uses CTRL_BREAK for a graceful stop of this process group.
    previous = signal.getsignal(signal.SIGBREAK)
    def stop_from_break(signum, frame):
        handler = signal.getsignal(signal.SIGINT)
        if callable(handler):
            handler(signal.SIGINT, frame)
    signal.signal(signal.SIGBREAK, stop_from_break)
    try:
        from event_optical.recorder import main as record
        print("[shutdown] entering recorder main", flush=True)
        result = record(sys.argv[1:] if arguments is None else arguments)
        print(f"[shutdown] recorder main returned {result}", flush=True)
        return result
    finally:
        print("[shutdown] restoring break handler", flush=True)
        signal.signal(signal.SIGBREAK, previous)
        print("[shutdown] SDK DLL search paths remain registered until process exit", flush=True)
        print("[shutdown] runtime cleanup finished; returning to Python", flush=True)


if __name__ == "__main__":
    try:
        status = main()
        print(f"[shutdown] Python exit requested: {status}", flush=True)
        raise SystemExit(status)
    except Exception as error:
        print(f"Windows event recorder: {error}", file=sys.stderr)
        raise SystemExit(1)
