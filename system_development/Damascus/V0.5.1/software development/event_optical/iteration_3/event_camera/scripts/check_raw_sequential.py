"""Decode RAW with consecutive HAL buffers; disable file indexing and seeking."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


def run(path, chunk_bytes, fingerprint=False):
    flags = sys.getdlopenflags() if sys.platform.startswith("linux") else None
    try:
        if flags is not None:
            sys.setdlopenflags(flags | os.RTLD_GLOBAL)
        hal = importlib.import_module("metavision_hal")
    finally:
        if flags is not None:
            sys.setdlopenflags(flags)
    config = hal.RawFileConfig()
    config.build_index = False
    config.n_events_to_read = chunk_bytes // 2  # EVT3 has 2-byte raw words.
    device = hal.DeviceDiscovery.open_raw_file(str(path.resolve()), config)
    if device is None:
        raise RuntimeError("Could not open RAW device")
    decoder = device.get_i_events_stream_decoder()
    cd = device.get_i_event_cd_decoder()
    stream = device.get_i_events_stream()
    if decoder is None or cd is None or stream is None:
        raise RuntimeError("File has no stream / event stream decoder / CD decoder")
    geometry = device.get_i_geometry()
    stats = {"path": str(path.resolve()), "chunk_bytes": chunk_bytes,
             "width": geometry.get_width() if geometry is not None else None,
             "height": geometry.get_height() if geometry is not None else None,
             "decoded_events": 0, "first_timestamp_us": None,
             "last_timestamp_us": None, "negative_timestamp_transitions": 0,
             "out_of_bounds_events": 0, "raw_bytes_fed": 0, "raw_buffers_fed": 0,
             "indexing_enabled": False}
    digest = hashlib.sha256() if fingerprint else None

    def on_events(events):
        if not len(events):
            return
        ts = events["t"]
        if stats["first_timestamp_us"] is None:
            stats["first_timestamp_us"] = int(ts[0])
        previous = stats["last_timestamp_us"]
        if previous is not None and int(ts[0]) < previous:
            stats["negative_timestamp_transitions"] += 1
        stats["negative_timestamp_transitions"] += int(np.count_nonzero(ts[1:] < ts[:-1]))
        stats["last_timestamp_us"] = int(ts[-1])
        stats["decoded_events"] += len(events)
        if digest is not None:
            canonical = np.empty(len(events), dtype=[("x", "<u2"), ("y", "<u2"),
                                                      ("p", "<i2"), ("t", "<i8")])
            for name in canonical.dtype.names:
                canonical[name] = events[name]
            digest.update(canonical.tobytes())
        if stats["width"] is not None and stats["height"] is not None:
            invalid = ((events["x"] < 0) | (events["x"] >= stats["width"]) |
                       (events["y"] < 0) | (events["y"] >= stats["height"]))
            stats["out_of_bounds_events"] += int(np.count_nonzero(invalid))

    callback_id = cd.add_event_buffer_callback(on_events)
    start = time.monotonic()
    try:
        with path.open("rb") as handle:
            for _ in range(256):
                line = handle.readline(4096)
                if not line.startswith(b"%"):
                    raise ValueError("Header has no '% end' marker")
                if line.strip() == b"% end":
                    break
            else:
                raise ValueError("Header too long")
            payload_offset = handle.tell()
            if (path.stat().st_size - payload_offset) % 2:
                raise ValueError("EVT3 payload has an incomplete 16-bit word")
        print(f"Geometry: {stats['width']} x {stats['height']}; chunk bytes: {chunk_bytes}", flush=True)
        stream.start()
        while stream.wait_next_buffer() > 0:
            buffer = stream.get_latest_raw_data()
            if buffer is not None:
                # Pass the SDK's RawBuffer directly; NumPy arrays are not accepted
                # by the object overload in the locally built 5.2.0 binding.
                decoder.decode(buffer)
                stats["raw_bytes_fed"] += buffer.size()
                stats["raw_buffers_fed"] += 1
            del buffer
    finally:
        try:
            stream.stop()
        finally:
            cd.remove_callback(callback_id)
    stats["decode_wall_seconds"] = time.monotonic() - start
    stats["expected_payload_bytes"] = path.stat().st_size - payload_offset
    if digest is not None:
        stats["event_sha256"] = digest.hexdigest()
    print("SEQUENTIAL_RESULT " + json.dumps(stats, sort_keys=True), flush=True)
    stream = decoder = cd = geometry = device = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--chunk-bytes", type=int, default=1048576)
    parser.add_argument("--fingerprint", action="store_true", help="Hash canonical decoded x/y/p/t events")
    args = parser.parse_args()
    if args.chunk_bytes < 2 or args.chunk_bytes % 2:
        parser.error("--chunk-bytes must be a positive multiple of 2")
    run(args.path, args.chunk_bytes, args.fingerprint)
