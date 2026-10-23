# Event and optical camera acquisition setup

Camera lens settings: `aperture: F2, focus: purple indicator ~5 mm past infinity mark (35mm/F1.8 Edmunds Optics Lens)` 

Record LUCID event-camera data as a native RAW file, then take one fresh FLIR
optical image after that recording closes. Both cameras run in separate Docker
containers. The camera components also work independently: event recording,
single optical images, or continuous optical image sequences.

**Validated on EndeavourOS / Arch Linux with Docker Engine.** Two paired runs
completed successfully, and the event reconstruction and optical image were
visually checked. Windows live camera acquisition remains unvalidated.

## Daily use: record events, then take the optical picture

After completing installation below, connect and power both cameras, verify the
Ethernet connection, and run from `iteration_3`:

```bash
sudo python3 coordinator/run_experiment.py --name sample-001 --duration 5
```

The optical camera is initialized and armed first. The event camera then records
for five seconds. After the event recorder exits cleanly and its RAW file closes,
the coordinator requests one software-triggered optical exposure. A unique run
folder prevents previous recordings from being overwritten.

Success ends with `State: complete`. The manifest under `data/runs/` links the
recording and photo. A single Ctrl+C **during event recording** requests a graceful
stop; a clean stop is still followed by the optical picture.

## Project layout

| Path | Purpose |
| --- | --- |
| `event_camera/` | Existing RAW recorder, settings, telemetry and offline analysis/reconstruction tools |
| `optical_camera/` | Independent Spinnaker image capture, settings, metadata and per-frame telemetry |
| `coordinator/run_experiment.py` | Experiment policy: event recording followed by an optical capture |
| `compose.yaml` | Separate event and optical container definitions and mounts |
| `data/runs/` | Manifests connecting the two components' output sessions |
| `ACQUISITION_GUIDE.md` | More detail about coordination, the command worker and failure behavior |

Neither camera component depends on the other or implements welding logic.
Compose configures the containers; the host-side coordinator sequences them.
The coordinator uses Python's standard library and Docker CLI. Camera containers
are not given the Docker socket.

## Starter Python files for Visual Studio

The project includes small launcher scripts for the common development workflow.
Open the script in Visual Studio, edit the variables at the top, and press Run.
These launchers are intentionally thin wrappers around the tested shell/Docker
commands, so the production acquisition and reconstruction code remains in the
camera components.

| File | Edit these variables | Result |
| --- | --- | --- |
| `event_camera/scripts/record_file.py` | `NAME`, `DURATION_SECONDS` | Records only the event camera |
| `event_camera/scripts/reconstruct_file.py` | `FILE_NUMBER` | Reconstructs the selected RAW recording |
| `coordinator/run_paired.py` | `NAME`, `DURATION_SECONDS` | Records the event camera, then captures one post-recording optical image |

Run the event-only launcher from the project root:

```bash
python event_camera/scripts/record_file.py
```

Run the reconstruction launcher after changing `FILE_NUMBER`:

```bash
python event_camera/scripts/reconstruct_file.py
```

Run the paired event-plus-optical launcher:

```bash
python coordinator/run_paired.py
```

The paired launcher requires Docker access and both cameras to be discoverable.
The event-only launcher does not start or require the optical camera. The paired
run writes one manifest linking the event RAW file, telemetry, and optical image.

## Tested cameras and software

| Component | Tested value |
| --- | --- |
| Event camera | LUCID Triton TRT009S-E, serial `250200198`, 1280 Ã— 720, EVT3 |
| Optical camera | FLIR Blackfly S BFS-PGE-200S6M, serial `19328838`, 5472 Ã— 3648 |
| Ethernet adapter | OWC Thunderbolt 10G adapter, Aquantia AQC113, Linux `atlantic` driver |
| Arena SDK | Linux x64 `1.0.10.11` |
| Event runtime | Patched OpenEB `5.2.0`, Python 3.12, NumPy 1.26.4 |
| Spinnaker / PySpin | Matching Linux x64 SDK and cp312 wheel, `4.4.0.246` |
| Optical runtime | Ubuntu 24.04, Python 3.12; NumPy 2.5.4 in the tested build |
| Event image tag | `lpbf-event-optical:0.1` |
| Optical image tag | `lpbf-optical:0.2` |

Serial numbers, MAC addresses, interface names and IP addresses below describe the
tested workstation. Substitute your hardware's values on another computer.

## 1. Install host tools

