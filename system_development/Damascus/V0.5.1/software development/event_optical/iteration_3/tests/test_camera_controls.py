import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from event_optical.camera_controls import read_config, apply_settings
from event_optical.stream_telemetry import StreamTelemetry


class BiasInfo:
    def get_bias_range(self): return (-10, 10)
    def is_modifiable(self): return True


class Biases:
    def __init__(self): self.values = {'bias_diff_on': 0, 'bias_diff_off': 0}; self.writes = []
    def get_all_biases(self): return self.values.copy()
    def get_bias_info(self, name): return BiasInfo()
    def get(self, name): return self.values[name]
    def set(self, name, value): self.writes.append((name, value)); self.values[name] = value; return True


class Erc:
    def __init__(self): self.rate = 20000000; self.enabled = False; self.writes = []
    def is_enabled(self): return self.enabled
    def get_cd_event_rate(self): return self.rate
    def get_min_supported_cd_event_rate(self): return 1000000
    def get_max_supported_cd_event_rate(self): return 100000000
    def set_cd_event_rate(self, rate): self.writes.append('rate'); self.rate = rate; return True
    def enable(self, enabled): self.writes.append('enable'); self.enabled = enabled; return True


class Device:
    def __init__(self): self.biases = Biases(); self.erc = Erc()
    def get_i_ll_biases(self): return self.biases
    def get_i_erc_module(self): return self.erc


class ControlTests(unittest.TestCase):
    def test_preflight_rejects_all_before_first_write(self):
        device = Device()
        with self.assertRaises(ValueError):
            apply_settings(device, {'biases': {'bias_diff_on': 2, 'bias_diff_off': 11}}, {})
        self.assertEqual(device.biases.writes, [])
        with self.assertRaises(ValueError):
            apply_settings(device, {'biases': {'bias_diff_on': 2}, 'erc': {'rate_limit_ev_s': 1}}, {})
        self.assertEqual(device.biases.writes, [])

    def test_readback_and_erc_rate_before_enable(self):
        device, report = Device(), {}
        apply_settings(device, {'biases': {'bias_diff_on': 4, 'bias_diff_off': 3},
                                'erc': {'enabled': True, 'rate_limit_ev_s': 10000000}}, report)
        self.assertEqual(report['state'], 'verified')
        self.assertEqual(report['applied']['biases.bias_diff_on']['readback'], 4)
        self.assertEqual(report['applied']['biases.bias_diff_off']['readback'], 3)
        self.assertEqual(device.erc.writes, ['rate', 'enable'])

    def test_mismatched_readback_fails(self):
        device, report = Device(), {}
        device.biases.set = lambda name, value: True
        with self.assertRaisesRegex(ValueError, 'read back 0'):
            apply_settings(device, {'biases': {'bias_diff_on': 4}}, report)
        self.assertEqual(report['applied']['biases.bias_diff_on']['readback'], 0)

    def test_omitted_settings_never_write(self):
        device = Device()
        apply_settings(device, read_config(), {})
        self.assertEqual(device.biases.writes + device.erc.writes, [])

    def test_config_type_and_unknown_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.toml'
            for text in ('[biases]\nbias_diff_on=true', '[erc]\nenabled=1',
                         '[telemetry]\ndecode_events=1', '[telemetry]\ninterval_s=0',
                         '[telemetry]\ninterface="../bad"', '[biases]\nbias_diff=0'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError): read_config(path)

    def test_telemetry_rates_deltas_and_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'stream_telemetry.csv'
            telemetry = StreamTelemetry(path, Device(), read_config()['telemetry'])
            with patch('event_optical.stream_telemetry.read_network', return_value={'nic_rx_bytes': 100, 'host_udp_in_errors': 7}):
                telemetry.start(10)
            class Raw:
                def size(self): return 200
            with patch('event_optical.stream_telemetry.time.monotonic', return_value=10.1):
                telemetry.consume(Raw())
            with patch('event_optical.stream_telemetry.time.monotonic', return_value=10.5), patch(
                    'event_optical.stream_telemetry.read_network', return_value={'nic_rx_bytes': 350, 'host_udp_in_errors': 8}):
                telemetry.sample(240)
            summary = telemetry.summary()
            telemetry.close()
            with path.open() as handle: row = next(csv.DictReader(handle))
            self.assertEqual(float(row['payload_rate_B_s']), 400)
            self.assertEqual(int(row['nic_rx_bytes_delta']), 250)
            self.assertEqual(int(row['host_udp_in_errors_delta']), 1)
            self.assertEqual(row['decoded_cd_events'], '')
            self.assertEqual(row['camera_event_rate_ev_s'], '')
            self.assertIsNone(summary['decoded_cd_events'])

    def test_decoding_callback_reports_timestamp_and_coordinate_errors(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as temp:
            telemetry = StreamTelemetry(Path(temp) / 'stats.csv', Device(), read_config()['telemetry'])
            telemetry.width, telemetry.height = 3, 2
            events = np.array([(0,0,1,10),(1,0,1,11),(3,0,0,9)],
                              dtype=[('x','u2'),('y','u2'),('p','u1'),('t','i8')])
            telemetry.on_events(events)
            self.assertEqual(telemetry.events, 3)
            self.assertEqual(telemetry.negative_ts, 1)
            self.assertEqual(telemetry.bad_coordinates, 1)
            telemetry.close()


if __name__ == '__main__': unittest.main()
