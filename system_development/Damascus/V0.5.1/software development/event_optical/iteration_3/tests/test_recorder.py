"""Hardware-independent failure/lifecycle checks; these do not validate the SDK."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from event_optical.recorder import record


class FakeStream:
    def __init__(self, stop, *, disconnected=False, fail_start=False,
                 fail_stop=False, log_ok=True, silent=False):
        self.stop_event = stop
        self.disconnected = disconnected
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.log_ok = log_ok
        self.silent = silent
        self.stopped = False
        self.calls = []
        self.file = None
        self.path = None

    def log_raw_data(self, path):
        self.calls.append("log")
        if not self.log_ok:
            return False
        self.path = Path(path)
        self.file = self.path.open("wb")
        self.file.write(b"% format EVT3;height=720;width=1280\n% end\n")
        return True

    def start(self):
        self.calls.append("start")
        if self.fail_start:
            raise RuntimeError("start failed")

    def poll_buffer(self):
        if self.stopped or self.disconnected:
            return -1
        return 0 if self.silent else 1

    def get_latest_raw_data(self):
        self.calls.append("consume")
        self.file.write(b"\x00\x00" * 100)
        self.stop_event.set()
        return b"test buffer"

    def stop(self):
        self.calls.append("stop")
        self.stopped = True
        if self.fail_stop:
            raise RuntimeError("stop failed")

    def stop_log_raw_data(self):
        self.calls.append("close_log")
        if self.file is not None:
            self.file.close()


class FakeDevice:
    def __init__(self, stream):
        self.stream = stream

    def get_i_events_stream(self):
        return self.stream


class FakeDiscovery:
    def __init__(self, stream, serials=None):
        self.stream = stream
        self.serials = ["250200198"] if serials is None else serials
        self.opened = []

    def list(self):
        return self.serials

    def open(self, serial):
        self.opened.append(serial)
        return FakeDevice(self.stream)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.stop = threading.Event()

    def run_record(self, **kwargs):
        stream_keys = ("disconnected", "fail_start", "fail_stop", "log_ok", "silent")
        stream = FakeStream(self.stop, **{k: kwargs.pop(k) for k in stream_keys if k in kwargs})
        discovery = FakeDiscovery(stream)
        self.stream = stream
        return record(discovery, output_dir=self.output, stop_event=self.stop, **kwargs)

    def metadata(self):
        paths = list(self.output.glob("*/metadata.json"))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text())

    def test_signal_stop_flushes_and_records_metadata(self):
        session = self.run_record()
        meta = self.metadata()
        self.assertEqual(meta["state"], "capture_stopped")
        self.assertEqual(meta["stop_reason"], "signal")
        self.assertEqual(meta["buffers_consumed"], 1)
        self.assertIsNone(meta["event_count"])
        self.assertFalse(meta["losslessness_verified"])
        self.assertEqual(meta["raw_file_bytes"], (session / "events.raw").stat().st_size)
        self.assertEqual(self.stream.calls, ["log", "start", "consume", "stop", "close_log"])

    def test_disconnection_is_error_and_log_is_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ended unexpectedly"):
            self.run_record(disconnected=True)
        self.assertEqual(self.metadata()["state"], "error")
        self.assertTrue(self.stream.file.closed)

    def test_failed_start_still_attempts_cleanup(self):
        with self.assertRaisesRegex(RuntimeError, "start failed"):
            self.run_record(fail_start=True)
        self.assertEqual(self.stream.calls, ["log", "start", "stop", "close_log"])
        self.assertEqual(self.metadata()["state"], "error")

    def test_stop_failure_does_not_prevent_closing_log(self):
        with self.assertRaisesRegex(RuntimeError, "Cleanup failed"):
            self.run_record(fail_stop=True)
        self.assertTrue(self.stream.file.closed)
        self.assertEqual(self.metadata()["state"], "error")

    def test_failed_log_does_not_start_stream(self):
        with self.assertRaisesRegex(RuntimeError, "could not open"):
            self.run_record(log_ok=False)
        self.assertNotIn("start", self.stream.calls)
        self.assertEqual(self.metadata()["state"], "error")

    def test_silent_camera_times_out(self):
        with self.assertRaisesRegex(RuntimeError, "No RAW buffer"):
            self.run_record(silent=True, no_data_timeout=0.005)
        self.assertEqual(self.metadata()["state"], "error")

    def test_duration_stops_quiet_stream_without_hanging(self):
        with self.assertRaisesRegex(RuntimeError, "no consumed RAW buffers"):
            self.run_record(silent=True, duration=0.005, no_data_timeout=0)
        self.assertEqual(self.metadata()["stop_reason"], "duration_reached")

    def test_multiple_cameras_require_selection(self):
        discovery = FakeDiscovery(None, ["a", "b"])
        with self.assertRaisesRegex(RuntimeError, "Multiple cameras"):
            record(discovery, output_dir=self.output)
        self.assertEqual(discovery.opened, [])
        self.assertEqual(list(self.output.iterdir()), [])

    def test_exact_requested_serial_is_preserved(self):
        stream = FakeStream(self.stop)
        discovery = FakeDiscovery(stream, [])
        record(discovery, output_dir=self.output, stop_event=self.stop,
               serial="Lucid:plugin:250200198")
        self.assertEqual(discovery.opened, ["Lucid:plugin:250200198"])

    def test_sessions_never_replace_earlier_recording(self):
        first = self.run_record()
        old_bytes = (first / "events.raw").read_bytes()
        self.stop.clear()
        second = self.run_record()
        self.assertNotEqual(first, second)
        self.assertEqual((first / "events.raw").read_bytes(), old_bytes)

    def test_invalid_arguments_fail_before_discovery(self):
        for kwargs in ({"duration": -1}, {"duration": float("nan")},
                       {"status_interval": 0}, {"name": "../escape"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                record(None, output_dir=self.output, **kwargs)


if __name__ == "__main__":
    unittest.main()
