# General optical image acquisition

FLIR Blackfly S / Spinnaker 4.4.0.246, Ubuntu 24.04, Python 3.12.
Independent of the event recorder and any welding workflow.

## Setup

Keep your previously downloaded matching Spinnaker SDK and cp312 PySpin tarballs
in `vendor/` (ignored by Git). The Dockerfile installs the runtime packages and
FFmpeg/OpenMP dependencies, imports the wheel, then runs camera-free unit tests.

From this optical_camera directory, after accepting the vendor EULA:

```bash
sudo bash docker/run.sh build --build-arg ACCEPT_SPINNAKER_EULA=true
sudo bash docker/run.sh --check
sudo bash docker/run.sh --list
sudo bash docker/run.sh test
```

Image: `lpbf-optical:0.2`. Source version 0.1 remains available as the earlier
bootstrap image. SDK build layers are reused where unchanged. Nothing installs
Spinnaker on the host. This wrapper targets Linux GigE host networking.

## Settings

Edit `config/camera.toml` on the host. Defaults select serial 19328838, Mono8,
1000 microsecond manual exposure and 0 dB manual gain. These are starter settings,
not a calibrated post-weld exposure. Settings are applied to the camera and remain
after exit; there is no automatic restoration or user-set save to flash.
Set serial for another camera, or an empty string to auto-select only if one exists.

Acquisition starts only after required writes and readbacks pass. If a later
setting fails, earlier writes can remain; acquisition does not start. Numeric
settings outside advertised limits or readback mismatches fail instead of silently
clamping. Camera node limits can depend on other active settings.
Supported image pixel formats: Mono8 / Mono16, saved as PNG without application
normalization or false coloring. Existing camera processing such as gamma is
recorded when readable, not automatically disabled. Mono16 intensity interpretation
must be checked against the camera's sensor bit depth.

## Standalone capture

```bash
# A fresh software-triggered exposure; one image in a unique session.
sudo bash docker/run.sh single --name sample

# Continuous acquisition, saving each returned frame as a separate PNG.
sudo bash docker/run.sh sequence --name sequence-test --duration 5

# Or stop after a specified number of saved frames.
sudo bash docker/run.sh sequence --name ten-images --frames 10
```

Without duration/frames, sequence runs until Ctrl+C or SIGTERM. Frame rate can be
limited with `frame_rate_hz` in the TOML file. The optional limit must be supported
by the camera. Continuous capture uses free-running acquisition, not a timer that
picks occasional frames. PNG writing may limit throughput at full resolution;
there is no claim that every sensor frame is saved. No video is encoded.

Outputs always go to this component's `data/recordings/`, independent of your shell
working directory. Each unique session contains:

- `images/frame-00000000.png`, etc.
- `frames.csv`: camera timestamp (ns), frame ID, host receive UTC, trigger command
  UTC when applicable, geometry, file size, save time and observed frame-ID gaps.
- `metadata.json`: requested/read-back settings, frame/incomplete counts, stream
  counter snapshots when the SDK exposes them, and final success/error state.

Camera timestamps and host UTC are different clocks. Trigger-issued UTC timestamps
the host command, not the measured sensor exposure start. Frame-ID gaps are clues,
not a complete transport-loss estimate. Missing counters are null, not zero.
Incomplete images, SDK timeouts, save failures and cleanup failures produce exit 1
and error metadata. Successfully saved earlier images are retained. SIGTERM waits
for the current SDK call/save (up to timeout plus processing); SIGKILL cannot
finalize metadata. Final `capture_stopped` is written after SDK cleanup succeeds.

## Generic command worker

`serve` opens/configures the camera once, arms FrameStart / Software trigger,
and waits without taking pictures. This supports any external controller.

```bash
sudo bash docker/run.sh serve --name requested-images
```

Send one JSON object per stdin line, with a unique request ID:

```json
{"id":"sample-001","command":"capture"}
{"id":"query-001","command":"status"}
{"id":"done","command":"stop"}
```

Read stdout lines prefixed `OPTICAL_RESPONSE ` as JSON. Events: `ready`, `captured`,
`status`, `stopping`, `finished`. Ignore other SDK diagnostic lines. `captured`
acknowledges a completed save and CSV/metadata update; `finished` follows cleanup.
A capture triggers one new exposure, waits for its image, saves it, then replies.
Commands run sequentially. Malformed/unknown commands fail and close the worker.
No automatic retry/deduplication exists: do not retry a capture after an ambiguous
connection failure. Closing stdin or SIGTERM closes the worker.

`serve` uses fixed manual exposure/gain, so auto-exposure settling isn't hidden in
the time between an external request and the picture. Per-frame exposure/gain
chunks are not enabled; the metadata records configured values.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use fake images/cameras for configuration rejection, trigger ordering,
resource cleanup, incomplete frames, save failure and sequence bookkeeping. Native
SDK triggering and sequence throughput still require testing on the connected
camera. Importing/discovering/saving a basic image in the earlier bootstrap image
was tested on the user's Linux host; the new acquisition interface must be tested.
