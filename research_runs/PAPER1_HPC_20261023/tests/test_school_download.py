"""Exercise the actual bootstrap with local bundle and mocked network/Slurm."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist/paper1-hpc-offline.tar.gz"


class SchoolDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.projects = self.base / "school projects"
        self.calls = self.base / "sbatch.jsonl"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PAPER1_PYTHON=sys.executable, TEST_BUNDLE=str(BUNDLE),
                        TEST_SBATCH_CALLS=str(self.calls), TEST_QUEUE="")
        self.program("curl", '''import os,shutil,sys
if os.environ.get("TEST_NETWORK_FAIL"):
    raise SystemExit(28)
shutil.copyfile(os.environ["TEST_BUNDLE"],sys.argv[-1])
''')
        self.program("squeue", 'import os; print(os.environ.get("TEST_QUEUE",""),end="")\n')
        self.program("sbatch", '''import json,os,sys
with open(os.environ["TEST_SBATCH_CALLS"],"a") as f:
    f.write(json.dumps(sys.argv[1:])+"\\n")
print("12345")
''')

    def program(self, name, body):
        file = self.bin / name
        file.write_text("#!" + sys.executable + "\n" + body)
        file.chmod(0o755)
        return file

    def tearDown(self):
        self.temporary.cleanup()

    def run_bootstrap(self):
        return subprocess.run(["bash", str(ROOT / "DOWNLOAD_ON_SCHOOL.sh"), str(self.projects)],
                              env=self.env, text=True, capture_output=True, timeout=30)

    def test_direct_download_extract_submit_and_duplicate_reuse(self):
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Data download submitted: 12345", result.stdout)
        job = json.loads(self.calls.read_text().splitlines()[0])
        for required in ("--account=zhuziyuan", "--partition=hpc_gpu1", "--cpus-per-task=24",
                         "--mem=128G", "--gres=gpu:NVIDIAA100-SXM4-80GB:1"):
            self.assertIn(required, job)
        script = self.projects / "paper1-risk-v1/state/download-data.sbatch"
        self.assertEqual(subprocess.run(["bash", "-n", str(script)]).returncode, 0)
        text = script.read_text()
        self.assertIn("FETCH_DATA.sh", text)
        self.assertIn("quick_raw_ready", text)
        self.assertNotIn("hpcmi.worker", text)
        self.assertNotIn("GH_TOKEN", text)
        output_arg = next(v.split("=", 1)[1] for v in job if v.startswith("--output="))
        self.assertTrue(Path(output_arg).is_absolute())
        self.assertTrue(Path(output_arg).parent.is_dir())
        self.env["TEST_QUEUE"] = "12345\n"
        self.env["TEST_NETWORK_FAIL"] = "1"
        second = self.run_bootstrap()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Existing data-download job", second.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_bad_archive_is_retained_and_never_submitted(self):
        self.projects.mkdir()
        archive = self.projects / "paper1-hpc-offline.tar.gz"
        archive.write_bytes(b"invalid archive retained")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(archive.read_bytes(), b"invalid archive retained")
        self.assertFalse(self.calls.exists())

    def test_complete_partial_is_verified_without_redownloading(self):
        self.projects.mkdir()
        shutil.copyfile(BUNDLE, self.projects / "paper1-hpc-offline.tar.gz.part")
        self.env["TEST_NETWORK_FAIL"] = "1"
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.projects / "paper1-hpc-offline.tar.gz").exists())
        self.assertFalse((self.projects / ".paper1-hpc-extract").exists())
        self.assertTrue(self.calls.exists())

    def test_network_failure_never_extracts_or_submits(self):
        self.env["TEST_NETWORK_FAIL"] = "1"
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 28)
        self.assertFalse((self.projects / "PAPER1_HPC_20261023").exists())
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
