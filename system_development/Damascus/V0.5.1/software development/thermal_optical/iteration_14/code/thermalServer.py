"""thermalServer.py - Optris NPZ acquisition with latest-saved-file preview.

Port 5000: newline-terminated grab <path>, focus <0-100>, flag, and quit.
Port 5100: push 4-byte big-endian JPEG length + JPEG bytes to LabVIEW.
The preview reads the completed NPZ after each successful save. It holds the
last saved image between saves and shows a waiting image before the first save.
After each successful save, last_recording.json beside this script records the
actual folder received from LabVIEW for the separate NPZ postprocessor.
Dependencies: numpy, Pillow, and the installed Optris OTC SDK.
"""
import os, sys, socket, threading, time, math, io, struct, json, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import optris.otcsdk as otc

HOST, PORT = "127.0.0.1", 5000
SAVE_DIR = Path(__file__).resolve().parent / "Recordings"   # used for bare names
SAVE_DIR.mkdir(exist_ok=True)
RECORDING_STATE_PATH = Path(__file__).resolve().parent / "last_recording.json"


def remember_recording(path):
    """Atomically publish the last successfully saved recording location."""
    actual = Path(path).resolve()
    state = {
        "input_folder": str(actual.parent),
        "latest_npz": str(actual),
        "updated_unix_ns": time.time_ns(),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=RECORDING_STATE_PATH.parent,
            prefix=".last_recording_", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, RECORDING_STATE_PATH)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SavedNpzPreview:
    """Serve JPEGs derived only from completed NPZ saves, never camera callbacks."""

    def __init__(self, host=HOST, port=5100, interval_s=0.2):
        self.host, self.port = host, port
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._condition = threading.Condition()
        self._pending = None
        self._generation = 0
        self._packet = self._waiting_packet()
        self._threads = []
        self._listener = None

    @staticmethod
    def _packet_for(image):
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        jpeg = buffer.getvalue()
        return struct.pack("!I", len(jpeg)) + jpeg

    @classmethod
    def _waiting_packet(cls):
        image = Image.new("RGB", (480, 320), (20, 20, 20))
        draw = ImageDraw.Draw(image)
        draw.text((16, 135), "Waiting for first saved thermal NPZ frame", fill="white")
        draw.text((16, 160), "Press START in LabVIEW to save a frame.", fill="white")
        return cls._packet_for(image)

    @classmethod
    def packet_from_npz(cls, path):
        # The writer has closed the file and atomically renamed it before publish().
        with np.load(path, allow_pickle=False) as recording:
            temps = np.array(recording["temps"], dtype=np.float32, copy=True)
            saved_ns = int(recording["time_unix_ns"].item())
        if temps.ndim != 2 or not temps.size:
            raise ValueError("preview expects one nonempty 2-D 'temps' array")
        finite = np.isfinite(temps)
        if not finite.any():
            raise ValueError("the frame contains no finite temperatures")
        lo, hi = float(temps[finite].min()), float(temps[finite].max())
        normalized = np.zeros(temps.shape, dtype=np.float32)
        if hi > lo:
            normalized[finite] = (temps[finite] - lo) / (hi - lo)
        # A display-only false-color palette: black/purple/red/orange/yellow.
        anchors = np.array([
            [0, 0, 4], [57, 9, 99], [137, 34, 106],
            [221, 81, 58], [252, 165, 10], [252, 255, 164],
        ], dtype=np.float32)
        positions = np.linspace(0, 1, len(anchors))
        colors = np.stack([
            np.interp(np.clip(normalized, 0, 1), positions, anchors[:, channel])
            for channel in range(3)
        ], axis=-1).astype(np.uint8)
        colors[~finite] = 0
        thermal = Image.fromarray(colors)
        width, height = thermal.size
        image = Image.new("RGB", (max(width, 480), height + 58), (20, 20, 20))
        image.paste(thermal, (0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((6, height + 4), Path(path).name[:70], fill="white")
        draw.text((6, height + 21),
                  f"Range: {lo:.2f} to {hi:.2f} C | auto-scaled preview", fill="white")
        saved_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(saved_ns / 1e9))
        draw.text((6, height + 38), "Host save time: " + saved_time, fill="white")
        return cls._packet_for(image)

    def publish(self, path):
        # This only queues a path; disk reading and JPEG encoding run separately.
        with self._condition:
            self._pending = Path(path)
            self._generation += 1
            self._condition.notify_all()

    def start(self):
        listener = socket.socket()
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            listener.listen(1)
            listener.settimeout(0.5)
        except Exception:
            listener.close()
            raise
        self._listener = listener
        self.port = listener.getsockname()[1]
        for target in (self._encode_loop, self._network_loop):
            thread = threading.Thread(target=target, daemon=True)
            self._threads.append(thread)
            thread.start()
        print(f"Saved-NPZ preview listening on {self.host}:{self.port}", flush=True)

    def _encode_loop(self):
        handled = 0
        while not self._stop.is_set():
            with self._condition:
                self._condition.wait_for(
                    lambda: self._stop.is_set() or self._generation != handled
                )
                if self._stop.is_set():
                    return
                path, handled = self._pending, self._generation
            try:
                packet = self.packet_from_npz(path)
            except Exception as error:
                print("NPZ preview failed:", path, error, flush=True)
                continue
            with self._condition:
                self._packet = packet

    def _network_loop(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                with connection:
                    connection.settimeout(2.0)
                    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    while not self._stop.is_set():
                        with self._condition:
                            packet = self._packet
                        # 4-byte big-endian length, followed immediately by JPEG bytes.
                        connection.sendall(packet)
                        if self._stop.wait(self.interval_s):
                            break
            except OSError:
                pass  # Stopping the LabVIEW preview must not stop acquisition.

    def close(self):
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._listener is not None:
            self._listener.close()
        for thread in self._threads:
            thread.join(timeout=3.0)


def connect(serialNumber=0):                      # same as functions.py
    otc.Sdk.init(otc.Verbosity_Info, otc.Verbosity_Off, sys.argv[0])
    otc.EnumerationManager.getInstance().addEthernetDetector("192.168.0.0/24")
    imager = otc.IRImagerFactory.getInstance().create('native')
    imager.connect(serialNumber)
    return imager


class CameraClient(otc.IRImagerClient):
    def __init__(self, imager, preview=None):
        super().__init__()
        self._imager = imager
        self._preview = preview
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
        try:
            remember_recording(path)
        except OSError as error:
            # The NPZ itself is already complete; metadata failure must not
            # interrupt camera acquisition or the saved-frame preview.
            print("Recording saved, but folder handoff failed:", error, flush=True)
        if self._preview is not None:
            self._preview.publish(path)
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
    preview = SavedNpzPreview()
    preview.start()
    imager = None
    try:
        imager = connect()
        client = CameraClient(imager, preview=preview)
        imager.runAsync()
        serve(client)
    finally:
        if imager is not None:
            imager.stopRunning()
        preview.close()