The tested Linux workflow uses Docker Engine, Docker Buildx, Docker Compose,
Python 3.11 or newer, Git, Bash, tar/gzip and unzip. Python 3.12 and vendor runtime
libraries are installed **inside the images**. A host Python virtual environment,
PySpin installation, OpenEB build, and system OpenCV installation are not required
for Docker operation.

On EndeavourOS / Arch:

```bash
sudo pacman -Syu --needed docker docker-buildx docker-compose git python unzip
sudo systemctl enable --now docker.service

sudo docker info
sudo docker buildx version
sudo docker compose version
```

These instructions use `sudo` consistently for Docker access. The wrappers and
coordinator use the invoking user's UID/GID for container output ownership.
For another Linux distribution, install Docker Engine and its Compose/Buildx
plugins using that distribution's supported instructions.

Clone or update the LPBF-Observer repository, then select this setup directory.
On the development workstation:

```bash
export PROJECT_ROOT="/home/thienan/Documents/GitHub/LPBF-Observer/system_development/Damascus/V0.5.1/software development/event_optical/iteration_3"
cd "$PROJECT_ROOT"
```

Use quoted paths: the repository path contains a space. Confirm that both
`event_camera/docker/run.sh` and `optical_camera/docker/run.sh` exist before building.
If migrating from the older single-directory layout, retain the existing event
project files and their own `.gitignore` together under `event_camera/`.

## 2. Download and prepare the SDKs

Download vendor packages separately; they are not included in Git.

