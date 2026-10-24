"""One-job submission tests: no real network, installation, Slurm or EEG."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hpcmi import submit_single as s
from hpcmi.common import atomic_json, read_json


class Scheduler:
    def __init__(self):
        self.rows = []
        self.after_cancel = []
        self.calls = []
        self.next_id = "880001"
        self.timeout = False
        self.fail = False

    def __call__(self, arguments, **kwargs):
        self.calls.append(arguments)
        if arguments[0] == "squeue":
            text = "\n".join("|".join(str(row[k]) for k in ("id", "name", "owner", "state", "partition", "directory")) for row in self.rows)
            return subprocess.CompletedProcess(arguments, 0, text, "")
        if arguments[0] == "scancel":
            self.rows = self.after_cancel
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[0] == "sbatch":
            if self.timeout:
                raise subprocess.TimeoutExpired(arguments, 30)
            return subprocess.CompletedProcess(arguments, 1 if self.fail else 0,
                                               "" if self.fail else self.next_id + ";school\n",
                                               "scheduler rejected" if self.fail else "")
        raise AssertionError(arguments)


class SingleSubmitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.project = self.folder / "paper one"
        self.scheduler = Scheduler()
        self.patchers = ExitStack()
        self.patchers.enter_context(patch.dict(s.os.environ, {}, clear=True))
        self.patchers.enter_context(patch.object(s.cli, "runtime_metadata", return_value={
            "python": "3.12.3", "torch": "2.5.1+cu121", "numpy": "2.2.6", "executable": sys.executable}))
        self.credentials = self.patchers.enter_context(patch("hpcmi.github_sync.confirm_credentials",
                                                         return_value=self.folder / "private/token"))
        self.prepare = self.patchers.enter_context(patch("hpcmi.prep_runtime.prepare", return_value=Path(sys.executable)))
        self.stop_controller = self.patchers.enter_context(patch.object(s.cli, "stop_legacy_controller", return_value=[991], create=True))

    def tearDown(self):
        self.patchers.close()
        self.temporary.cleanup()

    def submit(self, **kwargs):
        return s.submit(self.project, sys.executable, runner=self.scheduler, **kwargs)

    def row(self, prefix="p1-single-", state="RUNNING", job="880001", **changes):
        key = hashlib.sha256(str(self.project.resolve()).encode()).hexdigest()[:10]
        row = {"id": job, "name": prefix + key, "owner": "zhuziyuan", "state": state,
               "partition": "hpc_gpu", "directory": str(self.project.resolve())}
        row.update(changes)
        return row

    def commands(self, name):
        return [a for a in self.scheduler.calls if a[0] == name]

    def test_exactly_one_job_shape_private_setup_and_log_before_submit(self):
        original = self.scheduler.__class__.__call__
        def inspect(arguments, **kwargs):
            if arguments[0] == "sbatch":
                self.assertTrue((self.project / "logs/slurm").is_dir())
                ledger = read_json(self.project / "state/single_job_submissions.json")
                self.assertEqual(ledger["submissions"][-1]["status"], "SUBMITTING")
                self.credentials.assert_called_once()
                self.prepare.assert_called_once()
                self.assertEqual(read_json(self.project / "config/execution_mode.json")["mode"], "single_job")
            return original(self.scheduler, arguments, **kwargs)
        with patch.object(self.scheduler.__class__, "__call__", side_effect=inspect):
            result = self.submit()
        self.assertEqual(result["status"], "SINGLE_JOB_SUBMITTED")
        command = self.commands("sbatch")[0]
        for argument in ("--gres=gpu:2", "--cpus-per-task=32", "--mem=240G", "--partition=hpc_gpu",
                         "--account=zhuziyuan", "--signal=B:USR1@180", "--requeue", "--open-mode=append"):
            self.assertIn(argument, command)
        self.assertFalse(any(a.startswith("--array") for a in command))
        output = next(a.split("=", 1)[1] for a in command if a.startswith("--output="))
        error = next(a.split("=", 1)[1] for a in command if a.startswith("--error="))
        self.assertEqual(output, error)
        self.assertTrue(Path(output).is_absolute())
        self.assertNotIn(str(self.folder / "private/token"), command)
        self.assertEqual(read_json(self.project / "config/cluster.json")["cpus_per_task"], 16)
        self.assertEqual(read_json(self.project / "config/cluster.json")["max_parallel"], 2)
        self.assertEqual(read_json(self.project / "config/cluster.json")["single_job_memory"], "240G")
        self.assertEqual(result["memory"], "240G")
        self.assertEqual(read_json(self.project / "state/single_job_submissions.json")["submissions"][-1]["job_id"], "880001")

    def test_active_same_project_job_is_reused_without_another_submission(self):
        self.scheduler.rows = [self.row()]
        result = self.submit()
        self.assertEqual(result["status"], "EXISTING_SINGLE_JOB_REUSED")
        self.assertFalse(self.commands("sbatch"))
        self.assertFalse(self.commands("scancel"))
        self.stop_controller.assert_not_called()

    def test_wrong_user_or_project_identity_never_submits(self):
        for changes in ({"owner": "other"}, {"directory": str(self.folder / "another-paper")}):
            self.scheduler.rows = [self.row(**changes)]
            with self.assertRaisesRegex(RuntimeError, "user/directory"):
                self.submit()
        self.assertFalse(self.commands("sbatch"))
        self.assertFalse(self.commands("scancel"))

    def test_old_pending_download_cancel_is_state_filtered_and_evidence_retained(self):
        self.scheduler.rows = [self.row("p1-download-", "PENDING", "770682", partition="hpc_gpu1")]
        state = self.project / "state"
        state.mkdir(parents=True)
        (state / "download-data.sbatch").write_bytes(b"original old download script\n")
        raw = self.project / "raw/bnci"
        raw.mkdir(parents=True)
        (raw / "A01E.mat.part").write_bytes(b"partial preserved")
        result = self.submit()
        self.assertEqual(result["status"], "SINGLE_JOB_SUBMITTED")
        self.assertEqual(self.commands("scancel"), [["scancel", "--state=PENDING", "770682"]])
        self.assertEqual((state / "legacy-download-770682-original.sbatch").read_bytes(), b"original old download script\n")
        self.assertEqual((raw / "A01E.mat.part").read_bytes(), b"partial preserved")
        self.assertTrue((state / "legacy-download-770682-before-single.json").exists())
        self.assertTrue((state / "legacy-download-770682-after-single.json").exists())

    def test_old_running_download_and_pending_to_running_race_do_not_duplicate(self):
        self.scheduler.rows = [self.row("p1-download-", "RUNNING", "770688")]
        result = self.submit()
        self.assertEqual(result["status"], "LEGACY_DOWNLOAD_ACTIVE_NO_NEW_JOB")
        self.assertFalse(self.commands("scancel"))
        self.assertFalse(self.commands("sbatch"))
        self.scheduler.rows = [self.row("p1-download-", "PENDING", "770688")]
        self.scheduler.after_cancel = [self.row("p1-download-", "RUNNING", "770688")]
        result = self.submit()
        self.assertEqual(result["status"], "LEGACY_DOWNLOAD_STILL_ACTIVE_NO_NEW_JOB")
        self.assertFalse(self.commands("sbatch"))

    def test_active_old_training_array_prevents_single_job_submission(self):
        state = self.project / "state"
        state.mkdir(parents=True)
        atomic_json(state / "submissions.json", {"schema_version": 1, "submissions": [{"job_name": "old-array"}]})
        self.scheduler.rows = [self.row(name="old-array", job="123_4")]
        result = self.submit()
        self.assertEqual(result["status"], "LEGACY_TRAINING_ACTIVE_NO_NEW_JOB")
        self.assertFalse(self.commands("sbatch"))
        self.stop_controller.assert_not_called()

    def test_uncertain_sbatch_retains_intent_then_recovers_from_actual_queue(self):
        self.scheduler.timeout = True
        with self.assertRaisesRegex(RuntimeError, "outcome uncertain"):
            self.submit()
        path = self.project / "state/single_job_submissions.json"
        self.assertEqual(read_json(path)["submissions"][-1]["status"], "SUBMISSION_UNCERTAIN")
        self.scheduler.timeout = False
        with self.assertRaisesRegex(RuntimeError, "Previous sbatch outcome"):
            self.submit()
        self.assertEqual(len(self.commands("sbatch")), 1)
        self.scheduler.rows = [self.row()]
        result = self.submit()
        self.assertEqual(result["status"], "EXISTING_SINGLE_JOB_REUSED")
        self.assertEqual(read_json(path)["submissions"][-1]["status"], "SUBMITTED_RECOVERED")
        self.assertEqual(len(self.commands("sbatch")), 1)

    def test_explicit_scheduler_rejection_is_preserved_and_manual_retry_appends(self):
        self.scheduler.fail = True
        with self.assertRaisesRegex(RuntimeError, "submission failed") as raised:
            self.submit()
        self.assertIn("exit=1", str(raised.exception))
        self.assertIn("stderr='scheduler rejected'", str(raised.exception))
        self.assertIn("stdout=''", str(raised.exception))
        failed = read_json(self.project / "state/single_job_submissions.json")["submissions"][-1]
        self.assertEqual(failed["stderr"], "scheduler rejected")
        self.assertEqual(len(self.commands("sbatch")), 1)
        self.scheduler.fail = False
        self.submit()
        records = read_json(self.project / "state/single_job_submissions.json")["submissions"]
        self.assertEqual([r["status"] for r in records], ["SUBMISSION_FAILED", "SUBMITTED"])

    def test_invalid_success_output_is_visible_and_retains_uncertain_intent(self):
        self.scheduler.next_id = "unexpected scheduler response"
        with self.assertRaisesRegex(RuntimeError, "submission outcome uncertain") as raised:
            self.submit()
        self.assertIn("exit=0", str(raised.exception))
        self.assertIn("stderr=''", str(raised.exception))
        self.assertIn("unexpected scheduler response", str(raised.exception))
        failed = read_json(self.project / "state/single_job_submissions.json")["submissions"][-1]
        self.assertEqual(failed["status"], "SUBMISSION_UNCERTAIN")
        self.assertEqual(failed["returncode"], 0)
        with self.assertRaisesRegex(RuntimeError, "Previous sbatch outcome"):
            self.submit()
        self.assertEqual(len(self.commands("sbatch")), 1)

    def test_memory_override_is_saved_and_reused_without_changing_failed_record(self):
        self.scheduler.fail = True
        with self.assertRaisesRegex(RuntimeError, "submission failed"):
            self.submit()
        ledger_path = self.project / "state/single_job_submissions.json"
        original_failure = read_json(ledger_path)["submissions"][0]
        self.scheduler.fail = False
        result = self.submit(memory="110G")
        self.assertEqual(result["memory"], "110G")
        self.assertIn("--mem=110G", self.commands("sbatch")[-1])
        config = read_json(self.project / "config/cluster.json")
        self.assertEqual(config["single_job_memory"], "110G")
        self.assertEqual(config["mem"], "128G")
        self.assertEqual(config["cpus_per_task"], 16)
        self.assertTrue(list((self.project / "state").glob("cluster-before-single-*.json")))
        records = read_json(ledger_path)["submissions"]
        self.assertEqual(records[0], original_failure)
        self.assertEqual(records[1]["shape"], {"gpus": 2, "cpus": 32, "memory": "110G", "max_worker_processes": 2})
        resumed = self.submit()
        self.assertEqual(resumed["memory"], "110G")
        self.assertIn("--mem=110G", self.commands("sbatch")[-1])

    def test_invalid_memory_never_requests_credentials_or_submits(self):
        for value in ("", "-1", "0G", "1.5G", "all", "110G;echo bad", 0):
            with self.subTest(memory=value), self.assertRaises(ValueError):
                self.submit(memory=value)
        self.credentials.assert_not_called()
        self.prepare.assert_not_called()
        self.assertFalse(self.commands("sbatch"))

    def test_all_node_memory_requires_an_explicit_request_then_persists(self):
        with self.assertRaises(ValueError):
            s._job_memory("0")
        result = self.submit(memory="0")
        self.assertEqual(result["memory"], "0")
        self.assertIn("--mem=0", self.commands("sbatch")[-1])
        self.assertEqual(read_json(self.project / "config/cluster.json")["single_job_memory"], "0")

    def test_cli_memory_can_use_environment_override(self):
        with patch.dict(s.os.environ, {"PAPER1_JOB_MEMORY": "110G"}), patch.object(s, "submit", return_value={"status": "mocked"}) as submit:
            self.assertEqual(s.main([]), 0)
        self.assertEqual(submit.call_args.kwargs["memory"], "110G")

    def test_initial_credential_rejection_stops_before_install_or_sbatch(self):
        self.credentials.side_effect = RuntimeError("initial credential rejected")
        with self.assertRaisesRegex(RuntimeError, "credential rejected"):
            self.submit()
        self.prepare.assert_not_called()
        self.assertFalse(self.commands("sbatch"))

    def test_scientific_files_and_original_failed_download_log_are_retained(self):
        self.project.mkdir()
        originals = {"tasks.json": b"preserve original tasks", "state/old-checkpoint.json": b"preserve old count",
                     "logs/slurm/download-770688.err": b"original Transfer interrupted failure"}
        for name, payload in originals.items():
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        self.submit()
        for name, payload in originals.items():
            self.assertEqual((self.project / name).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
