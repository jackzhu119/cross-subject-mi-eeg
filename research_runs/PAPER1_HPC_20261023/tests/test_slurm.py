"""Targeted scheduler mocks and real Bash/worker signal propagation tests.

No Slurm installation, GPU, school-server access, or torch import is required.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from hpcmi.slurm import SlurmClient, submission_lock, submit_auxiliary, auxiliary_state


ROOT = Path(__file__).resolve().parents[1]


class FakeScheduler:
    def __init__(self):
        self.queue = ""
        self.accounting = ""
        self.calls = []
        self.fail_queue = False
        self.fail_accounting = False
        self.next_id = 101
        self.before_submit = None

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[0] == "squeue":
            return subprocess.CompletedProcess(argv, 1 if self.fail_queue else 0, self.queue, "offline" if self.fail_queue else "")
        if argv[0] == "sacct":
            if self.fail_accounting:
                raise FileNotFoundError("sacct")
            return subprocess.CompletedProcess(argv, 0, self.accounting, "")
        if argv[0] == "sbatch":
            if self.before_submit:
                self.before_submit(argv)
            result = subprocess.CompletedProcess(argv, 0, str(self.next_id) + ";school\n", "")
            self.next_id += 1
            return result
        raise AssertionError(argv)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "paper-one"
        self.scheduler = FakeScheduler()
        self.client = SlurmClient(self.project, runner=self.scheduler)

    def tearDown(self):
        self.tmp.cleanup()

    def ledger(self):
        return json.loads(self.client.ledger_path.read_text())

    def submit(self, tasks=("development-0", "development-1")):
        return self.client.submit_task_array(tasks, sys.executable, ROOT)

    def test_submit_logs_precede_sbatch_and_resources_are_portable(self):
        def inspect(argv):
            self.assertTrue((self.project / "logs/slurm").is_dir())
            self.assertEqual(self.ledger()["submissions"][-1]["status"], "SUBMITTING")
            for arg in ("--nodes=1", "--ntasks=1", "--account=zhuziyuan", "--partition=hpc_gpu",
                        "--gres=gpu:1", "--cpus-per-task=16", "--mem=128G",
                        "--signal=B:USR1@180", "--requeue", "--array=0-1%2"):
                self.assertIn(arg, argv)
            output = next(x.split("=", 1)[1] for x in argv if x.startswith("--output="))
            self.assertTrue(Path(output).is_absolute())
        self.scheduler.before_submit = inspect
        self.assertEqual(self.submit(), "101")
        record = self.ledger()["submissions"][-1]
        self.assertEqual(record["status"], "SUBMITTED")
        self.assertEqual(json.loads(Path(record["map_path"]).read_text())["tasks"], ["development-0", "development-1"])

    def test_active_array_stops_second_submission(self):
        self.submit()
        record = self.ledger()["submissions"][-1]
        self.scheduler.queue = "101_1|" + record["job_name"] + "|RUNNING\n"
        self.assertEqual(self.client.active_task_ids(), {"development-1"})
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_ARRAY_EXISTS"):
            self.submit(("development-2",))
        self.assertEqual(sum(x[0] == "sbatch" for x in self.scheduler.calls), 1)

    def test_squeue_failure_does_not_assume_idle_or_submit(self):
        self.scheduler.fail_queue = True
        with self.assertRaisesRegex(RuntimeError, "squeue failed"):
            self.submit()
        self.assertFalse(any(x[0] == "sbatch" for x in self.scheduler.calls))

    def test_sbatch_timeout_retains_intent_and_does_not_double_submit(self):
        def timed_out(argv):
            raise subprocess.TimeoutExpired(argv, 30)
        self.scheduler.before_submit = timed_out
        with self.assertRaisesRegex(RuntimeError, "outcome uncertain"):
            self.submit()
        self.assertEqual(self.ledger()["submissions"][-1]["status"], "SUBMISSION_UNCERTAIN")
        self.scheduler.before_submit = None
        with self.assertRaisesRegex(RuntimeError, "previous sbatch outcome is uncertain"):
            self.submit()
        self.assertEqual(sum(x[0] == "sbatch" for x in self.scheduler.calls), 1)

    def test_array_mapping_requires_expanded_indices(self):
        self.submit()
        record = self.ledger()["submissions"][-1]
        self.scheduler.queue = "101_[0-1]|" + record["job_name"] + "|PENDING\n"
        with self.assertRaisesRegex(RuntimeError, "not expanded"):
            self.client.active_task_ids()

    def test_manual_partial_resume_retains_previous_submission(self):
        self.submit()
        self.scheduler.accounting = "101_0|COMPLETED\n101_1|FAILED\n"
        self.assertEqual(self.client.task_scheduler_states(), {"development-0": "COMPLETED", "development-1": "FAILED"})
        self.assertEqual(self.submit(("development-1",)), "102")
        self.assertEqual(len(self.ledger()["submissions"]), 2)

    def test_crash_intent_recovers_from_real_queue_identity(self):
        self.submit()
        ledger = self.ledger()
        record = ledger["submissions"][-1]
        record.update(job_id=None, status="SUBMITTING")
        self.client.ledger_path.write_text(json.dumps(ledger))
        self.scheduler.queue = "101_0|" + record["job_name"] + "|PENDING\n"
        self.assertEqual(self.client.active_task_ids(), {"development-0"})
        self.assertEqual(self.ledger()["submissions"][-1]["status"], "SUBMITTED_RECOVERED")
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_ARRAY_EXISTS"):
            self.submit()

    def test_cancelled_and_unavailable_accounting_remain_distinct(self):
        self.submit()
        self.scheduler.accounting = "101_0|CANCELLED by 1000\n101_1|COMPLETED\n101_1.batch|COMPLETED\n"
        self.assertEqual(self.client.task_scheduler_states()["development-0"], "CANCELLED")
        self.scheduler.fail_accounting = True
        self.assertEqual(set(self.client.task_scheduler_states().values()), {"UNKNOWN"})

    def test_parallel_launcher_lock_rejects_without_deleting_inode(self):
        with submission_lock(self.project):
            inode = (self.project / "state/submission.lock").stat().st_ino
            with self.assertRaisesRegex(RuntimeError, "Another launch"):
                self.submit()
        self.assertEqual((self.project / "state/submission.lock").stat().st_ino, inode)

    def test_auxiliary_preparation_uses_gpu_partition_allocation_and_reuses_active_job(self):
        code = Path(self.tmp.name) / "code"
        (code / "slurm").mkdir(parents=True)
        (code / "slurm/prepare.sh").write_text("#!/bin/bash\nexit 0\n")
        with patch("hpcmi.slurm.subprocess.run", self.scheduler):
            job = submit_auxiliary(self.project, "prep", sys.executable, code_root=code)
            command = next(x for x in self.scheduler.calls if x[0] == "sbatch")
            self.assertIn("--gres=gpu:1", command)
            ledger = json.loads((self.project / "state/aux_prep.json").read_text())
            self.scheduler.queue = job + "|" + ledger["submissions"][-1]["job_name"] + "|RUNNING\n"
            self.assertEqual(submit_auxiliary(self.project, "prep", sys.executable, code_root=code), job)
            self.assertEqual(auxiliary_state(self.project, "prep")["state"], "RUNNING")
        self.assertEqual(sum(x[0] == "sbatch" for x in self.scheduler.calls), 1)

    def test_auxiliary_cancel_needs_explicit_resume_and_preserves_history(self):
        with patch("hpcmi.slurm.subprocess.run", self.scheduler):
            submit_auxiliary(self.project, "smoke", sys.executable, code_root=ROOT)
            self.scheduler.accounting = "101|CANCELLED by 1000\n"
            with self.assertRaisesRegex(RuntimeError, "MANUAL_RESUME"):
                submit_auxiliary(self.project, "smoke", sys.executable, code_root=ROOT)
            self.assertEqual(submit_auxiliary(self.project, "smoke", sys.executable,
                                             code_root=ROOT, explicit_resume=True), "102")
        ledger = json.loads((self.project / "state/aux_smoke.json").read_text())
        self.assertEqual(len(ledger["submissions"]), 2)
        self.assertEqual(ledger["submissions"][0]["job_id"], "101")


WORKER = '''import os,signal,sys,time
from pathlib import Path
root=Path(os.environ["TEST_ROOT"])
state={"signal":None}
def receive(sig,frame):
    state["signal"]=sig
signal.signal(signal.SIGUSR1,receive)
signal.signal(signal.SIGTERM,receive)
signal.signal(signal.SIGINT,receive)
(root/"ready").write_text(str(os.getpid()))
if os.environ.get("WORKER_FAIL"):
    sys.exit(7)
while state["signal"] is None:
    time.sleep(.01)
(root/"saving").write_text("yes")
time.sleep(.15)
(root/"checkpoint").write_text("saved")
sys.exit(75 if state["signal"]==signal.SIGUSR1 else 143)
'''


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        package = self.folder / "hpcmi"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "worker.py").write_text(WORKER)
        (self.folder / "map.json").write_text(json.dumps({"tasks": ["task-0"]}))
        binary = self.folder / "bin"
        binary.mkdir()
        control = binary / "scontrol"
        control.write_text('#!/usr/bin/env bash\n[ -f "$TEST_ROOT/checkpoint" ] || exit 97\nprintf "%s\\n" "$*" >> "$TEST_ROOT/requeue"\nexit "${REQUEUE_EXIT:-0}"\n')
        control.chmod(0o755)
        self.env = dict(os.environ, TEST_ROOT=str(self.folder), PATH=str(binary) + ":" + os.environ["PATH"],
                        SLURM_ARRAY_JOB_ID="123", SLURM_ARRAY_TASK_ID="0", SLURM_JOB_ID="123_0")
        self.process = None

    def tearDown(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.communicate(timeout=5)
        self.tmp.cleanup()

    def start(self):
        self.process = subprocess.Popen(["bash", str(ROOT / "slurm/train_array.sh"), str(self.folder), sys.executable,
                                         str(self.folder), str(self.folder / "map.json")], env=self.env,
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_file("ready")

    def wait_file(self, name):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if (self.folder / name).exists():
                return
            if self.process.poll() is not None:
                self.fail("worker exited before " + name + ": " + str(self.process.communicate()))
            time.sleep(.01)
        self.fail("worker failed to produce " + name)

    def finish(self):
        out, err = self.process.communicate(timeout=5)
        self.assertIn("BATCH_START", out)
        self.assertIn("WORKER_EXIT", out)
        return self.process.returncode, out, err

    def test_usr1_waits_for_checkpoint_then_requeues_exact_array_item_once(self):
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        code, out, err = self.finish()
        self.assertEqual(code, 75, out + err)
        self.assertEqual((self.folder / "checkpoint").read_text(), "saved")
        self.assertEqual((self.folder / "requeue").read_text(), "requeue 123_0\n")
        self.assertIn("REQUEUE_REQUEST_ACCEPTED", out)

    def test_denied_requeue_preserves_checkpoint_and_resumable_exit(self):
        self.env["REQUEUE_EXIT"] = "1"
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        code, out, err = self.finish()
        self.assertEqual(code, 75)
        self.assertEqual((self.folder / "requeue").read_text().count("requeue"), 1)
        self.assertIn("rerun the same LAUNCH.sh", err)

    def test_term_cancel_checkpoints_without_requeue(self):
        self.start()
        os.kill(self.process.pid, signal.SIGTERM)
        code, out, err = self.finish()
        self.assertEqual(code, 143, out + err)
        self.assertTrue((self.folder / "checkpoint").exists())
        self.assertFalse((self.folder / "requeue").exists())
        self.assertIn("CANCELLED_NO_REQUEUE", out)

    def test_cancel_during_usr1_save_overrides_requeue(self):
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        self.wait_file("saving")
        os.kill(self.process.pid, signal.SIGTERM)
        code, out, err = self.finish()
        self.assertEqual(code, 143, out + err)
        self.assertFalse((self.folder / "requeue").exists())

    def test_real_worker_failure_keeps_exit_code(self):
        self.env["WORKER_FAIL"] = "1"
        self.start()
        code, out, err = self.finish()
        self.assertEqual(code, 7, out + err)
        self.assertFalse((self.folder / "requeue").exists())


if __name__ == "__main__":
    unittest.main()
