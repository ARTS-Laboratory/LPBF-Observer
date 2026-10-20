# Reconstruction

Run from the `iteration_3` project directory with the Python 3.12 environment active:

```bash
python -m pip install -r requirements-reconstruction.txt
bash scripts/run_reconstruction.sh \
    "data/recordings/buffer-test-20261020T012235.400912Z-41835d81/events.raw" \
    --config config/reconstruction.toml
```

The launcher selects the patched OpenEB build at `.build/openeb-py312` and only its Prophesee RAW plugin. No camera, network connection, or Arena library is required for offline decoding. Set `OPENEB_ROOT` to relocate that build. The source decoder boundary patch must already have been applied and rebuilt; rerun `scripts/validate_raw.sh --recording PATH` when changing SDK builds. Protocol warnings from the native decoder remain visible. They are not automatically counted in the reconstruction report.

`requirements-reconstruction.txt` installs a headless OpenCV Python wheel for PNG rendering. Use a dedicated environment without another OpenCV Python wheel. This does not replace the separately installed C++ OpenCV libraries used by OpenEB. The existing recorder dependencies remain unchanged.

## Configuration

Edit `config/reconstruction.toml`:

```toml
[reconstruction]
window_us = 100000
start_s = 1.0
end_s = 4.0
modes = ["binary", "count_linear", "count_log", "signed_linear", "signed_log"]
```

The example reconstructs seconds 1 through 4 in consecutive 0.1-second windows. There is no separate step: the next window begins where the previous window ends. Times are relative to the first decoded CD event, not the host clock or a hardware trigger. Start is inclusive and end exclusive. Omit `end_s` to include the last event. Omit `start_s` to begin at zero. Selection boundaries round to the nearest microsecond.

Windows start at the selected start time. The last window is clipped to the selected end or available data. Events outside that final window cannot leak into its image. Empty windows inside the selected range are retained. Blank signed/binary frames are dark gray; blank count frames use the zero value of Viridis. An interval containing no CD events fails explicitly.

Command-line settings override the configuration:

```bash
bash scripts/run_reconstruction.sh PATH.raw \
    --window-us 10000 --start-s 1 --end-s 2 \
    --modes binary signed_log --output-root data/reconstructions
```

Legacy H5 inputs are also supported if they contain root `width` and `height` attributes and an `events` dataset with `x`, `y`, `p`, `t` fields. Polarity must be 0/1 and timestamps must be integer microseconds in nondecreasing order. Timestamp reversals and invalid coordinates fail explicitly; the pipeline does not discard the remaining recording silently.

## Rendering

| Mode | Meaning |
| --- | --- |
| Binary | Last polarity at each pixel wins; positive red, negative blue, untouched dark gray. |
| Count linear | Positive plus negative event count, per-frame min/max scaling, Viridis. |
| Count log | `log1p(positive + negative count)`, per-frame min/max scaling, Viridis. |
| Signed linear | Positive minus negative count; intensity proportional to absolute net count. |
| Signed log | Same net count; intensity proportional to `log1p(abs(net count))`. |

Signed intensities blend from BGR `(40,40,40)` toward red `(0,0,255)` or blue `(255,0,0)`, normalized by the maximum magnitude in that frame. Equal positive/negative counts cancel to gray. Signed-log emphasizes weaker net activity more than signed-linear. The old implementation assigned saturated colors based only on sign, making those two modes visually identical; this implementation retains magnitude. Per-frame normalization means color intensity is not an absolute scale across frames. Count normalization preserves the old behavior, including a uniform count image mapping to the zero end of Viridis.

## Outputs

Every run creates a fresh directory under `data/reconstructions`:

- One PNG directory for each selected mode.
- `frames.jsonl`: exact half-open timestamp boundaries, relative times, filenames, event counts; one row per frame.
- `curated.h5`: only the selected events, written incrementally with gzip compression.
- `metadata.json`: settings, preserved source information, counts, effective selection, completion status.

The curated `events` dataset uses `x:uint16`, `y:uint16`, `p:uint8` (0 negative, 1 positive), `t:int64` (microseconds). Sensor timestamps are preserved, never rebased. Events are exported once regardless of how many PNG modes are enabled.

For legacy H5 input, original root and event-dataset attributes are copied. Curated summary attributes such as total events and duration are updated. The original attributes are also retained separately in `source_metadata_json`, so original values remain accessible. Unrelated source datasets such as telemetry are not copied or trimmed.

For RAW input, `source_metadata_json` preserves the complete textual RAW header and neighboring recorder `metadata.json`, if present. Arbitrary nested recorder metadata is retained as JSON rather than flattened into H5 attributes. Geometry, timestamp units, source path, selected interval, and updated event count are H5 attributes. No original H5 exists to copy metadata from in this case.

Interrupted or failed runs retain partial outputs for diagnosis with `metadata.json` state `incomplete` and H5 `reconstruction_complete=false`. Treat them as incomplete. Successful H5 files have `reconstruction_complete=true`.

Processing reads the source sequentially without indexing or seeks and retains only a decoded chunk plus per-pixel accumulators. It scans the full source even when selecting a short interval, preserving ordered-decoder state and checking timestamp/coordinate validity throughout. Full-rate image output across all five modes can be expensive; use a short interval for the first test. PNG export and curated H5 are included; video and telemetry plotting are not part of this addition.

## Tests and portability

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_reconstruction.py' -v
```

These tests use synthetic/legacy H5 events to verify exact selection, clipped windows, chunk independence, signed rendering, metadata preservation, inclusion of the last event, and incomplete-run reporting. Native RAW decoding additionally needs the patched SDK on the user's machine.

The renderer accepts filesystem paths, has no GUI dependency or hardcoded user path, and can run in a future container. For H5-only reconstruction, the SDK is unnecessary:

```bash
PYTHONPATH=src python -m event_optical.reconstruction PATH.h5 \
    --config config/reconstruction.toml
```

A future RAW container must build the patched OpenEB and Python bindings inside its Linux image; do not copy Arch native libraries into an Ubuntu container. No Docker image is supplied by this change.
