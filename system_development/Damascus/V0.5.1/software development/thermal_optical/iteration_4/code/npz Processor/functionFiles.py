import csv
import os
import time
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:  # Pillow/Matplotlib fallback is used below.
    cv2 = None


def clear_terminal():
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def gimmeFileNames(path, includeFolders=False):
    folder = Path(path)
    if includeFolders:
        return sorted(item.name for item in folder.iterdir())
    return sorted(file.name for file in folder.iterdir() if file.is_file())


def buildFilePaths(path):
    return [str(Path(path) / name) for name in gimmeFileNames(path)]


def _scalar_from_npz(data, key, default=None):
    if key not in data.files:
        return default
    values = np.asarray(data[key]).reshape(-1)
    if values.size == 0:
        return default
    return values[0].item()


def loadRecording(path):
    """Load frames and recover their elapsed capture times in seconds."""
    path = Path(path)
    print(f"Loading {path.name}.")

    with np.load(path, allow_pickle=False) as data:
        if "frames" not in data.files:
            raise KeyError(f"{path.name} does not contain a 'frames' array.")

        frames = np.asarray(data["frames"], dtype=np.float32)
        if frames.ndim != 3:
            raise ValueError(
                f"Expected frames with shape [N, height, width]; got {frames.shape}."
            )
        if frames.shape[0] == 0:
            raise ValueError(f"{path.name} contains no thermal frames.")

        timestamp = _scalar_from_npz(data, "timestamp", "")
        capture_interval_s = _scalar_from_npz(data, "capture_interval_s", None)

        if "frame_timestamps_ns" in data.files:
            frame_timestamps_ns = np.asarray(
                data["frame_timestamps_ns"], dtype=np.int64
            ).reshape(-1)
        else:
            frame_timestamps_ns = np.array([], dtype=np.int64)

        if "elapsed_s" in data.files:
            elapsed_s = np.asarray(data["elapsed_s"], dtype=np.float64).reshape(-1)
        elif frame_timestamps_ns.size:
            elapsed_s = (
                frame_timestamps_ns - frame_timestamps_ns[0]
            ).astype(np.float64) / 1e9
        elif capture_interval_s is not None:
            elapsed_s = (
                np.arange(frames.shape[0], dtype=np.float64)
                * float(capture_interval_s)
            )
        else:
            raise KeyError(
                "The NPZ has no elapsed_s, frame_timestamps_ns, or "
                "capture_interval_s timing information."
            )

    if elapsed_s.size != frames.shape[0]:
        raise ValueError(
            f"Frame/time count mismatch: {frames.shape[0]} frames and "
            f"{elapsed_s.size} elapsed times."
        )
    if frame_timestamps_ns.size not in (0, frames.shape[0]):
        raise ValueError(
            f"Frame/timestamp count mismatch: {frames.shape[0]} frames and "
            f"{frame_timestamps_ns.size} timestamps."
        )
    if not np.all(np.isfinite(elapsed_s)) or np.any(np.diff(elapsed_s) < 0):
        raise ValueError("Elapsed capture times must be finite and nondecreasing.")

    elapsed_s = elapsed_s - elapsed_s[0]
    print(
        f"Loaded {frames.shape[0]} frames covering "
        f"{elapsed_s[-1]:.3f} seconds."
    )

    return {
        "frames": frames,
        "timestamp": timestamp,
        "frame_timestamps_ns": frame_timestamps_ns,
        "elapsed_s": elapsed_s,
        "capture_interval_s": (
            None if capture_interval_s is None else float(capture_interval_s)
        ),
    }


def loadData(path, name=None):
    """Backward-compatible loader used by older scripts."""
    recording = loadRecording(path)
    return (
        recording["frames"],
        recording["timestamp"],
        recording["frame_timestamps_ns"],
    )


def selectEqualIntervalFrames(elapsed_s, interval_s=None):
    """
    Select the recorded frame nearest to each equal target time.

    interval_s=None exports every stored frame. This is the preferred setting
    for NPZ files produced by the interval-enabled acquisition code because
    those frames were already captured at the requested equal interval.
    """
    elapsed_s = np.asarray(elapsed_s, dtype=np.float64)
    frame_count = elapsed_s.size
    if frame_count == 0:
        return np.array([], dtype=int), np.array([], dtype=np.float64)

    if interval_s is None:
        return np.arange(frame_count, dtype=int), elapsed_s.copy()

    interval_s = float(interval_s)
    if not np.isfinite(interval_s) or interval_s <= 0:
        raise ValueError("EXPORT_INTERVAL_S must be greater than zero.")

    positive_gaps = np.diff(elapsed_s)
    positive_gaps = positive_gaps[positive_gaps > 0]
    if positive_gaps.size:
        source_interval_s = float(np.median(positive_gaps))
        if interval_s < source_interval_s * 0.95:
            raise ValueError(
                f"Requested export interval {interval_s:g} s is shorter than "
                f"the recorded interval (approximately {source_interval_s:g} s). "
                "Missing intermediate thermal frames cannot be reconstructed."
            )

    target_count = int(np.floor(elapsed_s[-1] / interval_s)) + 1
    target_times_s = np.arange(target_count, dtype=np.float64) * interval_s

    right = np.searchsorted(elapsed_s, target_times_s, side="left")
    right = np.clip(right, 0, frame_count - 1)
    left = np.clip(right - 1, 0, frame_count - 1)

    choose_left = np.abs(elapsed_s[left] - target_times_s) <= np.abs(
        elapsed_s[right] - target_times_s
    )
    indices = np.where(choose_left, left, right).astype(int)

    # If irregular source timing maps two targets to one physical frame, write
    # that physical frame only once.
    keep = np.concatenate(([True], np.diff(indices) != 0))
    return indices[keep], target_times_s[keep]


