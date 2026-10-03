import sys
import optris.otcsdk as otc
import os
import numpy as np
import datetime
import time
import cv2
import socket
from pathlib import Path
import struct

BASE_DIR = Path(__file__).resolve().parent
outputPath = BASE_DIR / "Recordings"
os.makedirs(outputPath, exist_ok=True)

def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def connect(serialNumber=0):
    otc.Sdk.init(otc.Verbosity_Info, otc.Verbosity_Off, sys.argv[0])
    otc.EnumerationManager.getInstance().addEthernetDetector("192.168.0.0/24")

    imager = otc.IRImagerFactory.getInstance().create('native')
    imager.connect(serialNumber)

    return imager


class CameraClient(otc.IRImagerClient):
    def __init__(self, imager):
        super().__init__()
        self._imager = imager
        self._imager.addClient(self)
        self.recording = False
        self.recorded_frames = []   # RAM buffer: list of float32 temp maps
        self.recorded_timestamps = []
        self.capture_interval_s = 1.0
        self._capture_interval_ns = int(1e9)
        self._next_capture_ns = None
        self._recording_started_ns = None
        self._latest_frame = None
        self._frame_updated = False
        self._builder = otc.ImageBuilder(
            colorFormat=otc.ColorFormat_BGR,
            widthAlignment=otc.WidthAlignment_OneByte
        )

    def onFrame(self, evt):
        self._latest_frame = evt.clone()
        self._frame_updated = True

        if self.recording:
            now_ns = time.perf_counter_ns()

            # Keep the live preview at the camera frame rate, but only copy a
            # calibrated thermal frame when the next interval is due.
            if self._next_capture_ns is not None and now_ns < self._next_capture_ns:
                return

            frame = self._latest_frame.thermalFrame
            h = frame.getHeight()
            w = frame.getWidth()

            # copyTemperaturesTo writes into a flat float32 array
            temp_flat = np.empty(h * w, dtype=np.float32)
            frame.copyTemperaturesTo(temp_flat)
            
            self.recorded_frames.append(temp_flat.reshape(h, w).copy())
            self.recorded_timestamps.append(now_ns)

            # Advance from the previous target instead of from now. This
            # prevents image-copy and disk delays from accumulating as drift.
            self._next_capture_ns += self._capture_interval_ns
            while self._next_capture_ns <= now_ns:
                self._next_capture_ns += self._capture_interval_ns

    def start_recording(self, interval_s=1.0):
        """Capture one calibrated temperature map every ``interval_s`` seconds."""
        interval_s = float(interval_s)
        if not np.isfinite(interval_s) or interval_s <= 0:
            raise ValueError("Capture interval must be a finite number greater than 0.")

        self.recorded_frames = []
        self.recorded_timestamps = []
        self.capture_interval_s = interval_s
        self._capture_interval_ns = max(1, int(round(interval_s * 1e9)))
        self._recording_started_ns = time.perf_counter_ns()
        self._next_capture_ns = self._recording_started_ns
        self.recording = True
        print(f"Interval recording started: {interval_s:g} s.")

    def stop_recording(self):
        """Stop capturing and return the collected frames."""
        self.recording = False
        frames = self.recorded_frames
        print(f"Recording stopped. {len(frames)} frames captured.")
        return frames

    def save_recording(self, save_dir=outputPath):
        if not self.recorded_frames:
            print("No frames to save.")
            return None

        fileCount = len([f for f in save_dir.iterdir() if f.is_file()])
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(save_dir, f"thermalRun{fileCount}_{ts}.npz")
        
        
        stack = np.stack(self.recorded_frames, axis=0)
        timestamps_ns = np.array(self.recorded_timestamps, dtype=np.int64)
        elapsed_s = (
            (timestamps_ns - timestamps_ns[0]).astype(np.float64) / 1e9
        )

        np.savez_compressed(
            path,
            frames=stack,
            frame_timestamps_ns=timestamps_ns,
            elapsed_s=elapsed_s,
            capture_interval_s=np.array(self.capture_interval_s, dtype=np.float64),
            timestamp=np.array(datetime.datetime.now().isoformat())
        )
        print(f"Saved {stack.shape[0]} frames → {path}")
        return path

    def getImage(self):
        if self._latest_frame is None or not self._frame_updated:
            return None
        
        frame = self._latest_frame.thermalFrame
        h = frame.getHeight()
        w = frame.getWidth()
        
        temp_flat = np.empty(h * w, dtype=np.float32)
        frame.copyTemperaturesTo(temp_flat)
        temp_map = temp_flat.reshape(h, w)
        
        lo, hi = temp_map.min(), temp_map.max()
        normalized = ((temp_map - lo) / (hi - lo) * 255).astype(np.uint8)
        image = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
        
        self._frame_updated = False
        return image
    
    def getImageInfo(self):
        if self._latest_frame is None:
            return None

        frame = self._latest_frame.thermalFrame
        h = frame.getHeight()
        w = frame.getWidth()

        temp_flat = np.empty(h * w, dtype=np.float32)
        frame.copyTemperaturesTo(temp_flat)
        temp_map = temp_flat.reshape(h, w)

        return {
            "width": w,
            "height": h,
            "channels": 1,
            "dtype": str(temp_map.dtype),
            "size_bytes": int(temp_map.nbytes),

            "min_temp": float(np.nanmin(temp_map)),
            "max_temp": float(np.nanmax(temp_map)),
            "avg_temp": float(np.nanmean(temp_map)),
            "std_temp": float(np.nanstd(temp_map))
        }

