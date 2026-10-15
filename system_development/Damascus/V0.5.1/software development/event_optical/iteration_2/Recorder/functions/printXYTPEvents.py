from recorder_config import SERIAL_NUMBER, BUFFER_COUNT, WARMUP_EVENT_COUNT
import ctypes

def printXYTPEvents(device):
    """
    Configure the EVS camera for XYTPFrame output and print
    timestamp, x, y, polarity for each valid event. 
    """
    try:
        device.start_stream(BUFFER_COUNT)

        print("Streaming XYTP events...\n")
        print(f"{'Timestamp':>15} {'X':>6} {'Y':>6} {'P':>6}")
        print("-" * 40)

        while True:
            buffer = device.get_buffer()

            try:
                if buffer.is_incomplete:
                    continue

                src_data = ctypes.cast(
                    buffer.pdata,
                    ctypes.POINTER(ctypes.c_float)
                )

                bytes_per_event = buffer.bits_per_pixel // 8
                valid_events = buffer.size_filled // bytes_per_event

                for i in range(valid_events):

                    x = src_data[i * 4 + 0]
                    y = src_data[i * 4 + 1]
                    t = src_data[i * 4 + 2]
                    p = src_data[i * 4 + 3]

                    print(
                        f"{t:15.6f} "
                        f"{int(x):6d} "
                        f"{int(y):6d} "
                        f"{int(p):6d}"
                    )

            finally:
                device.requeue_buffer(buffer)

    except KeyboardInterrupt:
        get_buffer_error_count += 1
        print("\nStopped.")

    finally:
        device.stop_stream()