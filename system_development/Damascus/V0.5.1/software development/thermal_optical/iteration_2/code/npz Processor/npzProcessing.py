from pathlib import Path

import functionFiles as thermal


# ---------------------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR.parent / "Recordings"
OUTPUT_IMAGE_PATH = BASE_DIR / "Images"
OUTPUT_CSV_PATH = BASE_DIR / "CSV"

# None exports every frame already captured at equal intervals by LabVIEW and
# Python. Set a larger interval, for example 5.0, to export one image every
# five seconds from a recording captured more frequently.
EXPORT_INTERVAL_S = None

# None/None uses one fixed min/max scale across the complete NPZ recording.
# For identical colors across different tests, set fixed limits such as
# TEMPERATURE_MIN_C = 20.0 and TEMPERATURE_MAX_C = 120.0.
TEMPERATURE_MIN_C = None
TEMPERATURE_MAX_C = None

# Preserve the earlier behavior of exporting the raw temperature matrix for
# the hottest selected frame. This produces CSV data, not a video.
SAVE_HOTTEST_FRAME_CSV = True


def main():
    thermal.clear_terminal()

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {INPUT_PATH}\n"
            "Update INPUT_PATH at the top of npzProcessing.py."
        )

    npz_paths = sorted(INPUT_PATH.glob("*.npz"))
    if not npz_paths:
        raise FileNotFoundError(f"No .npz recordings were found in {INPUT_PATH}.")

    print(f"Found {len(npz_paths)} NPZ recording(s).")
    print(f"PNG output directory: {OUTPUT_IMAGE_PATH}\n")

    for path in npz_paths:
        print("-" * 70)
        result = thermal.saveImages(
            path=path,
            output=OUTPUT_IMAGE_PATH,
            interval_s=EXPORT_INTERVAL_S,
            temp_min_c=TEMPERATURE_MIN_C,
            temp_max_c=TEMPERATURE_MAX_C,
        )

        if SAVE_HOTTEST_FRAME_CSV:
            thermal.saveCSV(
                path=path,
                name=path.name,
                output=OUTPUT_CSV_PATH,
                frameIndex=result["hottest_source_index"],
            )

    print("All recordings processed. No videos were created.")


if __name__ == "__main__":
    main()
