"""General Spinnaker image acquisition; no experiment-specific sequencing."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import sys
import threading
import time
import tomllib
import uuid


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', value):
        raise ValueError('Names must be 1–96 letters, digits, dots, underscores or hyphens; begin with a letter/digit.')
    return value


def load_config(path=None):
    cfg = {'serial': '', 'exposure_us': 1000.0, 'gain_db': 0.0,
           'pixel_format': 'Mono8', 'timeout_ms': 10000}
    if path:
        supplied = tomllib.loads(Path(path).read_text())
        unknown = set(supplied) - set(cfg) - {'frame_rate_hz'}
        if unknown:
            raise ValueError(f'Unknown optical settings: {sorted(unknown)}')
        cfg.update(supplied)
    for name in ('exposure_us', 'gain_db', 'frame_rate_hz'):
        if name not in cfg:
            continue
        value = cfg[name]
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
        if name != 'gain_db' and value <= 0:
            raise ValueError(f'{name} must be positive')
    if type(cfg['timeout_ms']) is not int or not 100 <= cfg['timeout_ms'] <= 120000:
        raise ValueError('timeout_ms must be an integer from 100 to 120000')
    if not isinstance(cfg['serial'], str):
        raise ValueError('serial must be a string')
    if cfg['pixel_format'] not in ('Mono8', 'Mono16'):
        raise ValueError('This recorder currently supports Mono8 and Mono16 PNGs')
    return cfg


class SpinnakerCamera:
    def __init__(self, cfg, triggered):
        self.cfg, self.triggered = cfg, triggered
        self.system = self.cameras = self.camera = None
        self.initialized = self.streaming = False
        self.settings = {}

    def __enter__(self):
        import PySpin
        self.p = PySpin
        try:
            self.system = PySpin.System.GetInstance()
            self.cameras = self.system.GetCameras()
            if not self.cameras.GetSize():
                raise RuntimeError('No cameras discovered')
            if self.cfg['serial']:
                self.camera = self.cameras.GetBySerial(self.cfg['serial'])
            elif self.cameras.GetSize() == 1:
                self.camera = self.cameras.GetByIndex(0)
            else:
                raise RuntimeError('Multiple cameras found; specify serial')
            self.camera.Init()
            self.initialized = True
            self.settings['before'] = self.read_settings()
            self.configure()
            self.settings['readback'] = self.read_settings()
            self.camera.BeginAcquisition()
            self.streaming = True
            if self.triggered and not self.p.IsWritable(self.node('TriggerSoftware', 'CCommandPtr')):
                raise RuntimeError('TriggerSoftware is not executable after arming')
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def node(self, name, kind):
        return getattr(self.p, kind)(self.camera.GetNodeMap().GetNode(name))

    def enum(self, name, value):
        node = self.node(name, 'CEnumerationPtr')
        entry = node.GetEntryByName(value)
        if not self.p.IsWritable(node) or not self.p.IsReadable(entry):
            raise RuntimeError(f'{name}={value} is unavailable or not writable')
        node.SetIntValue(entry.GetValue())
        if node.GetCurrentEntry().GetSymbolic() != value:
            raise RuntimeError(f'{name} readback mismatch')

    def number(self, name, value):
        node = self.node(name, 'CFloatPtr')
        if not self.p.IsWritable(node):
            raise RuntimeError(f'{name} is not writable')
        if not node.GetMin() <= value <= node.GetMax():
            raise ValueError(f'{name}={value} outside [{node.GetMin()}, {node.GetMax()}]')
        node.SetValue(value)
        actual = node.GetValue()
        if not math.isclose(value, actual, rel_tol=1e-6, abs_tol=1e-3):
            raise RuntimeError(f'{name}: requested {value}, read back {actual}')

    def configure(self):
        # SDK changes can remain after a configuration failure. Never start acquisition on failure.
        self.enum('TriggerMode', 'Off')
        self.enum('AcquisitionMode', 'Continuous')
        self.enum('PixelFormat', self.cfg['pixel_format'])
        self.enum('ExposureAuto', 'Off')
        self.number('ExposureTime', self.cfg['exposure_us'])
        self.enum('GainAuto', 'Off')
        self.number('Gain', self.cfg['gain_db'])
        if 'frame_rate_hz' in self.cfg:
            node = self.node('AcquisitionFrameRateEnable', 'CBooleanPtr')
            if not self.p.IsWritable(node):
                raise RuntimeError('AcquisitionFrameRateEnable unavailable')
            node.SetValue(True)
            if not node.GetValue():
                raise RuntimeError('Frame rate enable readback mismatch')
            self.number('AcquisitionFrameRate', self.cfg['frame_rate_hz'])
        if self.triggered:
            self.enum('TriggerSelector', 'FrameStart')
            self.enum('TriggerSource', 'Software')
            self.enum('TriggerMode', 'On')

    def read_settings(self):
        names = ('DeviceModelName', 'DeviceSerialNumber', 'Width', 'Height', 'PixelFormat',
                 'ExposureAuto', 'ExposureTime', 'GainAuto', 'Gain', 'TriggerMode',
                 'TriggerSource', 'AcquisitionMode', 'AcquisitionFrameRate',
                 'AcquisitionFrameRateEnable', 'GammaEnable', 'Gamma')
        result = {}
        for name in names:
            try:
                node = self.node(name, 'CValuePtr')
                result[name] = node.ToString() if self.p.IsReadable(node) else None
            except self.p.SpinnakerException:
                result[name] = None
        return result

    def stream_stats(self):
        result = {}
        for name in ('StreamReceivedFrameCount', 'StreamLostFrameCount',
                     'StreamFailedBufferCount', 'StreamBufferUnderrunCount'):
            try:
                node = self.p.CIntegerPtr(self.camera.GetTLStreamNodeMap().GetNode(name))
                result[name] = node.GetValue() if self.p.IsReadable(node) else None
            except self.p.SpinnakerException:
                result[name] = None
        return result

    def next_image(self):
        issued = None
        if self.triggered:
            node = self.node('TriggerSoftware', 'CCommandPtr')
            if not self.p.IsWritable(node):
                raise RuntimeError('TriggerSoftware is not executable')
            issued = utc()
            node.Execute()
        return self.camera.GetNextImage(self.cfg['timeout_ms']), issued

    def __exit__(self, exc_type, exc, tb):
        errors = []
        for operation in ('end', 'deinit', 'clear', 'release'):
            try:
                if operation == 'end' and self.streaming:
                    self.camera.EndAcquisition()
                if operation == 'deinit' and self.initialized:
                    self.camera.DeInit()
                if operation == 'clear':
                    self.camera = None
                    if self.cameras is not None:
                        self.cameras.Clear()
                    self.cameras = None
                if operation == 'release' and self.system is not None:
                    self.system.ReleaseInstance()
            except Exception as error:
                errors.append(str(error))
        self.streaming = self.initialized = False
        self.system = None
        if errors:
            if exc is not None:
                exc.add_note('SDK cleanup: ' + '; '.join(errors))
            else:
                raise RuntimeError('SDK cleanup: ' + '; '.join(errors))


class Session:
    columns = ('index', 'filename', 'request_id', 'trigger_issued_utc', 'received_utc',
               'camera_timestamp_ns', 'frame_id', 'width', 'height', 'pixel_format',
               'file_bytes', 'save_seconds', 'elapsed_seconds', 'frame_id_gap')

    def __init__(self, root, name, cfg, mode):
        safe_name(name)
        identity = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + uuid.uuid4().hex[:8]
        self.path = Path(root) / f'{name}-{identity}'
        self.path.mkdir(parents=True, exist_ok=False)
        (self.path / 'images').mkdir()
        self.meta = {'schema_version': 1, 'state': 'initializing', 'created_utc': utc(),
                     'mode': mode, 'requested_settings': cfg, 'frames_saved': 0,
                     'incomplete_images': 0, 'observed_frame_id_gaps': 0,
                     'timestamp_clock': 'camera timestamp in ns; not synchronized to host UTC',
                     'losslessness_verified': False}
        self.started = time.monotonic()
        self.previous_id = None
        self.csvfile = (self.path / 'frames.csv').open('x', newline='')
        self.csv = csv.DictWriter(self.csvfile, fieldnames=self.columns)
        self.csv.writeheader()
        self.write()

    def write(self):
        atomic_json(self.path / 'metadata.json', self.meta)

    def capture(self, camera, request_id=''):
        image = None
        try:
            image, issued = camera.next_image()
            received = utc()
            if image.IsIncomplete():
                self.meta['incomplete_images'] += 1
                raise RuntimeError(f'Incomplete image: status {image.GetImageStatus()}')
            index = self.meta['frames_saved']
            filename = f'images/frame-{index:08d}.png'
            destination = self.path / filename
            temporary = destination.with_name(destination.stem + '.partial.png')
            row = {'index': index, 'filename': filename, 'request_id': request_id,
                   'trigger_issued_utc': issued, 'received_utc': received,
                   'camera_timestamp_ns': image.GetTimeStamp(), 'frame_id': image.GetFrameID(),
                   'width': image.GetWidth(), 'height': image.GetHeight(),
                   'pixel_format': image.GetPixelFormatName()}
            gap = 0 if self.previous_id is None else max(0, row['frame_id'] - self.previous_id - 1)
            start = time.monotonic()
            image.Save(str(temporary))
            temporary.replace(destination)
            row.update(file_bytes=destination.stat().st_size,
                       save_seconds=time.monotonic()-start, elapsed_seconds=time.monotonic()-self.started,
                       frame_id_gap=gap)
            self.csv.writerow(row)
            self.csvfile.flush()
            self.previous_id = row['frame_id']
            self.meta['frames_saved'] += 1
            self.meta['observed_frame_id_gaps'] += gap
            self.write()
            return row
        finally:
            if image is not None:
                image.Release()

    def finish(self, error=None):
        self.meta.update(state='error' if error else 'capture_stopped', stopped_utc=utc(),
                         elapsed_seconds=time.monotonic()-self.started)
        if error:
            self.meta['error'] = str(error)
        self.csvfile.close()
        self.write()


def reply(event, **values):
    print('OPTICAL_RESPONSE ' + json.dumps({'event': event, **values}), flush=True)


def capture_run(args, camera_factory=SpinnakerCamera, stop=None):
    cfg = load_config(args.config)
    safe_name(args.name)
    if args.command == 'serve' and (args.duration is not None or args.frames is not None):
        raise ValueError('serve uses capture/stop commands; duration and frames apply to CLI capture')
    if args.serial:
        cfg['serial'] = args.serial
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        raise ValueError('duration must be positive and finite')
    if args.frames is not None and args.frames <= 0:
        raise ValueError('frames must be positive')
    stop = stop or threading.Event()
    mode = args.command
    session = Session(args.output_root, args.name, cfg, mode)
    failure = None
    try:
        with camera_factory(cfg, triggered=mode != 'sequence') as camera:
            session.meta.update(state='ready', camera_settings=camera.settings,
                                stream_before=camera.stream_stats())
            session.write()
            reply('ready', session=str(session.path))
            try:
                if mode == 'serve':
                    # WINDOWS_PIPE_READER: select() on Windows accepts sockets, not stdin pipes.
                    import queue
                    commands = queue.Queue()
                    input_stream = sys.stdin
                    def read_commands():
                        try:
                            for command_line in input_stream:
                                commands.put(command_line)
                        except Exception as error:
                            commands.put(error)
                        finally:
                            commands.put(None)
                    threading.Thread(target=read_commands, daemon=True).start()
                    while not stop.is_set():
                        try:
                            line = commands.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        if isinstance(line, Exception):
                            raise line
                        if line is None:
                            break
                        request = json.loads(line)
                        request_id = safe_name(request['id'])
                        command = request['command']
                        if command == 'stop':
                            reply('stopping', id=request_id)
                            break
                        if command == 'status':
                            reply('status', id=request_id, state='ready', frames=session.meta['frames_saved'])
                        elif command == 'capture':
                            row = session.capture(camera, request_id)
                            reply('captured', id=request_id, session=str(session.path), frame=row)
                        else:
                            raise ValueError(f'Unknown optical command: {command}')
                else:
                    start = time.monotonic()
                    limit = 1 if mode == 'single' else args.frames
                    while not stop.is_set():
                        if limit is not None and session.meta['frames_saved'] >= limit:
                            break
                        if args.duration is not None and time.monotonic()-start >= args.duration:
                            break
                        row = session.capture(camera)
                        reply('captured', session=str(session.path), frame=row)
            finally:
                session.meta['stream_final'] = camera.stream_stats()
    except BaseException as error:
        failure = error
        raise
    finally:
        session.finish(failure)
        reply('finished', session=str(session.path), state=session.meta['state'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['single', 'sequence', 'serve'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--serial', default='')
    parser.add_argument('--name', default='optical')
    parser.add_argument('--output-root', type=Path, default=Path('/data/recordings'))
    parser.add_argument('--duration', type=float)
    parser.add_argument('--frames', type=int)
    args = parser.parse_args()
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        capture_run(args, stop=stop)
    except Exception as error:
        print(f'Optical capture failed: {error}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
