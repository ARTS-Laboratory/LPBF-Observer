import argparse
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location('optical_capture', Path(__file__).resolve().parents[1]/'capture.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class Image:
    def __init__(self, ident=1, incomplete=False, save_error=False):
        self.ident, self.incomplete, self.save_error = ident, incomplete, save_error
        self.released = False
    def IsIncomplete(self): return self.incomplete
    def GetImageStatus(self): return 3
    def GetTimeStamp(self): return self.ident * 1000000
    def GetFrameID(self): return self.ident
    def GetWidth(self): return 2
    def GetHeight(self): return 1
    def GetPixelFormatName(self): return 'Mono8'
    def Save(self, path):
        if self.save_error: raise OSError('disk full')
        Path(path).write_bytes(b'PNG-standin')
    def Release(self): self.released = True


class Camera:
    def __init__(self, images):
        self.images = iter(images)
        self.settings = {'readback': {'PixelFormat': 'Mono8'}}
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *_): self.closed = True
    def stream_stats(self): return {'StreamLostFrameCount': None}
    def next_image(self): return next(self.images), 'test-trigger'


class Tests(unittest.TestCase):
    def test_config_rejects_types_ranges_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'settings.toml'
            for value in ('gain_db = true', 'exposure_us = -1', 'timeout_ms = 0',
                          'frame_rate_hz = nan', 'unknown = 1', 'serial = 12',
                          'pixel_format = "BayerRG8"'):
                path.write_text(value)
                with self.assertRaises(ValueError, msg=value): m.load_config(path)

    def test_path_names_cannot_escape_output(self):
        for name in ('../escape', '/tmp/escape', '', 'hello/world'):
            with self.assertRaises(ValueError): m.safe_name(name)

    def run_capture(self, root, images, command='single', frames=None):
        args = argparse.Namespace(config=None, serial='', duration=None, frames=frames,
                                  command=command, output_root=Path(root), name='test')
        camera = Camera(images)
        factory = Mock(return_value=camera)
        with contextlib.redirect_stdout(io.StringIO()):
            m.capture_run(args, camera_factory=factory)
        return camera, factory, next(Path(root).iterdir())

    def test_single_is_triggered_releases_and_records_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            image = Image()
            camera, factory, session = self.run_capture(d, [image])
            self.assertTrue(factory.call_args.kwargs['triggered'])
            self.assertTrue(image.released)
            self.assertTrue(camera.closed)
            meta = json.loads((session/'metadata.json').read_text())
            self.assertEqual((meta['state'], meta['frames_saved']), ('capture_stopped', 1))
            with (session/'frames.csv').open() as f: rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]['camera_timestamp_ns'], '1000000')
            self.assertTrue((session/rows[0]['filename']).is_file())
            self.assertFalse(list(session.rglob('*.partial.png')))

    def test_sequence_saves_every_returned_frame_and_reports_gap(self):
        with tempfile.TemporaryDirectory() as d:
            images = [Image(1), Image(3), Image(4)]
            camera, factory, session = self.run_capture(d, images, 'sequence', 3)
            self.assertFalse(factory.call_args.kwargs['triggered'])
            meta = json.loads((session/'metadata.json').read_text())
            self.assertEqual(meta['frames_saved'], 3)
            self.assertEqual(meta['observed_frame_id_gaps'], 1)
            self.assertTrue(all(image.released for image in images))

    def test_incomplete_image_released_and_session_marked_error(self):
        with tempfile.TemporaryDirectory() as d:
            image = Image(incomplete=True)
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                self.run_capture(d, [image])
            self.assertTrue(image.released)
            meta = json.loads(next(Path(d).glob('*/metadata.json')).read_text())
            self.assertEqual(meta['state'], 'error')
            self.assertEqual(meta['frames_saved'], 0)
            self.assertEqual(meta['incomplete_images'], 1)

    def test_save_failure_releases_and_does_not_count_saved(self):
        with tempfile.TemporaryDirectory() as d:
            image = Image(save_error=True)
            with self.assertRaisesRegex(OSError, 'disk full'): self.run_capture(d, [image])
            self.assertTrue(image.released)
            meta = json.loads(next(Path(d).glob('*/metadata.json')).read_text())
            self.assertEqual(meta['frames_saved'], 0)
            self.assertEqual(meta['state'], 'error')

    def test_setting_mismatch_fails(self):
        camera = m.SpinnakerCamera({}, True)
        node = Mock()
        node.GetMin.return_value = 0
        node.GetMax.return_value = 100
        node.GetValue.return_value = 42
        camera.node = Mock(return_value=node)
        camera.p = Mock()
        camera.p.IsWritable.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'read back'):
            camera.number('Gain', 20)

    def test_settings_out_of_range_never_call_setter(self):
        camera = m.SpinnakerCamera({}, True)
        node = Mock()
        node.GetMin.return_value = 0
        node.GetMax.return_value = 100
        camera.node = Mock(return_value=node)
        camera.p = Mock()
        camera.p.IsWritable.return_value = True
        with self.assertRaises(ValueError): camera.number('Gain', 200)
        node.SetValue.assert_not_called()

    def test_software_trigger_executes_before_get_next_image(self):
        camera = m.SpinnakerCamera({'timeout_ms': 1000}, True)
        calls = []
        camera.p = Mock()
        camera.p.IsWritable.return_value = True
        trigger = Mock()
        trigger.Execute.side_effect = lambda: calls.append('trigger')
        camera.node = Mock(return_value=trigger)
        camera.camera = Mock()
        camera.camera.GetNextImage.side_effect = lambda *_: calls.append('get') or Image()
        camera.next_image()
        self.assertEqual(calls, ['trigger', 'get'])


if __name__ == '__main__': unittest.main()
