"""Read-only EVT3 word sample; candidate patterns are not SDK violation counts."""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np


def inspect(path, sample_mib=16):
    with path.open("rb") as handle:
        header = []
        for _ in range(256):
            line = handle.readline(4096)
            if not line.startswith(b"%"):
                raise ValueError("RAW header ended without a '% end' marker")
            header.append(line.decode("ascii", errors="replace").strip())
            if line.strip() == b"% end":
                break
        else:
            raise ValueError("RAW header is too long")
        if not any("EVT3" in line or line == "% evt 3.0" for line in header):
            raise ValueError("Header does not identify EVT3")
        offset = handle.tell()
        words = np.fromfile(handle, dtype="<u2", count=sample_mib * 1024 * 1024 // 2)
    print("\n".join(header))
    print(f"Payload offset: {offset}; payload bytes: {path.stat().st_size - offset}")
    print(f"Sample: {words.nbytes} bytes; assumes little-endian EVT3")
    kinds = (words >> 12).astype(np.uint8)
    print("Word-type counts:", {f"0x{i:X}": int(n) for i, n in
                                enumerate(np.bincount(kinds, minlength=16)) if n})
    if len(words) < 3:
        return
    triplets = ((kinds[:-2] == 4) & (kinds[1:-1] == 4) & (kinds[2:] == 5))
    starts = np.flatnonzero((kinds == 4) & np.r_[True, kinds[:-1] != 4])
    starts = starts[starts + 2 < len(words)]
    candidates = starts[(kinds[starts + 1] != 4) | (kinds[starts + 2] != 5)]
    print("Contiguous 4,4,5 triplets:", int(triplets.sum()))
    print("VECT_12 run starts without immediate 4,4,5:", len(candidates))
    print("Next type after those run starts:", dict(Counter(
        f"0x{int(kinds[i+1]):X}" for i in candidates)))
    print("First candidate contexts (brackets mark the run start):")
    for i in candidates[:12]:
        context = " ".join((f"[{int(words[j]):04X}]" if j == i else f"{int(words[j]):04X}")
                           for j in range(max(0, i - 4), min(len(words), i + 7)))
        print(f"file byte {offset + 2 * int(i)}: {context}")
    print("Candidates are structural clues, not a complete validation or lost-event estimate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--sample-mib", type=int, default=16)
    args = parser.parse_args()
    if args.sample_mib < 1:
        parser.error("--sample-mib must be positive")
    inspect(args.path, args.sample_mib)
