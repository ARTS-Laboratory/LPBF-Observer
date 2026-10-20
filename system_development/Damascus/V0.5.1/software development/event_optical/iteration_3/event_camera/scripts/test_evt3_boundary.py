"""Native HAL regression: the same valid RAW fixture must survive every split.

Run with the same PYTHONPATH, LD_LIBRARY_PATH and Prophesee HAL plugin environment
as check_raw_sequential.py. This invokes the actual installed decoder.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", type=Path, help="Also compare a real recording across chunk sizes")
    args = parser.parse_args()
    checker = Path(__file__).with_name("check_raw_sequential.py")
    # TIME_HIGH, TIME_LOW, Y=1, payload-free OTHERS, BASE_X=0,
    # VECT12(bit0 set), VECT12(empty), VECT8(empty) -> one CD event.
    # With 8-byte chunks, OTHERS ends chunk 1. Its maximum lookahead consumes
    # BASE_X and the first two vector words from chunk 2, ending mid-vector.
    words = (0x8001, 0x6001, 0x0001, 0xE123, 0x3000, 0x4001, 0x4000, 0x5000)
    header = b"% evt 3.0\n% format EVT3;height=720;width=1280\n% end\n"
    env = dict(os.environ)
    env["MV_FLAGS_EVT3_ROBUST_DECODER"] = "1"
    failed = False
    with tempfile.TemporaryDirectory(prefix="lpbf-evt3-regression-") as directory:
        path = Path(directory) / "one_event.raw"
        path.write_bytes(header + struct.pack("<8H", *words))
        for size in (8, 10, 12, 16):
            result = subprocess.run([sys.executable, str(checker), str(path),
                                     "--chunk-bytes", str(size)], env=env,
                                    capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            summaries = [line.removeprefix("SEQUENTIAL_RESULT ")
                         for line in output.splitlines() if line.startswith("SEQUENTIAL_RESULT ")]
            if result.returncode or len(summaries) != 1:
                print(f"FAIL chunk={size}: exit={result.returncode}\n{output}")
                failed = True
                continue
            stats = json.loads(summaries[0])
            ok = (stats["decoded_events"] == 1 and stats["raw_bytes_fed"] == 16 and
                  stats["negative_timestamp_transitions"] == 0 and
                  stats["out_of_bounds_events"] == 0 and "violation detected:" not in output)
            print(f"{'PASS' if ok else 'FAIL'} chunk={size}: events={stats['decoded_events']}, "
                  f"bytes={stats['raw_bytes_fed']}")
            if not ok:
                print(output)
                failed = True
    if args.recording:
        results = []
        for size in (1048576, 1048578):
            result = subprocess.run([sys.executable, str(checker), str(args.recording),
                                     "--chunk-bytes", str(size), "--fingerprint"],
                                    env=env, capture_output=True, text=True, timeout=300)
            output = result.stdout + result.stderr
            summaries = [line.removeprefix("SEQUENTIAL_RESULT ")
                         for line in output.splitlines() if line.startswith("SEQUENTIAL_RESULT ")]
            if result.returncode or len(summaries) != 1:
                print(f"FAIL recording chunk={size}: exit={result.returncode}\n{output[-6000:]}")
                failed = True
                continue
            stats = json.loads(summaries[0])
            warnings = output.count("violation detected:")
            ok = (stats["raw_bytes_fed"] == stats["expected_payload_bytes"] and
                  stats["decoded_events"] > 0 and not warnings and
                  stats["negative_timestamp_transitions"] == 0 and
                  stats["out_of_bounds_events"] == 0)
            print(f"{'PASS' if ok else 'FAIL'} recording chunk={size}: "
                  f"events={stats['decoded_events']}, warnings={warnings}, "
                  f"sha256={stats['event_sha256']}", flush=True)
            results.append(stats)
            if not ok:
                failed = True
        if len(results) == 2:
            same = all(results[0][key] == results[1][key] for key in (
                "decoded_events", "event_sha256", "first_timestamp_us", "last_timestamp_us"))
            print("PASS identical decoded events across chunk sizes" if same else
                  "FAIL decoded event content changes with chunk size")
            failed |= not same
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
