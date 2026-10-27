"""Exercise imports from the shipped offline archive, using existing packages."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def test_deterministic_bundle_payloads_and_real_offline_imports(self):
        spec = importlib.util.spec_from_file_location('build_delivery', ROOT/'build_delivery.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        first = module.build(ROOT)
        second = module.build(ROOT)
        self.assertEqual(first, second)
        archive = ROOT/'dist'/first['file']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), first['sha256'])
        with tempfile.TemporaryDirectory() as temp, tarfile.open(archive, 'r:gz') as source:
            manifest = json.load(source.extractfile('BUNDLE_MANIFEST.json'))
            for row in manifest['files']:
                path = Path(temp)/row['path']
                data = source.extractfile(row['path']).read()
                self.assertEqual(len(data), row['bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
                self.assertNotIn(path.suffix, ('.pt', '.edf', '.mat', '.whl'))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            code = ('import sys; sys.path.insert(0,sys.argv[1]); '
                    'import compmi.plan,compmi.classical,compmi.analysis,compmi.launch,compmi.runner,compmi.sync; '
                    'print("OFFLINE_CODE_IMPORTS_PASSED")')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, temp],
                                    text=True, capture_output=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('OFFLINE_CODE_IMPORTS_PASSED', result.stdout)


if __name__ == '__main__':
    unittest.main()
