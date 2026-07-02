# Triton2 EVS Python Display Starter

This is a first milestone project:

```text
Triton2 EVS -> Arena Python -> OpenCV display window
```

No LabVIEW TCP is included yet. Once this displays reliably, the display step can be replaced or duplicated with a TCP sender.

## Files

```text
evs_functions.py    # reusable camera/helper functions
main_display.py     # main script that calls the functions
```

## Install / environment

Use the Python environment installed with ArenaView JupyterLab, or install the Arena Python wheel from the Arena SDK install directory into your own Python environment.

Then install:

```bash
pip install numpy opencv-python
```

## Run

```bash
python main_display.py
```

Optional:

```bash
python main_display.py --serial YOUR_CAMERA_SERIAL
python main_display.py --buffers 30
python main_display.py --accumulation-us 5000
python main_display.py --frame-rate 60
```

Press `q` or `Esc` to close the OpenCV window.

## Notes for the Triton2 EVS

The Triton2 EVS is an event camera. It does not make normal exposure-based frames. For first display, you want CD frames, which are accumulated event images. If the script says the buffer looks like raw event data, then Python is receiving EVT/event buffers rather than displayable CD frames.

If that happens, open ArenaView, confirm you can display CD frames there, then check the exact EVS/CD-frame GenICam node names used by your SDK/firmware version. Update the candidate node names in `configure_for_display()` if needed.

## Development order

1. Run ArenaView and confirm the camera displays CD frames.
2. Close ArenaView so Python has read-write camera access.
3. Run `python main_display.py`.
4. Move a high-contrast object in front of the camera. A stationary scene may show little or no event activity.
5. Once OpenCV display works, add TCP output as the next milestone.
