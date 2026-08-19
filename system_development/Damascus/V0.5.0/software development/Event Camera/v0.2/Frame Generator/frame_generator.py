from config import WINDOW_US, STEP_US, START_TIME_S, END_TIME_S
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

    print(f"\nOpening: {filename.name}\n")

    return filename, file_path

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

def generate_frame(events,timestamps,width,height,file_path,time_begin_us,):        
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

    

    frame = np.full(
        (height, width, 3),
        BACKGROUND,
        dtype=np.uint8,
    )

    for event in frame_events:

        x = event["x"]
        y = event["y"]

        if event["p"]:
            frame[y, x] = POSITIVE_VALUE      # Red
        else:
            frame[y, x] = NEGATIVE_VALUE      # Blue

    relative_time = (
        time_begin_us - timestamps[0]
    ) / 1_000_000

    frame_file = (
        file_path /
        f"frame_{relative_time:.6f}s_{len(frame_events)}.png"
    )
    cv2.imwrite(str(frame_file), frame)

    print(
        f"{relative_time:.3f}s : "
        f"{len(frame_events)} events"
    )

    return True
        
def generate_frames(h5_file, file_path):

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

        while current_time < end_time:

            saved = generate_frame(
                events,
                timestamps,
                width,
                height,
                file_path,
                current_time,
            )

            if saved:
                print(f"Saved frame at {current_time}")

            current_time += STEP_US

def data_viewer(h5_file):
    with h5py.File(h5_file, "r") as h5:
        events = h5["events"][:]

        print(events[:15])






