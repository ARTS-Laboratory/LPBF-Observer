from __future__ import annotations
from pytictoc import TicToc
from recorder_config import SERIAL_NUMBER, BUFFER_COUNT, WARMUP_EVENT_COUNT
import time
from arena_api.system import system
import logging
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent
output_path = BASE_PATH / "recordings"
output_path.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     datefmt='%Y-%m-%d %I:%M:%S %p')
t = TicToc()

def initializeDevice():
    """
    Initialize and return the configured Triton camera.
    """

    t.tic()

    tries = 0
    triesMax = 6
    sleepTimeSecs = 10

    while tries < triesMax:

        # Discover all connected GigE Vision devices
        device_infos = system.device_infos

        # Find the configured camera by serial number
        camera_info = next(
            (
                info
                for info in device_infos
                if str(info.get("serial")) == str(SERIAL_NUMBER)
            ),
            None,
        )

        if camera_info is not None:

            # Open ONLY the configured camera
            devices = system.create_device(camera_info)

            if devices:

                device = devices[0]

                # Verify the correct camera was opened
                serial = str(
                    device.nodemap[
                        "DeviceSerialNumber"
                    ].value
                )

                if serial != str(SERIAL_NUMBER):
                    raise RuntimeError(
                        f"Opened wrong camera ({serial}). "
                        f"Expected {SERIAL_NUMBER}."
                    )

                logging.info(
                    f"Connected to "
                    f"{camera_info.get('vendor')} | "
                    f"{camera_info.get('model')} | "
                    f"S/N {serial}"
                )

                t.toc("Device initialization completed in")
                return device

            logging.warning(
                f"Found camera {SERIAL_NUMBER}, "
                "but failed to open it."
            )

        else:

            logging.info(
                f"Try {tries + 1} of {triesMax}: "
                f"Camera {SERIAL_NUMBER} not found."
            )

            if device_infos:

                logging.info("Detected devices:")

                for info in device_infos:

                    logging.info(
                        f"    {info.get('vendor')} | "
                        f"{info.get('model')} | "
                        f"{info.get('serial')}"
                    )

            else:

                logging.info("No GigE Vision devices detected.")

        tries += 1

        if tries < triesMax:

            logging.info(
                f"Waiting {sleepTimeSecs} seconds before retry..."
            )

            time.sleep(sleepTimeSecs)

    t.toc("Device initialization failed after")

    raise RuntimeError(
        f"Camera with serial number "
        f"{SERIAL_NUMBER} was not found."
    )

def destroyDevice(devices) -> None:
    if devices:
        system.destroy_device(devices)
        logging.info("Destroyed device(s)")

def configureDevice(device) -> None:
    nodemap = device.nodemap
    tl_stream = device.tl_stream_nodemap
    nodemap["AcquisitionMode"].value = "Continuous"
    nodemap["EventFormat"].value = "EVT3_0"
    tl_stream["StreamBufferHandlingMode"].value = "OldestFirst"
    tl_stream["StreamAutoNegotiatePacketSize"].value = True
    tl_stream["StreamPacketResendEnable"].value = True
    tl_stream["StreamEvsOutputFormat"].value = "XYTPFrame"

    # ERC (ErcEnable / ErcRateLimit) intentionally left out here --
    # it's controlled by setErcSettings() instead, so there's one
    # place that decides its value, not two that can disagree.

    logging.info("Camera configuration applied:")
    logging.info(
        f"  Acquisition Mode      : {nodemap['AcquisitionMode'].value}"
    )
    logging.info(
        f"  Width                 : {nodemap['Width'].value}"
    )
    logging.info(
        f"  Height                : {nodemap['Height'].value}"
    )
    logging.info(
        f"  Buffer Handling Mode  : "
        f"{tl_stream['StreamBufferHandlingMode'].value}"
    )
    logging.info(
        f"  Auto Packet Size      : "
        f"{tl_stream['StreamAutoNegotiatePacketSize'].value}"
    )
    logging.info(
        f"  Packet Resend         : "
        f"{tl_stream['StreamPacketResendEnable'].value}"
    )

