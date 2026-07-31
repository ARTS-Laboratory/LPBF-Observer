from pytictoc import TicToc
import time
from arena_api.system import system
import logging
import time
from pathlib import Path
import ctypes

BASE_PATH = Path(__file__).resolve().parent
output_path = BASE_PATH / "recordings"
output_path.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     datefmt='%Y-%m-%d %I:%M:%S %p')
t = TicToc()

def initializeDevice() -> list:
    t.tic()
    tries = 0
    triesMax = 6
    sleepTimeSecs = 10

    while tries < triesMax:
        devices = system.create_device()
        if not devices:
            logging.info(f"Try {tries + 1} of {triesMax}: waiting for {sleepTimeSecs} seconds for a device to be connected!")
            for secCount in range(sleepTimeSecs):
                time.sleep(1)
                logging.info(f"{secCount + 1} seconds passed {'.' * secCount}")
            tries += 1
        else:
            logging.info(f"Created {len(devices)} device(s)")
            t.toc(f"Device initialization completed in")
            return devices
        
    else: 
        t.toc(f"Device initialization failed after")
        logging.error("No device found! Please connect a device and run the example again.")

def destroyDevice(devices) -> None:
    if devices:
        system.destroy_device(devices)
        logging.info("Destroyed device(s)")

def configureDevice(device) -> None:
    nodemap = device.nodemap
    tl_stream = device.tl_stream_nodemap
    nodemap["AcquisitionMode"].value = "Continuous"
    nodemap["EventFormat"].value = "EVT3_0"
    nodemap["ErcEnable"].value = True
    nodemap["ErcRateLimit"].value = 10.0
    tl_stream["StreamBufferHandlingMode"].value = "NewestOnly"
    tl_stream["StreamAutoNegotiatePacketSize"].value = True
    tl_stream["StreamPacketResendEnable"].value = True
    tl_stream["StreamEvsOutputFormat"].value = "XYTPFrame"

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

def selectDevice(devices):
    device = system.select_device(devices)

    return device

def recordXYTPEvents(device):
    """
    Configure the EVS camera for XYTPFrame output and print
    timestamp, x, y, polarity for each valid event. 
    """
    try:
        device.start_stream()

        print("Streaming XYTP events...\n")
        print(f"{'Timestamp':>15} {'X':>6} {'Y':>6} {'P':>6}")
        print("-" * 40)

        while True:
            buffer = device.get_buffer()

            try:
                if buffer.is_incomplete:
                    continue

                src_data = ctypes.cast(
                    buffer.pdata,
                    ctypes.POINTER(ctypes.c_float)
                )

                bytes_per_event = buffer.bits_per_pixel // 8
                valid_events = buffer.size_filled // bytes_per_event

                for i in range(valid_events):

                    x = src_data[i * 4 + 0]
                    y = src_data[i * 4 + 1]
                    t = src_data[i * 4 + 2]
                    p = src_data[i * 4 + 3]

                    print(
                        f"{t:15.6f} "
                        f"{int(x):6d} "
                        f"{int(y):6d} "
                        f"{int(p):6d}"
                    )

            finally:
                device.requeue_buffer(buffer)

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        device.stop_stream()
