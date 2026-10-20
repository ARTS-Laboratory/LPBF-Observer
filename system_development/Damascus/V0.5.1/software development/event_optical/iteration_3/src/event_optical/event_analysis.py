"""Analyze saved CD events in sensor-time bins without affecting acquisition."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

import numpy as np

from .reconstruction import read_events, json_default


class EventAnalysis:
    FIELDS = ('bin_index', 'start_timestamp_us', 'end_timestamp_us_exclusive',
              'relative_start_s', 'relative_end_s', 'duration_us', 'partial_bin',
              'cd_events', 'positive_events', 'negative_events', 'cd_event_rate_ev_s')

    def __init__(self, output, bin_us):
        if type(bin_us) is not int or bin_us <= 0:
            raise ValueError('bin_us must be a positive integer')
        self.output, self.bin_us = Path(output), bin_us
        self.handle = None
        self.first = self.last = None
        self.total = self.positive_total = self.negative_total = 0
        self.current = self.count = self.positive = self.bins = 0
        self.negative_transitions = self.invalid_coordinates = self.invalid_polarities = 0
        self.maximum_bin_rate = 0.0
        self.width = self.height = None
        self.source_metadata = {}

    def begin(self, width, height, metadata):
        self.width, self.height = width, height
        self.source_metadata = metadata
        self.handle = (self.output / 'event_rate.csv').open('x', newline='')
        self.writer = csv.DictWriter(self.handle, fieldnames=self.FIELDS)
        self.writer.writeheader()

    def feed(self, events):
        if not len(events):
            return
        if not events.dtype.names or not {'x', 'y', 'p', 't'} <= set(events.dtype.names):
            raise ValueError('Events must contain x/y/p/t fields')
        if any(events.dtype.fields[key][0].kind not in 'iu' for key in ('x', 'y', 't')):
            raise ValueError('Coordinates and timestamps must be integers (timestamps in microseconds)')
        ts = events['t'].astype(np.int64)
        reversals = int(np.count_nonzero(ts[1:] < ts[:-1]))
        reversals += int(self.last is not None and int(ts[0]) < self.last)
        self.negative_transitions += reversals
        if reversals:
            raise ValueError('Timestamp reversal detected; analysis is incomplete')
        invalid = int(np.count_nonzero((events['x'] < 0) | (events['x'] >= self.width) |
                                      (events['y'] < 0) | (events['y'] >= self.height)))
        self.invalid_coordinates += invalid
        bad_polarity = int(np.count_nonzero((events['p'] != 0) & (events['p'] != 1)))
        self.invalid_polarities += bad_polarity
        if invalid or bad_polarity:
            raise ValueError('Invalid CD coordinates or polarity; analysis is incomplete')
        if self.first is None:
            self.first = int(ts[0])
        self.last = int(ts[-1])
        self.total += len(events)
        positive = events['p'].astype(bool)
        self.positive_total += int(np.count_nonzero(positive))
        self.negative_total = self.total - self.positive_total
        indices = (ts - self.first) // self.bin_us
        unique, offsets, counts = np.unique(indices, return_index=True, return_counts=True)
        # Per-buffer grouped reduction; memory scales with the chunk, not file size.
        pos_counts = np.add.reduceat(positive.astype(np.int64), offsets)
        for index, count, pos_count in zip(unique, counts, pos_counts):
            while self.current < int(index):
                self.write_bin(self.first + (self.current + 1) * self.bin_us)
            self.count += int(count)
            self.positive += int(pos_count)

    def write_bin(self, end):
        start = self.first + self.current * self.bin_us
        duration = end - start
        rate = self.count * 1_000_000 / duration
        self.writer.writerow(dict(bin_index=self.current, start_timestamp_us=start,
                                  end_timestamp_us_exclusive=end,
                                  relative_start_s=(start - self.first) / 1e6,
                                  relative_end_s=(end - self.first) / 1e6,
                                  duration_us=duration, partial_bin=duration < self.bin_us,
                                  cd_events=self.count, positive_events=self.positive,
                                  negative_events=self.count - self.positive,
                                  cd_event_rate_ev_s=rate))
        self.maximum_bin_rate = max(self.maximum_bin_rate, rate)
        self.bins += 1
        self.current += 1
        self.count = self.positive = 0

    def finish(self):
        if not self.total:
            raise ValueError('Recording contains no decoded CD events')
        self.write_bin(self.last + 1)
        self.handle.flush()
        return self.summary()

    def summary(self):
        coverage = None if self.first is None else (self.last - self.first + 1) / 1e6
        host_seconds = self.source_metadata.get('recorder_metadata', {}).get('elapsed_seconds')
        return {'width': self.width, 'height': self.height, 'bin_us': self.bin_us,
                'bins_written': self.bins, 'decoded_cd_events': self.total,
                'positive_events': self.positive_total, 'negative_events': self.negative_total,
                'first_cd_timestamp_us': self.first, 'last_cd_timestamp_us': self.last,
                'cd_event_span_seconds': coverage,
                'host_capture_elapsed_seconds': host_seconds,
                'event_span_to_host_duration_ratio': coverage / host_seconds if coverage is not None and host_seconds else None,
                'mean_cd_event_rate_ev_s': self.total / coverage if coverage else None,
                'maximum_bin_cd_event_rate_ev_s': self.maximum_bin_rate if self.bins else None,
                'negative_timestamp_transitions': self.negative_transitions,
                'out_of_bounds_cd_events': self.invalid_coordinates,
                'invalid_polarity_events': self.invalid_polarities,
                'decoder_protocol_warning_count': None, 'losslessness_verified': False,
                'source_metadata': self.source_metadata}

    def close(self):
        if self.handle is not None:
            self.handle.close()


def plot_rates(csv_path, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with Path(csv_path).open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    # Include rightmost edge for a step plot of half-open time bins.
    x = [float(row['relative_start_s']) for row in rows]
    x.append(float(rows[-1]['relative_end_s']))
    duration = np.array([float(row['duration_us']) for row in rows]) / 1e6
    fig, axis = plt.subplots(figsize=(11, 4))
    for key, label in [('cd_events', 'All CD'), ('positive_events', 'Positive'), ('negative_events', 'Negative')]:
        rates = np.array([int(row[key]) for row in rows]) / duration / 1e6
        axis.step(x, list(rates) + [rates[-1]], where='post', label=label)
    axis.set(xlabel='Sensor time relative to first CD event (s)', ylabel='Million decoded CD events/s',
             title='Offline CD event rate')
    axis.grid(alpha=.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def analyze(path, output_root, *, bin_us=250000, make_plot=False):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    output = Path(output_root) / (path.parent.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    worker = EventAnalysis(output, bin_us)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'state': 'running', 'source_file': str(path)}
    try:
        read_events(path, worker)
        report.update(worker.finish(), state='complete')
    except BaseException as error:
        report.update(worker.summary(), state='incomplete', error=str(error))
        raise
    finally:
        worker.close()
        report['analysis_wall_seconds'] = time.monotonic() - started
        (output / 'summary.json').write_text(json.dumps(report, indent=2, default=json_default) + '\n')
        print(f'Analysis: {output}', flush=True)
    if make_plot:
        # Plot failure does not invalidate the completed CSV/summary analysis.
        plot_rates(output / 'event_rate.csv', output / 'event_rate_plot.png')
    for key in ('decoded_cd_events', 'cd_event_span_seconds', 'host_capture_elapsed_seconds',
                'mean_cd_event_rate_ev_s', 'negative_timestamp_transitions', 'out_of_bounds_cd_events'):
        print(f'{key}: {report[key]}')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--bin-us', type=int, default=250000)
    parser.add_argument('--output-root', type=Path, default=Path('data/analysis'))
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args(argv)
    try:
        analyze(args.input, args.output_root, bin_us=args.bin_us, make_plot=args.plot)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(1, f'Analysis failed: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
