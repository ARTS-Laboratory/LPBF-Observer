
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import re

FOLDER = Path(r"C:\Users\killedar\OneDrive - University of South Carolina\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_12\data\raw\test_1_optical_thermal")

optical_files = {}
thermal_files = {}

for f in FOLDER.iterdir():
    optical = re.fullmatch(
        r"optical_(\d+)\.png", f.name, re.IGNORECASE
    )
    thermal = re.fullmatch(
        r"thermal_(\d+)\.npz", f.name, re.IGNORECASE
    )

    if optical:
        optical_files[optical.group(1)] = f
    if thermal:
        thermal_files[thermal.group(1)] = f

results = []

for frame_id in sorted(
    optical_files.keys() & thermal_files.keys(), key=int
):
    png_path = optical_files[frame_id]
    npz_path = thermal_files[frame_id]

    with np.load(npz_path) as data:
        thermal_time_ns = int(data["time_unix_ns"])

    # Windows filesystem timestamp:
    # modification time is when PNG was last written
    optical_write_ns = png_path.stat().st_mtime_ns

    difference_ms = (
        thermal_time_ns - optical_write_ns
    ) / 1_000_000

    results.append({
        "Frame_ID": frame_id,
        "Optical_File": png_path.name,
        "Thermal_File": npz_path.name,
        "Optical_Write_Time": datetime.fromtimestamp(
            optical_write_ns / 1e9
        ).isoformat(timespec="microseconds"),
        "Thermal_Stored_Time": datetime.fromtimestamp(
            thermal_time_ns / 1e9
        ).isoformat(timespec="microseconds"),
        "Difference_ms": difference_ms
    })

df = pd.DataFrame(results)

if df.empty:
    print("No matching files found.")
else:
    df.to_csv(
        FOLDER / "camera_timing_comparison.csv",
        index=False
    )

    print(df.to_string(index=False))

    print("\nMean difference (ms):",
          df["Difference_ms"].mean())

    print("Standard deviation (ms):",
          df["Difference_ms"].std())

    print("Maximum absolute difference (ms):",
          df["Difference_ms"].abs().max())

