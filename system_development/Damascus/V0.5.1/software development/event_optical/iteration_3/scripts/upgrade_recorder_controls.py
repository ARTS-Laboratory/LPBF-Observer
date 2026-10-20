"""Apply the controls/telemetry integration to the existing recorder, with backup."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'src/event_optical/recorder.py'
text = path.read_text()
marker = '# Camera controls and telemetry integration v1'
if marker in text:
    print('Recorder integration already applied.')
    raise SystemExit(0)
changes = [
('from . import __version__', '''from . import __version__
# Camera controls and telemetry integration v1
from .camera_controls import read_config, apply_settings
from .stream_telemetry import StreamTelemetry'''),
('status_interval=1.0, stop_event=None):', 'status_interval=1.0, stop_event=None, config_path=None):'),
('    stop_event = stop_event if stop_event is not None else threading.Event()',
 '    config = read_config(config_path)\n    stop_event = stop_event if stop_event is not None else threading.Event()'),
('"schema_version": 1,', '"schema_version": 2,'),
('    failure = None\n', '    failure = None\n    telemetry = None\n    meta["camera_controls"] = {}\n'),
('    try:\n        logging_attempted = True', '''    try:
        meta["camera_before_settings"] = meta["camera"]
        apply_settings(device, config, meta["camera_controls"])
        meta["camera"] = camera_metadata(device)
        write_metadata(meta_path, meta)
        telemetry = StreamTelemetry(session / "stream_telemetry.csv", device, config["telemetry"])
        logging_attempted = True'''),
('        start = time.monotonic()\n', '        start = time.monotonic()\n        telemetry.start(start)\n'),
('                    meta["buffers_consumed"] += 1\n                    last_data',
 '                    meta["buffers_consumed"] += 1\n                    telemetry.consume(buffer)\n                    last_data'),
('            if now - last_status >= status_interval:',
 '            telemetry.sample(file_size(raw_path))\n            if now - last_status >= status_interval:'),
('                write_metadata(meta_path, meta)\n                print(',
 '                meta["telemetry"] = telemetry.summary()\n                write_metadata(meta_path, meta)\n                print('),
('        failure = exc\n        meta.update(state="error",',
 '        failure = exc\n        if meta["camera_controls"].get("state") != "verified":\n            meta["camera_controls"]["state"] = "failed"\n        meta.update(state="error",'),
('                        meta["buffers_consumed"] += 1\n                    del buffer',
 '                        meta["buffers_consumed"] += 1\n                        if telemetry is not None:\n                            telemetry.consume(buffer)\n                    del buffer'),
('        meta.update(\n            stopped_utc=utc_now()', '''        if telemetry is not None:
            try:
                telemetry.sample(file_size(raw_path), force=True, phase="stopped")
                meta["telemetry"] = telemetry.summary()
            except Exception as exc:
                meta["cleanup_errors"].append(f"telemetry final sample: {exc}")
            finally:
                try:
                    telemetry.close()
                except Exception as exc:
                    meta["cleanup_errors"].append(f"telemetry close: {exc}")
        meta.update(
            stopped_utc=utc_now()'''),
('    args = parser.parse_args(argv)',
 '    parser.add_argument("--config", type=Path, help="Camera bias/ERC and telemetry TOML settings")\n    args = parser.parse_args(argv)'),
('status_interval=args.status_interval, stop_event=stop)',
 'status_interval=args.status_interval, stop_event=stop, config_path=args.config)'),
]
for old, new in changes:
    if text.count(old) != 1:
        raise SystemExit(f'Expected exactly one integration anchor; found {text.count(old)}: {old!r}. Recorder left unchanged.')
    text = text.replace(old, new)
compile(text, str(path), 'exec')
backup = path.parents[2] / '.build/backups/recorder.py.before-controls'
if backup.exists():
    raise SystemExit(f'Backup already exists; refusing to overwrite: {backup}')
backup.parent.mkdir(parents=True, exist_ok=True)
backup.write_text(path.read_text())
path.write_text(text)
print('Recorder updated. Backup:', backup)
