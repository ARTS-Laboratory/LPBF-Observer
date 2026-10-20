"""Validate and apply supported HAL bias/ERC settings before acquisition."""
import math
import tomllib
from pathlib import Path

BIAS_NAMES = {'bias_diff_on', 'bias_diff_off', 'bias_fo', 'bias_hpf', 'bias_refr'}


def read_config(path=None):
    config = {}
    if path is not None:
        with Path(path).open('rb') as handle:
            config = tomllib.load(handle)
    unknown = set(config) - {'biases', 'erc', 'telemetry'}
    if unknown:
        raise ValueError(f'Unknown recorder config sections: {sorted(unknown)}')
    allowed = {'biases': BIAS_NAMES, 'erc': {'enabled', 'rate_limit_ev_s'},
               'telemetry': {'interval_s', 'interface', 'decode_events'}}
    for section, keys in allowed.items():
        values = config.get(section, {})
        if not isinstance(values, dict) or set(values) - keys:
            raise ValueError(f'Unknown or invalid [{section}] settings')
    for name, value in config.get('biases', {}).items():
        if type(value) is not int:
            raise ValueError(f'{name} must be an integer bias offset')
    erc = config.get('erc', {})
    if 'enabled' in erc and type(erc['enabled']) is not bool:
        raise ValueError('erc.enabled must be true or false')
    if 'rate_limit_ev_s' in erc and (type(erc['rate_limit_ev_s']) is not int or erc['rate_limit_ev_s'] <= 0):
        raise ValueError('ERC rate limit must be a positive integer events/s')
    telemetry = config.setdefault('telemetry', {})
    telemetry.setdefault('interval_s', .25)
    telemetry.setdefault('decode_events', False)
    telemetry.setdefault('interface', '')
    interval = telemetry['interval_s']
    if type(interval) not in (int, float) or not math.isfinite(interval) or interval <= 0:
        raise ValueError('telemetry.interval_s must be finite and positive')
    if type(telemetry['decode_events']) is not bool:
        raise ValueError('telemetry.decode_events must be true or false')
    interface = telemetry['interface']
    if not isinstance(interface, str) or interface in ('.', '..') or '/' in interface:
        raise ValueError('Invalid telemetry network interface name')
    return config


def required(device, getter):
    facility = getattr(device, getter, lambda: None)()
    if facility is None:
        raise ValueError(f'Requested camera control unavailable: {getter}')
    return facility


def apply_settings(device, config, report):
    """Preflight all settings, then write and read back; report partial failures.

    Writes are not atomic. On error capture does not start, but successful camera
    writes remain applied and are described in the caller's metadata report.
    """
    report.update(requested={'biases': config.get('biases', {}), 'erc': config.get('erc', {})},
                  before={}, applied={}, state='validating')
    operations = []
    biases = config.get('biases', {})
    if biases:
        facility = required(device, 'get_i_ll_biases')
        available = facility.get_all_biases()
        report['before']['biases'] = dict(available)
        for name, value in biases.items():
            if name not in available:
                raise ValueError(f'Camera does not expose bias {name}')
            info = facility.get_bias_info(name)
            low, high = info.get_bias_range()
            if not info.is_modifiable() or not low <= value <= high:
                raise ValueError(f'{name}={value} not writable or outside [{low}, {high}]')
            operations.append(('biases.' + name, lambda n=name, v=value: facility.set(n, v),
                               lambda n=name: facility.get(n), value))
    erc_config = config.get('erc', {})
    if erc_config:
        erc = required(device, 'get_i_erc_module')
        report['before']['erc'] = {'enabled': erc.is_enabled(), 'rate_limit_ev_s': erc.get_cd_event_rate()}
        if 'rate_limit_ev_s' in erc_config:
            rate = erc_config['rate_limit_ev_s']
            low, high = erc.get_min_supported_cd_event_rate(), erc.get_max_supported_cd_event_rate()
            if not low <= rate <= high:
                raise ValueError(f'ERC rate {rate} outside [{low}, {high}] events/s')
            operations.append(('erc.rate_limit_ev_s', lambda: erc.set_cd_event_rate(rate), erc.get_cd_event_rate, rate))
        if 'enabled' in erc_config:
            enabled = erc_config['enabled']
            operations.append(('erc.enabled', lambda: erc.enable(enabled), erc.is_enabled, enabled))
    report['state'] = 'applying'
    for key, setter, getter, requested in operations:
        result = setter()
        actual = getter()
        report['applied'][key] = {'requested': requested, 'readback': actual, 'setter_result': result}
        if result is False or actual != requested:
            raise ValueError(f'{key}: requested {requested}, read back {actual}, setter returned {result}; capture not started')
    report['state'] = 'verified'
