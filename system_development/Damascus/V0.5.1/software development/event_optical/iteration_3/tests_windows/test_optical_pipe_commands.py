"""Exercise the patched real optical serve loop using a fake camera, without SDKs."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class OpticalPipeTests(unittest.TestCase):
    def capture(self, commands, expected_frames):
        fixtures = runpy.run_path(str(ROOT / 'optical_camera/tests/test_capture.py'))
        optical = fixtures['m']
        self.assertIn('WINDOWS_PIPE_READER', (ROOT / 'optical_camera/capture.py').read_text())
        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(config=None, serial='', duration=None, frames=None,
                command='serve', output_root=Path(d), name='pipe-test')
            camera = fixtures['Camera']([fixtures['Image']()])
            stdout = io.StringIO()
            with patch.object(optical.sys, 'stdin', io.StringIO(commands)), contextlib.redirect_stdout(stdout):
                optical.capture_run(args, camera_factory=lambda *a, **kw: camera)
            meta = json.loads(next(Path(d).glob('*/metadata.json')).read_text())
            self.assertEqual(meta['state'], 'capture_stopped')
            self.assertEqual(meta['frames_saved'], expected_frames)
            self.assertTrue(camera.closed)
            return [json.loads(line.split(' ', 1)[1]) for line in stdout.getvalue().splitlines()
                    if line.startswith('OPTICAL_RESPONSE ')]

    def test_piped_capture_then_stop_saves_one_image(self):
        replies = self.capture('{"command":"capture","id":"post-recording"}\n'
                               '{"command":"stop","id":"complete"}\n', 1)
        captured = [message for message in replies if message['event'] == 'captured']
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['id'], 'post-recording')
        self.assertEqual(replies[0]['event'], 'ready')
        self.assertEqual(replies[-1]['event'], 'finished')

    def test_eof_without_command_never_captures(self):
        self.capture('', 0)

    def test_stop_without_capture_never_captures(self):
        self.capture('{"command":"stop","id":"cleanup"}\n', 0)


if __name__ == '__main__':
    unittest.main()
