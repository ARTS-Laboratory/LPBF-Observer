#!/usr/bin/env bash
# Reuse the existing, locally patched OpenEB source in a separate build directory.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${EVENT_PYTHON:-$project_root/.venv/bin/python}"
source_root="${OPENEB_SOURCE:-$HOME/src/openeb-5.2.0}"
build_root="${OPENEB_BUILD:-$project_root/.build/openeb-py312}"
opencv_root="${OPENCV_ROOT:-$HOME/opt/opencv-4.12.0}"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
pybind_dir="$("$python_bin" -m pybind11 --cmakedir)"
cmake -S "$source_root" -B "$build_root" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$project_root/.deps/openeb-py312" \
    -DOpenCV_DIR="$opencv_root/lib/cmake/opencv4" \
    -DPython3_EXECUTABLE="$python_bin" \
    -Dpybind11_DIR="$pybind_dir" \
    -DCOMPILE_PYTHON3_BINDINGS=ON \
    -DBUILD_TESTING=OFF \
    -DBUILD_SAMPLES=OFF \
    -DCMAKE_CXX_FLAGS="-include cstdint -DH5Dread_chunk_vers=1"
cmake --build "$build_root" --parallel "${BUILD_JOBS:-4}"
# Use the build-tree py3 and lib directories. No sudo install or udev changes.
OPENEB_ROOT="$build_root" bash "$project_root/scripts/run_recorder.sh" --check
