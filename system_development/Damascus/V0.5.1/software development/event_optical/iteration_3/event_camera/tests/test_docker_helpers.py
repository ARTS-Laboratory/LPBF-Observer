"""Check Docker command construction/dispatch without a Docker daemon."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DockerHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='container helpers ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        mock = '#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n'
        for name in ('docker','python'):
            executable = self.bin / name
            executable.write_text(mock)
            executable.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        EVENT_DATA_DIR=str(self.base / 'data with spaces'), EVENT_CONFIG_DIR=str(ROOT / 'config'))

    def invoke(self, script, *args, env=None, expected=0):
        process = subprocess.run(['bash', str(ROOT / 'docker' / script), *args],
                                 env=env or self.env, capture_output=True, text=True)
        self.assertEqual(process.returncode, expected, process.stderr)
        return process

    def test_offline_mount_keeps_spaces_and_avoids_host_network(self):
        args=json.loads(self.invoke('run.sh','analyze','/data/a b/events.raw','--plot').stdout)
        self.assertIn('/data/a b/events.raw',args)
        self.assertIn(f'type=bind,source={self.base / "data with spaces"},target=/data',args)
        self.assertNotIn('--network',args)

    def test_live_only_mount_and_host_network(self):
        sdk=self.base/'sdk';sdk.mkdir()
        args=json.loads(self.invoke('run.sh','record','--list',env=dict(self.env,ARENA_ROOT=str(sdk))).stdout)
        self.assertEqual(args[args.index('--network')+1],'host')
        self.assertIn(f'type=bind,source={sdk},target=/sdk/arena,readonly',args)
        self.assertEqual(args[-2:],['record','--list'])

    def test_build_passes_args_and_project_context(self):
        args=json.loads(self.invoke('run.sh','build','--build-arg','BUILD_JOBS=2').stdout)
        self.assertEqual(args[:2],['buildx','build'])
        self.assertIn('--load',args)
        self.assertIn('BUILD_JOBS=2',args)
        self.assertEqual(args[-1],str(ROOT))

    def test_entrypoint_routes_outputs_inside_mount(self):
        for command,module,target in [('analyze','event_optical.event_analysis','/data/analysis'),
                                      ('reconstruct','event_optical.reconstruction','/data/reconstructions')]:
            args=json.loads(self.invoke('entrypoint.sh',command,'/data/events.raw').stdout)
            self.assertIn(module,args)
            self.assertEqual(args[args.index('--output-root')+1],target)
            self.assertEqual(args[-1],'/data/events.raw')

    def test_sudo_preserves_invoking_user_and_sdk_home(self):
        home=self.base/'caller home'
        sdk=home/'opt/arena/ArenaSDK_Linux_x64'
        sdk.mkdir(parents=True)
        # Existing user-owned data directory: no real chown is required in this test.
        (self.base/'data with spaces').mkdir()
        getent=self.bin/'getent'
        getent.write_text('#!/bin/sh\nprintf \'%s\\n\' \'caller:x:1001:1002::' + str(home) + ':/bin/bash\'\n')
        getent.chmod(0o755)
        env=dict(self.env,SUDO_UID='1001',SUDO_GID='1002')
        env.pop('ARENA_ROOT',None)
        args=json.loads(self.invoke('run.sh','record','--list',env=env).stdout)
        self.assertEqual(args[args.index('--user')+1],'1001:1002')
        self.assertIn(f'type=bind,source={sdk},target=/sdk/arena,readonly',args)

    def test_missing_sdk_and_unknown_command_fail(self):
        result=self.invoke('entrypoint.sh','record','--list',
                           env=dict(self.env,ARENA_ROOT=str(self.base/'missing')),expected=2)
        self.assertIn('Missing Linux Arena SDK directory',result.stderr)
        self.invoke('entrypoint.sh','not-a-command',expected=2)


if __name__ == '__main__': unittest.main()