def sendPreview(client, imager, stopFeed, HOST, PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(1)
        print(f"        [VideoServer] Listening on {HOST}:{PORT}", flush=True)

        conn, addr = server.accept()
        print(f"        [VideoServer] Connected to {addr}", flush=True)

        imager.runAsync()

        while not stopFeed.is_set():
            image = client.getImage()
            if image is None:
                time.sleep(0.001)
                continue

            ok, jpg = cv2.imencode(".jpg", image)
            if not ok:
                continue

            payload = jpg.tobytes()

            conn.sendall(struct.pack(">I", len(payload)))
            conn.sendall(payload)

def runSocketServer(client, HOST, PORT, stopFeed, imager):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen(1)
        print(f"        [SocketServer] Listening for commands on {HOST}:{PORT}")
        running = True

        while running:
            connect, address = server.accept()
            print("        [SocketServer]" + "Successfully connected to: " + str(address))
            while True:
                dataRec = connect.recv(1024)
                clientInput = dataRec.decode().strip().lower()
                if clientInput == 'record' or clientInput.startswith('record '):
                    startRecord(client, connect, clientInput)
                elif clientInput == 'stop':
                    stopRecord(client, connect)
                elif clientInput == 'quit':
                    quitProgram(client, connect, stopFeed)
                    break
                elif 'focus ' in clientInput:
                    focusInput = dataRec

                    adjustFocus(focusInput, imager, connect)
                elif clientInput == 'flag':
                    forceFlag(imager, client, connect)
                else:
                    unknownCommand(connect)
        
def startRecord(client, connect, command='record'):
    if not client.recording:
        parts = command.split()
        try:
            interval_s = float(parts[1]) if len(parts) == 2 else 1.0
            if len(parts) > 2:
                raise ValueError
            client.start_recording(interval_s)
        except (ValueError, IndexError):
            connect.sendall(
                b'Invalid record command. Use: record <interval_seconds>\n'
            )
            return

        connect.sendall(
            f'Recording started; interval={interval_s:g} s\n'.encode()
        )
    else:
        connect.sendall(b'Already recording. Press s to stop.\n')
        print("Already recording — press s to stop.")

def stopRecord(client, connect):
    if client.recording:
        connect.sendall(b'Stopped and saved recording.\n')
        client.stop_recording()
        client.save_recording()   # saves thermal_YYYYMMDD_HHMMSS.npz
    else:
        connect.sendall(b'Not currently recording.\n')
        print("Not currently recording.")

def quitProgram(client, connect, stopFeed):
    if client.recording:
        connect.sendall(b'Quitting program.\n')
        client.stop_recording()
        stopFeed.set()
        connect.close()
    else:
        stopFeed.set()
        
def unknownCommand(connect):
    connect.sendall(b'Unknown command.\n')

def adjustFocus(dataRec, imager, connect):
    focusInput = (dataRec.decode().strip().lower()).split(' ')
    previousFocus = imager.getFocusMotorPosition()

    if not isinstance(focusInput[1], float):
        connect.sendall(b"Invalid focus command.\n")

    newFocus = float(focusInput[1])

    if len(focusInput) == 1 or newFocus == None:
        connect.sendall(b'Missing focus value. Ex. "focus 22"\n')
    
    if newFocus > 100 and newFocus < 0:
        connect.sendall(b'Focus values must be within 0 and 100\n')

    
    imager.setFocusMotorPosition(newFocus)
    focusMessage = f"Focus changed from {previousFocus} to {newFocus}.\n"
    connect.sendall(focusMessage.encode())

def forceFlag(imager, client, connect):
    if client.recording:
        connect.sendall(b'Currently recording, cannot force flag.\n')
    
    imager.forceFlagEvent(0)
    connect.sendall(b'Forcing flag event.\n')

def placeRecSymbol(image, client):
    if client.recording:
        n = len(client.recorded_frames)
        cv2.circle(image, (12, 12), 8, (0, 0, 220), -1)
        cv2.putText(image, f"REC {n}", (24, 17),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1, cv2.LINE_AA)



