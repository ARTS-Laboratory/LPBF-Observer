"""thermalServer.py - keep the Optris open, save one frame per 'grab <name>'.

LabVIEW: TCP Open (localhost:5000) once, TCP Write "grab frame_0001" + End of
Line per shot, "focus <0-100>" to adjust motorized focus, "flag" to request\na shutter correction, and "quit" + End of Line at the end. Python never replies: the file
appearing on disk is the acknowledgment.
"""
import os, sys, socket, threading, time, math
from pathlib import Path
import numpy as np
import optris.otcsdk as otc

HOST, PORT = "127.0.0.1", 5000
SAVE_DIR = Path(__file__).resolve().parent / "Recordings"   # used for bare names
SAVE_DIR.mkdir(exist_ok=True)


def connect(serialNumber=0):                      # same as functions.py
    otc.Sdk.init(otc.Verbosity_Info, otc.Verbosity_Off, sys.argv[0])
    otc.EnumerationManager.getInstance().addEthernetDetector("192.168.0.0/24")
    imager = otc.IRImagerFactory.getInstance().create('native')
    imager.connect(serialNumber)
    return imager


class CameraClient(otc.IRImagerClient):
    def __init__(self, imager):
        super().__init__()
        self._imager = imager
        self._lock = threading.Lock()
        self._latest = None
        imager.addClient(self)

    def onFrame(self, evt):                        # SDK thread, every frame
        with self._lock:
            self._latest = evt.clone()

    def set_focus(self, value):
        position = float(value)
        if not math.isfinite(position) or not 0 <= position <= 100:
            raise ValueError("focus position must be a finite number from 0 to 100")
        self._imager.setFocusMotorPosition(position)
        return position

    def refresh_flag(self):
        self._imager.forceFlagEvent()

    def save_latest(self, name):
        with self._lock:
            evt = self._latest
        if evt is None:
            raise RuntimeError("no frame yet")
        f = evt.thermalFrame
        h, w = f.getHeight(), f.getWidth()
        temps = np.empty(h * w, dtype=np.float32)
        f.copyTemperaturesTo(temps)                # deg C from the SDK
        path = SAVE_DIR / name                     # full paths also work
        if path.suffix.lower() != ".npz":
            path = path.with_name(path.name + ".npz")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as fh:                # write, then rename:
            np.savez(fh, temps=temps.reshape(h, w), time_unix_ns=time.time_ns())
        os.replace(tmp, path)                      # file exists => file complete
        return path


def serve(client):
    with socket.socket() as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(1)
        print(f"Listening on {HOST}:{PORT}", flush=True)
        while True:                                # survives LabVIEW restarts
            conn, _ = srv.accept()
            try:
                with conn, conn.makefile("r") as lines:
                    for line in lines:             # one command per line
                        parts = line.strip().split(maxsplit=1)
                        if not parts:
                            continue
                        cmd = parts[0].lower()
                        if cmd == "grab" and len(parts) == 2:
                            try:
                                print("saved", client.save_latest(parts[1]), flush=True)
                            except Exception as e:     # no file = failed grab
                                print("grab failed:", parts[1], e, flush=True)
                        elif cmd == "focus":
                            try:
                                if len(parts) != 2:
                                    raise ValueError("use focus <position from 0 to 100>")
                                print("focus requested:", client.set_focus(parts[1]), flush=True)
                            except Exception as e:
                                print("focus failed:", e, flush=True)
                        elif cmd == "flag":
                            try:
                                if len(parts) != 1:
                                    raise ValueError("use flag with no argument")
                                client.refresh_flag()
                                print("flag correction requested", flush=True)
                            except Exception as e:
                                print("flag failed:", e, flush=True)
                        elif cmd == "quit":
                            return
                        else:
                            print("ignored:", line.strip(), flush=True)
            except ConnectionError as e:
                print("LabVIEW disconnected:", e, flush=True)


if __name__ == "__main__":
    imager = connect()
    client = CameraClient(imager)
    imager.runAsync()                              # frames flow into onFrame
    try:
        serve(client)
    finally:
        imager.stopRunning()

