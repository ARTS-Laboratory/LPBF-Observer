from recorder_config import SERIAL_NUMBER, BUFFER_COUNT, WARMUP_EVENT_COUNT
from functions.streamTelemetry import StreamTelemetry
import ctypes
import h5py
import numpy as np
import datetime 
import time
from pathlib import Path
import logging
from pytictoc import TicToc
import arena_api

BASE_PATH = Path(__file__).resolve().parent.parent
output_path = BASE_PATH / "recordings"
output_path.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     datefmt='%Y-%m-%d %I:%M:%S %p')
t = TicToc()

def recordEventsXYTP(
    device,
    warmup_event_count: int = WARMUP_EVENT_COUNT,
):
    """
    Record XYTP events after a cumulative warm-up event count has passed.

    Buffers received during warm-up are immediately requeued and are not
    stored. The buffer that reaches the count is also discarded, so the first
    recorded buffer begins only after the requested warm-up has completed.
    """
    if warmup_event_count < 0:
        raise ValueError("warmup_event_count cannot be negative")

    fileCount = len(list(output_path.glob("event_recording_*")))
    event_dtype = np.dtype([
        ("x", np.uint16),
        ("y", np.uint16),
        ("t", np.uint64),  
        ("p", np.uint8),
    ])
    ts = datetime.datetime.now().strftime("%I%M%S_%p_%m%d%Y")

    parent_folder = output_path / f"event_recording_{fileCount}_{ts}"
    parent_folder.mkdir(parents=True, exist_ok=True)

    file_name = parent_folder / f"event_recording_{fileCount}_{ts}.h5"
    telemetry_path = file_name.with_name(f"{file_name.stem}_stream_telemetry.csv")

    with h5py.File(file_name, "w") as event_file:
        nodemap = device.nodemap
        tl_stream = device.tl_stream_nodemap

        event_file.attrs["camera_model"] = nodemap["DeviceModelName"].value
        event_file.attrs["serial_number"] = nodemap["DeviceSerialNumber"].value
        event_file.attrs["width"] = nodemap["Width"].value
        event_file.attrs["height"] = nodemap["Height"].value
        event_file.attrs["event_format"] = nodemap["EventFormat"].value
        event_file.attrs["stream_output"] = (
            tl_stream["StreamEvsOutputFormat"].value
        )
        event_file.attrs["recorded"] = ts
        event_file.attrs["acquisition_mode"] = nodemap["AcquisitionMode"].value

        event_file.attrs["stream_buffer_handling_mode"] = (
            tl_stream["StreamBufferHandlingMode"].value
        )

        event_file.attrs["stream_auto_packet_size"] = (
            tl_stream["StreamAutoNegotiatePacketSize"].value
        )

        event_file.attrs["stream_packet_resend"] = (
            tl_stream["StreamPacketResendEnable"].value
        )

        event_file.attrs["requested_stream_buffer_count"] = BUFFER_COUNT
        event_file.attrs["warmup_event_count_required"] = warmup_event_count
        event_file.attrs["recording_triggered"] = False
        event_file.attrs["erc_enable"] = nodemap["ErcEnable"].value
        event_file.attrs["erc_rate_limit"] = nodemap["ErcRateLimit"].value
        event_file.attrs["software"] = "Event Camera Recorder"
        event_file.attrs["software_version"] = "0.2"

        #event_file.attrs["python_version"] = platform.python_version()

        event_file.attrs["arena_api_version"] = getattr(
                arena_api,
                "__version__",
                "unknown",
            )

        dataset = event_file.create_dataset(
            "events",
            shape=(0,),
            maxshape=(None,),
            dtype=event_dtype,
            chunks=(500000,),
            compression="gzip",
            compression_opts=4
        )

        telemetry = None
        buffer_counter = 0
        total_events = 0
        incomplete_buffer_count = 0
        get_buffer_error_count = 0
        max_stream_event_rate = 0.0
        max_link_throughput = 0.0
        pretrigger_buffers = 0
        pretrigger_events = 0
        recording_started = warmup_event_count == 0
        armed_time = None
        recording_start_time = None
        stream_started = False

        try:
            print(f"Starting stream with {BUFFER_COUNT} host buffers.")
            device.start_stream(BUFFER_COUNT)
            armed_time = time.time()
            stream_started = True

            print(
                "\nRecorder warming up. Discarding the first "
                f"{warmup_event_count:,} events..."
            )

            if recording_started:
                recording_start_time = armed_time
                event_file.attrs["recording_triggered"] = True
                event_file.attrs["warmup_buffers_discarded"] = 0
                event_file.attrs["warmup_events_discarded"] = 0
                event_file.attrs["warmup_duration_seconds"] = 0.0

                telemetry = StreamTelemetry(
                    telemetry_path,
                    sample_interval_s=1.0,
                )

                print("No warm-up requested. Recording begins immediately.")
                print("\nRecording XYTP events...\n")
                print(f"{'Timestamp':>15} {'X':>6} {'Y':>6} {'P':>6}")
                print("-" * 40)

            while True:
                try:
                    buffer = device.get_buffer(timeout=2000)

                except Exception as e:
                    get_buffer_error_count += 1
                    print(f"get_buffer() failed: {e}")
                    break

                try:
                    if buffer.is_incomplete:
                        incomplete_buffer_count += 1
                        continue

                    src_data = ctypes.cast(
                        buffer.pdata,
                        ctypes.POINTER(ctypes.c_float)
                    )

                    bytes_per_event = buffer.bits_per_pixel // 8
                    valid_events = buffer.size_filled // bytes_per_event

                    if not recording_started:
                        pretrigger_buffers += 1
                        pretrigger_events += valid_events

                        if pretrigger_events < warmup_event_count:
                            continue

                        recording_started = True
                        recording_start_time = time.time()
                        telemetry = StreamTelemetry(telemetry_path, sample_interval_s=1)

                        event_file.attrs["recording_triggered"] = True
                        event_file.attrs["warmup_buffers_discarded"] = (
                            pretrigger_buffers
                        )
                        event_file.attrs["warmup_events_discarded"] = (
                            pretrigger_events
                        )
                        event_file.attrs["warmup_duration_seconds"] = (
                            recording_start_time - armed_time
                        )

                        print(
                            "Warm-up complete after "
                            f"{pretrigger_events:,} discarded events. "
                            "Recording begins with the next buffer.\n"   
                        )

                        print("Recording XYTP events...\n")
                        print(f"{'Timestamp':>15} {'X':>6} {'Y':>6} {'P':>6}")
                        print("-" * 40)

                        continue

                    raw = np.ctypeslib.as_array(
                        src_data,
                        shape=(valid_events, 4),
                    )

                    events = np.empty(valid_events, dtype=event_dtype)

                    events["x"] = raw[:, 0]
                    events["y"] = raw[:, 1]
                    events["t"] = raw[:, 2]
                    events["p"] = raw[:, 3]

                    old_size = dataset.shape[0]
                    new_size = old_size + valid_events

                    dataset.resize((new_size,))
                    dataset[old_size:new_size] = events

                    total_events += valid_events
                    buffer_counter += 1

                    if telemetry is not None:
                        telemetry.sample(
                            tl_stream,
                            total_events=total_events,
                            incomplete_buffers=incomplete_buffer_count,
                            get_buffer_errors=get_buffer_error_count,
                        )

                    if buffer_counter % 500 == 0:
                        event_file.flush()

                        try:
                            stream_event_rate = tl_stream["StreamEvsEventRate"].value
                            gvsp_frame_rate = tl_stream["StreamEvsGvspFrameRate"].value
                            link_throughput = tl_stream["StreamEvsLinkThroughput"].value

                            max_stream_event_rate = max(
                                max_stream_event_rate,
                                stream_event_rate,
                            )
                            max_link_throughput = max(
                                max_link_throughput,
                                link_throughput,
                            )

                            print(
                                f"  Camera rate: {stream_event_rate / 1_000_000:.2f} Mev/s | "
                                f"GVSP rate: {gvsp_frame_rate:.0f} | "
                                f"Link: {link_throughput / 1_000_000:.1f} MB/s "
                                f"({link_throughput * 8 / 1_000_000_000:.2f} Gb/s) | "
                                f"Incomplete: {incomplete_buffer_count:,}"
                            )

                            print(
                                f"bits_per_pixel={buffer.bits_per_pixel}, "
                                f"size_filled={buffer.size_filled}, "
                                f"valid_events={valid_events}"
                            )

                        except Exception as stats_error:
                            logging.warning(
                                f"Could not read EVS stream statistics: {stats_error}"
                            )

                        print(
                            f"Buffers: {buffer_counter:,} | "
                            f"Events: {total_events:,}"
                        )

                except Exception as e:
                    print(f"Processing error: {e}")

                finally:
                    device.requeue_buffer(buffer)

        except KeyboardInterrupt:
            print("\nStopped.")

        finally:
            end_time = time.time()
            elapsed = (
                end_time - recording_start_time
                if recording_start_time is not None
                else 0.0
            )

            #
            # dataset.resize() and the write that fills it are two
            # separate statements. If recording stops (Ctrl+C, or
            # any exception caught above) between them, the dataset
            # can end up larger than what was actually written —
            # h5py fills those leftover rows with 0 for every field,
            # which corrupts anything that assumes timestamps are
            # monotonically increasing (e.g. h5FileViewer.py).
            # total_events only increments after a resize+write both
            # succeed, so trimming to it removes any such dangling
            # rows.
            if dataset.shape[0] != total_events:
                logging.info(
                    f"Trimming {dataset.shape[0] - total_events} "
                    "unwritten trailing row(s) left over from an "
                    "interrupted buffer."
                )
                dataset.resize((total_events,))

            event_file.attrs["total_events"] = total_events
            event_file.attrs["total_buffers"] = buffer_counter
            event_file.attrs["duration_seconds"] = elapsed
            event_file.attrs["stream_armed_duration_seconds"] = (
                end_time - armed_time
                if armed_time is not None
                else 0.0
            )

            event_file.attrs["incomplete_buffers"] = incomplete_buffer_count
            event_file.attrs["get_buffer_errors"] = get_buffer_error_count
            event_file.attrs["max_stream_event_rate_ev_s"] = max_stream_event_rate
            event_file.attrs["max_link_throughput_B_s"] = max_link_throughput

            if elapsed > 0:
                event_file.attrs["event_rate"] = total_events / elapsed

            if telemetry is not None:
                telemetry.close()

            event_file.attrs["stream_telemetry_file"] = telemetry_path.name
            event_file.attrs["incomplete_buffers"] = incomplete_buffer_count
            event_file.attrs["get_buffer_errors"] = get_buffer_error_count
            
            event_file.flush()

            if stream_started:
                device.stop_stream()
