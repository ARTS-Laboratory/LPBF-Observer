"""Shared Windows paths. Edit these if the SDKs move; no terminal setup needed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK_HOME = Path.home() / "Documents" / "camera-sdks"
OPENEB_SOURCE = SDK_HOME / "openeb-4.6.2"
OPENEB_INSTALL = SDK_HOME / "openeb-4.6.2-py312"
EVENT_PYTHON = OPENEB_SOURCE / ".venv-py312" / "Scripts" / "python.exe"
DEPENDENCY_BIN = SDK_HOME / "openeb-4.6.2-deps" / "vcpkg_installed" / "x64-windows-v143" / "bin"
ARENA_BIN = Path(r"C:\Program Files\Lucid Vision Labs\Arena SDK\x64Release")
OPTICAL_PYTHON = ROOT / "optical_camera" / ".venv" / "Scripts" / "python.exe"
EVENT_SERIAL = ":lucid_imx63x_plugin:250200198"
OPTICAL_SERIAL = "19328838"
EVENT_CONFIG = ROOT / "event_camera" / "config" / "recorder-windows.toml"
OPTICAL_CONFIG = ROOT / "optical_camera" / "config" / "camera.toml"

# Keep native paired capture paths short for Windows and vendor SDK file APIs.
# Manifests store file paths relative to this directory.
PAIRED_DATA_ROOT = Path.home() / "documents" / "lpbf-data"
