NPZ Thermal Image Processing :

This utility exports timestamped thermal PNG images, from the `.npz` recordings created by the LabVIEW/Python acquisition system.


Usage :

Keep `npzProcessing.py` and `functionFIles.py` in the same directory.
Confirm that `INPUT_PATH` in `npzProcessing.py` points to the recording
folder containing the `.npz` files.
Configure `EXPORT_INTERVAL_S`:
`None`: export every thermal frame. Use this for new recordings because
the acquisition code has already captured those frames at the interval
selected in LabVIEW.
`5.0`: export the recorded frame nearest to 0, 5, 10, 15, ... seconds.
The export interval cannot be shorter than the original capture interval.
Run:
```powershell
   python npzProcessing.py
   ```

Output:

Each NPZ receives its own folder under `Images`. The folder contains:
numbered, timestamped `.png` thermal images;
`image_index.csv`, containing the target time, actual capture time, timing
error, source-frame index, and temperature statistics for every PNG.
The same temperature color scale is used for every image from one NPZ. To use
an identical scale across multiple experiments, set `TEMPERATURE_MIN_C` and
`TEMPERATURE_MAX_C` to fixed values in `npzProcessing.py`.
If `SAVE_HOTTEST_FRAME_CSV` is enabled, the raw temperature matrix for the
hottest exported frame is also written to the `CSV` directory.
This workflow does not create MP4 or other video files.
