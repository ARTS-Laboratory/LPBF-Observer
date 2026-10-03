from reconstruction_config import WINDOW_US, STEP_US, START_TIME_S, END_TIME_S
from pathlib import Path

import cv2
import h5py
import numpy as np

# ============================================================
# Visualization Settings
# ============================================================
BACKGROUND = (40, 40, 40)     # Dark gray
POSITIVE_VALUE = (0, 0, 255)    # Red
NEGATIVE_VALUE = (255, 0, 0)    # Blue

def file_path(filenumber):
    BASE_PATH = Path(__file__).resolve().parent.parent
    RECORDINGS = BASE_PATH / "Recorder" / "recordings"

    RECONSTRUCTIONS = BASE_PATH / "Frame Generator" / "reconstructions"
    RECONSTRUCTIONS.mkdir(parents=True, exist_ok=True)

    files = sorted(
        RECORDINGS.glob("*.h5"),
        key=lambda f: f.stat().st_mtime,
        reverse=False,
    )

    if not files:
        raise FileNotFoundError("No recordings found.")

    filename = files[filenumber]
    file_path = RECONSTRUCTIONS / filename.stem
    file_path.mkdir(parents=True, exist_ok=True)

    folders = {
        "binary": file_path / "binary",
        "count_linear": file_path / "count_linear",
        "count_log": file_path / "count_log",
        "signed_linear": file_path / "signed_linear",
        "signed_log": file_path / "signed_log",
    }

    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)

    print(f"\nOpening: {filename.name}\n")

    return filename, file_path, folders

def save_metadata_md(h5_file, file_path):
    md_file = file_path / "metadata.md"

    with h5py.File(h5_file, "r") as h5, open(md_file, "w", encoding="utf-8") as md:

        md.write(f"# {Path(h5_file).stem}\n\n")

        md.write("## Recording Metadata\n\n")

        for key, value in sorted(h5.attrs.items()):
            md.write(f"- **{key.replace('_', ' ').title()}**: `{value}`\n")

        events = h5["events"]

        md.write("\n## Dataset Information\n\n")

        md.write(f"- **Shape:** `{events.shape}`\n")
        md.write(f"- **Dtype:** `{events.dtype}`\n")

    print(f"Metadata saved to: {md_file}\n")

def generate_frame(events,timestamps,width,height,file_path,folders,time_begin_us,):        
    time_end_us = time_begin_us + WINDOW_US

    start_idx = np.searchsorted(
        timestamps,
        time_begin_us,
    )

    end_idx = np.searchsorted(
        timestamps,
        time_end_us,
    )

    frame_events = events[start_idx:end_idx]

    if len(frame_events) == 0:
        return False

    print(f"Events in frame: {len(frame_events)}\n")

    binary_frame = np.full(
        (height, width, 3),
        BACKGROUND,
        dtype=np.uint8,
    )

    for event in frame_events:

        x = event["x"]
        y = event["y"]

        if event["p"]:
            binary_frame[y, x] = POSITIVE_VALUE      # Red
        else:
            binary_frame[y, x] = NEGATIVE_VALUE      # Blue

    positive_counts = np.zeros(
        (height, width),
        dtype=np.uint32,
    )

    negative_counts = np.zeros(
        (height, width),
        dtype=np.uint32,
    )

    x = frame_events["x"]
    y = frame_events["y"]
    p = frame_events["p"].astype(bool)

    np.add.at(
        positive_counts,
        (y[p], x[p]),
        1,
    )

    np.add.at(
        negative_counts,
        (y[~p], x[~p]),
        1,
    )

    total_counts = positive_counts + negative_counts

    signed_counts = (
        positive_counts.astype(np.int32)
        - negative_counts.astype(np.int32)
    )

    relative_time = (
        time_begin_us - timestamps[0]
    ) / 1_000_000

    count_linear = cv2.normalize(
        total_counts,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    ).astype(np.uint8)

    count_linear = cv2.applyColorMap(
        count_linear,
        cv2.COLORMAP_VIRIDIS,
    )

    count_log_data = np.log1p(total_counts)

    count_log = cv2.normalize(
        count_log_data,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    ).astype(np.uint8)

    count_log = cv2.applyColorMap(
        count_log,
        cv2.COLORMAP_VIRIDIS,
    )

    max_abs = np.max(np.abs(signed_counts))

    signed_linear = np.full(
        (height, width, 3),
        BACKGROUND,
        dtype=np.uint8,
    )

    if max_abs > 0:

        positive = signed_counts > 0
        negative = signed_counts < 0

        signed_linear[positive] = POSITIVE_VALUE
        signed_linear[negative] = NEGATIVE_VALUE

    signed_log_data = (
        np.sign(signed_counts)
        * np.log1p(np.abs(signed_counts))
    )

    signed_log = np.full(
        (height, width, 3),
        BACKGROUND,
        dtype=np.uint8,
    )

    positive = signed_log_data > 0
    negative = signed_log_data < 0

    signed_log[positive] = POSITIVE_VALUE
    signed_log[negative] = NEGATIVE_VALUE
    
    filename = (
        f"frame_{relative_time:.6f}s_"
        f"{len(frame_events)}.png"
    )
    cv2.imwrite(
        str(folders["binary"] / filename),
        binary_frame,
    )

    cv2.imwrite(
        str(folders["count_linear"] / filename),
        count_linear,
    )

    cv2.imwrite(
        str(folders["count_log"] / filename),
        count_log,
    )

    cv2.imwrite(
        str(folders["signed_linear"] / filename),
        signed_linear,
    )

    cv2.imwrite(
        str(folders["signed_log"] / filename),
        signed_log,
    )

    print(
        f"{relative_time:.3f}s : "
        f"{len(frame_events)} events"
    )

    return True

