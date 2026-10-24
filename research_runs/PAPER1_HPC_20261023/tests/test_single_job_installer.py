"""Exercise actual bootstrap/overlay files; mock only network and final submit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SingleInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.projects = self.base / "school projects"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.trace = self.base / "curl.jsonl"
        self.submitted = self.base / "submit.jsonl"
        fetch = self.bin / "curl"
        fetch.write_text("#!" + sys.executable + '''
import json,os,shutil,sys
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
args=sys.argv[1:]
url=next(x for x in args if x.startswith('https://'))
parts=urlsplit(url)
assert parts.scheme=='https' and parts.hostname=='api.github.com', 'Unexpected transport host'
assert not any(x in ('--location','--location-trusted','--insecure') or (x.startswith('-') and not x.startswith('--') and any(c in x[1:] for c in ('L','k'))) for x in args), 'Redirect or TLS bypass'
assert '-4' in args and args[args.index('--connect-timeout')+1]=='8'
assert args[args.index('--speed-time')+1]=='30' and args[args.index('--speed-limit')+1]=='128'
assert args[args.index('--retry')+1]=='1'
assert any(args[i+1]=='Accept: application/vnd.github.raw+json' for i,x in enumerate(args[:-1]) if x in ('-H','--header'))
if '/git/blobs/' in parts.path:
    assert parts.path.endswith('/6e4661c5fc6f1ac5530bcebddd746608cf6310e8')
    name='paper1-hpc-offline.tar.gz'
    assert args[args.index('--max-time')+1]=='900'
else:
    assert '/contents/' in parts.path and len(parse_qs(parts.query).get('ref',[''])[0])==40
    name=parts.path.rsplit('/',1)[1]
    assert args[args.index('--max-time')+1]=='90'
root=Path(os.environ['TEST_CODE_ROOT'])
with open(os.environ['TEST_CURL_TRACE'],'a') as f:f.write(json.dumps({'name':name,'url':url,'arguments':args})+'\\n')
if os.environ.get('TEST_BLOCK_API'):
    print('Simulated official API connect timeout',file=sys.stderr)
    sys.exit(28)
if name=='DOWNLOAD_ON_SCHOOL.sh': source=root/name
else: source=root/'dist'/name
if name=='paper1-single-job-operations.tar.gz' and os.environ.get('TEST_BAD_PATCH'):
    Path(sys.argv[-1]).write_bytes(b'corrupt operations retained')
else: shutil.copyfile(source,sys.argv[-1])
''')
        fetch.chmod(0o755)
        interpreter = self.bin / "school-python"
        interpreter.write_text("#!" + sys.executable + '''
import json,os,sys
if '-m' in sys.argv and sys.argv[sys.argv.index('-m')+1]=='hpcmi.submit_single':
    with open(os.environ['TEST_SUBMIT_TRACE'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
    print('SINGLE_JOB_SUBMISSION_MOCKED')
else: os.execv(sys.executable,[sys.executable]+sys.argv[1:])
''')
        interpreter.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PAPER1_PYTHON=str(interpreter), TEST_CODE_ROOT=str(ROOT),
                        TEST_CURL_TRACE=str(self.trace), TEST_SUBMIT_TRACE=str(self.submitted))

    def tearDown(self):
        self.temp.cleanup()

    def run_installer(self):
        return subprocess.run(["bash", str(ROOT / "RUN_SINGLE_JOB_ON_SCHOOL.sh"), str(self.projects)],
                              env=self.env, text=True, capture_output=True, timeout=30)

    def test_overlay_and_resume_preserve_science_data_failures_and_original_manifest(self):
        project = self.projects / "paper1-risk-v1"
        (project / "raw").mkdir(parents=True)
        (project / "logs/slurm").mkdir(parents=True)
        partial = project / "raw/source.part"
        failure = project / "logs/slurm/download-770688.err"
        partial.write_bytes(b"existing partial bytes")
        failure.write_text("Original A01E transfer failure retained\n")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SINGLE_JOB_SUBMISSION_MOCKED", result.stdout)
        self.assertIn("no Slurm job submitted by setup-only", result.stdout)
        code = self.projects / "PAPER1_HPC_20261023"
        protected = ["hpcmi/worker.py", "hpcmi/models.py", "hpcmi/objectives.py",
                     "config/study.json", "vendor/eligible_v3/config/filter_bank18.json", "OFFLINE_MANIFEST.json"]
        with tarfile.open(ROOT / "dist/paper1-hpc-offline.tar.gz") as archive:
            for relative in protected:
                original = archive.extractfile("PAPER1_HPC_20261023/" + relative).read()
                self.assertEqual((code / relative).read_bytes(), original)
        for relative in ["hpcmi/acquire.py", "hpcmi/single_job.py", "hpcmi/submit_single.py", "slurm/single_job.sh"]:
            self.assertEqual((code / relative).read_bytes(), (ROOT / relative).read_bytes())
        self.assertEqual(partial.read_bytes(), b"existing partial bytes")
        self.assertEqual(failure.read_text(), "Original A01E transfer failure retained\n")
        first_requests = self.trace.read_text()
        repeat = self.run_installer()
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(self.trace.read_text(), first_requests)
        self.assertEqual(len(self.submitted.read_text().splitlines()), 2)
        self.assertEqual(partial.read_bytes(), b"existing partial bytes")

    def test_blocked_api_does_not_submit_or_publish_code(self):
        self.env["TEST_BLOCK_API"] = "1"
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Simulated official API connect timeout", result.stderr)
        self.assertFalse(self.submitted.exists())
        self.assertFalse((self.projects / "PAPER1_HPC_20261023").exists())
        calls = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "DOWNLOAD_ON_SCHOOL.sh")

    def test_cached_resume_works_when_network_is_unavailable(self):
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        requests = self.trace.read_bytes()
        self.env["TEST_BLOCK_API"] = "1"
        resumed = self.run_installer()
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.trace.read_bytes(), requests)
        self.assertEqual(len(self.submitted.read_text().splitlines()), 2)

    def test_bundle_partials_are_preserved_and_verified_archive_is_reused(self):
        self.projects.mkdir(parents=True)
        old_partial = self.projects / "paper1-hpc-offline.tar.gz.part"
        api_partial = self.projects / "paper1-hpc-offline.tar.gz.api-download.part"
        old_partial.write_bytes(b"old raw-host partial retained")
        api_partial.write_bytes(b"interrupted API full-blob candidate retained")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(old_partial.read_bytes(), b"old raw-host partial retained")
        interrupted = list(self.projects.glob("paper1-hpc-offline.tar.gz.api-interrupted.*"))
        self.assertEqual(len(interrupted), 1)
        self.assertEqual(interrupted[0].read_bytes(), b"interrupted API full-blob candidate retained")
        archive = self.projects / "paper1-hpc-offline.tar.gz"
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         "72225f30c83be9bbc94d52eac672bee272690f6cf9949933e3d61380401d2675")
        calls = [json.loads(line) for line in self.trace.read_text().splitlines()]
        bundle_calls = [row for row in calls if row["name"] == "paper1-hpc-offline.tar.gz"]
        self.assertEqual(len(bundle_calls), 1)
        self.assertNotIn("-C", bundle_calls[0]["arguments"])
        self.assertNotIn("--continue-at", bundle_calls[0]["arguments"])
        self.assertNotIn("--range", bundle_calls[0]["arguments"])
        requests = self.trace.read_bytes()
        self.env["TEST_BLOCK_API"] = "1"
        resumed = self.run_installer()
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.trace.read_bytes(), requests)
        self.assertEqual(old_partial.read_bytes(), b"old raw-host partial retained")
        self.assertEqual(interrupted[0].read_bytes(), b"interrupted API full-blob candidate retained")

    def test_corrupt_operations_stop_before_code_or_job_changes(self):
        self.env["TEST_BAD_PATCH"] = "1"
        result = self.run_installer()
        self.assertEqual(result.returncode, 2)
        self.assertIn("checksum differs", result.stderr)
        self.assertFalse(self.submitted.exists())
        self.assertFalse((self.projects / "PAPER1_HPC_20261023").exists())
        self.assertTrue(list((self.projects / "paper1-risk-v1/state/single-job-install-cache").glob("*.part")))


if __name__ == "__main__":
    unittest.main()
