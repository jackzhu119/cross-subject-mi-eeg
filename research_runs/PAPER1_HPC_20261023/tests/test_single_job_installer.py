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
url=next(x for x in sys.argv[1:] if x.startswith('https://'))
name=url.rsplit('/',1)[1]
root=Path(os.environ['TEST_CODE_ROOT'])
with open(os.environ['TEST_CURL_TRACE'],'a') as f:f.write(json.dumps({'name':name})+'\\n')
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
