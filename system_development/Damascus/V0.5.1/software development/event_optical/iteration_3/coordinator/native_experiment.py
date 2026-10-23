"""Windows experiment policy: clean event recording, then one optical exposure.

Each general camera program runs in its own Python environment. No Docker,
WSL, shell activation, or camera-specific policy inside either camera is needed.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid

import windows_settings as settings
from windows_runtime import check_paths, event_command, validate_settings, stop_event


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_manifest(path, manifest):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def validate_event_session(parent):
    paths = list(parent.glob('*/metadata.json'))
    if len(paths) != 1:
        raise RuntimeError(f'Expected one event session under {parent}; found {len(paths)}')
    data = json.loads(paths[0].read_text(encoding='utf-8'))
    raw = paths[0].parent / 'events.raw'
    if data.get('state') != 'capture_stopped' or data.get('cleanup_errors'):
        raise RuntimeError('Event capture did not finish cleanly; skipping optical exposure')
    if not raw.is_file() or raw.stat().st_size == 0:
        raise RuntimeError('Event RAW output is missing or empty; skipping optical exposure')
    return paths[0], data


class Worker:
    def __init__(self, process, log=None):
        self.process, self.log = process, log
        self.messages = queue.Queue()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if self.log:
                    self.log.write(line)
                    self.log.flush()
                if line.startswith('OPTICAL_RESPONSE '):
                    self.messages.put(json.loads(line.split(' ', 1)[1]))
                print('[optical] ' + line.rstrip(), flush=True)
        except Exception as error:
            self.messages.put({'event': 'reader_error', 'error': str(error)})
        finally:
            self.messages.put({'event': 'eof'})

    def wait(self, event, timeout=60, request_id=None):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'Timed out waiting for optical {event}')
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f'Timed out waiting for optical {event}') from None
            if not isinstance(message, dict) or 'event' not in message:
                raise RuntimeError(f'Invalid optical response: {message}')
            if message['event'] in ('eof', 'reader_error') or (message['event'] == 'finished' and event != 'finished'):
                raise RuntimeError(f'Optical worker ended before {event}: {message}')
            if message['event'] == event and (request_id is None or message.get('id') == request_id):
                return message

    def send(self, command, request_id):
        self.process.stdin.write(json.dumps({'command': command, 'id': request_id}) + '\n')
        self.process.stdin.flush()


def preflight():
    check_paths(settings.EVENT_PYTHON, settings.OPTICAL_PYTHON, settings.EVENT_CONFIG,
                settings.OPTICAL_CONFIG, settings.ROOT / 'optical_camera' / 'capture.py',
                settings.ROOT / 'event_camera' / 'src' / 'event_optical' / 'recorder.py')
    text = (settings.ROOT / 'optical_camera' / 'capture.py').read_text(encoding='utf-8-sig')
    if 'select.select([sys.stdin]' in text and 'WINDOWS_PIPE_READER' not in text:
        raise RuntimeError('Run coordinator/install_windows_support.py once before paired recording.')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    subprocess.run(event_command(['--check']), cwd=settings.ROOT, env=env, check=True)
    subprocess.run([str(settings.OPTICAL_PYTHON), '-c',
                    'import PySpin; print("Native optical PySpin import OK")'],
                   cwd=settings.ROOT, env=env, check=True)
    return env


def run(name, duration):
    validate_settings(name, duration)
    if sys.platform != 'win32':
        raise RuntimeError('Use run_paired.py on Linux; this launcher is for native Windows.')
    env = preflight()
    root = settings.ROOT
    data_root = settings.PAIRED_DATA_ROOT.expanduser().resolve()
    run_id = f'{name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}'
    event_parent = data_root / 'event_camera' / 'recordings' / run_id
    optical_parent = data_root / 'optical_camera' / 'recordings' / run_id
    run_dir = data_root / 'runs' / run_id
    for directory in (event_parent, optical_parent, run_dir):
        directory.mkdir(parents=True, exist_ok=False)
    path = run_dir / 'manifest.json'
    manifest = {'run_id': run_id, 'state': 'initializing', 'created_utc': utc(),
                'backend': 'windows-native', 'event_duration_s': duration,
                'data_root': str(data_root), 'project_root': str(root),
                'policy': 'event recording then one software-triggered optical image',
                'hardware_synchronized': False, 'timing': {},
                'event_python': str(settings.EVENT_PYTHON), 'optical_python': str(settings.OPTICAL_PYTHON)}
    write_manifest(path, manifest)
    event_process = optical_process = worker = None
    optical_log = None
    stop_sent = False
    try:
        optical_log = (run_dir / 'optical-worker.log').open('x', encoding='utf-8')
        optical_process = subprocess.Popen([
            str(settings.OPTICAL_PYTHON), str(root / 'optical_camera' / 'capture.py'),
            'serve', '--config', str(settings.OPTICAL_CONFIG), '--serial', settings.OPTICAL_SERIAL,
            '--name', 'optical', '--output-root', str(optical_parent),
        ], cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        worker = Worker(optical_process, optical_log)
        manifest['optical_ready'] = worker.wait('ready', timeout=120)
        manifest['state'] = 'event_recording'
        write_manifest(path, manifest)
        print(f'Experiment: {run_dir}', flush=True)
        event_process = subprocess.Popen(event_command([
            '--config', settings.EVENT_CONFIG, '--serial', settings.EVENT_SERIAL,
            '--name', 'events', '--duration', duration, '--output-dir', event_parent,
        ]), cwd=root, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        try:
            status = event_process.wait()
        except KeyboardInterrupt:
            print('Stopping event recording; a clean stop will be followed by the optical photo.', flush=True)
            manifest['stop_requested_by_user'] = True
            status = stop_event(event_process)
        manifest['event_exit_code'] = status
        if status != 0:
            raise RuntimeError(f'Event recorder exit status {status}; skipping optical exposure')
        metadata_path, event_meta = validate_event_session(event_parent)
        manifest['event_metadata'] = str(metadata_path.relative_to(data_root))
        manifest['timing']['event_stopped_utc'] = event_meta.get('stopped_utc')
        manifest['timing']['event_process_exited_utc'] = utc()
        manifest['state'] = 'optical_capture'
        manifest['timing']['photo_request_utc'] = utc()
        write_manifest(path, manifest)
        worker.send('capture', 'post-recording')
        manifest['optical_capture'] = worker.wait('captured', timeout=150, request_id='post-recording')
        worker.send('stop', 'complete')
        stop_sent = True
        final = worker.wait('finished', timeout=40)
        if final.get('state') != 'capture_stopped' or optical_process.wait(timeout=15) != 0:
            raise RuntimeError('Optical worker did not close cleanly')
        optical_paths = list(optical_parent.glob('*/metadata.json'))
        if len(optical_paths) != 1:
            raise RuntimeError('Expected one optical metadata file')
        optical_meta = json.loads(optical_paths[0].read_text(encoding='utf-8'))
        if optical_meta.get('state') != 'capture_stopped' or optical_meta.get('frames_saved') != 1:
            raise RuntimeError('Optical metadata does not confirm exactly one saved photo')
        filename = manifest['optical_capture']['frame']['filename']
        image = (optical_paths[0].parent / filename).resolve()
        if not image.is_relative_to(optical_paths[0].parent.resolve()) or not image.is_file() or image.stat().st_size == 0:
            raise RuntimeError('Optical photo is missing, empty, or outside its session')
        manifest['optical_metadata'] = str(optical_paths[0].relative_to(data_root))
        manifest['optical_image'] = str(image.relative_to(data_root))
        manifest['state'] = 'complete'
    except BaseException as failure:
        manifest.update(state='error', error=f'{type(failure).__name__}: {failure}')
        print(manifest['error'], file=sys.stderr, flush=True)
    finally:
        for process, kind in ((event_process, 'event'), (optical_process, 'optical')):
            if process is not None and process.poll() is None:
                try:
                    if kind == 'event':
                        stop_event(process)
                    else:
                        if worker and not stop_sent:
                            worker.send('stop', 'cleanup')
                        process.wait(timeout=40)
                except BaseException as cleanup_error:
                    manifest.setdefault('cleanup_errors', []).append(f'{kind}: {cleanup_error}')
                    try:
                        process.kill()
                        process.wait(timeout=10)
                    except BaseException as kill_error:
                        manifest['cleanup_errors'].append(str(kill_error))
        if worker:
            worker.thread.join(timeout=3)
        if optical_log and (worker is None or not worker.thread.is_alive()):
            optical_log.close()
        for process in (event_process, optical_process):
            if process is not None and process.poll() is not None:
                for stream in (process.stdin, process.stdout):
                    if stream:
                        stream.close()
        if manifest.get('cleanup_errors'):
            manifest['state'] = 'error'
        manifest['finished_utc'] = utc()
        write_manifest(path, manifest)
        print(f'Manifest: {path}\nState: {manifest["state"]}', flush=True)
    return 0 if manifest['state'] == 'complete' else 1
