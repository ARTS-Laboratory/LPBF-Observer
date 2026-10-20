# Event Optical Docker workflow

Run commands from the `iteration_3` directory. Existing local Python and SDK installations are not replaced. The image builds a separate Python 3.12/OpenEB environment.

## What this packages

- Ubuntu 24.04 x86_64, Python 3.12, NumPy 1.26.4, pybind11 2.13.6, Python OpenCV, h5py, and Matplotlib.
- OpenEB 5.2.0 at commit `9003b5416676e78ba994d912087486cfa94fae73`, built from source with the project's EVT3 boundary patch and C++ compatibility flags.
- Native RAW recorder, camera settings/read-back, host telemetry, offline event analysis, PNG reconstruction and curated H5 export.
- Unit tests and actual native boundary fixture tests run during image build; any failure aborts the build.

The original OpenEB source/build tree and compiler are retained in this initial image for diagnostics. The image will be sizable and the first build can take a while. Do not copy Arch `.so` files or the host virtual environment into the container. Ubuntu supplies its own C++ OpenCV/Boost/HDF5 libraries; the build-info directory records the installed package versions.

Offline tools need no LUCID SDK. Live recording mounts the extracted **Linux x64** Arena SDK read-only at `/sdk/arena`; it is not included in the image. This version expects the tested `liblucid_imx63x_plugin5.so.1.0.10` release plugin and keeps the bundled Metavision 4 runtime dependencies. It preserves the validated global HAL import and GenTL preload shutdown fixes. Do not substitute the Windows Arena SDK binaries.

## Linux: build and check

If your user cannot access the Docker socket, prefix wrapper commands with `sudo bash` instead of `bash`. The wrapper preserves `SUDO_UID`/`SUDO_GID` for output ownership and resolves the invoking user's home for the default Arena SDK path. Custom environment variables may need to be passed explicitly through sudo.

Docker Engine must already be installed and running, with the Buildx plugin available and access to Ubuntu package repositories, PyPI, and GitHub during the build. The wrapper uses your current Docker context. Use the local Linux Engine for camera recording; a remote daemon or Docker Desktop VM does not share the laptop camera interface in the same way.

```bash
docker version
docker buildx version
bash docker/run.sh build
bash docker/run.sh check
bash docker/run.sh validate
```

To reduce compilation memory/CPU pressure:

```bash
bash docker/run.sh build --build-arg BUILD_JOBS=2
```

Image name defaults to `lpbf-event-optical:0.1`; override with `EVENT_DOCKER_IMAGE`. Source commit and primary Python SDK ABI inputs are pinned, but Ubuntu base tags, apt repositories and some Python dependency ranges remain mutable. This is a portable build recipe, not a byte-identical lock. Package manifests are stored at `/opt/build-info`. Keep/share the built image by digest when exact repeatability is required.

## Linux: offline verification first

The wrapper mounts the project's `data` directory as `/data` and `config` as `/settings` read-only. Output files belong to your Linux UID/GID. It runs without the Arena SDK for offline commands.

Use the already validated recording to compare results with the host:

```bash
bash docker/run.sh analyze \
    /data/recordings/controls-test-20261020T144321.981450Z-29f6a647/events.raw \
    --bin-us 250000 --plot
```

Expected host reference: **144,376,093 CD events**, **5.00216 seconds** CD event span, zero timestamp reversals and out-of-bounds coordinates. Confirm the same result in the container before live recording. The plot and summary appear under the host project's `data/analysis`.

Reconstruct the selected interval:

```bash
bash docker/run.sh reconstruct \
    /data/recordings/controls-test-20261020T144321.981450Z-29f6a647/events.raw \
    --config /settings/reconstruction.toml --start-s 1 --end-s 2
```

PNG directories, curated H5, manifest and metadata appear under `data/reconstructions`. Use absolute container paths such as `/data/...` and `/settings/...` when supplying paths. The entrypoint explicitly routes default analysis and reconstruction output to `/data/analysis` and `/data/reconstructions`. The working directory is `/data`.

You may override bind mount sources with absolute `EVENT_DATA_DIR` and `EVENT_CONFIG_DIR`. Keep outputs on a disk with adequate free space. Analysis/reconstruction run only when explicitly invoked; they are not started alongside capture.

## Linux: live discovery and capture

The Linux host remains responsible for USB4 authorization, the `atlantic` driver, the Ethernet interface, addressing, firewall rules, NIC MTU and host socket-buffer settings. A container does not fix a missing `enp3s0`. The wrapper does not change those settings or require `--privileged`.

Check the local interface/profile first, then discover from the container:

```bash
ip -br address show enp3s0
export ARENA_ROOT="$HOME/opt/arena/ArenaSDK_Linux_x64"
bash docker/run.sh record --list
```

Live commands use `--network host`, sharing the Linux Engine host's network namespace. Retain the camera-specific host firewall rule already tested. If host/camera link-local addresses change, update the corresponding rule on the host. Verify adapter/link stability before high-rate captures; the earlier reconnect reported a restricted PCIe link and that still deserves a separate check.