def setEventBiases(
    device,
    positive: int | None = None,
    negative: int | None = None,
    low_pass_cutoff: int | None = None,
    high_pass_cutoff: int | None = None,
    refractory_period: int | None = None,
) -> None:
    """
    Set the EVS sensor's tunable biases in one call. Any parameter
    left as None is left unchanged on the device.

    Parameters
    ----------
    positive, negative
        Bias Event Threshold Positive/Negative — sensitivity to
        brightness increases/decreases. Lower = more sensitive, more
        events, more noise. Default on the sensor is 0.
    low_pass_cutoff
        Bias Low Pass Filter Cutoff — higher preserves fast
        (high-frequency) contrast changes; lower filters them out
        and reduces noise/event rate at the cost of latency.
    high_pass_cutoff
        Bias High Pass Filter Cutoff — higher removes slow
        (low-frequency) changes/drift; lower preserves them.
    refractory_period
        Bias Refractory Period — how long a pixel "sleeps" after
        firing. Shorter = more events from rapid repeated triggering
        at the same pixel; longer thins those out.

    Node names confirmed against a real TRT009S-E (S/N 250200198)
    on 2026-08-04 via findBiasNodes().
    """
    nodemap = device.nodemap

    settings = {
        "BiasEventThresholdPositive": positive,
        "BiasEventThresholdNegative": negative,
        "BiasLowPassFilterCutoff": low_pass_cutoff,
        "BiasHighPassFilterCutoff": high_pass_cutoff,
        "BiasRefractoryPeriod": refractory_period,
    }

    for node_name, value in settings.items():

        if value is None:
            continue

        nodemap[node_name].value = value

        logging.info(f"{node_name} set to {value}")

def verifyEventBiases(device) -> dict:
    """
    Read back the current value of every bias node and log it.

    Run this right after setEventBiases() the first time you use it.
    If a value doesn't match what you just set, BiasTuningControl
    (found alongside these but not yet understood — see the
    docstring note in setEventBiases callers) may be overriding
    manual writes, and is worth investigating in ArenaView before
    you trust any of these settings in production.
    """
    nodemap = device.nodemap

    node_names = [
        "BiasEventThresholdPositive",
        "BiasEventThresholdNegative",
        "BiasLowPassFilterCutoff",
        "BiasHighPassFilterCutoff",
        "BiasRefractoryPeriod",
        "BiasEventThresholdReference",
        "BiasTuningControl",
    ]

    current_values = {}

    for node_name in node_names:

        try:
            value = nodemap[node_name].value
        except Exception as e:
            value = f"<could not read: {e}>"

        current_values[node_name] = value

        logging.info(f"{node_name} currently = {value}")

    return current_values

def setErcSettings(
    device,
    enable: bool | None = None,
    rate_limit: float | None = None,
) -> None:
    """
    Set Event Rate Control (ERC) enable state and/or rate limit.
    Any parameter left as None is left unchanged on the device.

    ERC drops events once the output rate exceeds rate_limit during
    each ~200us referencing period, with no concept of which events
    matter more — it's a blunt bandwidth safety net, not a smart
    filter. For defect-detection use cases, prefer raising this
    limit over relying on it to do anything intelligent.

    Node names (ErcEnable, ErcRateLimit) already confirmed working —
    they're used directly in configureDevice().
    """
    nodemap = device.nodemap

    if enable is not None:
        nodemap["ErcEnable"].value = enable
        logging.info(f"ErcEnable set to {enable}")

    if rate_limit is not None:
        nodemap["ErcRateLimit"].value = rate_limit
        logging.info(f"ErcRateLimit set to {rate_limit}")

def findNodesByKeyword(device, keywords: list[str]) -> list[str]:
    """
    General-purpose version of findBiasNodes(): list every nodemap
    feature whose name contains any of the given keywords
    (case-insensitive).

    Use this to discover the Event Burst Filter (TRAIL/STC) node
    names, which findBiasNodes() would have missed since they don't
    contain "bias" or "threshold". Try something like:

        findNodesByKeyword(device, ["filter", "burst", "trail", "stc"])

    Same caveats as findBiasNodes(): this is a one-time discovery
    call, not something to leave in a production recording run, and
    if the enumeration methods below don't work on your installed
    arena_api version, fall back to ArenaView's feature tree.
    """
    nodemap = device.nodemap

    try:
        names = list(nodemap.feature_names)
    except AttributeError:
        try:
            names = [node.name for node in nodemap]
        except (AttributeError, TypeError):
            names = [
                n for n in dir(nodemap)
                if not n.startswith("_")
            ]

    keywords_lower = [k.lower() for k in keywords]

    matches = [
        name for name in names
        if any(k in name.lower() for k in keywords_lower)
    ]

    for name in matches:
        logging.info(f"Found candidate node: {name}")

    return matches

def readDeviceSettings(device) -> dict:
    nodemap = device.nodemap
    tl_stream = device.tl_stream_nodemap

    return {
        "width": nodemap["Width"].value,
        "height": nodemap["Height"].value,
        "acquisition_mode": nodemap["AcquisitionMode"].value,
        "stream_buffer_mode": tl_stream["StreamBufferHandlingMode"].value,
        "auto_packet_size": tl_stream["StreamAutoNegotiatePacketSize"].value,
        "packet_resend": tl_stream["StreamPacketResendEnable"].value,
    }

