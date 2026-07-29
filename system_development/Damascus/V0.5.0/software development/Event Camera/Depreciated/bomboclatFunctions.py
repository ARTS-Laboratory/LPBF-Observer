from pytictoc import TicToc
import time
from arena_api.system import system
import cv2
import logging
import numpy as np
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     datefmt='%Y-%m-%d %I:%M:%S %p')
time = TicToc()



def initializeDevice() -> list:
    time.tic()
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
            time.toc(f"Device initialization completed in")
            return devices
        
    else: 
        time.toc(f"Device initialization failed after")
        logging.error("No device found! Please connect a device and run the example again.")

def destroyDevice(devices) -> None:
    if devices:
        system.destroy_device(devices)
        logging.info("Destroyed device(s)")

def configureDevice(device) -> dict:
    nodemap = device.nodemap
    tlStreamNodeMap = device.tl_stream_nodemap
    widthInitial = device.nodemap.get_node("Width")
    heightInitial = device.nodemap.get_node("Height")

    initialAcquisitionMode = nodemap.get_node("AcquisitionMode").value

    nodemap.get_node("AcquisitionMode").value = "Continuous"
    tlStreamNodeMap["StreamBufferHandlingMode"].value = "NewestOnly"
    tlStreamNodeMap['StreamAutoNegotiatePacketSize'].value = True
    tlStreamNodeMap['StreamPacketResendEnable'].value = True

    deviceSettings = {"width" : widthInitial, "height" : heightInitial, "acquisitionMode" : initialAcquisitionMode}

    return deviceSettings

def selectDevice(devices):
    device = system.select_device(devices)

    return device

def recordVideo(device, seconds=10, out_file="triton2_recording.avi", fps=30):
    nodemap = device.nodemap
    tl_stream = device.tl_stream_nodemap

    nodemap.get_node("AcquisitionMode").value = "Continuous"
    tl_stream["StreamBufferHandlingMode"].value = "NewestOnly"
    tl_stream["StreamAutoNegotiatePacketSize"].value = True
    tl_stream["StreamPacketResendEnable"].value = True

    device.start_stream(100)

    writer = None
    start = time.time()

    try:
        while time.time() - start < seconds:
            buf = device.get_buffer()

            try:
                frame = np.ctypeslib.as_array(
                    buf.pdata,
                    shape=(buf.height, buf.width, int(buf.bits_per_pixel / 8))
                ).copy()

                if frame.ndim == 3 and frame.shape[2] == 1:
                    frame = frame[:, :, 0]

                if writer is None:
                    h, w = frame.shape[:2]
                    is_color = (frame.ndim == 3)
                    fourcc = cv2.VideoWriter_fourcc(*"XVID")
                    writer = cv2.VideoWriter(out_file, fourcc, fps, (w, h), isColor=is_color)

                if frame.ndim == 2:
                    frame_to_write = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    frame_to_write = frame

                writer.write(frame_to_write)

            finally:
                device.requeue_buffer(buf)

    finally:
        if writer is not None:
            writer.release()
        device.stop_stream()