def _write_inferno_png(image_8bit, image_path):
    """Write an Inferno-colored PNG with OpenCV or a portable fallback."""
    if cv2 is not None:
        color = cv2.applyColorMap(image_8bit, cv2.COLORMAP_INFERNO)
        if not cv2.imwrite(str(image_path), color):
            raise OSError(f"OpenCV could not write {image_path}.")
        return

    from matplotlib import colormaps
    from PIL import Image

    rgb = colormaps["inferno"](image_8bit / 255.0, bytes=True)[..., :3]
    Image.fromarray(rgb, mode="RGB").save(image_path, format="PNG")


def saveImages(
    path,
    output,
    interval_s=None,
    temp_min_c=None,
    temp_max_c=None,
):
    """Export timestamped thermal PNG images; no video is created."""
    started = time.perf_counter()
    path = Path(path)
    recording = loadRecording(path)
    frames = recording["frames"]
    elapsed_s = recording["elapsed_s"]

    indices, target_times_s = selectEqualIntervalFrames(elapsed_s, interval_s)
    selected = frames[indices]

    low_c = float(np.nanmin(frames)) if temp_min_c is None else float(temp_min_c)
    high_c = float(np.nanmax(frames)) if temp_max_c is None else float(temp_max_c)
    if not np.isfinite(low_c) or not np.isfinite(high_c) or high_c <= low_c:
        raise ValueError(
            f"Invalid temperature scale: minimum={low_c}, maximum={high_c}."
        )

    folder = Path(output) / path.stem
    folder.mkdir(parents=True, exist_ok=True)
    summary_path = folder / "image_index.csv"

    rows = []
    for image_number, (frame_index, target_s, frame) in enumerate(
        zip(indices, target_times_s, selected), start=1
    ):
        actual_s = int(elapsed_s[frame_index])
        normalized = np.clip((frame - low_c) / (high_c - low_c), 0.0, 1.0)
        normalized = np.nan_to_num(normalized, nan=0.0)
        image_8bit = np.rint(normalized * 255.0).astype(np.uint8)
        filename = (
            f"thermal_{actual_s:09d}.png"
            # f"thermal_{image_number:05d}_"
            # "target_{target_s:010.3f}s_actual_{actual_s:010.3f}s.png"

        )
        image_path = folder / filename
        _write_inferno_png(image_8bit, image_path)

        rows.append(
            {
                # "image_number": image_number,
                # "source_frame_index": int(frame_index),
                # "target_time_s": f"{target_s:.9f}",
                "actual_time_s": f"{actual_s:09d}",
                # "timing_error_s": f"{actual_s - target_s:.9f}",
                # "minimum_temperature_c": f"{np.nanmin(frame):.6f}",
                # "maximum_temperature_c": f"{np.nanmax(frame):.6f}",
                # "mean_temperature_c": f"{np.nanmean(frame):.6f}",
                # "png_file": filename,
            }
        )

    with summary_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    hottest_local_index = int(np.nanargmax(np.nanmax(selected, axis=(1, 2))))
    hottest_source_index = int(indices[hottest_local_index])
    elapsed = time.perf_counter() - started

    print(
        f"Saved {len(indices)} PNG images to {folder} "
        f"in {elapsed:.2f} seconds."
    )
    print(
        f"Temperature color scale: {low_c:.3f} to {high_c:.3f} °C. "
        f"Hottest exported source frame: {hottest_source_index}.\n"
    )

    return {
        "folder": folder,
        "summary_csv": summary_path,
        "exported_indices": indices,
        "target_times_s": target_times_s,
        "hottest_source_index": hottest_source_index,
    }


def saveCSV(path, name, output, frameIndex):
    """Save the raw temperature matrix for one selected source frame."""
    folder = Path(output) / Path(name).stem
    folder.mkdir(parents=True, exist_ok=True)

    frames = loadRecording(path)["frames"]
    frameIndex = int(frameIndex)
    if not 0 <= frameIndex < frames.shape[0]:
        raise IndexError(
            f"Frame index {frameIndex} is outside 0 to {frames.shape[0] - 1}."
        )

    output_file = folder / f"{Path(name).stem}_frame{frameIndex:06d}.csv"
    np.savetxt(output_file, frames[frameIndex], delimiter=",", fmt="%.6f")
    print(f"Saved raw temperature CSV for frame {frameIndex} to {output_file}.\n")
