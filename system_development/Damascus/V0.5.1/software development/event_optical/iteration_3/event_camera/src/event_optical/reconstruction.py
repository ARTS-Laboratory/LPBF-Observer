"""Stream RAW or legacy H5 events into consecutive PNG windows and curated H5."""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tomllib
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np

MODES = ('binary', 'count_linear', 'count_log', 'signed_linear', 'signed_log')
EVENT_DTYPE = np.dtype([('x', '<u2'), ('y', '<u2'), ('p', 'u1'), ('t', '<i8')])
BACKGROUND = np.array([40, 40, 40], dtype=np.float64)
POSITIVE = np.array([0, 0, 255], dtype=np.float64)  # OpenCV BGR
NEGATIVE = np.array([255, 0, 0], dtype=np.float64)


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def read_raw_header(path):
    lines = []
    with path.open('rb') as handle:
        for _ in range(256):
            line = handle.readline(4096)
            if not line.startswith(b'%'):
                break
            lines.append(line.decode('utf-8', errors='replace').rstrip())
            if line.strip() == b'% end':
                return lines, handle.tell()
    raise ValueError("RAW header has no '% end' marker")


def read_events(path, consumer):
    """Consumer has begin(width, height, metadata) and feed(events)."""
    if path.suffix.lower() in ('.h5', '.hdf5'):
        import h5py
        with h5py.File(path, 'r') as source:
            dataset = source['events']
            consumer.begin(int(source.attrs['width']), int(source.attrs['height']),
                           {'source_h5_attributes': dict(source.attrs),
                            'source_event_attributes': dict(dataset.attrs)})
            for start in range(0, len(dataset), 262144):
                consumer.feed(dataset[start:start + 262144])
        return
    if path.suffix.lower() != '.raw':
        raise ValueError('Input must be .raw, .h5, or .hdf5')
    lines, offset = read_raw_header(path)
    payload_bytes = path.stat().st_size - offset
    if payload_bytes % 2:
        raise ValueError('RAW payload ends with an incomplete 16-bit word')
    flags = sys.getdlopenflags() if sys.platform.startswith('linux') else None
    try:
        if flags is not None:
            sys.setdlopenflags(flags | os.RTLD_GLOBAL)
        hal = importlib.import_module('metavision_hal')
    finally:
        if flags is not None:
            sys.setdlopenflags(flags)
    config = hal.RawFileConfig()
    config.build_index = False
    config.n_events_to_read = 524288
    device = hal.DeviceDiscovery.open_raw_file(str(path.resolve()), config)
    if device is None:
        raise RuntimeError('Unable to open RAW file')
    geometry = device.get_i_geometry()
    stream = device.get_i_events_stream()
    decoder = device.get_i_events_stream_decoder()
    cd = device.get_i_event_cd_decoder()
    if any(item is None for item in (geometry, stream, decoder, cd)):
        raise RuntimeError('RAW file lacks required geometry or CD decoder')
    metadata = {'raw_header_lines': lines}
    sidecar = path.with_name('metadata.json')
    if sidecar.exists():
        metadata['recorder_metadata'] = json.loads(sidecar.read_text())
    consumer.begin(geometry.get_width(), geometry.get_height(), metadata)
    callback = cd.add_event_buffer_callback(consumer.feed)
    fed = 0
    try:
        stream.start()
        while stream.wait_next_buffer() > 0:
            raw = stream.get_latest_raw_data()
            if raw is not None:
                decoder.decode(raw)
                fed += raw.size()
            del raw
        if fed != payload_bytes:
            raise RuntimeError(f'Incomplete RAW read: {fed} / {payload_bytes} payload bytes')
    finally:
        try:
            stream.stop()
        finally:
            cd.remove_callback(callback)


