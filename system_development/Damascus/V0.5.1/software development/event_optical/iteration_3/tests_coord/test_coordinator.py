import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('coordinator', Path(__file__).resolve().parents[1]/'coordinator/run_experiment.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_failed_or_ambiguous_event_session_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            for state, cleanup in [('error', []), ('recording', []), ('capture_stopped', ['drain error'])]:
                session = parent/'capture'
                session.mkdir(exist_ok=True)
                (session/'metadata.json').write_text(json.dumps({'state': state, 'cleanup_errors': cleanup}))
                (session/'events.raw').write_bytes(b'raw data')
                with self.assertRaises(RuntimeError): m.validate_event_session(parent)
            (parent/'extra').mkdir()
            (parent/'extra/metadata.json').write_text('{}')
            with self.assertRaises(RuntimeError): m.validate_event_session(parent)

    def test_clean_event_session_and_raw_required(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            session = parent/'capture'
            session.mkdir()
            (session/'metadata.json').write_text(json.dumps({'state': 'capture_stopped', 'cleanup_errors': []}))
            with self.assertRaises(RuntimeError): m.validate_event_session(parent)
            (session/'events.raw').write_bytes(b'raw data')
            path, data = m.validate_event_session(parent)
            self.assertEqual(path, session/'metadata.json')

    def test_response_requires_matching_request_id(self):
        process = Mock()
        process.stdout = io.StringIO(
            'vendor message\nOPTICAL_RESPONSE {"event":"ready"}\n'
            'OPTICAL_RESPONSE {"event":"captured","id":"old"}\n'
            'OPTICAL_RESPONSE {"event":"captured","id":"new"}\n')
        worker = m.Worker(process)
        self.assertEqual(worker.wait('ready')['event'], 'ready')
        self.assertEqual(worker.wait('captured', request_id='new')['id'], 'new')

    def test_eof_before_capture_is_error(self):
        process = Mock(stdout=io.StringIO(''))
        worker = m.Worker(process)
        with self.assertRaises(RuntimeError): worker.wait('captured')

    def test_event_failure_never_sends_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for folder, name in [('event_camera/config', 'recorder.toml'), ('optical_camera/config', 'camera.toml')]:
                (root/folder).mkdir(parents=True)
                (root/folder/name).write_text('')
            (root/'arena/lib64').mkdir(parents=True)
            optical = Mock()
            optical.poll.return_value = 0
            event = Mock()
            event.wait.return_value = 1
            event.poll.return_value = 1
            worker = Mock()
            worker.wait.return_value = {'event': 'ready', 'session': '/data/test'}
            with patch.object(m, 'ROOT', root), patch.dict(m.os.environ, {'ARENA_ROOT': str(root/'arena')}), \
                 patch.object(m.sys, 'argv', ['run', '--duration', '1']), \
                 patch.object(m.subprocess, 'run'), patch.object(m.subprocess, 'Popen', side_effect=[optical, event]), \
                 patch.object(m, 'Worker', return_value=worker):
                self.assertEqual(m.main(), 1)
            worker.send.assert_not_called()
            manifest = json.loads(next((root/'data/runs').glob('*/manifest.json')).read_text())
            self.assertEqual(manifest['state'], 'error')

    def test_success_requests_one_photo_after_event_finished(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for folder, name in [('event_camera/config', 'recorder.toml'), ('optical_camera/config', 'camera.toml')]:
                (root/folder).mkdir(parents=True)
                (root/folder/name).write_text('')
            (root/'arena/lib64').mkdir(parents=True)
            calls = []
            optical = Mock()
            optical.poll.return_value = 0
            optical.wait.return_value = 0
            event = Mock()
            event.poll.return_value = 0
            def event_done(*_):
                calls.append('event_finished')
                parent = next((root/'event_camera/data/recordings').iterdir())/'events'
                parent.mkdir()
                (parent/'metadata.json').write_text(json.dumps({'state': 'capture_stopped', 'cleanup_errors': []}))
                (parent/'events.raw').write_bytes(b'raw data')
                return 0
            event.wait.side_effect = event_done
            worker = Mock()
            def wait_message(event, **kwargs):
                if event == 'ready': return {'event': 'ready'}
                if event == 'captured':
                    parent = next((root/'optical_camera/data/recordings').iterdir())/'optical'
                    parent.mkdir()
                    (parent/'metadata.json').write_text('{"state":"capture_stopped"}')
                    return {'event': 'captured', 'id': 'post-recording'}
                return {'event': 'finished', 'state': 'capture_stopped'}
            worker.wait.side_effect = wait_message
            worker.send.side_effect = lambda command, *_: calls.append(command)
            with patch.object(m, 'ROOT', root), patch.dict(m.os.environ, {'ARENA_ROOT': str(root/'arena')}), \
                 patch.object(m.sys, 'argv', ['run', '--duration', '1']), \
                 patch.object(m.subprocess, 'run'), patch.object(m.subprocess, 'Popen', side_effect=[optical, event]), \
                 patch.object(m, 'Worker', return_value=worker):
                self.assertEqual(m.main(), 0)
            self.assertEqual(calls, ['event_finished', 'capture', 'stop'])


if __name__ == '__main__': unittest.main()
