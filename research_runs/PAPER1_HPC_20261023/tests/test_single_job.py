"""Single-allocation orchestration tests; no Slurm, network, CUDA or EEG."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

from hpcmi.common import atomic_json, read_json
from hpcmi import single_job as s


def task(name, phase="development"):
    return {"id": name, "phase": phase, "method": "erm", "seed": 7}


def finish(project, item):
    folder = project / "outputs/runs" / item["id"]
    atomic_json(folder / "evaluations/result.json", {"synthetic": True})
    atomic_json(folder / "complete.json", {"status": "complete", "task_id": item["id"],
                "phase": item["phase"], "method": item["method"], "seed": item["seed"],
                "evaluations": {"synthetic": "evaluations/result.json"}})


class FakeProcess:
    sequence = 100

    def __init__(self, callback=None, code=0, ticks=1, factory=None, worker=False):
        FakeProcess.sequence += 1
        self.pid = FakeProcess.sequence
        self.callback, self.code, self.ticks = callback, code, ticks
        self.returncode, self.signals = None, []
        self.factory, self.worker = factory, worker

    def poll(self):
        if self.returncode is None:
            if self.ticks > 0:
                self.ticks -= 1
                return None
            self.returncode = self.code
            if self.callback and self.code == 0:
                self.callback()
            if self.worker:
                self.factory.active -= 1
        return self.returncode

    def send_signal(self, number):
        self.signals.append(number)
        self.code = 75 if number == signal.SIGUSR1 else 143
        self.ticks = 0

    def terminate(self):
        self.send_signal(signal.SIGTERM)

    def kill(self):
        self.send_signal(signal.SIGKILL)

    def wait(self, timeout=None):
        while self.poll() is None:
            pass
        return self.returncode


class Factory:
    def __init__(self, project, tasks):
        self.project, self.tasks = project, {t["id"]: t for t in tasks}
        self.calls, self.worker_processes = [], []
        self.fail, self.omit_completion = set(), set()
        self.active, self.maximum = 0, 0

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if "hpcmi.worker" in command:
            name = command[command.index("--task-id")+1]
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            callback = None if name in self.omit_completion else lambda: finish(self.project, self.tasks[name])
            process = FakeProcess(callback, 9 if name in self.fail else 0, 2, self, True)
            self.worker_processes.append(process)
            return process
        return FakeProcess(ticks=0)


class SingleJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "synthetic-single-job"
        self.project.mkdir()
        atomic_json(self.project / "config/paths.json", {"training_python": sys.executable,
                    "preprocessing_python": sys.executable, "raw_dir": str(self.project / "raw"),
                    "cache_dir": str(self.project / "cache"), "data_dir": str(self.project / "data")})
        atomic_json(self.project / "config/study.json", {"science_version": "SYNTHETIC_ONLY"})
        self.env = {**os.environ, "SLURM_JOB_ID": "synthetic-job", "CUDA_VISIBLE_DEVICES": "GPU-assigned-A,GPU-assigned-B"}
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.tmp.cleanup()

    def runner(self, tasks):
        factory = Factory(self.project, tasks)
        runner = s.SingleJob(self.project, popen=factory, environ=self.env, poll_seconds=0, heartbeat_seconds=0)
        return runner, factory

    def test_slots_use_only_actual_allocation_values(self):
        self.assertEqual(s.allocated_slots(self.env), ["GPU-assigned-A", "GPU-assigned-B"])
        self.assertEqual(s.allocated_slots({"CUDA_VISIBLE_DEVICES": "3,7"}), ["3", "7"])
        for mask in ("", "0", "0,0", "-1,0"):
            with self.assertRaises(RuntimeError):
                s.allocated_slots({"CUDA_VISIBLE_DEVICES": mask})
        runner, unused = self.runner([])
        self.assertEqual(runner.environment(1)["CUDA_VISIBLE_DEVICES"], "GPU-assigned-B")
        self.assertNotIn("torch", s.__dict__)

    def test_two_slots_skip_completed_and_keep_independent_tasks_after_failure(self):
        tasks = [task("done"), task("fails"), task("good1"), task("good2")]
        finish(self.project, tasks[0])
        runner, factory = self.runner(tasks)
        factory.fail.add("fails")
        self.assertEqual(runner.fit_pool(tasks, "development"), 1)
        self.assertEqual(factory.maximum, 2)
        commands = [c for c, unused in factory.calls]
        self.assertEqual(len(commands), 3)
        self.assertFalse(any("done" in c for c in commands))
        self.assertTrue(s.is_complete(self.project, tasks[2]))
        self.assertTrue(s.is_complete(self.project, tasks[3]))
        self.assertEqual([r["worker_exit_code"] for r in read_json(self.project / "state/development-unfinished.json")["failures"]], [9])
        devices = {kwargs["env"]["CUDA_VISIBLE_DEVICES"] for command, kwargs in factory.calls}
        self.assertEqual(devices, set(runner.slots))
        self.assertFalse(any("sbatch" in c or "srun" in c for c in commands))

    def test_exit_zero_without_completion_is_not_success(self):
        tasks = [task("missing")]
        runner, factory = self.runner(tasks)
        factory.omit_completion.add("missing")
        self.assertEqual(runner.fit_pool(tasks, "development"), 1)
        failure = read_json(self.project / "state/development-unfinished.json")["failures"][0]
        self.assertEqual(failure["worker_exit_code"], 0)
        self.assertFalse(failure["completion_verified"])

    def test_corrupt_completion_does_not_cancel_other_independent_work(self):
        tasks = [task("corrupt"), task("good")]
        atomic_json(self.project / "outputs/runs/corrupt/complete.json", {"status": "bad"})
        runner, unused = self.runner(tasks)
        self.assertEqual(runner.fit_pool(tasks, "development"), 1)
        self.assertTrue(s.is_complete(self.project, tasks[1]))

    def test_usr1_forwards_to_both_workers_and_term_has_precedence(self):
        runner, unused = self.runner([])
        first, second = FakeProcess(ticks=100), FakeProcess(ticks=100)
        runner.children = {first: {"stage": "test"}, second: {"stage": "test"}}
        runner.request_stop(signal.SIGUSR1)
        self.assertEqual(runner.stop_code, 75)
        self.assertEqual(first.signals, [signal.SIGUSR1])
        self.assertEqual(second.signals, [signal.SIGUSR1])
        # Still-active checkpoint writers receive cancellation after the warning.
        first.ticks = second.ticks = 100
        runner.request_stop(signal.SIGTERM)
        self.assertEqual(runner.stop_code, 143)
        self.assertEqual(first.signals[-1], signal.SIGTERM)
        self.assertEqual(second.signals[-1], signal.SIGTERM)

    def test_execute_source_selection_then_final_and_complete_analysis(self):
        development, final = [task("dev-a"), task("dev-b")], [task("final-a", "final")]
        runner, factory = self.runner(development+final)
        atomic_json(self.project / "tasks.json", development)
        def append(unused_project):
            self.assertTrue(all(s.is_complete(self.project, item) for item in development))
            atomic_json(self.project / "tasks.json", development+final)
            return final
        with mock.patch.object(runner, "ensure_inputs", return_value=0), \
                mock.patch.object(runner, "smoke_slots", return_value=0), \
                mock.patch("hpcmi.plan.create_plan"), \
                mock.patch("hpcmi.plan.append_final_tasks", side_effect=append) as selector, \
                mock.patch("hpcmi.analysis.analyze", return_value={"status": "complete"}):
            self.assertEqual(runner.execute(), 0)
        self.assertEqual(selector.call_count, 1)
        self.assertEqual(len(factory.calls), 3)
        self.assertEqual(read_json(self.project / "state/single_job_status.json")["stage"], "complete")
        # A completed restart consumes only saved completion records.
        before = len(factory.calls)
        self.assertEqual(runner.fit_pool(development+final, "saved_resume"), 0)
        self.assertEqual(len(factory.calls), before)

    def test_failed_stage_preserves_real_return_code(self):
        runner, unused = self.runner([])
        runner.popen = lambda *a, **kw: FakeProcess(code=28, ticks=0)
        with self.assertRaises(s.StageFailure) as error:
            runner.run_stage("raw_download", [sys.executable, "-c", "raise SystemExit(28)"])
        self.assertEqual(error.exception.returncode, 28)
        event = json.loads((self.project / "state/single_job_history.jsonl").read_text().splitlines()[-1])
        self.assertEqual(event["worker_exit_code"], 28)
        self.assertEqual(event["stage"], "raw_download")

    def test_cancellation_during_cleanup_controls_final_exit(self):
        runner, unused = self.runner([])
        def work():
            runner.request_stop(signal.SIGUSR1)
            return 75
        def cleanup():
            runner.request_stop(signal.SIGTERM)
        with mock.patch.object(runner, "start_sync"), mock.patch.object(runner, "execute", side_effect=work), \
                mock.patch.object(runner, "stop_sync", side_effect=cleanup):
            self.assertEqual(runner.run(), 143)

    def test_prepared_receipt_reuses_metadata_without_raw_scan_or_preprocessing(self):
        runner, unused = self.runner([])
        atomic_json(self.project / "state/data_prepared.json", {"status": "complete",
                    "data_dir": runner.paths["data_dir"], "fingerprint": "verified-synthetic-input"})
        registry = mock.Mock(fingerprint="verified-synthetic-input")
        with mock.patch("hpcmi.data.Registry", return_value=registry), \
                mock.patch("hpcmi.acquire.quick_raw_ready", side_effect=AssertionError("Repeated raw scan")), \
                mock.patch.object(runner, "run_stage", side_effect=AssertionError("Repeated preparation")):
            self.assertEqual(runner.ensure_inputs(), 0)

    def test_reporting_exit_race_and_failure_never_change_scientific_result(self):
        runner, unused = self.runner([])
        runner.sync_process = mock.Mock()
        runner.sync_process.poll.return_value = None
        runner.sync_process.terminate.side_effect = ProcessLookupError()
        runner.sync_stream = io.BytesIO()
        runner.sync_arguments = ["--once-synthetic-only"]
        with mock.patch.object(s.subprocess, "run", side_effect=s.subprocess.TimeoutExpired("synthetic", 45)):
            runner.stop_sync()
        self.assertTrue(runner.sync_stream.closed)
        self.assertIsNone(runner.stop_code)

    def test_preparation_is_direct_child_and_only_success_publishes_receipt(self):
        runner, unused = self.runner([])
        receipt = self.project / "state/data_prepared.json"
        registry = mock.Mock(fingerprint="prepared-synthetic", source_ids=["source-a"],
                             external_ids=["external-a", "external-b"])
        with mock.patch("hpcmi.acquire.quick_raw_ready", return_value=True), \
                mock.patch("hpcmi.data.Registry", return_value=registry), \
                mock.patch.object(runner, "run_stage", return_value=75) as stage:
            self.assertEqual(runner.ensure_inputs(), 75)
            self.assertFalse(receipt.exists())
            self.assertEqual(stage.call_args.args[1], [sys.executable, "-u", "-m", "hpcmi.raw_prepare",
                "--raw-dir", runner.paths["raw_dir"], "--cache-dir", runner.paths["cache_dir"],
                "--output", runner.paths["data_dir"]])
            self.assertNotIn("hpcmi.cli", stage.call_args.args[1])
            stage.return_value = 0
            self.assertEqual(runner.ensure_inputs(), 0)
        self.assertEqual(read_json(receipt)["fingerprint"], "prepared-synthetic")
        self.assertEqual(read_json(receipt)["source_people"], 1)
        self.assertEqual(read_json(receipt)["external_people"], 2)


if __name__ == "__main__":
    unittest.main()
