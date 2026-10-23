import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'coordinator'))
import windows_runtime as runtime


class DllLifetimeTests(unittest.TestCase):
    def invoke(self, recorder):
        handles = [Mock(), Mock(), Mock()]
        fake_module = types.ModuleType('event_optical.recorder')
        fake_module.main = recorder
        with patch.object(runtime.sys, 'platform', 'win32'), \
             patch.object(runtime, 'check_paths'), \
             patch.object(runtime, '_DLL_DIRECTORY_HANDLES', []) as retained, \
             patch.object(runtime.os, 'add_dll_directory', side_effect=handles, create=True), \
             patch.object(runtime.signal, 'SIGBREAK', 21, create=True), \
             patch.object(runtime.signal, 'getsignal', return_value=Mock()), \
             patch.object(runtime.signal, 'signal'), \
             patch.dict(runtime.os.environ), \
             patch.dict(sys.modules, {'event_optical.recorder': fake_module}), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                result = runtime.main(['--check'])
            finally:
                self.assertEqual(retained, handles)
                for handle in handles:
                    handle.close.assert_not_called()
        return result

    def test_success_keeps_lookup_paths_registered(self):
        self.assertEqual(self.invoke(Mock(return_value=0)), 0)

    def test_nonzero_recorder_result_is_preserved(self):
        self.assertEqual(self.invoke(Mock(return_value=3)), 3)

    def test_recorder_exception_is_not_suppressed(self):
        with self.assertRaisesRegex(RuntimeError, 'recorder failed'):
            self.invoke(Mock(side_effect=RuntimeError('recorder failed')))


if __name__ == '__main__': unittest.main()
