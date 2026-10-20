# Independent camera components and coordinated experiments

Layout:

```
iteration_3/
  optical_camera/        # Spinnaker image capture; independent CLI/worker
  event_camera/          # Existing OpenEB RAW recorder and offline tools
  coordinator/           # Experiment sequencing only; host Python standard library
  compose.yaml           # Two independent Linux camera containers
  data/runs/             # Experiment manifests linking component outputs
```

The event recorder is unchanged by this update. Its acquisition CLI writes RAW,
metadata and telemetry; reconstruction and analysis remain separate commands.
Neither camera component imports the other or contains welding policy.
Compose describes runtime mounts/networking. The coordinator implements the policy.
It runs on the host and invokes Docker Compose; neither camera container needs
the Docker socket. This avoids giving camera code control of the container engine.

## Install the update

Extract `camera-acquisition-update.zip` from **iteration_3**, not from inside either
component. Keep the SDK archives already in `optical_camera/vendor/`. Existing
optical data is preserved, but the optical source/config files in this update
replace their previous versions; preserve personal configuration edits first.
The update does not move or change event-camera files.

```bash
cd "/home/thienan/Documents/GitHub/LPBF-Observer/system_development/Damascus/V0.5.1/software development/event_optical/iteration_3"
unzip -o "$HOME/Downloads/camera-acquisition-update.zip" -d .

sudo bash optical_camera/docker/run.sh build --build-arg ACCEPT_SPINNAKER_EULA=true
sudo bash optical_camera/docker/run.sh single --name trigger-test
```

Check the new single image and its metadata before coordinating a weld experiment.
A successful bootstrap capture did not test software triggering. If trigger setup,
manual settings or readbacks fail, report the output before attempting a weld.

## Event recording followed by one optical picture

Requirements: the existing `lpbf-event-optical:0.1` image, new `lpbf-optical:0.2`
image, Docker Compose v2, working host network/firewall rules for both cameras,
and Linux Arena SDK. Existing event settings must be at
`event_camera/config/recorder.toml`; optical settings are at
`optical_camera/config/camera.toml`.

```bash
sudo docker compose version

# From iteration_3; automatic Arena default uses the invoking user's home under sudo.
sudo python3 coordinator/run_experiment.py --name paired-test --duration 5
```

If Arena is installed elsewhere:

```bash
sudo env ARENA_ROOT="$HOME/opt/arena/ArenaSDK_Linux_x64" \
    python3 coordinator/run_experiment.py --name paired-test --duration 5
```

Override the event serial using `--event-serial "Integrator:plugin:serial"`.
Edit the optical serial in its TOML. Image tags can be overridden using
`OPTICAL_DOCKER_IMAGE` / `EVENT_DOCKER_IMAGE`; pass them explicitly through sudo.

Sequence:

1. Open/configure/arm the optical worker and wait for readiness.
2. Start the event recorder for the requested duration.
3. Wait for its process to exit, then verify success state and completed RAW output.
4. Request exactly one new optical exposure and await the saved-image response.
5. Close the optical worker and finalize the experiment manifest.

One Ctrl+C during event recording asks Docker to terminate that recorder gracefully.
If it exits cleanly with finalized metadata, the photo is still taken. A failed
recorder, invalid event metadata, optical failure, timeout or cleanup failure marks
the experiment as error. No retry silently takes a second photo. Hardware failures
can leave partially complete sessions, which are retained for inspection.

The photo occurs after recorder shutdown, RAW draining and file closure. This is
software coordination, not measured weld-end detection or hardware synchronization.
Container/process shutdown and file operations add latency; timestamps are retained
for assessment. A later laser/PLC signal can be implemented in the coordinator
without adding weld-specific logic to either camera component.

Output locations:

- `event_camera/data/recordings/<run-id>/<event-session>/events.raw`
- `optical_camera/data/recordings/<run-id>/<optical-session>/images/frame-00000000.png`
- `data/runs/<run-id>/manifest.json`: relative metadata links, response, exit state,
  event completion UTC and optical request UTC.

Container paths `/data/...` in optical responses refer to optical_camera/data;
use the manifest's relative metadata path to locate outputs on the host.
On sudo runs, newly created directories/files are assigned to the invoking UID/GID.
No existing data tree is recursively chowned. Host component directories should
already be writable by that user.

## Separate operation

From optical_camera, use `bash docker/run.sh single` or `sequence`; the event
camera and coordinator are not needed. From event_camera, retain existing recorder
commands. Generic start is CLI launch, stop is SIGINT/SIGTERM, final status is
exit code plus session metadata. Optical `serve` additionally supports explicit
capture/status/stop JSON commands while staying armed. There is no event API server
in this update; Compose runs its existing CLI unchanged.

Compose services can also be run manually with RUN_UID, RUN_GID and ARENA_ROOT
explicitly set, but the coordinator supplies these automatically.

## Validation and scope

```bash
python3 -m unittest discover -s optical_camera/tests -v
python3 -m unittest discover -s tests_coord -v
```

Camera-free tests cover successful event-then-photo ordering and skipping the photo
after event failure, response IDs/EOF, bad settings, image-release paths and output
accounting. No Docker daemon or physical camera was available to the code author;
new native triggering, Compose execution and combined capture must be verified on
the user's machine. Continuous full-resolution PNG throughput is not yet measured.
Windows live GigE capture is not validated. Source/config only are in this update;
SDK archives, images and recordings are excluded from Git.
