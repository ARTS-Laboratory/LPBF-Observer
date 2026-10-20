"""Host telemetry; optional native decoding counts CD events without copying them."""
import csv
from datetime import datetime, timezone
import time
from pathlib import Path


def read_network(interface):
    values = {}
    if interface:
        for key in ('rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped', 'rx_missed_errors',
                    'tx_bytes', 'tx_errors', 'tx_dropped'):
            try:
                values['nic_' + key] = int((Path('/sys/class/net') / interface / 'statistics' / key).read_text())
            except (OSError, ValueError):
                values['nic_' + key] = None
    try:
        lines = Path('/proc/net/snmp').read_text().splitlines()
        for index, line in enumerate(lines[:-1]):
            if line.startswith('Udp:') and 'RcvbufErrors' in line:
                udp = dict(zip(line.split()[1:], map(int, lines[index + 1].split()[1:])))
                values['host_udp_in_errors'] = udp.get('InErrors')
                values['host_udp_rcvbuf_errors'] = udp.get('RcvbufErrors')
                break
    except (OSError, ValueError):
        pass
    return values


class StreamTelemetry:
    NETWORK_KEYS = tuple('nic_' + key for key in ('rx_bytes', 'rx_packets', 'rx_errors',
                         'rx_dropped', 'rx_missed_errors', 'tx_bytes', 'tx_errors', 'tx_dropped')) + (
                         'host_udp_in_errors', 'host_udp_rcvbuf_errors')
    FIELDS = ('utc', 'elapsed_seconds', 'phase', 'buffers_consumed', 'raw_payload_bytes',
              'raw_file_bytes', 'payload_rate_B_s', 'buffer_rate_s', 'max_buffer_gap_seconds',
              'decoded_cd_events', 'decoded_cd_event_rate_ev_s', 'negative_timestamp_transitions',
              'out_of_bounds_cd_events', 'camera_event_rate_ev_s', 'gvsp_frame_rate',
              'link_throughput_B_s', 'incomplete_buffers', 'get_buffer_errors') + NETWORK_KEYS + tuple(
              key + '_delta' for key in NETWORK_KEYS)

    def __init__(self, path, device, config):
        self.path = Path(path)
        self.config = config
        self.file = self.path.open('x', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file, fieldnames=self.FIELDS)
        self.writer.writeheader()
        self.start_time = self.last_sample = None
        self.buffers = self.payload = self.last_buffers = self.last_payload = self.last_events = 0
        self.events = self.negative_ts = self.bad_coordinates = 0
        self.last_ts = self.first_ts = self.last_buffer_time = None
        self.max_gap = 0.0
        self.decoder = self.cd = self.callback = None
        self.baseline = {}
        self.samples = 0
        self.last_network = {}
        if config['decode_events']:
            try:
                import numpy  # Load before acquisition, rather than in the first callback.
                self.decoder = device.get_i_events_stream_decoder()
                self.cd = device.get_i_event_cd_decoder()
                geometry = device.get_i_geometry()
                if self.decoder is None or self.cd is None or geometry is None:
                    raise ValueError('CD decoding requested but required HAL facilities unavailable')
                self.width, self.height = geometry.get_width(), geometry.get_height()
                self.callback = self.cd.add_event_buffer_callback(self.on_events)
            except BaseException:
                self.file.close()
                raise

    def on_events(self, events):
        if not len(events):
            return
        # Vectorized reduction only; no event conversion, copying, or HDF5 writing.
        import numpy as np
        ts = events['t']
        if self.first_ts is None:
            self.first_ts = int(ts[0])
        if self.last_ts is not None and int(ts[0]) < self.last_ts:
            self.negative_ts += 1
        self.negative_ts += int(np.count_nonzero(ts[1:] < ts[:-1]))
        self.last_ts = int(ts[-1])
        self.events += len(events)
        self.bad_coordinates += int(np.count_nonzero((events['x'] < 0) | (events['x'] >= self.width) |
                                                     (events['y'] < 0) | (events['y'] >= self.height)))

    def start(self, started):
        self.start_time = self.last_sample = self.last_buffer_time = started
        self.baseline = read_network(self.config['interface'])

    def consume(self, raw):
        now = time.monotonic()
        if self.last_buffer_time is not None:
            self.max_gap = max(self.max_gap, now - self.last_buffer_time)
        self.last_buffer_time = now
        self.buffers += 1
        self.payload += raw.size() if hasattr(raw, "size") else len(raw)
        if self.decoder is not None:
            self.decoder.decode(raw)

    def sample(self, raw_file_bytes, *, force=False, phase='recording'):
        if self.start_time is None:
            return
        now = time.monotonic()
        interval = now - self.last_sample
        if not force and interval < self.config['interval_s']:
            return
        network = read_network(self.config['interface'])
        row = {'utc': datetime.now(timezone.utc).isoformat(), 'elapsed_seconds': now - self.start_time,
               'phase': phase, 'buffers_consumed': self.buffers, 'raw_payload_bytes': self.payload,
               'raw_file_bytes': raw_file_bytes,
               'payload_rate_B_s': (self.payload - self.last_payload) / interval if interval > 0 else None,
               'buffer_rate_s': (self.buffers - self.last_buffers) / interval if interval > 0 else None,
               'max_buffer_gap_seconds': self.max_gap}
        if self.decoder is not None:
            row.update(decoded_cd_events=self.events,
                       decoded_cd_event_rate_ev_s=(self.events - self.last_events) / interval if interval > 0 else None,
                       negative_timestamp_transitions=self.negative_ts, out_of_bounds_cd_events=self.bad_coordinates)
        for key in self.NETWORK_KEYS:
            value, initial = network.get(key), self.baseline.get(key)
            row[key] = value
            row[key + '_delta'] = value - initial if value is not None and initial is not None and value >= initial else None
        self.writer.writerow(row)
        self.file.flush()
        self.samples += 1
        self.last_network = network
        self.last_sample = now
        self.last_buffers, self.last_payload, self.last_events = self.buffers, self.payload, self.events

    def summary(self):
        return {'file': self.path.name, 'samples': self.samples, 'settings': self.config,
                'raw_payload_bytes_consumed': self.payload,
                'decoded_cd_events': self.events if self.decoder is not None else None,
                'first_cd_timestamp_us': self.first_ts, 'last_cd_timestamp_us': self.last_ts,
                'negative_timestamp_transitions': self.negative_ts if self.decoder is not None else None,
                'out_of_bounds_cd_events': self.bad_coordinates if self.decoder is not None else None,
                'network_baseline': self.baseline, 'network_final': self.last_network,
                'unavailable_camera_fields': ['camera_event_rate_ev_s', 'gvsp_frame_rate',
                                              'link_throughput_B_s', 'incomplete_buffers', 'get_buffer_errors']}

    def close(self):
        try:
            if self.callback is not None:
                self.cd.remove_callback(self.callback)
                self.callback = None
        finally:
            self.file.close()
