from recorder_config import SERIAL_NUMBER, BUFFER_COUNT, WARMUP_EVENT_COUNT
from functions.streamTelemetry import StreamTelemetry
import ctypes
import csv
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

HDF5_WRITE_BATCH_EVENTS = 250_000
HDF5_FLUSH_INTERVAL_EVENTS = 5_000_000

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
    diagnostics_path = file_name.with_name(
        f"{file_name.stem}_buffer_diagnostics.csv"
    )

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
            chunks=(500_000,),
        )

        '''dataset = event_file.create_dataset(
            "events",
            shape=(0,),
            maxshape=(None,),
            dtype=event_dtype,
            chunks=(500000,),
            compression="gzip",
            compression_opts=4
        )'''

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
        last_frame_id = None
        last_event_timestamp = None
        timestamp_reset_count = 0
        first_timestamp_reset_event = None
        total_payload_bytes = 0
        first_buffer_event_timestamp = None
        first_buffer_wall_elapsed = None
        diagnostics_file = None
        diagnostics_writer = None
        pending_event_arrays = []
        pending_event_count = 0
        written_event_count = 0
        last_hdf5_flush_count = 0


        def flush_event_batch():
            """
            Write all pending event arrays to HDF5 in one operation.

            Returns the number of events written.
            """
            nonlocal pending_event_count
            nonlocal written_event_count

            if pending_event_count == 0:
                return 0

            event_batch = np.concatenate(pending_event_arrays)

            old_size = dataset.shape[0]
            batch_size = len(event_batch)
            new_size = old_size + batch_size

            try:
                dataset.resize((new_size,))
                dataset[old_size:new_size] = event_batch

            except Exception:
                # Remove any unwritten space created by resize().
                dataset.resize((old_size,))
                raise

            pending_event_arrays.clear()
            pending_event_count = 0
            written_event_count += batch_size

            return batch_size

        try:
            print(f"Starting stream with {BUFFER_COUNT} host buffers.")
            device.start_stream(BUFFER_COUNT)
            armed_time = time.time()
            stream_started = True

            diagnostics_file = diagnostics_path.open(
                "w",
                newline="",
                encoding="utf-8",
            )
            diagnostics_writer = csv.writer(diagnostics_file)
            diagnostics_writer.writerow([
                "wall_time_s",
                "buffer_counter",
                "frame_id",
                "valid_events",
                "first_timestamp_us",
                "last_timestamp_us",
                "buffer_timestamp_span_us",
                "event_elapsed_s",
                "wall_elapsed_since_first_event_s",
                "stream_lag_s",
                "size_filled_bytes",
                "camera_event_rate_ev_s",
                "gvsp_frame_rate",
                "camera_link_throughput_B_s",
            ])

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

                    # Track every recorded buffer, not only every 500th buffer.
                    current_frame_id = int(buffer.frame_id)

                    if last_frame_id is not None:
                        frame_gap = current_frame_id - last_frame_id

                        if frame_gap <= 0:
                            logging.warning(
                                "FRAME-ID RESET OR REVERSAL: "
                                f"previous={last_frame_id}, "
                                f"current={current_frame_id}, "
                                f"received_buffer={buffer_counter:,}, "
                                f"recorded_events={total_events:,}"
                            )

                    last_frame_id = current_frame_id

                    total_payload_bytes += int(buffer.size_filled)

                    raw = np.ctypeslib.as_array(
                        src_data,
                        shape=(valid_events, 4),
                    )

                    buffer_timestamps = raw[:, 2].astype(np.int64)

                    buffer_wall_time = time.time()
                    wall_time_s = (
                        buffer_wall_time - recording_start_time
                        if recording_start_time is not None
                        else 0.0
                    )

                    buffer_first_t = None
                    buffer_last_t = None
                    buffer_span_us = None
                    event_elapsed_s = None
                    wall_elapsed_since_first_event_s = None
                    stream_lag_s = None

                    if len(buffer_timestamps) > 0:
                        buffer_first_t = int(buffer_timestamps[0])
                        buffer_last_t = int(buffer_timestamps[-1])
                        buffer_span_us = buffer_last_t - buffer_first_t

                        if first_buffer_event_timestamp is None:
                            first_buffer_event_timestamp = buffer_first_t
                            first_buffer_wall_elapsed = wall_time_s

                        event_elapsed_s = (
                            buffer_last_t - first_buffer_event_timestamp
                        ) / 1_000_000.0

                        wall_elapsed_since_first_event_s = (
                            wall_time_s - first_buffer_wall_elapsed
                        )

                        stream_lag_s = (
                            wall_elapsed_since_first_event_s
                            - event_elapsed_s
                        )

                    # Check for a timestamp reset between consecutive buffers.
                    if (
                        last_event_timestamp is not None
                        and len(buffer_timestamps) > 0
                        and buffer_timestamps[0] < last_event_timestamp
                    ):
                        timestamp_reset_count += 1

                        if first_timestamp_reset_event is None:
                            first_timestamp_reset_event = total_events

                        logging.error(
                            "TIMESTAMP RESET between buffers: "
                            f"event_index={total_events:,}, "
                            f"previous={last_event_timestamp}, "
                            f"current={buffer_timestamps[0]}"
                        )

                    # Check for a timestamp reset inside the current buffer.
                    internal_resets = np.flatnonzero(
                        np.diff(buffer_timestamps) < 0
                    ) + 1

                    for reset_index in internal_resets:
                        timestamp_reset_count += 1
                        absolute_index = total_events + int(reset_index)

                        if first_timestamp_reset_event is None:
                            first_timestamp_reset_event = absolute_index

                        logging.error(
                            "TIMESTAMP RESET inside buffer: "
                            f"event_index={absolute_index:,}, "
                            f"previous={buffer_timestamps[reset_index - 1]}, "
                            f"current={buffer_timestamps[reset_index]}"
                        )

                    if len(buffer_timestamps) > 0:
                        last_event_timestamp = int(buffer_timestamps[-1])

                    events = np.empty(valid_events, dtype=event_dtype)

                    events["x"] = raw[:, 0]
                    events["y"] = raw[:, 1]
                    events["t"] = raw[:, 2]
                    events["p"] = raw[:, 3]

                    # Store this buffer's converted events in memory.
                    pending_event_arrays.append(events)
                    pending_event_count += valid_events

                    total_events += valid_events
                    buffer_counter += 1

                    # Write accumulated events to HDF5 in one large batch.
                    if pending_event_count >= HDF5_WRITE_BATCH_EVENTS:
                        flush_event_batch()

                    # Force HDF5 data to disk after every 5 million written events.
                    if (
                        written_event_count - last_hdf5_flush_count
                        >= HDF5_FLUSH_INTERVAL_EVENTS
                    ):
                        event_file.flush()
                        last_hdf5_flush_count = written_event_count

                    if telemetry is not None:
                        telemetry.sample(
                            tl_stream,
                            total_events=total_events,
                            total_payload_bytes=total_payload_bytes,
                            incomplete_buffers=incomplete_buffer_count,
                            get_buffer_errors=get_buffer_error_count,
                        )

                    if buffer_counter % 500 == 0:

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

                            diagnostics_writer.writerow([
                                f"{wall_time_s:.9f}",
                                buffer_counter,
                                current_frame_id,
                                valid_events,
                                buffer_first_t,
                                buffer_last_t,
                                buffer_span_us,
                                (
                                    f"{event_elapsed_s:.9f}"
                                    if event_elapsed_s is not None
                                    else ""
                                ),
                                (
                                    f"{wall_elapsed_since_first_event_s:.9f}"
                                    if wall_elapsed_since_first_event_s is not None
                                    else ""
                                ),
                                (
                                    f"{stream_lag_s:.9f}"
                                    if stream_lag_s is not None
                                    else ""
                                ),
                                int(buffer.size_filled),
                                stream_event_rate,
                                gvsp_frame_rate,
                                link_throughput,
                            ])
                            diagnostics_file.flush()

                            stream_lag_text = (
                                f"{stream_lag_s:.6f} s"
                                if stream_lag_s is not None
                                else "n/a"
                            )

                            print(
                                f"  Camera rate: {stream_event_rate / 1_000_000:.2f} Mev/s | "
                                f"GVSP rate: {gvsp_frame_rate:.0f} | "
                                f"Link: {link_throughput / 1_000_000:.1f} MB/s "
                                f"({link_throughput * 8 / 1_000_000_000:.2f} Gb/s) | "
                                f"Incomplete: {incomplete_buffer_count:,}"
                            )

                            print(
                                "  Buffer sample: "
                                f"events={valid_events:,} | "
                                f"frame_id={current_frame_id} | "
                                f"first_t={buffer_first_t} | "
                                f"last_t={buffer_last_t} | "
                                f"span={buffer_span_us} us | "
                                f"stream_lag={stream_lag_text}"
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
            try:
                flush_event_batch()

            except Exception as flush_error:
                logging.exception(
                    "Failed to write the final HDF5 event batch: "
                    f"{flush_error}"
                )

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
            if dataset.shape[0] != written_event_count:
                logging.warning(
                    "Correcting HDF5 dataset length: "
                    f"dataset={dataset.shape[0]:,}, "
                    f"written={written_event_count:,}"
                )
                dataset.resize((written_event_count,))

            event_file.attrs["total_events"] = written_event_count
            event_file.attrs["events_received"] = total_events
            event_file.attrs["events_written"] = written_event_count
            event_file.attrs["unwritten_events"] = (
                total_events - written_event_count
            )
            event_file.attrs["hdf5_write_batch_events"] = (
                HDF5_WRITE_BATCH_EVENTS
            )
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

            if diagnostics_file is not None:
                diagnostics_file.close()

            event_file.attrs["total_payload_bytes"] = total_payload_bytes

            event_file.attrs["stream_telemetry_file"] = telemetry_path.name
            event_file.attrs["buffer_diagnostics_file"] = (
                diagnostics_path.name
            )
            event_file.attrs["incomplete_buffers"] = incomplete_buffer_count
            event_file.attrs["get_buffer_errors"] = get_buffer_error_count

            event_file.attrs["timestamp_resets"] = timestamp_reset_count

            event_file.attrs["first_timestamp_reset_event"] = (
                -1
                if first_timestamp_reset_event is None
                else first_timestamp_reset_event
            )
            
            event_file.flush()

            if stream_started:
                device.stop_stream()


    if timestamp_reset_count > 0:
        logging.error(
            "RECORDING FAILED INTEGRITY CHECK: "
            f"timestamp_resets={timestamp_reset_count}, "
        )
    else:
        logging.info(
            "Recording passed integrity check: "
            "no timestamp resets detected."
        )
