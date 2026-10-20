"""Inspect LUCID HAL controls without configuring or starting acquisition."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys

FACILITIES = {
    'biases': 'get_i_ll_biases',
    'erc': 'get_i_erc_module',
    'monitoring': 'get_i_monitoring',
    'roi': 'get_i_roi',
    'trail_filter': 'get_i_event_trail_filter_module',
    'antiflicker': 'get_i_antiflicker_module',
    'hardware_register': 'get_i_hw_register',
    'event_rate': 'get_i_event_rate',
}


def query(obj, method, *args):
    try:
        result = getattr(obj, method)(*args)
        # Convert ranges and plain SDK enums when needed; never use a setter.
        return json.loads(json.dumps(result, default=str))
    except Exception as error:
        return {'unavailable': str(error)}


def inspect(device):
    from event_optical.recorder import camera_metadata
    report = {'camera': camera_metadata(device), 'facilities': {}}
    facilities = {}
    for label, getter in FACILITIES.items():
        try:
            facility = getattr(device, getter)()
            if facility is None:
                report['facilities'][label] = {'available': False}
                continue
            facilities[label] = facility
            report['facilities'][label] = {
                'available': True,
                'methods': [name for name in dir(facility) if not name.startswith('_')],
            }
        except Exception as error:
            report['facilities'][label] = {'available': False, 'error': str(error)}
    if 'biases' in facilities:
        facility = facilities['biases']
        values = query(facility, 'get_all_biases')
        details = {}
        if isinstance(values, dict) and 'unavailable' not in values:
            for name, value in values.items():
                entry = {'value': value}
                try:
                    info = facility.get_bias_info(name)
                    for method in ('get_description', 'get_bias_range', 'get_bias_allowed_range',
                                   'get_bias_recommended_range', 'is_modifiable'):
                        entry[method] = query(info, method)
                except Exception as error:
                    entry['info_unavailable'] = str(error)
                details[name] = entry
        report['bias_details'] = details
        report['bias_values'] = values
    readouts = {
        'erc': ('is_enabled', 'get_cd_event_rate', 'get_min_supported_cd_event_rate',
                'get_max_supported_cd_event_rate', 'get_event_count_period_us', 'get_cd_event_count'),
        'monitoring': ('get_temperature', 'get_illumination', 'get_pixel_dead_time'),
        'trail_filter': ('is_enabled', 'get_type', 'get_threshold'),
        'antiflicker': ('is_enabled', 'get_frequency_band'),
    }
    for label, methods in readouts.items():
        if label in facilities:
            report['facilities'][label]['readouts'] = {
                method: query(facilities[label], method) for method in methods
                if hasattr(facilities[label], method)
            }
    # Report available extension names without calling undocumented vendor getters.
    report['device_facility_getters'] = [name for name in dir(device) if name.startswith('get_i_')]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='')
    parser.add_argument('--output', type=Path, default=Path('data/debug/camera-controls.json'))
    args = parser.parse_args()
    flags = sys.getdlopenflags() if sys.platform.startswith('linux') else None
    try:
        if flags is not None:
            sys.setdlopenflags(flags | os.RTLD_GLOBAL)
        hal = importlib.import_module('metavision_hal')
    finally:
        if flags is not None:
            sys.setdlopenflags(flags)
    from event_optical.recorder import select_serial
    serial = select_serial(hal.DeviceDiscovery, args.serial)
    device = hal.DeviceDiscovery.open(serial)
    if device is None:
        raise RuntimeError(f'Unable to open camera: {serial}')
    try:
        report = inspect(device)
        report['selected_source'] = serial
        text = json.dumps(report, indent=2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
        print(text)
        print(f'\nSaved: {args.output}')
    finally:
        device = None


if __name__ == '__main__':
    main()
