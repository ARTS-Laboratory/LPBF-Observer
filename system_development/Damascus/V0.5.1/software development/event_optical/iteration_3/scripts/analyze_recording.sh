#!/usr/bin/env bash
# Offline reconstruction uses only the patched Prophesee RAW plugin.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export OPENEB_ROOT="${OPENEB_ROOT:-$project_root/.build/openeb-py312}"
python_bin="${EVENT_PYTHON:-$project_root/.venv/bin/python}"
plugin_dir="$project_root/.deps/prophesee-hal"
"$python_bin" - "$OPENEB_ROOT" "$plugin_dir" <<'PY'
from pathlib import Path
import sys
root, destination = map(Path, sys.argv[1:])
target = root / 'lib/libhal_plugin_prophesee.so'
if not target.is_file():
    raise SystemExit(f'Missing rebuilt Prophesee RAW plugin: {target}')
destination.mkdir(parents=True, exist_ok=True)
link = destination / 'libhal_plugin_prophesee.so'
if link.exists() and not link.is_symlink():
    raise SystemExit(f'Refusing to replace regular file: {link}')
link.unlink(missing_ok=True)
link.symlink_to(target.resolve())
PY
export PYTHONPATH="$project_root/src:$OPENEB_ROOT/py3${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$OPENEB_ROOT/lib:$OPENEB_ROOT/lib64:${OPENCV_ROOT:-$HOME/opt/opencv-4.12.0}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MV_HAL_PLUGIN_PATH="$plugin_dir"
export MV_HAL_PLUGIN_SEARCH_MODE=PLUGIN_PATH_ONLY
export MV_FLAGS_EVT3_ROBUST_DECODER=1
exec "$python_bin" -u -m event_optical.event_analysis "$@"
