from pytictoc import TicToc
import time
from arena_api.system import system
import cv2
import logging

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
        logging.info(f"{type(devices[0])}")
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



