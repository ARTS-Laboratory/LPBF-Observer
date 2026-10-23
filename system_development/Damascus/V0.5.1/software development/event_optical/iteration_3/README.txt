Extract run_reconstruction_windows.py into iteration_3/event_camera/.

Start Docker Desktop. In VS Code open the script, change FILE_NUMBER, save,
and select Run Python File (the Play button). Any Windows Python 3.12 works;
the launcher itself uses only the standard library.

Set LIST_ONLY = True and press Play to see the recording numbers without
reconstructing. Then set it back to False and select FILE_NUMBER. Numbers
are sorted by path and may change as recordings are added. INPUT_FILE can
select a recording permanently by full path instead of number.

Search locations:
  iteration_3/event_camera/data/recordings
  ~/lpbf-data/event_camera/recordings (includes nested paired sessions)

Output: ~/lpbf-data/reconstructions
Config: iteration_3/event_camera/config/reconstruction.toml
START_S, END_S and WINDOW_US optionally override the config.

This launches the previously tested Docker image lpbf-event-optical:0.1.
It does not require Compose environment variables, Arena SDK mounts, cameras,
or the native OpenEB Python environment. Existing camera launchers are unchanged.
The input session and config are read-only mounts. Output is a separate mount.

Validation: launcher selection, mounts and process invocation checked locally
with temporary recordings and a simulated Docker command. Actual Windows
Docker execution must be confirmed on the laptop.
