 # Iteration 19



## Optical Camera Acquisition Benchmarks

For each VI, measure the sustained acquisition rate under the following conditions:

1. **Acquisition only:** Capture frames without displaying or saving.
2. **PNG saving:** Capture frames and save each frame as a PNG, without displaying.
3. **Binary saving:** Capture frames and write the raw pixel data directly to a binary file, without displaying.

| VI | Acquisition only (FPS) | PNG saving (FPS) | Binary saving (FPS) |
|---|---|---|---|
| NI-IMAQdx Snap | 5 | 1 | 5 |
| NI-IMAQdx Grab | 16.67 | 2 | 16.67 |
| NI-IMAQdx Low-Level Get Image | TBD | 2 | TBD |
| NI-IMAQdx Low-Level Get Image Data| TBD | N/A | TBD |