Inspect controls:

```bash
bash docker/run.sh camera-info \
    --serial "Lucid Vision Labs:lucid_imx63x_plugin5:250200198"
```

In the mounted `config/recorder.toml`, keep `decode_events=false`; native capture plus offline decoding is the tested acquisition workflow. Set the telemetry interface to the current host camera NIC. Then run a short test:

```bash
bash docker/run.sh record \
    --config /settings/recorder.toml \
    --serial "Lucid Vision Labs:lucid_imx63x_plugin5:250200198" \
    --name docker-test --duration 5
```

Recordings appear under host `data/recordings`. Inspect settings read-back, state, telemetry, output permissions and clean process exit. Run offline `analyze` on this new RAW and compare sensor span with host capture duration. Neither close duration agreement nor zero counters proves lossless capture; the new container/native vendor combination needs its own representative-load validation.

Stop an indefinite capture with Ctrl+C. The wrapper uses Docker init and a 30-second stop timeout; the Python recorder handles SIGINT/SIGTERM. Avoid forced termination if you need finalized recording metadata.

Vendor access permissions may need investigation if the non-root capture fails while host capture succeeds. Do not broadly grant privileged access as a default workaround. A normal camera-network connection should be tested first with the current non-root host-network setup.

## Windows: offline analysis and reconstruction

Use Docker Desktop configured for **Linux containers** on an x86_64 Windows system. No Windows Python, OpenEB or Arena installation is needed for offline tools. Run these commands in PowerShell from `iteration_3`:

```powershell
docker version
docker buildx version
docker buildx build --load --platform linux/amd64 -f docker/Dockerfile -t lpbf-event-optical:0.1 .
docker run --rm lpbf-event-optical:0.1 check
docker run --rm lpbf-event-optical:0.1 validate

New-Item -ItemType Directory -Force .\data | Out-Null
$Data = (Resolve-Path .\data).Path
$Settings = (Resolve-Path .\config).Path
```

Copy a RAW recording folder (including `metadata.json` if available) under the Windows project's `data\recordings`. Then use its path **inside the container**:

```powershell
docker run --rm --init --mount "type=bind,source=$Data,target=/data" --mount "type=bind,source=$Settings,target=/settings,readonly" lpbf-event-optical:0.1 analyze /data/recordings/SESSION/events.raw --plot

docker run --rm --init --mount "type=bind,source=$Data,target=/data" --mount "type=bind,source=$Settings,target=/settings,readonly" lpbf-event-optical:0.1 reconstruct /data/recordings/SESSION/events.raw --config /settings/reconstruction.toml --start-s 1 --end-s 2
```

Replace `SESSION` with the recording folder name. Generated files are accessible in the Windows `data` directory. These PowerShell commands use the same Linux image as Linux processing. Do not run the Bash host wrapper directly in PowerShell. WSL users can use the Bash wrapper for offline work with paths accessible to the selected Docker daemon.

## Windows live capture: separate validation required

The supplied Windows workflow covers offline tools. Live GigE capture inside Docker Desktop is **not verified** by this package. Docker Desktop host networking differs from native Linux host networking: it has layer-4 support and does not directly expose host interfaces/IP binding in the same way. Do not assume enabling `--network host` makes Arena broadcast discovery or high-rate camera streaming work on Windows.

For portable acquisition, the initial verified target is a Linux Engine host with its physical NIC. Windows users can process the resulting RAW files with this image. Native Windows acquisition or a suitably networked Linux VM remains a separate option to validate, including the Linux Arena SDK and physical camera access where applicable. Installing the Docker image does not validate any of these capture paths.

References:

- Docker host networking: https://docs.docker.com/engine/network/drivers/host/
- Docker Desktop networking: https://docs.docker.com/desktop/features/networking/
- OpenEB source: https://github.com/prophesee-ai/openeb/tree/5.2.0

## Sharing and troubleshooting

Share project source and the Docker recipe in GitHub. Do not commit recordings, host environments, compiled SDK builds, or vendor binaries. Distributing a vendor-inclusive image would require a separate review of the applicable vendor terms; this image avoids bundling that SDK.

To move a built offline image to another machine without rebuilding:

```bash
docker save -o event-optical-image.tar lpbf-event-optical:0.1
# On the other machine:
docker load -i event-optical-image.tar
```

No registry publication is performed automatically. For a failed build, retain the error and nearby compiler output. If you need expanded logs, run `bash docker/run.sh build --progress=plain`. The build deliberately stops on dependency, compile, unit-test or native decoder-regression failures. Do not bypass those checks to obtain a nominally successful image.

The first Ubuntu image build completed on the EndeavourOS host, including unit tests and native boundary regressions. Container import checks and a separate native validation run also passed. The sudo-aware wrapper has six hardware-independent tests. Container analysis of the known recording, live capture, and Windows execution still need their own host verification.
