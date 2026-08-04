from pathlib import Path

import cv2
import h5py
import numpy as np

from config import (
    VIDEO_FPS,
    WINDOW_US,
    VIDEO_CODEC,
)

# ============================================================
# Visualization Settings
# ============================================================

BACKGROUND = 127

POSITIVE_VALUE = 255
NEGATIVE_VALUE = 0

DECAY = 0.95         # 0.95-0.99 works well

# ============================================================

BASE_PATH = Path(__file__).resolve().parent
RECORDINGS = BASE_PATH / "recordings"

RECONSTRUCTIONS = BASE_PATH / "reconstructions"
RECONSTRUCTIONS.mkdir(parents=True, exist_ok=True)

files = sorted(
    RECORDINGS.glob("*.h5"),
    key=lambda f: f.stat().st_mtime,
    reverse=True,
)

if not files:
    raise FileNotFoundError("No recordings found.")

filename = files[0]

print(f"\nOpening: {filename.name}\n")


def update_event_image(
    image,
    events,
):
    # Decay every pixel back toward the neutral gray background,
    # not toward black. This is what makes stationary areas settle
    # to gray instead of fading to black over time.
    image += (BACKGROUND - image) * (1.0 - DECAY)

    if len(events) == 0:
        return

    x = events["x"]
    y = events["y"]

    polarity = events["p"].astype(bool)

    # Positive (brightness increase) events -> white.
    # Negative (brightness decrease) events -> black.
    image[y[polarity], x[polarity]] = POSITIVE_VALUE
    image[y[~polarity], x[~polarity]] = NEGATIVE_VALUE


def render_gray(image):

    gray = np.clip(image, 0, 255).astype(np.uint8)

    # cv2.VideoWriter still expects a 3-channel BGR frame even for
    # an achromatic image; this just replicates gray into B=G=R
    # rather than tinting it.
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


