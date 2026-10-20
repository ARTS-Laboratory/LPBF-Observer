#!/usr/bin/env bash
# Start in any directory. Override SDK locations through environment variables.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export OPENEB_ROOT="${OPENEB_ROOT:-$project_root/.build/openeb-py312}"
export ARENA_ROOT="${ARENA_ROOT:-$HOME/opt/arena/ArenaSDK_Linux_x64}"
export OPENCV_ROOT="${OPENCV_ROOT:-$HOME/opt/opencv-4.12.0}"
export MV_HAL_PLUGIN_PATH="${MV_HAL_PLUGIN_PATH:-$HOME/opt/lucid-hal-release}"
export MV_HAL_PLUGIN_SEARCH_MODE="${MV_HAL_PLUGIN_SEARCH_MODE:-PLUGIN_PATH_ONLY}"
export LD_LIBRARY_PATH="$OPENEB_ROOT/lib:$OPENEB_ROOT/lib64:$OPENCV_ROOT/lib:$ARENA_ROOT/lib64:$ARENA_ROOT/GenICam/library/lib/Linux64_x64:$ARENA_ROOT/Metavision/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$project_root/src:${METAVISION_PYTHON_DIR:-$OPENEB_ROOT/py3}${PYTHONPATH:+:$PYTHONPATH}"
export EVENT_OUTPUT_DIR="${EVENT_OUTPUT_DIR:-$project_root/data/recordings}"
python_bin="${EVENT_PYTHON:-$project_root/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
    echo "Python not found: $python_bin. Create the Python 3.12 environment described in README.md." >&2
    exit 2
fi
export LD_PRELOAD="libgentl.so.1${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$python_bin" -u -m event_optical.recorder "$@"