- [LUCID Arena SDK downloads](https://thinklucid.com/downloads-hub/): tested
  archive `ArenaSDK_v_1.0.10.11_Linux_x64.tar.gz`.
- [Teledyne Spinnaker downloads](https://www.teledynevisionsolutions.com/products/spinnaker-sdk/):
  SDK `spinnaker-4.4.0.246-noble-amd64-pkg.tar.gz` and Python wrapper
  `spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.tar.gz`.

Choose Linux Ubuntu 24.04 / amd64 packages for these containers even when the host
is Arch. PySpin and Spinnaker versions must match, and the wheel must target
Python 3.12 (`cp312`). Different SDK versions require compatibility testing.

Check that downloads are complete:

```bash
gzip -t "$HOME/Downloads/ArenaSDK_v_1.0.10.11_Linux_x64.tar.gz"
gzip -t "$HOME/Downloads/spinnaker-4.4.0.246-noble-amd64-pkg.tar.gz"
gzip -t "$HOME/Downloads/spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.tar.gz"
```

No output means the gzip integrity check passed. A zero-byte archive or
`unexpected end of file` means the download is incomplete. Let the browser finish
or resume the download; its `.part` file is not the completed archive.

Extract Arena to a host folder that is mounted read-only by the event container:

```bash
mkdir -p "$HOME/opt/arena"
tar -xzf "$HOME/Downloads/ArenaSDK_v_1.0.10.11_Linux_x64.tar.gz" \
    -C "$HOME/opt/arena"

export ARENA_ROOT="$HOME/opt/arena/ArenaSDK_Linux_x64"
```

The expected SDK directories include `lib64`,
`GenICam/library/lib/Linux64_x64`, `Metavision/lib` and `Metavision/hal_plugin`.
Do not run its Ubuntu installation script on Arch. Host linker changes are not
needed for this Docker workflow.

From `iteration_3`, copy the Spinnaker archives into the optical build context:

```bash
mkdir -p optical_camera/vendor

cp -n \
    "$HOME/Downloads/spinnaker-4.4.0.246-noble-amd64-pkg.tar.gz" \
    "$HOME/Downloads/spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.tar.gz" \
    optical_camera/vendor/
```

`cp -n` preserves existing files; if a destination archive is an old incomplete
copy, replace that specific file with the completed download. `vendor/` is ignored
by Git. Native Spinnaker packages and the wheel are installed in the optical image.

## 3. Connect and configure Ethernet

Both GigE cameras need an Ethernet path to the workstation and appropriate power
(for example, a suitable powered PoE switch/injector). A USB/Thunderbolt adapter
being present does not itself establish camera power or connectivity.

On the tested workstation, NetworkManager manages the adapter:

```bash
ip -br link
nmcli device status
```

The reference interface is `enp3s0`, with adapter MAC `00:23:a4:0d:49:31`.
Create the profile below **only if `event-camera` does not already exist**:

```bash
sudo nmcli connection add \
    type ethernet \
    ifname enp3s0 \
    con-name event-camera \
    ipv4.method link-local \
    ipv4.never-default yes \
    ipv6.method disabled
```

Configure automatic reconnection by adapter MAC, allowing the interface name to
change after reconnecting:

```bash
sudo nmcli connection modify event-camera \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    connection.autoconnect-retries 0 \
    connection.interface-name "" \
    802-3-ethernet.mac-address "00:23:a4:0d:49:31"

sudo nmcli connection up event-camera
ip -br address show enp3s0
```

The tested host receives `169.254.218.157/16`. Its Wi-Fi remains the default
Internet route. The cameras also use link-local IPv4 on this setup:

| Device | Reference IP |
| --- | --- |
| Host Ethernet | `169.254.218.157` |
| LUCID event camera | `169.254.59.67` |
| FLIR optical camera | `169.254.71.239` |

Link-local addresses can change. Inspect the actual addresses before applying
address-specific firewall rules. A camera previously configured with a persistent
address outside this subnet needs separate IP configuration.

### Firewalld on the tested workstation

Discovery initially found no cameras until incoming UDP replies were allowed.
Check the interface zone:

```bash
sudo firewall-cmd --get-zone-of-interface=enp3s0
```

For the reference host, this is `public`. A temporary discovery rule is:

```bash
sudo firewall-cmd --zone=public \
    --add-rich-rule='rule family="ipv4" source address="169.254.0.0/16" destination address="169.254.218.157" protocol value="udp" accept' \
    --timeout=300
```

Once the camera IPs are known, use camera-specific runtime and permanent rules:

```bash
for camera_ip in 169.254.59.67 169.254.71.239; do
    camera_rule="rule family=\"ipv4\" source address=\"$camera_ip\" destination address=\"169.254.218.157\" protocol value=\"udp\" accept"
    sudo firewall-cmd --zone=public --add-rich-rule="$camera_rule"
    sudo firewall-cmd --permanent --zone=public --add-rich-rule="$camera_rule"
done
```

Use your actual zone and addresses. These commands are specific to a firewalld
host; they are not an instruction to install or replace another firewall.

### UDP receive buffers

Arena's Linux README recommends 32 MiB receive-buffer defaults/limits. Inspect
current values before high-rate tests:

```bash
sysctl net.core.rmem_default net.core.rmem_max
```

To use those values persistently on this Linux host:

```bash
sudo tee /etc/sysctl.d/90-event-camera-buffers.conf >/dev/null <<'SYSCTL'
net.core.rmem_default=33554432
net.core.rmem_max=33554432
SYSCTL

sudo sysctl -p /etc/sysctl.d/90-event-camera-buffers.conf
```

These are host kernel settings; the SDK also controls its socket buffering.
Larger limits do not prove loss-free acquisition. The tested Ethernet MTU is 1500;
jumbo frames are not required by these instructions.

## 4. Build the images

From `iteration_3`:

```bash
sudo bash event_camera/docker/run.sh build

# Review and accept the vendor EULA before using the acceptance argument.
sudo bash optical_camera/docker/run.sh build \
    --build-arg ACCEPT_SPINNAKER_EULA=true
```

The event build compiles OpenEB inside Ubuntu, applies the EVT3 decoder boundary
fix, and runs unit/native decoder regression checks. Keep that patch in the build:
it resolved chunk-boundary warnings and inconsistent decoding of the same RAW data.

The optical build installs the matching native runtime and Python wrapper, checks
imports, runs camera-free tests, and makes the SDK cache writable for the runtime
user. SDK license acceptance is explicit. Optional Spinnaker analytics are disabled
for the configured runtime HOME.

Compilation is performed inside Docker. The vendor SDKs are binary packages, not
compiled from source by this project. Source-code changes require rebuilding the
corresponding image. Mounted TOML setting changes do not require a rebuild.

Installed dependency manifests are saved in `/opt/build-info` in each image.
Some base/dependency selections are not fully locked, so rebuilding later is not
guaranteed to reproduce byte-identical images.

## 5. Check each camera independently

```bash
sudo bash event_camera/docker/run.sh check
sudo bash optical_camera/docker/run.sh --check

sudo bash event_camera/docker/run.sh record --list
sudo bash optical_camera/docker/run.sh --list
```

Expected reference identifiers:

- Event: `Lucid Vision Labs:lucid_imx63x_plugin5:250200198`
- Optical serial: `19328838`

FLIR discovery may show `OpenReadOnly` before initialization. That value alone did
not prevent initialization, changing settings or acquiring images on this setup.

### Optical settings and first image

Edit `optical_camera/config/camera.toml`:

```toml
serial = "19328838"
exposure_us = 1010.0
gain_db = 0.0
pixel_format = "Mono8"
timeout_ms = 10000
# frame_rate_hz = 1.0
```

The reference camera read back **1010 Âµs** when 1000 Âµs was requested. Requesting
1010 Âµs passed the strict readback check. Use 1010.0 for this tested setup; this
is not a universal exposure recommendation. If an older supplied config still
contains 1000.0, change it before running.

Exposure/gain auto modes are turned off by the capture component. Requested manual
settings must be supported and read back correctly. Configuration failure prevents
acquisition, but earlier setting changes may remain on the camera.

```bash
sudo bash optical_camera/docker/run.sh single --name optical-check
```

Open the saved PNG under `optical_camera/data/recordings/` and check brightness,
focus and field of view. A single capture uses a fresh software-triggered exposure.
It does not return a frame captured earlier while the camera was waiting.

### Event settings and standalone recording

Edit `event_camera/config/recorder.toml` for bias/ERC and telemetry settings.
Omitted camera settings are left unchanged. Use camera-reported bias ranges;
integer bias offsets are not physical exposure times or frequencies.

Keep `telemetry.decode_events = false` for the established high-rate capture path.
Decoding in the recording loop showed a substantial throughput penalty in testing.
Use offline analysis for decoded event counts/rates.

```bash
sudo bash event_camera/docker/run.sh record \
    --config /settings/recorder.toml \
    --serial "Lucid Vision Labs:lucid_imx63x_plugin5:250200198" \
    --name event-check \
    --duration 5
```

The recorder creates native `events.raw`, `metadata.json` and
`stream_telemetry.csv` in a unique session under `event_camera/data/recordings/`.
Omit duration for standalone recording until Ctrl+C. The normal final state is
`capture_stopped`; errors or cleanup failures must be investigated.

## 6. Run the paired experiment

Check Compose, then launch the coordinator from `iteration_3`:

```bash
sudo docker compose version

sudo python3 coordinator/run_experiment.py \
    --name sample-001 \
    --duration 5
```

The coordinator resolves Arena under the invoking user's home, including under
sudo. For another SDK location, pass it explicitly:

```bash
sudo env ARENA_ROOT="$HOME/opt/arena/ArenaSDK_Linux_x64" \
    python3 coordinator/run_experiment.py --name sample-001 --duration 5
```

Use `--event-serial` to select another event camera. Select the optical camera in
its TOML. Use descriptive run names; each run also gets a timestamp and unique ID.

Sequence and completion rules:

1. Initialize/configure/arm the optical camera and wait for readiness.
2. Start event recording for the requested duration.
3. Wait for event shutdown, RAW draining/closure, a successful exit and clean metadata.
4. Trigger exactly one new optical image, then wait for its save acknowledgement.
5. Shut down the optical worker and write the final run manifest.

A failed event capture skips the optical request. An optical failure marks the
combined experiment as error while retaining the event recording. Requests are
not automatically retried after ambiguous failures.

This is software sequencing, not laser/PLC weld-end detection or hardware timing
synchronization. In one validated run, the host optical trigger command occurred
149 ms after event RAW finalization. That is one measurement, not a latency
specification, and it excludes sensor trigger-to-exposure delay.

## 7. Find the output

| Output | Host path relative to `iteration_3` |
| --- | --- |
| Run manifest | `data/runs/<run-id>/manifest.json` |
| Event RAW | `event_camera/data/recordings/<run-id>/<event-session>/events.raw` |
| Event metadata/telemetry | Beside the RAW file |
| Optical image | `optical_camera/data/recordings/<run-id>/<optical-session>/images/frame-00000000.png` |
| Optical metadata and frame CSV | In the optical session folder |
| Reconstruction output | `event_camera/data/reconstructions/` |
| Event analysis | `event_camera/data/analysis/` |

Container `/data` means the relevant component's host `data/` directory. It is not
the repository's shared `iteration_3/data/` folder.

The manifest has relative `event_metadata` and `optical_metadata` links. The
`optical_capture.frame.filename` value is relative to the optical session.
Every saved optical frame has camera timestamp, host receive UTC, trigger command
UTC when applicable, frame ID, dimensions, pixel format, save time and file size.
Camera timestamps and host UTC are different clocks; they are not automatically
synchronized. Unavailable SDK counters are null rather than zero.

## 8. Reconstruct and analyze the event recording

Use the run's manifest to find the exact RAW path. For the validated retest:

```bash
sudo bash event_camera/docker/run.sh reconstruct \
    /data/recordings/paired-retest-20261020T181742-036bcada/events-20261020T181747.112371Z-142f7d84/events.raw \
    --config /settings/reconstruction.toml
```

Replace that example path with your own session. Reconstruction supports:

- Accumulation window in microseconds; consecutive windows without a separate step.
- Binary, count linear, count log, signed linear and signed log images.
- Start/end selection in seconds relative to the first CD event.
- A curated H5 containing selected events and retained metadata.

For a one-second selected section, add `--start-s 1 --end-s 2`. Configure window
and modes in `event_camera/config/reconstruction.toml`. The selection start is
inclusive and end is exclusive; the final partial window is clipped appropriately.

Analyze event counts/rates separately from recording:

```bash
sudo bash event_camera/docker/run.sh analyze \
    /data/recordings/paired-retest-20261020T181742-036bcada/events-20261020T181747.112371Z-142f7d84/events.raw \
    --bin-us 250000 \
    --plot
```

This produces summary JSON, rate CSV and an optional plot. Sensor event-span time
and host recording duration are reported separately. Smooth images and zero
reported network errors do not by themselves establish loss-free capture.

## 9. Optical-only continuous image sequences

The optical component can save a sequence without the event camera or coordinator:

```bash
sudo bash optical_camera/docker/run.sh sequence --name optical-sequence --duration 5

# Or stop after ten successfully saved frames:
sudo bash optical_camera/docker/run.sh sequence --name ten-images --frames 10
```

No video is encoded. Every returned complete image is saved as a numbered PNG with
a CSV record. At full resolution, PNG encoding/disk writes can limit throughput;
the first triggered-image test took about 3.17 seconds to save its PNG. Continuous
throughput has not yet been measured. Frame-ID gaps and exposed SDK counters help
identify problems, but do not provide a complete loss estimate.

The generic `serve` mode supports capture/status/stop JSON commands over stdin and
stdout for other coordinators. See [optical_camera/README.md](optical_camera/README.md)
for its protocol. The post-weld policy is not part of this optical worker.

## 10. Troubleshooting

### Ethernet profile disappears after a Thunderbolt reconnect

A saved profile cannot activate if Linux has not enumerated its Ethernet hardware.
Inspect:

```bash
boltctl list
sudo lspci -nnk | rg -A4 -i 'ethernet|aquantia|marvell'
ip -br link
```

The adapter may be USB4-authorized while the Aquantia PCI device is absent.
A PCI rescan recovered it during testing:

```bash
echo 1 | sudo tee /sys/bus/pci/rescan
nmcli device status
```

Allow time for the Ethernet link and NetworkManager autoconnection. If a rescan
does not help, fully disconnect the adapter from the laptop and external power,
wait roughly 15 seconds, then reconnect directly to a USB4/Thunderbolt port.
Inspect recent kernel messages if it remains absent:

```bash
sudo journalctl -k -b --since "5 minutes ago" --no-pager |
    rg -i 'thunderbolt|usb4|atlantic|aquantia|pcie|aer|timeout|failed'
```

This is a recovery procedure, not a permanent fix for the intermittent enumeration
issue. Do not delete/recreate the saved network profile every time this occurs.

The interface name may change after reconnecting. It has appeared as both
`enp3s0` and `eth0` on the tested workstation. Always use the name currently
shown by `ip -br link`; do not assume the old name:

```bash
ip -br link
nmcli device status
```

If the interface is present but disconnected, activate the saved profile with
the current name:

```bash
sudo nmcli connection up event-camera ifname <current-interface>
```

If the interface is missing but `boltctl` still reports the adapter as authorized,
check PCIe enumeration and reload the driver:

```bash
echo 1 | sudo tee /sys/bus/pci/rescan
sudo modprobe atlantic
sudo lspci -nnk | rg -A4 -i 'ethernet|aquantia|marvell'
ip -br link
```

If the Aquantia device is still absent, fully disconnect the Thunderbolt adapter,
wait about 15 seconds, reconnect it, and rescan again. A reboot may be required
after a failed USB4/PCIe re-enumeration. `boltctl` showing `authorized` alone does
not guarantee that Linux created the Ethernet interface.

After the interface and link-local address return, reapply the discovery rule and
test both wrappers:

```bash
HOST_IP=$(ip -4 -o addr show <current-interface> | awk '{split($4,a,"/"); print a[1]}')

sudo firewall-cmd --zone=public \
    --add-rich-rule="rule family=\"ipv4\" source address=\"169.254.0.0/16\" destination address=\"$HOST_IP\" protocol value=\"udp\" accept" \
    --timeout=300

sudo bash optical_camera/docker/run.sh --list
sudo bash event_camera/docker/run.sh record --list
```

The event wrapper's list syntax includes the `record` subcommand. If optical
discovery succeeds but event discovery logs an access-denied warning naming the
FLIR camera, this is usually the LUCID HAL probing a camera already owned by
Spinnaker; use the explicit event serial for recording.

### SDK imports work but no cameras are discovered

Check the physical link, camera power, host/camera subnets and firewalld zone/rules.
The tested setup required UDP rules for both cameras. An old host or camera
link-local IP makes an address-specific rule ineffective.

### LUCID discovery reports access denied for the FLIR camera

In paired runs, LUCID discovery attempted to open the already-owned FLIR device
and logged an access error naming `Blackfly S BFS-PGE-200S6M`. The selected LUCID
camera then opened, recorded and closed normally; both paired runs completed.
Check the named device and final states rather than treating every access-denied
message as an event-camera failure. Do not suppress unrelated discovery failures.

### Spinnaker cache permission error

`Permission denied: /tmp/.config/spinnaker/xml` means the runtime UID could not
create the SDK cache. Use the updated optical Dockerfile and rebuild; its cache
permission fix is container-local. Running the camera as root is not required.

### Exposure readback mismatch

The reference camera required `exposure_us = 1010.0` for the verified test.
Do not disable all readback checks to conceal a mismatch. If another value is
needed, inspect the camera's supported range and actual returned value.

### Missing libraries while building the optical image

The corrected Dockerfile includes `spinupdate` and FFmpeg/OpenMP runtimes required
by this PySpin wheel. Errors previously encountered included `libSpinUpdate.so.4`,
`libgomp.so.1` and `libswscale.so.7`. Rebuild from the corrected Dockerfile rather
than installing Ubuntu runtime packages on Arch.

### GenTL/HAL import or shutdown problems

Use the event wrapper/container entrypoint so the required SDK paths, global HAL
import handling and `libgentl.so.1` preload are applied. Loading the vendor stack
manually previously caused undefined symbols and a Boost mutex exception at exit.
The tested container recording path exits cleanly. Do not replace cleanup with
`os._exit()` to hide an SDK failure.

### Optical image is dark

The optical acquisition component uses fixed manual settings rather than automatic
exposure/gain. Tune its TOML for the post-weld illumination and inspect a standalone
image before collecting a test series. Settings apply before capture and are saved
in metadata; configuring the camera is not an optical calibration.

## 11. Tests and version control

Camera-free checks:

```bash
python3 -m unittest discover -s optical_camera/tests -v
python3 -m unittest discover -s tests_coord -v

sudo bash event_camera/docker/run.sh test
sudo bash optical_camera/docker/run.sh test
```

The new optical/coordinator tests passed (15 tests). The optical image build also
runs its tests. Native software-triggered capture and two coordinated runs were
then validated on the connected cameras. Continuous optical sequence throughput,
long weld-series reliability and Windows live acquisition need separate testing.

Keep source, TOML configuration, Compose, tests and documentation in Git. Exclude
SDK archives, native SDK copies, virtual environments, build folders, core dumps,
recordings and generated images. Component `.gitignore` files must remain with
those components after reorganizing directories.

Before committing from `iteration_3`, inspect:

```bash
git status --short
git diff --cached --stat
git diff --cached --name-only
```

## Windows status

A Windows school laptop will need IT assistance for Docker Desktop and required
WSL2/virtualization setup. Linux SDK tarballs and OpenEB compilation can be handled
inside Linux containers; a separate Windows SDK installation is not needed for
this container design.

However, live GigE discovery/streaming through Docker Desktop has **not** been
validated. Desktop host networking differs from native Linux host networking;
do not assume this Linux procedure can be copied directly to Windows. The current
coordinator also uses Linux-specific account/UID handling. Offline image processing
and a Windows controller/network path require their own validation.

References:

- [Docker on Arch Linux](https://wiki.archlinux.org/title/Docker)
- [Docker Desktop installation on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker host networking](https://docs.docker.com/engine/network/drivers/host/)
- [Spinnaker Python guide](https://softwareservices.flir.com/Spinnaker/4.4/guides/python-programmer-guide.html)
- [LUCID Arena SDK](https://thinklucid.com/arena-software-development-kit/)