def save_curated_h5(
    source_h5,
    output_folder,
    events,
    timestamps,
    start_time_us,
    end_time_us,
):
    """
    Create a curated HDF5 containing only events within
    the configured reconstruction time range.
    """

    start_idx = np.searchsorted(
        timestamps,
        start_time_us,
        side="left",
    )

    end_idx = np.searchsorted(
        timestamps,
        end_time_us,
        side="left",
    )

    curated_events = events[start_idx:end_idx].copy()

    output_file = (
        output_folder /
        f"{Path(source_h5).stem}_curated.h5"
    )

    with h5py.File(source_h5, "r") as source, \
         h5py.File(output_file, "w") as curated:

        # Copy all original metadata
        for key, value in source.attrs.items():
            curated.attrs[key] = value

        # Add/update metadata describing the curated data
        curated.attrs["curated"] = True
        curated.attrs["source_file"] = Path(source_h5).name

        curated.attrs["curated_start_seconds"] = (
            START_TIME_S
        )

        curated.attrs["curated_end_seconds"] = (
            END_TIME_S
        )

        curated.attrs["total_events"] = len(
            curated_events
        )

        curated.attrs["duration_seconds"] = (
            end_time_us - start_time_us
        ) / 1_000_000

        curated.create_dataset(
            "events",
            data=curated_events,
            compression="gzip",
            compression_opts=4,
        )

    print(
        f"\nCurated HDF5 saved to:\n"
        f"{output_file}"
    )

    print(
        f"Curated events: "
        f"{len(curated_events):,}\n"
    )

def generate_frames(h5_file, file_path, folders):

    with h5py.File(h5_file, "r") as h5:

        events = h5["events"][:]
        timestamps = events["t"].astype(np.int64)

        WRAP_PERIOD_US = 1 << 24          # 16,777,216
        WRAP_THRESHOLD_US = WRAP_PERIOD_US // 2

        timestamps = timestamps.astype(np.int64)

        diffs = np.diff(timestamps)

        wrap_mask = diffs < -WRAP_THRESHOLD_US

        if wrap_mask.any():

            offsets = np.cumsum(
                np.where(wrap_mask, WRAP_PERIOD_US, 0)
            )

            timestamps[1:] += offsets

        width = int(h5.attrs["width"])
        height = int(h5.attrs["height"])

        recording_start = int(timestamps[0])
        recording_end = int(timestamps[-1])

        if START_TIME_S is None:
            current_time = recording_start
        else:
            current_time = recording_start + int(START_TIME_S * 1_000_000)

        if END_TIME_S is None:
            end_time = recording_end
        else:
            end_time = recording_start + int(END_TIME_S * 1_000_000)

        save_curated_h5(
            h5_file,
            file_path,
            events,
            timestamps,
            current_time,
            end_time,
        )

        while current_time < end_time:

            saved = generate_frame(
                events,
                timestamps,
                width,
                height,
                file_path,
                folders,
                current_time,
            )

            if saved:
                print(f"Saved frame at {current_time}")

            current_time += STEP_US

def data_viewer(h5_file):
    with h5py.File(h5_file, "r") as h5:
        events = h5["events"][:]

        print(events[:15])






