from pathlib import Path

import functionFiles as thermal


# ---------------------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR.parent / "Recordings"
OUTPUT_IMAGE_PATH = BASE_DIR / "Images"
OUTPUT_CSV_PATH = BASE_DIR / "CSV"

# Austin's server saves ONE frame per NPZ under 'temps'. Keep None to export
# one PNG per NPZ. Timing is controlled by LabVIEW, not this exporter.
# A larger interval is supported only for legacy multi-frame 'frames' NPZs;
# it does not select intervals across a folder of single-frame files.
EXPORT_INTERVAL_S = None

# None/None uses a min/max scale per NPZ (per image for Austin's server).
# For identical colors across different tests, set fixed limits such as
# TEMPERATURE_MIN_C = 20.0 and TEMPERATURE_MAX_C = 120.0.
TEMPERATURE_MIN_C = None
TEMPERATURE_MAX_C = None

# For Austin's files this exports the sole frame's temperatures in deg C.
# For legacy recordings it exports the hottest selected frame.
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

    print("All recordings processed and images created.")


if __name__ == "__main__":
    main()
