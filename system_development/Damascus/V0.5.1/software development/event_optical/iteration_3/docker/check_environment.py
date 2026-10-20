"""Check container imports and native offline prerequisites without a camera."""
import importlib
import os
from pathlib import Path
import platform
import sys

print('Python:', platform.python_version())
if sys.version_info[:2] != (3,12):
    raise SystemExit('Python 3.12 required')
flags=sys.getdlopenflags()
try:
    sys.setdlopenflags(flags | os.RTLD_GLOBAL)
    hal=importlib.import_module('metavision_hal')
finally:
    sys.setdlopenflags(flags)
print('HAL:',hal.__file__)
for name in ('numpy','cv2','h5py','matplotlib'):
    module=importlib.import_module(name)
    print(name + ':',module.__version__)
plugin=Path(os.environ['MV_HAL_PLUGIN_PATH'])/'libhal_plugin_prophesee.so'
if not plugin.is_file():
    raise SystemExit(f'Missing offline plugin: {plugin}')
print('Offline plugin:',plugin.resolve())
manifest=Path('/opt/build-info/openeb-commit.txt')
print('OpenEB commit:',manifest.read_text().strip())
print('No camera opened. Live discovery/capture require separate network/SDK checks.')
