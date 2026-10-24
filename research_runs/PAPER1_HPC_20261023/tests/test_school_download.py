"""Exercise the actual bootstrap with local bundle and mocked network/Slurm."""
import json
import hashlib
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
                        TEST_SBATCH_CALLS=str(self.calls), TEST_QUEUE="",
                        TEST_CANCEL=str(self.base / "cancel.jsonl"),
                        TEST_CANCELLED=str(self.base / "cancelled"))
        self.program("curl", '''import os,shutil,sys
if os.environ.get("TEST_NETWORK_FAIL"):
    raise SystemExit(28)
shutil.copyfile(os.environ["TEST_BUNDLE"],sys.argv[-1])
''')
        self.program("squeue", '''import os
from pathlib import Path
if Path(os.environ["TEST_CANCELLED"]).exists():
    print(os.environ.get("TEST_AFTER_QUEUE",""),end="")
else:
    print(os.environ.get("TEST_QUEUE",""),end="")
''')
        self.program("scancel", '''import os,json,sys
from pathlib import Path
with open(os.environ["TEST_CANCEL"],"a") as f:
    f.write(json.dumps(sys.argv[1:])+"\\n")
Path(os.environ["TEST_CANCELLED"]).touch()
''')
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
        for required in ("--account=zhuziyuan", "--partition=hpc_gpu", "--cpus-per-task=16",
                         "--mem=128G", "--gres=gpu:1"):
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
        self.env["TEST_QUEUE"] = self.queue_row("hpc_gpu")
        self.env["TEST_NETWORK_FAIL"] = "1"
        second = self.run_bootstrap()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Existing data-download job already uses", second.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def queue_row(self, partition="hpc_gpu1", state="PENDING", owner="zhuziyuan"):
        project = str(self.projects / "paper1-risk-v1")
        name = "p1-download-" + hashlib.sha256(project.encode()).hexdigest()[:10]
        return f"770682|{name}|{owner}|{state}|{partition}|{project}\n"

    def test_pending_download_migrates_and_existing_project_config_is_updated(self):
        project = self.projects / "paper1-risk-v1"
        (project / "config").mkdir(parents=True)
        (project / "state").mkdir()
        old = {"account": "zhuziyuan", "partition": "hpc_gpu1", "gres": "gpu:NVIDIAA100-SXM4-80GB:1",
               "exclude": ["gpu3"], "max_parallel": 3, "cpus_per_task": 24, "mem": "128G"}
        (project / "config/cluster.json").write_text(json.dumps(old))
        (project / "state/download-data.sbatch").write_text("original queued script\n")
        raw = project / "raw"
        raw.mkdir()
        (raw / "keep.part").write_bytes(b"retained-download-bytes")
        self.env["TEST_QUEUE"] = self.queue_row()
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        cancelled = json.loads(Path(self.env["TEST_CANCEL"]).read_text())
        self.assertEqual(cancelled, ["--state=PENDING", "770682"])
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        for file in (project / "config/cluster.json", self.projects / "PAPER1_HPC_20261023/config/cluster.json"):
            updated = json.loads(file.read_text())
            self.assertEqual((updated["partition"], updated["gres"], updated["exclude"]), ("hpc_gpu", "gpu:1", []))
            self.assertEqual(updated["max_parallel"], 2)
            self.assertEqual(updated["cpus_per_task"], 16)
        self.assertEqual((project / "state/download-migration-770682-original.sbatch").read_text(), "original queued script\n")
        self.assertEqual((raw / "keep.part").read_bytes(), b"retained-download-bytes")

    def test_running_download_and_identity_mismatch_are_never_cancelled(self):
        self.env["TEST_QUEUE"] = self.queue_row(state="RUNNING")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertFalse(Path(self.env["TEST_CANCEL"]).exists())
        self.env["TEST_QUEUE"] = self.queue_row(owner="someone_else")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(Path(self.env["TEST_CANCEL"]).exists())

    def test_pending_to_running_race_does_not_submit_duplicate(self):
        self.env["TEST_QUEUE"] = self.queue_row()
        self.env["TEST_AFTER_QUEUE"] = self.queue_row(state="RUNNING")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(self.env["TEST_CANCEL"]).exists())
        self.assertFalse(self.calls.exists())

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
