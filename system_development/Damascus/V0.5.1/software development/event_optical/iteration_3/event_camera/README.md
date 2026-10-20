# Event optical — iteration 3

Python 3.12 native RAW recorder for the LUCID event camera. This is the first
recorder version; reconstruction and a tested Docker image are future work.

## Setup on the current EndeavourOS machine

Extract this package's contents into:

```text
/home/thienan/Documents/GitHub/LPBF-Observer/system_development/Damascus/V0.5.1/software development/event_optical/iteration_3
```

The existing C++ OpenEB build has Python bindings disabled. It cannot supply
`metavision_hal` until bindings are built for Python 3.12. Do not use the system
Python 3.14 or try to install Metavision with an unrelated PyPI package.

If `python3.12` is already available:

```bash
cd "/home/thienan/Documents/GitHub/LPBF-Observer/system_development/Damascus/V0.5.1/software development/event_optical/iteration_3"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python -m pip install -e .
```

Alternatively, if `uv` is already available, it can provision Python 3.12:

```bash
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements-build.txt
uv pip install -e .
```

Use one route. If neither tool exists, first install a separate Python 3.12;
leave Arch's system Python in place.

Build Python-enabled OpenEB using the existing locally patched 5.2.0 source and
OpenCV 4.12.0 installation:

```bash
bash scripts/build_openeb_python.sh
export OPENEB_ROOT="$PWD/.build/openeb-py312"
bash scripts/run_recorder.sh --check
```

The build script uses `.build/openeb-py312` inside this project, leaving the
working C++ build and installation in place. It carries forward the `<cstdint>`
and HDF5 API compatibility flags needed on this Arch system. It does not install
udev rules or change firewall/network settings. This native build recipe has
not been executed on your hardware; if configuration or compilation fails, keep
the first error and resolve it before attempting camera recording.

The launcher uses build-tree `lib` and `py3` directories. If the OpenEB source
checks demand additional Python packages, install the reported build dependency
in `.venv` and record it in `requirements-build.txt`. The recorder itself uses
Python's standard library and the HAL binding; NumPy is included for the binding.

## List and record

Keep the camera powered and connected to `enp3s0`, using the working link-local
NetworkManager profile and firewalld rules. For the selected camera, the last
verified IP was `169.254.59.67`, host `169.254.218.157`, serial `250200198`.
Those network addresses are not assumed or changed by Python.

```bash
bash scripts/run_recorder.sh --list
```

Copy the exact returned identifier if it includes a plugin prefix. Otherwise:

```bash
bash scripts/run_recorder.sh --serial 250200198 --name trt009-test --duration 20
```

Recording starts immediately, with no Space key required. Omit `--duration` to
record until Ctrl+C. SIGTERM also requests a normal stop, for a future container.
Only one automatically discovered camera is selected without `--serial`;
multiple cameras require an explicit selection.

Choose a different output directory when needed:

```bash
bash scripts/run_recorder.sh --serial 250200198 \
    --output-dir "$HOME/Documents/event-recordings" --name weld-001
```

By default, each session is a new directory under `data/recordings`, named with
a UTC timestamp and random suffix. It contains:

| File | Contents |
| --- | --- |
| `events.raw` | Native RAW stream and the SDK's camera header |
| `metadata.json` | Identity, available geometry/biases, timestamps, duration, buffers, file size, errors |

No preview, per-event Python conversion or reconstruction runs during capture.
Status reports raw file size and consumed buffers, **not decoded event rate**.
RAW bytes include protocol words; they cannot be converted into an event count
by dividing by an assumed event size. A future offline decoder can count events.
Biases are read when supported; unsupported metadata fields are listed as
warnings. The recorder does not apply new thresholds, ROI, ERC or camera settings.

The default no-data timeout is 10 seconds. An intentionally silent scene or
external trigger may need `--no-data-timeout 0`. A timeout or stream error leaves
the session on disk and reports failure. Output size updates may lag briefly
because the SDK buffers file writes.

## Playback check

After recording, use the path printed by the recorder:

```bash
MV_HAL_PLUGIN_PATH="$HOME/opt/openeb-5.2.0/lib/metavision/hal/plugins" \
MV_HAL_PLUGIN_SEARCH_MODE=PLUGIN_PATH_ONLY \
metavision_viewer -i "/absolute/path/to/session/events.raw"
```

This uses the Prophesee offline decoder, which already produced smooth playback
for this camera. Use the environment from the working C++ viewer terminal.

## SDK paths

Only the Bash launcher supplies the current machine's SDK defaults. The Python
recorder uses the process environment and accepts a configurable output path.

| Environment variable | Default in the launcher |
| --- | --- |
| `OPENEB_ROOT` | Project `.build/openeb-py312` |
| `ARENA_ROOT` | `$HOME/opt/arena/ArenaSDK_Linux_x64` |
| `OPENCV_ROOT` | `$HOME/opt/opencv-4.12.0` |
| `MV_HAL_PLUGIN_PATH` | `$HOME/opt/lucid-hal-release` |
| `METAVISION_PYTHON_DIR` | `$OPENEB_ROOT/py3` |
| `EVENT_PYTHON` | Project `.venv/bin/python` |
| `EVENT_OUTPUT_DIR` | Project `data/recordings` |

Your previous shell may still export `OPENEB_ROOT` pointing to the C++-only
installation. Override it explicitly for this recorder:

```bash
OPENEB_ROOT="$PWD/.build/openeb-py312" bash scripts/run_recorder.sh --check
```

For subsequent commands either use that prefix or export the new `OPENEB_ROOT`.
The release-only LUCID plugin directory must contain the symlink established
during setup. Both Arena library directories and its bundled Metavision 4 libs
remain necessary for the vendor's transitive dependencies.

## Validation and known limitations

Run hardware-independent checks:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

They exercise recording lifecycle, interrupted sessions, empty capture,
disconnect/error cleanup, selection and overwrite prevention using a fake HAL.
They do not establish compatibility, lossless recording or reliable native
shutdown on the camera. Validate a 20-second hand-wave capture and playback on
the real system before collecting experimental data.

The existing LUCID/Arena shutdown abort (`boost::lock_error`) is unresolved.
Python attempts `stop`, drains available queued buffers, closes RAW logging and
writes final metadata before releasing the device. A native abort can bypass
Python cleanup, including during any SDK call. `capture_stopped` describes the
Python capture lifecycle, not proof of a clean process exit or file integrity.
Earlier playback also reported `InvalidVectBase`; investigate event stream
integrity separately. This implementation does not hide native errors or claim
that recording is lossless.

## References

- [Metavision RAW recording guide](https://docs.prophesee.ai/stable/guides/events_recording.html)
- [HAL Python API](https://docs.prophesee.ai/stable/api/python/hal/bindings.html)
- [OpenEB 5.2.0 source](https://github.com/prophesee-ai/openeb/tree/5.2.0)

Current online API documentation may describe a newer SDK. The included recorder
must still be checked against the locally built 5.2.0 bindings.
