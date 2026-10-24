"""Run the actual submitter repair; mock only its download and final launch."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SubmissionRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.code = self.base / "existing school code"
        self.project = self.base / "existing project"
        self.target = self.code / "hpcmi/submit_single.py"
        self.target.parent.mkdir(parents=True)
        self.old_module = b"# Original installed submitter retained as evidence.\noriginal = True\n"
        self.target.write_bytes(self.old_module)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.requests = self.base / "requests.jsonl"
        self.launches = self.base / "launches.jsonl"
        self.protected = {
            "state/single_job_submissions.json": b'{"schema_version":1,"submissions":[{"status":"SUBMISSION_FAILED","stderr":"Memory specification can not be satisfied"}]}\n',
            "raw/bnci/A01E.mat.part": b"Original incomplete EEG transfer bytes",
            ".private/token-marker": b"Synthetic private cached authorization marker",
            "outputs/checkpoint-marker": b"Original saved checkpoint marker",
        }
        for relative, payload in self.protected.items():
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        launch = self.code / "LAUNCH.sh"
        launch.write_text("#!/bin/bash\nexec \"$PAPER1_PYTHON\" -c 'import json,os,sys; f=open(os.environ[\"TEST_LAUNCHES\"],\"a\"); f.write(json.dumps(sys.argv[1:])+\"\\n\")' \"$@\"\n")
        fetch = self.bin / "curl"
        fetch.write_text("#!" + sys.executable + '''
import json,os,shutil,sys
from pathlib import Path
from urllib.parse import urlsplit
args=sys.argv[1:]
url=next(x for x in args if x.startswith('https://'))
assert urlsplit(url).hostname=='api.github.com'
assert urlsplit(url).path.endswith('/git/blobs/055acd83b28418c89199db48a66dc7f4dde2bebe')
assert '-4' in args and '--insecure' not in args and '-k' not in args
with open(os.environ['TEST_REQUESTS'],'a') as f:f.write(json.dumps({'url':url})+'\\n')
if os.environ.get('TEST_NETWORK_BLOCKED'):sys.exit(28)
destination=Path(args[args.index('-o')+1])
if os.environ.get('TEST_BAD_PAYLOAD'):destination.write_bytes(b'wrong payload retained')
else:shutil.copyfile(os.environ['TEST_MODULE'],destination)
''')
        fetch.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PAPER1_CODE_ROOT=str(self.code), PAPER1_PROJECT=str(self.project),
                        PAPER1_PYTHON=sys.executable, TEST_MODULE=str(ROOT / "hpcmi/submit_single.py"),
                        TEST_REQUESTS=str(self.requests), TEST_LAUNCHES=str(self.launches))

    def tearDown(self):
        self.temporary.cleanup()

    def run_repair(self):
        return subprocess.run(["bash", str(ROOT / "REPAIR_SUBMISSION_ON_SCHOOL.sh"), "--memory", "240G"],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def assert_original_evidence(self):
        for relative, payload in self.protected.items():
            self.assertEqual((self.project / relative).read_bytes(), payload)

    def test_one_module_update_preserves_evidence_and_cached_repeat_needs_no_network(self):
        result = self.run_repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), (ROOT / "hpcmi/submit_single.py").read_bytes())
        backup = self.project / "state/submission-code-repair" / ("before-" + hashlib.sha256(self.old_module).hexdigest() + ".py")
        self.assertEqual(backup.read_bytes(), self.old_module)
        self.assert_original_evidence()
        self.assertEqual(json.loads(self.launches.read_text()), ["--project", str(self.project), "--memory", "240G"])
        requests = self.requests.read_bytes()
        self.env["TEST_NETWORK_BLOCKED"] = "1"
        repeated = self.run_repair()
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(self.requests.read_bytes(), requests)
        self.assertEqual(len(self.launches.read_text().splitlines()), 2)
        self.assertEqual(backup.read_bytes(), self.old_module)
        self.assert_original_evidence()

    def test_wrong_payload_retains_original_code_and_never_launches(self):
        self.env["TEST_BAD_PAYLOAD"] = "1"
        result = self.run_repair()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("checksum differs", result.stderr)
        self.assertEqual(self.target.read_bytes(), self.old_module)
        self.assertFalse(self.launches.exists())
        self.assert_original_evidence()
        partials = list((self.project / "state/submission-code-repair").glob("*.part"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"wrong payload retained")


if __name__ == "__main__":
    unittest.main()
