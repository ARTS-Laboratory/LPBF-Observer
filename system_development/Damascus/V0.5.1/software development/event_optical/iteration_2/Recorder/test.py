import ctypes
import numpy as np
import time
import functions.functions as fun

BUFFER_BATCH_SIZE = 64
BUFFER_COUNT = 256

device = fun.initializeDevice()

fun.configureDevice(device)

device.start_stream(BUFFER_COUNT)

buffer_counter = 0
start_wall = time.perf_counter()
first_event_t = None
first_event_wall = None

try:
    while True:
        buffers = device.get_buffer(BUFFER_BATCH_SIZE)

        try:
            buffer_counter += len(buffers)

            # Inspect only the newest buffer in this returned batch.
            newest_buffer = buffers[-1]

            bytes_per_event = newest_buffer.bits_per_pixel // 8
            valid_events = (
                newest_buffer.size_filled // bytes_per_event
            )

            if valid_events > 0:
                src_data = ctypes.cast(
                    newest_buffer.pdata,
                    ctypes.POINTER(ctypes.c_float),
                )

                raw = np.ctypeslib.as_array(
                    src_data,
                    shape=(valid_events, 4),
                )

                last_event_t = int(raw[-1, 2])
                wall_elapsed = time.perf_counter() - start_wall

                if first_event_t is None:
                    first_event_t = last_event_t
                    first_event_wall = wall_elapsed

                event_elapsed = (
                    last_event_t - first_event_t
                ) / 1_000_000.0

                wall_since_first = (
                    wall_elapsed - first_event_wall
                )

                stream_lag = (
                    wall_since_first - event_elapsed
                )

                if buffer_counter % 512 == 0:
                    print(
                        f"Buffers: {buffer_counter:,} | "
                        f"Rate: "
                        f"{buffer_counter / wall_elapsed:,.0f} buffers/s | "
                        f"Events in newest buffer: "
                        f"{valid_events:,} | "
                        f"Event elapsed: "
                        f"{event_elapsed:.3f} s | "
                        f"Stream lag: "
                        f"{stream_lag:.3f} s | "
                        f"Frame ID: "
                        f"{int(newest_buffer.frame_id)}"
                    )

        finally:
            device.requeue_buffer(buffers)

except KeyboardInterrupt:
    print("\nBatched discard-only test stopped.")

finally:
    device.stop_stream()