with h5py.File(filename, "r") as f:

    events = f["events"]

    # h5py attrs commonly come back as numpy scalar types (e.g.
    # numpy.int64). cv2.VideoWriter's frame-size tuple is safer as
    # plain Python ints.
    width = int(f.attrs["width"])
    height = int(f.attrs["height"])

    print(f"Events : {len(events):,}")
    print(f"Size   : {width} x {height}")

    if len(events) == 0:
        raise ValueError(
            "This recording has zero events — nothing to reconstruct."
        )

    if WINDOW_US <= 0:
        raise ValueError(
            f"WINDOW_US must be > 0 (got {WINDOW_US}); with 0 or a "
            "negative value, current_time never advances and the "
            "render loop would produce zero frames."
        )

    output_file = RECONSTRUCTIONS / f"{filename.stem}_metavision.avi"

    fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)

    writer = cv2.VideoWriter(
        str(output_file),
        fourcc,
        VIDEO_FPS,
        (width, height),
        True,
    )

    if not writer.isOpened():
        raise RuntimeError(
            "Failed to open the AVI writer.\n"
            f"Path   : {output_file}\n"
            f"Codec  : {VIDEO_CODEC}\n"
            f"Size   : {width}x{height} @ {VIDEO_FPS} fps\n"
            "This is the classic cause of a 'corrupted' AVI: the "
            "writer never actually opened, so every write() silently "
            "did nothing. Try a different VIDEO_CODEC (e.g. 'mp4v' "
            "with a .mp4 extension, or confirm 'MJPG' is available "
            "on this machine)."
        )

    image = np.full(
        (height, width),
        BACKGROUND,
        dtype=np.float32,
    )

    # Read the full timestamp column into memory once. Leaving this
    # as a lazy h5py field-selection object and calling
    # np.searchsorted() on it every iteration forces a fresh
    # (decompression-heavy, for a gzip-compressed dataset) read of
    # the entire column on every single frame.
    all_events = events[:]
    timestamps = all_events["t"].astype(np.int64)

    # --- Case 1: an interrupted write left unpopulated trailing rows ---
    #
    # dataset.resize() and the write that fills it are two separate
    # statements in functions.py. If recording stops (Ctrl+C, or any
    # exception) between them, h5py leaves the newly-grown rows at
    # their default fill value of 0 for EVERY field. That's a short
    # trailing run where x, y, t, and p are all exactly zero
    # together — distinct from a real event, which would only have
    # t landing on zero by pure coincidence.
    zero_row = (
        (all_events["x"] == 0)
        & (all_events["y"] == 0)
        & (timestamps == 0)
        & (all_events["p"] == 0)
    )

    if zero_row.any():
        real_rows = np.where(~zero_row)[0]
        last_real = int(real_rows[-1]) if len(real_rows) else -1

        if last_real < len(all_events) - 1:
            dropped = len(all_events) - (last_real + 1)

            print(
                f"WARNING: dropping {dropped:,} trailing all-zero "
                "row(s) (x=y=t=p=0) — unwritten data left over from "
                "an interrupted recording. See the resize()-without-"
                "write fix in functions.py."
            )

            all_events = all_events[: last_real + 1]
            timestamps = timestamps[: last_real + 1]

    # --- Case 2: genuine EVT3.0 timestamp wraparound ---
    #
    # Prophesee's EVT3.0 timestamp representation only spans about
    # 16.77s (2^24 = 16,777,216) before cycling back to a small
    # value — this is documented, expected behavior for long
    # recordings, not corruption. Unlike Case 1, the values right
    # after the drop are ordinary, varying event data — so instead
    # of truncating, add one wrap period at every point the
    # timestamp decreases, reconstructing one continuous timeline.
    #
    # IMPORTANT: functions.py never sorts events before writing
    # them — individual pixels can report near-simultaneous
    # activity that gets serialized slightly out of order within or
    # between camera buffers, so the raw "t" column has small local
    # backward jitter (a handful of microseconds) scattered
    # throughout, completely separate from real wraps. Treating
    # every decrease as a full wrap (as an earlier version of this
    # script did) adds a spurious 16.78s offset on ordinary jitter,
    # which corrupts the timeline far worse than the wrap itself —
    # only a drop on the same order of magnitude as the wrap period
    # counts as a real wrap.
    WRAP_PERIOD_US = 1 << 24  # 16,777,216
    WRAP_THRESHOLD_US = WRAP_PERIOD_US // 2

    diffs = np.diff(timestamps)
    wrap_mask = diffs < -WRAP_THRESHOLD_US

    if wrap_mask.any():
        print(
            f"Unwrapping {int(wrap_mask.sum()):,} EVT3.0 timestamp "
            f"wraparound(s) (period = {WRAP_PERIOD_US:,})..."
        )

        cumulative_offset = np.cumsum(
            np.where(wrap_mask, WRAP_PERIOD_US, 0)
        )

        timestamps[1:] += cumulative_offset

    # Now clean up the ordinary local jitter mentioned above. Once
    # real wraps are corrected, timestamps should be very close to
    # sorted already, so this is cheap — but it's what guarantees
    # np.searchsorted() below (which requires strictly sorted input)
    # behaves correctly instead of silently misbucketing events.
    sort_order = np.argsort(timestamps, kind="stable")

    if not np.array_equal(sort_order, np.arange(len(timestamps))):
        print(
            "Re-sorting events: the raw stream wasn't perfectly "
            "time-ordered (normal — see the note above)."
        )
        timestamps = timestamps[sort_order]
        all_events = all_events[sort_order]

    events = all_events

    current_time = int(timestamps[0])
    last_time = int(timestamps[-1])

    if current_time >= last_time:
        raise ValueError(
            f"First timestamp ({current_time}) is not before the "
            f"last ({last_time}) — the render loop would produce "
            "zero frames."
        )

    # A pixel this far from BACKGROUND (out of 0-255) still reads as
    # a visible trail; below this it's indistinguishable from plain
    # gray. Used to decide when a decaying frame has genuinely
    # finished, vs still being worth writing.
    SETTLED_THRESHOLD = 1.0

    start_idx = 0
    frame_number = 0
    skipped_frames = 0

    try:

        while current_time < last_time:

            end_time = current_time + WINDOW_US

            end_idx = np.searchsorted(
                timestamps,
                end_time,
                side="left",
            )

            frame_events = events[start_idx:end_idx]

            update_event_image(
                image,
                frame_events,
            )

            has_new_events = len(frame_events) > 0
            still_visible = (
                np.abs(image - BACKGROUND).max() > SETTLED_THRESHOLD
            )

            # Skip windows where nothing changed and there's no
            # visible trail left to fade — these are the "do
            # nothing" frames: a quiet stretch with no events, after
            # any earlier activity has already fully decayed back to
            # gray. Writing them just stretches the video with
            # identical frames.
            if has_new_events or still_visible:

                frame = render_gray(
                    image,
                )

                writer.write(frame)

                frame_number += 1

                if frame_number % 100 == 0:
                    print(
                        f"Rendered {frame_number} frames..."
                    )

            else:
                skipped_frames += 1

            start_idx = end_idx
            current_time = end_time

    finally:

        # Guarantees the AVI trailer/index gets written even if the
        # loop above raises partway through. Without this, any
        # exception mid-render leaves an unfinalized, unplayable
        # file — indistinguishable from a "corrupted" AVI.
        writer.release()

    if frame_number == 0:
        print(
            "WARNING: zero frames were written. The output file "
            "exists but contains no video and will not play."
        )
    else:
        print(
            f"Wrote {frame_number} frames "
            f"(skipped {skipped_frames} quiet frame(s) with nothing "
            "to show)."
        )

print("\nDone.")
print(output_file)