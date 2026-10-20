# Camera controls and telemetry

This addition uses the LUCID Metavision plugin and existing native RAW recorder. It does not start a second Arena connection or replace RAW acquisition with XYTP conversion.

## Install

From `iteration_3`, activate the existing Python 3.12 environment, extract the archive, and apply the guarded recorder integration:

```bash
unzip -n "$HOME/Downloads/recorder-controls-telemetry.zip" -d .
python scripts/upgrade_recorder_controls.py
PYTHONPATH=src python -m unittest discover -s tests -p 'test_camera_controls.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_recorder.py' -v
```

The integration script checks all expected source anchors before changing the recorder and saves its original version in `.build/backups/recorder.py.before-controls`. Re-running is a no-op. If your source has different anchors, the script refuses to change it. Keep the new modules and integration recipe in git along with the updated recorder.

## Configuration

Use `--config config/recorder.toml`. Without that option the recorder changes no camera settings and still writes basic host telemetry at 0.25-second intervals. The config file also leaves all camera settings unchanged until you uncomment them. No config file is loaded implicitly.

| Previous setting | Config entry under `[biases]` | Reported range on serial 250200198 |
| --- | --- | --- |
| Positive event threshold | `bias_diff_on` | -88 to 152 |
| Negative event threshold | `bias_diff_off` | -40 to 200 |
| Low-pass cutoff bias | `bias_fo` | -43 to 22 |
| High-pass cutoff bias | `bias_hpf` | 0 to 120 |
| Refractory period bias | `bias_refr` | -20 to 235 |

These are integer bias offsets reported by the camera, not physical units of Hz or microseconds. Zero is a value to apply; omitting a setting leaves it unchanged. `bias_diff`, the reference level, is deliberately excluded because the camera description advises against adjusting it. The plugin's low-pass description contains contradictory noise wording; this addition does not infer tuning direction from that description.

Ranges are checked against the connected camera every time, rather than assumed from this table. A missing control, invalid range, false setter result, or mismatched read-back prevents capture. The metadata includes original camera values, requested settings, individual setter results, and actual read-back values. Writes are not transactional: if a later write fails, earlier writes remain applied. They are recorded in metadata; capture does not start. Successful settings remain on the camera after recording. There is no automatic reset or claim of nonvolatile persistence.

ERC entries under `[erc]`:

```toml
[erc]
enabled = true
rate_limit_ev_s = 20000000
```

This example demonstrates syntax, not a validated weld limit. An enabled ERC intentionally suppresses events to constrain output; choose it as an experiment parameter, not as evidence of lossless acquisition. The reported target is a configuration value, not the measured camera rate. The current camera reports a minimum target of 1,000,000 events/s. HAL may quantize targets to its count period; this recorder requires exact read-back and stops on a mismatch rather than silently accepting another target. Rate is applied before enabling ERC. Omit `enabled` to leave its existing state unchanged.

Run a short capture first:

```bash
bash scripts/run_recorder.sh \
    --config config/recorder.toml \
    --serial "Lucid Vision Labs:lucid_imx63x_plugin5:250200198" \
    --name controls-test --duration 5
```

The existing Linux GenTL preload and global HAL import fixes remain in use. No SDK rebuild is required for these Python changes.

## Telemetry

Each session gains `stream_telemetry.csv`. Rows are flushed every configured interval and once after stopping/draining. Measurements use host monotonic time; UTC is included as a separate label. The final `phase=stopped` row can include queued data drained after the capture loop. Host elapsed time is not synchronized to the event sensor's clock or a weld trigger.

Always available for received RAW buffers:

- Buffer count, consumed native RAW payload bytes, measured payload bytes/s, buffers/s.
- RAW file size, which can lag consumed bytes while SDK logging buffers writes.
- Maximum interval between host buffer consumption calls, including startup. This is a host scheduling/consumption diagnostic, not a packet-loss or sensor latency measurement.

Linux host statistics when readable:

- Interface RX/TX bytes, RX packets, errors and drops, and changes since acquisition began.
- UDP input errors and receive-buffer errors, and changes since acquisition began. UDP counters cover the entire current network namespace, including other applications. NIC counters cover the whole interface. Neither is a camera-specific loss count.
- Set `[telemetry] interface="enp3s0"` to the current camera NIC. Missing interfaces/counters produce blank fields, not zero. Deltas remain blank if a counter resets below its baseline.

The inspected LUCID plugin does not provide hardware monitoring, hardware register access, or a measured camera-rate facility. Camera event rate, GVSP frame rate, camera-reported link throughput, incomplete-buffer count and Arena get-buffer error count remain explicitly unavailable (blank CSV values and a list in metadata). Generic host errors are not relabeled as those vendor statistics. No vendor setting or telemetry is queried repeatedly during capture.

## Optional measured CD event rate

Set this in the config before launching:

```toml
[telemetry]
interval_s = 0.25
interface = "enp3s0"
decode_events = true
```

The existing RAW buffers are decoded natively in the capture loop after the SDK logs them. A NumPy callback counts CD events, timestamp reversals, and out-of-bounds coordinates. It does not construct images or write event H5 during recording. This adds native decoding and callback CPU work; compare throughput under representative activity before enabling for weld capture. Default is `false`, preserving the recorder's undecoded acquisition path.

The CSV gains decoded CD count and CD events/s over the host sampling interval. These count events delivered by the decoder after camera filtering/ERC and any upstream losses; they are not an independent sensor-rate or losslessness measurement. Counts exclude other event types such as triggers. Metadata retains first/last decoded CD timestamps and integrity counters. Decoder warnings remain visible. Integrity counts are diagnostic and do not automatically stop the recording; inspect them before accepting data.

## Offline telemetry plot

Plot outside acquisition, so plotting cannot slow the recorder:

```bash
python -m pip install 'matplotlib>=3.8,<4'
PYTHONPATH=src python -m event_optical.telemetry_plot \
    "data/recordings/SESSION/stream_telemetry.csv"
```

This saves `stream_telemetry_plot.png` next to the CSV. It plots RAW payload throughput, optional decoded CD event rate, and selected network error/drop deltas. Missing values stay missing. There is no hardcoded network bandwidth line. It works headlessly for the future container.

The existing reconstruction preserves recorder metadata inside the curated H5's `source_metadata_json`. The telemetry CSV stays alongside the original RAW; it is not currently time-trimmed or embedded into curated H5. Sensor-relative reconstruction time and host telemetry time are different clocks.

## Validation status

Hardware-independent recorder lifecycle tests and control/telemetry unit tests pass in the development environment. Tests cover preflight before writes, exact read-back, ERC operation order, unchanged omitted settings, malformed config, telemetry rates/counter deltas/missing values, and decoding statistics. Actual HAL writes and live telemetry need a short capture on the connected camera before weld use. Hardware capability names and ranges were read from serial 250200198; the implementation still discovers and validates them per run.
