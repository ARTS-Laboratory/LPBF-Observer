"""Record native Metavision RAW streams without decoding or rendering events."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import sys
import threading
import time
import uuid

from . import __version__
# Camera controls and telemetry integration v1
from .camera_controls import read_config, apply_settings
from .stream_telemetry import StreamTelemetry


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_metadata(path, metadata):
    """Replace metadata atomically; leave the previous snapshot on write failure."""
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def file_size(path):
    return path.stat().st_size if path.exists() else 0


def camera_metadata(device):
    """Record available identity, geometry and biases without changing settings."""
    result = {}
    warnings = []
    queries = {
        "serial_number": ("get_i_hw_identification", "get_serial"),
        "integrator": ("get_i_hw_identification", "get_integrator"),
        "connection_type": ("get_i_hw_identification", "get_connection_type"),
        "event_format": ("get_i_hw_identification", "get_current_data_encoding_format"),
        "width": ("get_i_geometry", "get_width"),
        "height": ("get_i_geometry", "get_height"),
        "biases": ("get_i_ll_biases", "get_all_biases"),
    }
    for key, (getter, method) in queries.items():
        try:
            facility = getattr(device, getter)()
            if facility is not None:
                value = getattr(facility, method)()
                json.dumps(value)  # Skip SDK objects that cannot be serialized.
                result[key] = value
        except Exception as exc:
            warnings.append(f"{key}: {exc}")
    result["metadata_warnings"] = warnings
    return result


def select_serial(discovery, requested):
    if requested:
        return requested  # Accept full plugin-qualified identifiers unchanged.
    serials = list(discovery.list())
    if not serials:
        raise RuntimeError("No camera discovered. Check Ethernet, camera power, firewall and HAL plugin path.")
    if len(serials) > 1:
        raise RuntimeError("Multiple cameras found; specify --serial. Available: " + ", ".join(serials))
    return serials[0]


def record(discovery, *, output_dir, serial="", name="capture", duration=None,
           no_data_timeout=10.0, status_interval=1.0, stop_event=None, config_path=None):
    """Capture until duration, signal, stream failure or no-data timeout.

    One new directory per session prevents accidental overwrites. RAW logging is
    performed by HAL when get_latest_raw_data() consumes each queued buffer.
    No Python event conversion, image generation or HDF5 writing occurs here.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
        raise ValueError("Name must be 1–80 letters, digits, dots, underscores or hyphens; start with a letter/digit.")
    for label, value, allow_zero in (("duration", duration, False),
                                     ("no_data_timeout", no_data_timeout, True),
                                     ("status_interval", status_interval, False)):
        if value is not None and (not math.isfinite(value) or value < 0 or (not allow_zero and value == 0)):
            raise ValueError(f"Invalid {label}: {value}")
    config = read_config(config_path)
    stop_event = stop_event if stop_event is not None else threading.Event()
    selected = select_serial(discovery, serial)
    device = discovery.open(selected)
    if device is None:
        raise RuntimeError(f"Could not open camera {selected!r}.")
    stream = device.get_i_events_stream()
    if stream is None:
        raise RuntimeError("Camera does not expose I_EventsStream.")

    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%m_%d_%Y_T%H%M%S.%fZ")
    session = root / f"{name}-{stamp}"
    session.mkdir(exist_ok=False)
    raw_path = session / "events.raw"
    meta_path = session / "metadata.json"
    meta = {
        "schema_version": 2, "recorder_version": __version__, "state": "initializing",
        "created_utc": utc_now(), "raw_file": raw_path.name,
        "requested_serial": serial, "selected_source": selected,
        "requested_duration_seconds": duration, "no_data_timeout_seconds": no_data_timeout,
        "camera": camera_metadata(device), "python_version": platform.python_version(),
        "platform": platform.platform(),
        "runtime": {key: os.environ.get(key) for key in (
            "OPENEB_ROOT", "MV_HAL_PLUGIN_PATH", "MV_HAL_PLUGIN_SEARCH_MODE")},
        "buffers_consumed": 0, "raw_file_bytes": 0,
        "event_count": None, "losslessness_verified": False,
        "cleanup_errors": [],
    }
    write_metadata(meta_path, meta)
    start = None
    capture_end = None
    stream_attempted = False
    logging_attempted = False
    failure = None
    telemetry = None
    meta["camera_controls"] = {}
    print(f"Camera: {selected}\nSession: {session}", flush=True)
    try:
        meta["camera_before_settings"] = meta["camera"]
        apply_settings(device, config, meta["camera_controls"])
        meta["camera"] = camera_metadata(device)
        write_metadata(meta_path, meta)
        telemetry = StreamTelemetry(session / "stream_telemetry.csv", device, config["telemetry"])
        logging_attempted = True
        if not stream.log_raw_data(str(raw_path)):
            raise RuntimeError("HAL could not open the RAW output file.")
        stream_attempted = True
        stream.start()
        start = time.monotonic()
        telemetry.start(start)
        last_data = last_status = start
        meta.update(state="recording", started_utc=utc_now())
        write_metadata(meta_path, meta)
        print("Recording started automatically. Press Ctrl+C to stop.", flush=True)
        while not stop_event.is_set():
            now = time.monotonic()
            if duration is not None and now - start >= duration:
                meta["stop_reason"] = "duration_reached"
                break
            ready = stream.poll_buffer()  # Nonblocking: permits signal/time checks in a quiet scene.
            if ready < 0:
                raise RuntimeError("Live stream ended unexpectedly; camera may have disconnected.")
            if ready > 0:
                buffer = stream.get_latest_raw_data()  # This call writes the RAW buffer via HAL.
                if buffer is not None:
                    meta["buffers_consumed"] += 1
                    telemetry.consume(buffer)
                    last_data = time.monotonic()
                del buffer
            else:
                stop_event.wait(0.001)
            now = time.monotonic()
            if no_data_timeout and now - last_data >= no_data_timeout:
                raise RuntimeError(f"No RAW buffer received for {no_data_timeout:g}s. "
                                   "Check connectivity; use --no-data-timeout 0 for intentionally quiet capture.")
            telemetry.sample(file_size(raw_path))
            if now - last_status >= status_interval:
                meta.update(elapsed_seconds=now - start, raw_file_bytes=file_size(raw_path))
                meta["telemetry"] = telemetry.summary()
                write_metadata(meta_path, meta)
                print(f"{now - start:8.1f}s  {meta['raw_file_bytes'] / 2**20:10.1f} MiB  "
                      f"{meta['buffers_consumed']} buffers", flush=True)
                last_status = now
        else:
            meta["stop_reason"] = "signal"
    except KeyboardInterrupt:
        meta["stop_reason"] = "keyboard_interrupt"
    except Exception as exc:
        failure = exc
        if meta["camera_controls"].get("state") != "verified":
            meta["camera_controls"]["state"] = "failed"
        meta.update(state="error", stop_reason="error", error=str(exc))
    finally:
        capture_end = time.monotonic()
        # Stop the producer before closing the RAW log. The SDK may retain queued
        # buffers on stop; consume any available tail without restarting capture.
        if stream_attempted:
            try:
                stream.stop()
                drain_deadline = time.monotonic() + 10.0
                while stream.poll_buffer() > 0:
                    if time.monotonic() > drain_deadline:
                        raise RuntimeError("Stopped stream did not finish draining within 10 seconds.")
                    buffer = stream.get_latest_raw_data()
                    if buffer is not None:
                        meta["buffers_consumed"] += 1
                        if telemetry is not None:
                            telemetry.consume(buffer)
                    del buffer
            except Exception as exc:
                meta["cleanup_errors"].append(f"stop/drain: {exc}")
        if logging_attempted:
            try:
                stream.stop_log_raw_data()
            except Exception as exc:
                meta["cleanup_errors"].append(f"stop_log_raw_data: {exc}")
        if telemetry is not None:
            try:
                telemetry.sample(file_size(raw_path), force=True, phase="stopped")
                meta["telemetry"] = telemetry.summary()
            except Exception as exc:
                meta["cleanup_errors"].append(f"telemetry final sample: {exc}")
            finally:
                try:
                    telemetry.close()
                except Exception as exc:
                    meta["cleanup_errors"].append(f"telemetry close: {exc}")
        meta.update(
            stopped_utc=utc_now(), raw_file_bytes=file_size(raw_path),
            elapsed_seconds=0.0 if start is None else capture_end - start,
        )
        if failure is None and not meta["cleanup_errors"]:
            if meta["buffers_consumed"] == 0:
                failure = RuntimeError("Recording contains no consumed RAW buffers.")
                meta.update(error=str(failure), state="error")
            else:
                meta["state"] = "capture_stopped"
        else:
            meta["state"] = "error"
        write_metadata(meta_path, meta)
        print(f"RAW: {raw_path}\nMetadata: {meta_path}\nState: {meta['state']}", flush=True)
        # Metadata is finalized before device destruction, where the known vendor
        # crash may happen. Do not mask it with os._exit() or claim successful exit.
        stream = None
        device = None
    if failure:
        raise RuntimeError(f"{failure} Session retained at {session}") from failure
    if meta["cleanup_errors"]:
        raise RuntimeError("Cleanup failed: " + "; ".join(meta["cleanup_errors"]))
    return session


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List camera identifiers and exit")
    parser.add_argument("--check", action="store_true", help="Check Python binding import without opening a camera")
    parser.add_argument("--serial", default="", help="Exact camera identifier; auto-select only if one camera exists")
    parser.add_argument("--name", default="capture", help="Session name prefix")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(os.environ.get("EVENT_OUTPUT_DIR", "data/recordings")))
    parser.add_argument("--duration", type=float, help="Wall-clock seconds; omit to record until Ctrl+C")
    parser.add_argument("--no-data-timeout", type=float, default=10.0,
                        help="Stop on absent RAW buffers after this many seconds; 0 disables")
    parser.add_argument("--status-interval", type=float, default=1.0)
    parser.add_argument("--config", type=Path, help="Camera bias/ERC and telemetry TOML settings")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("Use Python 3.12 and Metavision bindings built for that interpreter.")
    try:
        previous_flags = sys.getdlopenflags() if sys.platform.startswith("linux") else None
        try:
            if previous_flags is not None:
                sys.setdlopenflags(previous_flags | os.RTLD_GLOBAL)
            hal = importlib.import_module("metavision_hal")
        finally:
            if previous_flags is not None:
                sys.setdlopenflags(previous_flags)
    except ImportError as exc:
        print(f"Cannot import metavision_hal: {exc}\n"
              "Build Python 3.12 OpenEB bindings and load scripts/run_recorder.sh; see README.md.", file=sys.stderr)
        return 2
    stop = threading.Event()
    previous_handlers = {}
    def request_stop(signum, frame):
        stop.set()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[sig] = signal.signal(sig, request_stop)
        if args.check:
            print(f"Python: {sys.version}\nmetavision_hal: {hal.__file__}", flush=True)
            return 0
        if args.list:
            sources = list(hal.DeviceDiscovery.list())
            print("\n".join(sources) if sources else "No cameras discovered.", flush=True)
            return 0 if sources else 1
        record(hal.DeviceDiscovery, output_dir=args.output_dir, serial=args.serial,
               name=args.name, duration=args.duration, no_data_timeout=args.no_data_timeout,
               status_interval=args.status_interval, stop_event=stop, config_path=args.config)
        return 0
    except Exception as exc:
        print(f"Recorder error: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
