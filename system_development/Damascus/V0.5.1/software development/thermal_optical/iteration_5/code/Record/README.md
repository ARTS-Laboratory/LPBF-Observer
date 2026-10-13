# Record

LabVIEW interface for operating Optris thermal cameras and recording thermal image data.

## Requirements

Before using the software:

1. Install the Optris OTC SDK.
2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

### Python Dependencies

The following Python packages are required:

* `numpy`
* `opencv-python`

> **Note:** The Optris OTC SDK is not installed through `pip` and must be installed separately.

## Current Features

* Live thermal image streaming to LabVIEW
* Thermal recording to compressed `.npz` files
* Camera focus control
* Flag event triggering
* Thermal video streaming over a dedicated socket connection

## Usage

1. Open `thermalCamera.vi`.
2. Run the VI.
3. Wait for the terminal to indicate that camera calibration has completed and temperature measurements are reliable.
4. Press **Record** to begin recording thermal data.

## Recording Format

Recordings are saved as compressed `.npz` files containing:

* `frames` — thermal image data stored as `float32` temperature values.
* `frame_timestamps_ns` — per-frame timestamps.
* `timestamp` — recording save time.

## Notes

> For best temperature accuracy, trigger a **Flag** event before recording.

Camera preview and recording are controlled through a Python server running in the background and communicating with LabVIEW through TCP socket connections.
