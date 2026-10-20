"""Experiment policy: event recording, then one fresh optical exposure.

This host-side controller calls Compose. Camera containers never receive Docker's
socket. The optical worker protocol is generic JSON lines over stdin/stdout.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import pwd
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def utc():
    return datetime.now(timezone.utc).isoformat()


def mkdir_owned(path, uid, gid):
    missing = []
    p = path
    while not p.exists():
        missing.append(p)
        p = p.parent
    for p in reversed(missing):
        p.mkdir()
        if os.geteuid() == 0:
            os.chown(p, uid, gid)


def write_manifest(path, data, uid, gid):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    if os.geteuid() == 0:
        os.chown(temporary, uid, gid)
    temporary.replace(path)


def validate_event_session(parent):
    paths = list(parent.glob('*/metadata.json'))
    if len(paths) != 1:
        raise RuntimeError(f'Expected one event session under {parent}; got {len(paths)}')
    data = json.loads(paths[0].read_text())
    if data.get('state') != 'capture_stopped' or data.get('cleanup_errors'):
        raise RuntimeError('Event capture did not finish cleanly; optical exposure was not requested')
    raw = paths[0].parent / 'events.raw'
    if not raw.is_file() or raw.stat().st_size <= 0:
        raise RuntimeError('Event RAW output is missing or empty')
    return paths[0], data


class Worker:
    def __init__(self, process):
        self.process = process
        self.messages = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if line.startswith('OPTICAL_RESPONSE '):
                    self.messages.put(json.loads(line.split(' ', 1)[1]))
                else:
                    print('[optical] ' + line.rstrip(), flush=True)
        except Exception as error:
            self.messages.put({'event': 'reader_error', 'error': str(error)})
        finally:
            self.messages.put({'event': 'eof'})

    def wait(self, event, timeout=60, request_id=None):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'Timed out waiting for optical {event}')
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f'Timed out waiting for optical {event}') from None
            if message['event'] in ('eof', 'reader_error'):
                raise RuntimeError(f'Optical worker ended before {event}: {message}')
            if message['event'] == 'finished' and event != 'finished':
                raise RuntimeError(f'Optical worker finished before {event}: {message}')
            if message['event'] == event and (request_id is None or message.get('id') == request_id):
                return message

    def send(self, command, request_id):
        self.process.stdin.write(json.dumps({'command': command, 'id': request_id})+'\n')
        self.process.stdin.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--name', default='weld')
    parser.add_argument('--event-serial', default='Lucid Vision Labs:lucid_imx63x_plugin5:250200198')
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error('duration must be positive and finite')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', args.name):
        parser.error('name must be a simple label, at most 64 characters')
    uid = int(os.environ.get('SUDO_UID', os.getuid()))
    gid = int(os.environ.get('SUDO_GID', os.getgid()))
    env = os.environ.copy()
    env.update(RUN_UID=str(uid), RUN_GID=str(gid))
    env.setdefault('ARENA_ROOT', str(Path(pwd.getpwuid(uid).pw_dir)/'opt/arena/ArenaSDK_Linux_x64'))
    required = [ROOT/'optical_camera/config/camera.toml', ROOT/'event_camera/config/recorder.toml',
                Path(env['ARENA_ROOT'])/'lib64']
    for path in required:
        if not path.exists():
            parser.error(f'Required path missing: {path}')
    run_id = args.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    event_parent = ROOT/'event_camera/data/recordings'/run_id
    optical_parent = ROOT/'optical_camera/data/recordings'/run_id
    run_dir = ROOT/'data/runs'/run_id
    for path in (event_parent, optical_parent, run_dir):
        mkdir_owned(path, uid, gid)
    compose = ['docker', 'compose', '--project-name', 'lpbf-observer', '--file', str(ROOT/'compose.yaml')]
    subprocess.run(compose+['config', '--quiet'], env=env, check=True)
    manifest = {'run_id': run_id, 'state': 'initializing', 'created_utc': utc(),
                'policy': 'event recording then one software-triggered optical image',
                'event_duration_s': args.duration, 'timing': {}, 'hardware_synchronized': False}
    path = run_dir/'manifest.json'
    event_name, optical_name = 'lpbf-event-'+uuid.uuid4().hex[:12], 'lpbf-optical-'+uuid.uuid4().hex[:12]
    event_process = optical_process = worker = None
    error = None
    try:
        optical_process = subprocess.Popen(compose+['run', '--rm', '--no-deps', '-T', '--name', optical_name,
            'optical', 'serve', '--config', '/settings/camera.toml', '--name', 'optical',
            '--output-root', '/data/recordings/'+run_id], env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        worker = Worker(optical_process)
        manifest['optical_ready'] = worker.wait('ready', timeout=120)
        manifest.update(state='event_recording')
        write_manifest(path, manifest, uid, gid)
        print(f'Experiment: {run_dir}', flush=True)
        event_process = subprocess.Popen(compose+['run', '--rm', '--no-deps', '-T', '--name', event_name,
            'event', 'record', '--config', '/settings/recorder.toml', '--serial', args.event_serial,
            '--name', 'events', '--duration', str(args.duration), '--output-dir', '/data/recordings/'+run_id],
            env=env, start_new_session=True)
        try:
            status = event_process.wait()
        except KeyboardInterrupt:
            print('Stopping event capture gracefully; a clean stop will be followed by the optical image.', flush=True)
            subprocess.run(['docker', 'stop', '--time', '30', event_name], check=True, timeout=40)
            status = event_process.wait(timeout=10)
            manifest['stop_requested_by_user'] = True
        manifest['event_exit_code'] = status
        if status != 0:
            raise RuntimeError(f'Event recorder exit status {status}; skipping optical capture')
        metadata_path, event_meta = validate_event_session(event_parent)
        manifest['event_metadata'] = str(metadata_path.relative_to(ROOT))
        manifest['timing']['event_stopped_utc'] = event_meta.get('stopped_utc')
        manifest['timing']['photo_request_utc'] = utc()
        manifest['state'] = 'optical_capture'
        write_manifest(path, manifest, uid, gid)
        worker.send('capture', 'post-recording')
        manifest['optical_capture'] = worker.wait('captured', timeout=150, request_id='post-recording')
        worker.send('stop', 'complete')
        final = worker.wait('finished', timeout=30)
        if final['state'] != 'capture_stopped' or optical_process.wait(timeout=15) != 0:
            raise RuntimeError('Optical worker did not close cleanly')
        optical_meta_paths = list(optical_parent.glob('*/metadata.json'))
        if len(optical_meta_paths) != 1:
            raise RuntimeError('Expected one optical session metadata file')
        manifest['optical_metadata'] = str(optical_meta_paths[0].relative_to(ROOT))
        manifest['state'] = 'complete'
    except BaseException as failure:
        error = failure
        manifest.update(state='error', error=str(failure))
    finally:
        # Stop any surviving native process through Docker, so SDK cleanup can run.
        for process, container in ((event_process, event_name), (optical_process, optical_name)):
            if process is not None and process.poll() is None:
                try:
                    subprocess.run(['docker', 'stop', '--time', '30', container], timeout=40, check=True)
                    process.wait(timeout=10)
                except Exception as cleanup_error:
                    manifest.setdefault('cleanup_errors', []).append(str(cleanup_error))
        if manifest.get('cleanup_errors'):
            manifest['state'] = 'error'
        manifest['finished_utc'] = utc()
        write_manifest(path, manifest, uid, gid)
        print(f'Manifest: {path}\nState: {manifest["state"]}', flush=True)
    if error:
        print(str(error), file=sys.stderr)
    return 0 if manifest['state'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
