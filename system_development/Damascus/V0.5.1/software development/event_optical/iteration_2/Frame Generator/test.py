import h5py
import numpy as np

file_path = r"C:\Users\THIENAN\Documents\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\event_optical\iteration_2\Recorder\recordings\event_recording_2_022133_PM_10152026\event_recording_2_022133_PM_10152026.h5"

with h5py.File(file_path, "r") as h5_file:
    events = h5_file["events"]

    print("Event count:", len(events))

    timestamps = events["t"]

    print("First timestamp:", int(timestamps[0]))
    print("Last timestamp:", int(timestamps[-1]))
    print("Minimum timestamp:", int(np.min(timestamps)))
    print("Maximum timestamp:", int(np.max(timestamps)))

    negative_jumps = np.count_nonzero(np.diff(timestamps) < 0)
    print("Timestamp reversals:", negative_jumps)

    duration_us = int(timestamps[-1]) - int(timestamps[0])
    print("Timestamp duration:", duration_us, "us")
    print("Timestamp duration:", duration_us / 1_000_000, "s")

    timestamps = events["t"].astype(np.int64)
    reversal_indices = np.flatnonzero(np.diff(timestamps) < 0) + 1

    print("Timestamp reversals:", len(reversal_indices))

    for index in reversal_indices[:20]:
        print(
            f"Timestamp reset at event {index:,}: "
            f"{timestamps[index - 1]} -> {timestamps[index]}"
        )