class Reconstruction:
    def __init__(self, output, *, window_us=100000, start_s=0, end_s=None, modes=MODES):
        if isinstance(window_us, bool) or not isinstance(window_us, int) or window_us <= 0:
            raise ValueError('window_us must be a positive integer')
        start_s = 0 if start_s is None else start_s
        if not math.isfinite(start_s) or start_s < 0:
            raise ValueError('start_s must be finite and nonnegative')
        if end_s is not None and (not math.isfinite(end_s) or end_s <= start_s):
            raise ValueError('end_s must be finite and greater than start_s')
        if not modes or len(set(modes)) != len(modes) or set(modes) - set(MODES):
            raise ValueError(f'modes must be unique values from {MODES}')
        self.output = Path(output)
        self.window_us = window_us
        self.start_offset = round(start_s * 1_000_000)
        self.end_offset = None if end_s is None else round(end_s * 1_000_000)
        if self.end_offset is not None and self.end_offset <= self.start_offset:
            raise ValueError('Selected range is shorter than timestamp precision (1 us)')
        self.modes = tuple(modes)
        self.first = self.last = None
        self.selected = self.frames = self.frame_events = 0
        self.h5 = self.manifest = None
        self.metadata = {}

    def begin(self, width, height, metadata):
        import h5py
        if width <= 0 or height <= 0 or width > 65536 or height > 65536:
            raise ValueError('Unsupported event geometry')
        self.width, self.height = width, height
        self.metadata = metadata
        self.h5 = h5py.File(self.output / 'curated.h5', 'x')
        # Keep original H5 metadata, including exact attribute types.
        for key, value in metadata.get('source_h5_attributes', {}).items():
            self.h5.attrs[key] = value
        self.dataset = self.h5.create_dataset('events', shape=(0,), maxshape=(None,),
                                             dtype=EVENT_DTYPE, chunks=(65536,),
                                             compression='gzip', compression_opts=4)
        for key, value in metadata.get('source_event_attributes', {}).items():
            self.dataset.attrs[key] = value
        self.h5.attrs['width'], self.h5.attrs['height'] = width, height
        self.h5.attrs['timestamp_unit'] = 'us'
        self.h5.attrs['timestamps_rebased'] = False
        self.h5.attrs['reconstruction_complete'] = False
        # Preserve source information separately from updated curated attributes.
        self.h5.create_dataset('source_metadata_json', data=json.dumps(metadata, default=json_default),
                               dtype=h5py.string_dtype('utf-8'))
        for mode in self.modes:
            (self.output / mode).mkdir()
        self.manifest = (self.output / 'frames.jsonl').open('x')
        self.positive = np.zeros(width * height, dtype=np.int64)
        self.negative = np.zeros_like(self.positive)
        self.latest = np.zeros(width * height, dtype=np.int8)

    def feed(self, events):
        if not len(events):
            return
        if not events.dtype.names or not {'x', 'y', 'p', 't'} <= set(events.dtype.names):
            raise ValueError('Event dataset must contain x, y, p, t fields')
        if any(events.dtype.fields[name][0].kind not in 'iu' for name in ('x', 'y', 't')):
            raise ValueError('Coordinates and timestamps must be integers; timestamps use microseconds')
        ts = events['t'].astype(np.int64)
        if (self.last is not None and int(ts[0]) < self.last) or np.any(ts[1:] < ts[:-1]):
            raise ValueError('Timestamp reversal detected; reconstruction stopped without discarding events')
        if (np.any(events['x'] < 0) or np.any(events['x'] >= self.width) or
                np.any(events['y'] < 0) or np.any(events['y'] >= self.height)):
            raise ValueError('Out-of-bounds event coordinate')
        if not np.all((events['p'] == 0) | (events['p'] == 1)):
            raise ValueError('Expected polarity encoded as 0 or 1')
        if self.first is None:
            self.first = int(ts[0])
            self.start = self.first + self.start_offset
            self.end = None if self.end_offset is None else self.first + self.end_offset
            self.cursor = self.start
        self.last = int(ts[-1])
        left = int(np.searchsorted(ts, self.start))
        right = len(ts) if self.end is None else int(np.searchsorted(ts, self.end))
        selected = events[left:right]
        if len(selected):
            canonical = np.empty(len(selected), dtype=EVENT_DTYPE)
            for name in EVENT_DTYPE.names:
                canonical[name] = selected[name]
            old = len(self.dataset)
            self.dataset.resize((old + len(selected),))
            self.dataset[old:] = canonical
            self.selected += len(selected)
            pos = left
            while pos < right:
                frame_end = self.cursor + self.window_us
                if self.end is not None:
                    frame_end = min(frame_end, self.end)
                if int(ts[pos]) >= frame_end:
                    self.save_frame(frame_end)
                    continue
                stop = min(right, int(np.searchsorted(ts, frame_end)))
                part = events[pos:stop]
                pixels = part['y'].astype(np.int64) * self.width + part['x']
                polarity = part['p'].astype(bool)
                np.add.at(self.positive, pixels[polarity], 1)
                np.add.at(self.negative, pixels[~polarity], 1)
                # Last event at each pixel wins, including repeated pixels in a buffer.
                unique, reverse_index = np.unique(pixels[::-1], return_index=True)
                self.latest[unique] = np.where(polarity[::-1][reverse_index], 1, -1)
                self.frame_events += len(part)
                pos = stop
        # Advance empty windows when later events establish elapsed time.
        limit = self.last if self.end is None else min(self.last, self.end)
        while self.cursor + self.window_us <= limit:
            self.save_frame(self.cursor + self.window_us)

    def save_frame(self, end):
        import cv2
        total = (self.positive + self.negative).reshape(self.height, self.width)
        signed = (self.positive - self.negative).reshape(self.height, self.width)
        latest = self.latest.reshape(self.height, self.width)
        filename = f'frame_{self.frames:08d}_{self.cursor - self.first:012d}us.png'
        for mode in self.modes:
            if mode.startswith('count_'):
                values = total.astype(np.float64)
                if mode == 'count_log':
                    values = np.log1p(values)
                low, high = values.min(), values.max()
                scaled = np.zeros_like(values) if high == low else (values - low) / (high - low)
                image = cv2.applyColorMap((scaled * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
            else:
                values = latest if mode == 'binary' else signed
                strength = np.abs(values).astype(np.float64)
                if mode == 'signed_log':
                    strength = np.log1p(strength)
                maximum = strength.max()
                if maximum:
                    strength /= maximum
                colors = np.where((values > 0)[..., None], POSITIVE, NEGATIVE)
                image = np.rint(BACKGROUND + strength[..., None] * (colors - BACKGROUND)).astype(np.uint8)
            if not cv2.imwrite(str(self.output / mode / filename), image):
                raise OSError(f'Unable to write PNG: {filename}')
        self.manifest.write(json.dumps({'frame': self.frames, 'filename': filename,
                                      'start_us': self.cursor, 'end_us_exclusive': end,
                                      'relative_start_s': (self.cursor - self.first) / 1e6,
                                      'relative_end_s': (end - self.first) / 1e6,
                                      'events': self.frame_events}) + '\n')
        self.frames += 1
        if self.frames % 50 == 0:
            print(f'{self.frames} frames; {self.selected:,} selected events', flush=True)
        self.positive.fill(0)
        self.negative.fill(0)
        self.latest.fill(0)
        self.frame_events = 0
        self.cursor = end

    def finish(self):
        if not self.selected:
            raise ValueError('Selected interval contains no CD events')
        # Add one microsecond to include the last event in a half-open interval.
        effective_end = self.last + 1 if self.end is None else min(self.end, self.last + 1)
        while self.cursor < effective_end:
            self.save_frame(min(self.cursor + self.window_us, effective_end))
        attributes = {'curated': True, 'total_events': self.selected,
                      'duration_seconds': (effective_end - self.start) / 1e6,
                      'curated_start_seconds': self.start_offset / 1e6,
                      'curated_end_seconds': (effective_end - self.first) / 1e6,
                      'recording_first_timestamp_us': self.first,
                      'selection_start_us': self.start, 'selection_end_us_exclusive': effective_end,
                      'window_us': self.window_us, 'reconstruction_complete': True}
        for key, value in attributes.items():
            self.h5.attrs[key] = value
        self.h5.flush()
        return attributes

    def close(self):
        if self.manifest is not None:
            self.manifest.close()
        if self.h5 is not None:
            self.h5.close()


def reconstruct(path, output_root, **settings):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    output = Path(output_root) / (path.parent.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    reconstruction = Reconstruction(output, **settings)
    output.mkdir(parents=True, exist_ok=False)
    report = {'state': 'running', 'source_file': str(path), 'settings': settings}
    try:
        read_events(path, reconstruction)
        attributes = reconstruction.finish()
        reconstruction.h5.attrs['source_file'] = str(path)
        report.update(state='complete', frames=reconstruction.frames,
                      selection=attributes, source_metadata=reconstruction.metadata)
    except BaseException as error:
        report.update(state='incomplete', error=str(error))
        raise
    finally:
        reconstruction.close()
        (output / 'metadata.json').write_text(json.dumps(report, indent=2, default=json_default) + '\n')
        print(f'Reconstruction: {output}', flush=True)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output-root', type=Path, default=Path('data/reconstructions'))
    parser.add_argument('--window-us', type=int)
    parser.add_argument('--start-s', type=float)
    parser.add_argument('--end-s', type=float)
    parser.add_argument('--modes', nargs='+', choices=MODES)
    args = parser.parse_args(argv)
    settings = {}
    if args.config:
        with args.config.open('rb') as handle:
            settings = tomllib.load(handle).get('reconstruction', {})
        unknown = set(settings) - {'window_us', 'start_s', 'end_s', 'modes'}
        if unknown:
            parser.error(f'Unknown configuration settings: {sorted(unknown)}')
    for key in ('window_us', 'start_s', 'end_s', 'modes'):
        if getattr(args, key) is not None:
            settings[key] = getattr(args, key)
    try:
        reconstruct(args.input, args.output_root, **settings)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        parser.exit(1, f'Reconstruction failed: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
