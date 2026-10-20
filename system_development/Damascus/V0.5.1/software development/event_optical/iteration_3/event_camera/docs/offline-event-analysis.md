# Offline event-rate telemetry

Keep `[telemetry] decode_events=false` in the recorder config. Live telemetry still captures RAW payload throughput, buffer consumption and available host/NIC counters. Decode saved events after acquisition to avoid competing with the capture loop.

## Install and run

Extract from `iteration_3` and run the hardware-independent tests:

```bash
unzip -n "$HOME/Downloads/offline-event-analysis.zip" -d .
PYTHONPATH=src python -m unittest discover -s tests -p 'test_event_analysis.py' -v
```

For a RAW recording:

```bash
bash scripts/analyze_recording.sh \
    "data/recordings/SESSION/events.raw" --bin-us 250000
```

The launcher uses the patched OpenEB build at `OPENEB_ROOT` (default `.build/openeb-py312`) and selects only its Prophesee RAW plugin. No camera or Arena connection is opened. The existing `reconstruction.py` provides the proven sequential RAW reader, with indexing disabled and native RawBuffers passed directly to the decoder. It checks that the entire RAW payload was fed to the decoder. No PNG frames or curated H5 are produced by this command.

For an optional plot, install Matplotlib into the active environment:

```bash
python -m pip install -r requirements-analysis.txt
bash scripts/analyze_recording.sh PATH.raw --bin-us 250000 --plot
```

Legacy H5 input is also accepted through the same reader. For H5-only analysis, with h5py installed, no SDK or launcher is required:

```bash
PYTHONPATH=src python -m event_optical.event_analysis PATH.h5 --plot
```

## Outputs

Each run creates a new directory in `data/analysis` (override with `--output-root`):

- `event_rate.csv`: total CD, positive, and negative counts and total CD events/s for each sensor-time bin.
- `summary.json`: totals, first/last CD timestamps, event span, mean rate, maximum bin rate, geometry, integrity checks, preserved source metadata and analysis completion status.
- `event_rate_plot.png`: optional headless plot of total/positive/negative rates.

Timestamps are integer microseconds. Bins are consecutive half-open intervals anchored at the first decoded CD event. A 250000-us bin covers 0.25 seconds of sensor time. Empty bins between events are included. The last event is included using a final exclusive endpoint at `last_timestamp + 1 us`. That last bin can be shorter than the requested size; its rate uses its actual duration, recorded in the CSV. The maximum-bin rate includes partial bins; a very short final bin can produce a large rate. Inspect `duration_us` and `partial_bin` when interpreting peaks. A single-event file gets a one-microsecond observation interval, not an estimate of long-term activity.

Rates describe decoded CD events in the saved recording after camera bias/filter/ERC decisions and any upstream losses. They are not independently measured camera output or loss counts. Trigger and other non-CD events are not included. No lost events are synthesized or repaired.

For native recorder RAW input, a neighboring `metadata.json` supplies `host_capture_elapsed_seconds`. `cd_event_span_seconds` covers only the first through last decoded CD event (inclusive to microsecond resolution). These clocks are not synchronized here. A shorter CD span can reflect quiet time or incomplete capture; the ratio alone does not distinguish them and does not prove loss. This analyzer cannot recover data missing from the RAW. It also cannot infer that missing events were caused specifically by the live decoder.

The source is read sequentially. Analysis memory scales with a decoded chunk rather than recording size; the optional plotting step currently reads the smaller per-bin CSV into memory. Timestamp reversals, out-of-bounds coordinates, invalid polarity and incomplete RAW reads fail explicitly. Partial outputs remain with `state=incomplete`. Full success is `state=complete`. Decoder protocol warnings are still printed by HAL but are not programmatically counted (`decoder_protocol_warning_count=null`). Zero timestamp/coordinate errors do not establish lossless acquisition (`losslessness_verified=false`).

The existing `stream_telemetry.csv` and its offline plot use host time. This analysis uses sensor time; graphs are deliberately separate rather than overlaid without a synchronization model. Filesystem paths and the headless renderer work with the planned Docker container.
