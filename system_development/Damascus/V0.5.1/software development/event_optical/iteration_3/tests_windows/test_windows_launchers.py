"""Hardware-free regressions. Run from iteration_3 with unittest discovery."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'coordinator'))
import native_experiment as native
import windows_runtime as runtime
import install_windows_support as installer


class ProtocolTests(unittest.TestCase):
    def test_eof_does_not_report_photo(self):
        worker = native.Worker(Mock(stdout=io.StringIO('')))
        with self.assertRaisesRegex(RuntimeError, 'ended before captured'):
            worker.wait('captured', timeout=1, request_id='post-recording')
        worker.thread.join()

    def test_only_matching_request_completes_wait(self):
        source = '\n'.join([
            'OPTICAL_RESPONSE {"event":"captured","id":"old"}',
            'OPTICAL_RESPONSE {"event":"captured","id":"post-recording"}',
        ])
        with contextlib.redirect_stdout(io.StringIO()):
            worker = native.Worker(Mock(stdout=io.StringIO(source)))
            message = worker.wait('captured', request_id='post-recording')
            worker.thread.join()
        self.assertEqual(message['id'], 'post-recording')

    def test_invalid_settings_rejected(self):
        for duration in (True, 0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                runtime.validate_settings('test', duration)
        with self.assertRaises(ValueError):
            runtime.validate_settings('../escape', 1)

    def test_optical_pipe_patch_is_guarded_idempotent_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'capture.py'
            # Wrap the original fragment into valid Python at its existing indentation.
            source = 'def f():\n    if True:\n        if True:\n            if True:\n' + installer.OLD
            path.write_bytes(source.replace('\n', '\r\n').encode())
            original = path.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(installer.patch(path))
                self.assertFalse(installer.patch(path))
            self.assertEqual(path.with_name('capture.py.before-windows-pipes.bak').read_bytes(), original)
            self.assertIn('commands.get(timeout=0.2)', path.read_text())
            path.write_text('# Different source\n')
            with self.assertRaises(RuntimeError): installer.patch(path)
            self.assertEqual(path.read_text(), '# Different source\n')


class ExperimentTests(unittest.TestCase):
    def execute(self, root, status=0, event_state='capture_stopped', optical_state='capture_stopped', missing_photo=False):
        calls = []
        event = Mock()
        event.stdin = event.stdout = None
        event.poll.return_value = status
        def event_done():
            calls.append('event-exited')
            parent = next((root / 'output/event_camera/recordings').iterdir()) / 'events'
            parent.mkdir()
            (parent / 'events.raw').write_bytes(b'raw payload')
            (parent / 'metadata.json').write_text(json.dumps({'state': event_state, 'stopped_utc': '2026-10-22T12:00:00+00:00'}))
            return status
        event.wait.side_effect = event_done
        optical = Mock()
        optical.poll.return_value = 0
        optical.wait.return_value = 0
        worker = Mock()
        worker.thread.is_alive.return_value = False
        def wait_message(event, **kwargs):
            if event == 'ready': return {'event': 'ready'}
            if event == 'captured':
                session = next((root / 'output/optical_camera/recordings').iterdir()) / 'optical'
                (session / 'images').mkdir(parents=True)
                (session / 'metadata.json').write_text(json.dumps({'state': optical_state, 'frames_saved': 1}))
                if not missing_photo:
                    (session / 'images/frame.png').write_bytes(b'image')
                return {'event': 'captured', 'id': 'post-recording', 'frame': {'filename': 'images/frame.png'}}
            return {'event': 'finished', 'state': optical_state}
        worker.wait.side_effect = wait_message
        worker.send.side_effect = lambda command, ident: calls.append(command)
        with patch.object(native.settings, 'ROOT', root), \
             patch.object(native.settings, 'PAIRED_DATA_ROOT', root / 'output'), \
             patch.object(native.sys, 'platform', 'win32'), \
             patch.object(native, 'preflight', return_value={}), \
             patch.object(native.subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, create=True), \
             patch.object(native.subprocess, 'Popen', side_effect=[optical, event]), \
             patch.object(native, 'Worker', return_value=worker), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = native.run('paired-test', 5)
        manifest = json.loads(next((root / 'output/runs').glob('*/manifest.json')).read_text())
        return result, calls, manifest, worker

    def test_photo_only_after_clean_event_exit(self):
        with tempfile.TemporaryDirectory() as d:
            result, calls, manifest, worker = self.execute(Path(d))
            self.assertEqual((result, manifest['state']), (0, 'complete'))
            self.assertEqual(calls, ['event-exited', 'capture', 'stop'])
            self.assertFalse(manifest['hardware_synchronized'])
            self.assertTrue((Path(manifest['data_root']) / manifest['optical_image']).is_file())

    def test_outputs_use_short_data_root_outside_project(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result, calls, manifest, worker = self.execute(root)
            self.assertEqual(result, 0)
            self.assertEqual(Path(manifest['data_root']), (root / 'output').resolve())
            self.assertFalse((root / 'event_camera/data').exists())
            for key in ('event_metadata', 'optical_metadata', 'optical_image'):
                self.assertFalse(Path(manifest[key]).is_absolute())
                self.assertTrue((Path(manifest['data_root']) / manifest[key]).is_file())

    def test_failed_event_exit_never_requests_photo(self):
        with tempfile.TemporaryDirectory() as d:
            result, calls, manifest, worker = self.execute(Path(d), status=3)
            self.assertEqual((result, manifest['state']), (1, 'error'))
            worker.send.assert_not_called()

    def test_error_metadata_with_zero_exit_never_requests_photo(self):
        with tempfile.TemporaryDirectory() as d:
            result, calls, manifest, worker = self.execute(Path(d), event_state='error')
            self.assertEqual(result, 1)
            worker.send.assert_not_called()

    def test_missing_photo_is_error_even_after_captured_response(self):
        with tempfile.TemporaryDirectory() as d:
            result, calls, manifest, worker = self.execute(Path(d), missing_photo=True)
            self.assertEqual((result, manifest['state']), (1, 'error'))

    def test_optical_error_is_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            result, calls, manifest, worker = self.execute(Path(d), optical_state='error')
            self.assertEqual((result, manifest['state']), (1, 'error'))

    def test_graceful_stop_uses_ctrl_break_before_wait(self):
        process = Mock()
        process.poll.return_value = None
        calls = []
        process.send_signal.side_effect = lambda signum: calls.append('break')
        process.wait.side_effect = lambda **kwargs: calls.append('wait') or 0
        with patch.object(runtime.signal, 'CTRL_BREAK_EVENT', 1, create=True):
            self.assertEqual(runtime.stop_event(process), 0)
        self.assertEqual(calls, ['break', 'wait'])


if __name__ == '__main__':
    unittest.main()
