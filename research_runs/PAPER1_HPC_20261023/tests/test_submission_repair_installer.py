"""Legacy repair entry delegates to the coherent, pinned operations installer."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SubmissionRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        binary = self.root / 'bin'
        binary.mkdir()
        self.launch = self.root / 'launches'
        fetch = binary / 'curl'
        fetch.write_text('#!' + sys.executable + '''
import os,shutil,sys
from pathlib import Path
if os.environ.get('TEST_BAD_PAYLOAD'):
    Path(sys.argv[-1]).write_bytes(b'Invalid bootstrap retained')
else:shutil.copyfile(os.environ['TEST_FIXED_LAUNCHER'],sys.argv[-1])
''')
        fetch.chmod(0o755)
        shell = binary / 'bash'
        shell.write_text('#!' + sys.executable + '''
import json,os,sys
from pathlib import Path
Path(os.environ['TEST_LAUNCH_TRACE']).write_text(json.dumps(sys.argv[2:]))
''')
        shell.chmod(0o755)
        self.env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                        TEST_FIXED_LAUNCHER=str(ROOT / 'RUN_SINGLE_JOB_ON_SCHOOL.sh'),
                        TEST_LAUNCH_TRACE=str(self.launch))

    def repair(self):
        return subprocess.run(['/bin/bash', str(ROOT / 'REPAIR_SUBMISSION_ON_SCHOOL.sh'),
                               '--reauthorize', '--gpus', '2', '--memory', '128G'],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def test_legacy_entry_passes_exact_current_launcher_and_resource_arguments(self):
        import json
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.launch.read_text()),
                         ['--reauthorize', '--gpus', '2', '--memory', '128G'])

    def test_invalid_launcher_is_never_executed(self):
        self.env['TEST_BAD_PAYLOAD'] = '1'
        result = self.repair()
        self.assertEqual(result.returncode, 2)
        self.assertIn('checksum differs', result.stderr)
        self.assertFalse(self.launch.exists())


if __name__ == '__main__':
    unittest.main()
