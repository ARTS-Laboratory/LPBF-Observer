
from pathlib import Path
from datetime import datetime
import pandas as pd
import re

# -------- USER SETTINGS --------
FOLDER = Path(r"C:\Users\killedar\OneDrive - University of South Carolina\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_12\data\raw\test_1_optical_thermal")
OUTPUT_CSV = FOLDER / "camera_file_timing_comparison.csv"

# -------- MATCH FILES --------
optical_files = {}
thermal_files = {}

for file in FOLDER.iterdir():
    optical_match = re.fullmatch(
        r"optical_(\d+)\.png", file.name, re.IGNORECASE
    )
    thermal_match = re.fullmatch(
        r"thermal_(\d+)\.npz", file.name, re.IGNORECASE
    )

    if optical_match:
        optical_files[optical_match.group(1)] = file

    if thermal_match:
        thermal_files[thermal_match.group(1)] = file

# -------- COMPARE TIMESTAMPS --------
results = []

for file_id in sorted(
    optical_files.keys() & thermal_files.keys(),
    key=int
):
    optical = optical_files[file_id]
    thermal = thermal_files[file_id]

    optical_stat = optical.stat()
    thermal_stat = thermal.stat()

    # Creation time (Windows)
    optical_created = optical_stat.st_ctime
    thermal_created = thermal_stat.st_ctime

    # Last modification time
    optical_modified = optical_stat.st_mtime
    thermal_modified = thermal_stat.st_mtime

    creation_diff_ms = (
        thermal_created - optical_created
    ) * 1000

    modification_diff_ms = (
        thermal_modified - optical_modified
    ) * 1000

    results.append({
        "File_ID": file_id,
        "Optical_File": optical.name,
        "Thermal_File": thermal.name,
        "Optical_Creation_Time": datetime.fromtimestamp(
            optical_created
        ).isoformat(timespec="microseconds"),
        "Thermal_Creation_Time": datetime.fromtimestamp(
            thermal_created
        ).isoformat(timespec="microseconds"),
        "Creation_Difference_ms": creation_diff_ms,
        "Modification_Difference_ms": modification_diff_ms,
    })

# -------- SAVE RESULTS --------
df = pd.DataFrame(results)

if df.empty:
    print("No matching optical/thermal file pairs found.")
else:
    df.to_csv(OUTPUT_CSV, index=False)

    print(df.to_string(index=False))
    print("\nNumber of matched pairs:", len(df))

    print(
        "\nMean creation time difference (ms):",
        df["Creation_Difference_ms"].mean()
    )

    print(
        "Mean absolute creation time difference (ms):",
        df["Creation_Difference_ms"].abs().mean()
    )

    print("\nResults saved to:", OUTPUT_CSV)
