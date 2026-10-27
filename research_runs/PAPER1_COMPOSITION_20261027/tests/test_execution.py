import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compmi import runner, launch
from hpcmi.common import atomic_json


class FakeProcess:
    counter = 100

    def __init__(self, code=0):
        type(self).counter += 1
        self.pid = self.counter
        self.code = code
        self.signals = []

    def poll(self):
        return self.code

    def send_signal(self, value):
        self.signals.append(value)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "paper1-composition-v2"
        atomic_json(self.project / "config/paths.json", {"training_python": sys.executable, "data_dir": "/unused"})
        self.env = {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": "GPU-left,GPU-right"}

    def tearDown(self):
        self.temp.cleanup()

    def test_slots_use_slurm_identifiers(self):
        self.assertEqual(runner.allocated_slots(self.env), ["GPU-left", "GPU-right"])
        for value in ("", "0", "0,0", "0,1,2", "-1,2"):
            with self.assertRaises(RuntimeError):
                runner.allocated_slots({"CUDA_VISIBLE_DEVICES": value})

    def test_child_cuda_assignment_and_thread_budget(self):
        value = runner.Runner(self.project, environ=self.env)
        self.assertEqual(value.child_environment(1)["CUDA_VISIBLE_DEVICES"], "GPU-right")
        self.assertEqual(value.child_environment()["CUDA_VISIBLE_DEVICES"], "")
        self.assertEqual(value.child_environment(0)["OPENBLAS_NUM_THREADS"], "1")

    def test_cancellation_overrides_preemption(self):
        value = runner.Runner(self.project, environ=self.env)
        child = FakeProcess(code=None)
        value.children[child] = {}
        value.request_stop(signal.SIGUSR1)
        self.assertEqual(value.stop_code, 75)
        self.assertEqual(child.signals[-1], signal.SIGUSR1)
        value.request_stop(signal.SIGTERM)
        value.request_stop(signal.SIGUSR1)
        self.assertEqual(value.stop_code, 143)
        self.assertEqual(child.signals[-1], signal.SIGTERM)

    def task(self, name="one", family="neural", phase="development"):
        return {"id": name, "family": family, "cell_id": "s9-all", "phase": phase,
                "method": "erm" if family == "neural" else "weighted_csp_rlda", "seed": 1 if family == "neural" else 0,
                "fold": 0 if phase == "development" else None, "train_trials_sha256": "a" * 64,
                "epochs": 40, "updates_per_epoch": 128, "test_ids": ["test-person"]}

    def complete(self, task):
        run = self.project / "outputs/runs" / task["id"]
        variant = "outer_fixed40" if task["phase"] == "development" else "fixed40"
        atomic_json(run / "evaluations/summary.json", {"variant": variant, "model_sha256": "b" * 64,
                    "people": [{"person_id": "test-person", "variant": variant, "seed": task["seed"]}]})
        value = {**task, "status": "complete", "complete": True, "task_id": task["id"],
                 "global_step": 5120 if task["family"] == "neural" else 0,
                 "optimizer_updates": 5120 if task["family"] == "neural" else 0, "epochs_completed": 40,
                 "classical_fits_completed": 1, "model_sha256": "b" * 64,
                 "evaluations": {variant: "evaluations/summary.json"}}
        atomic_json(run / "complete.json", value)
        return run, value

    def test_complete_requires_endpoint_and_evaluation_identity(self):
        task = self.task()
        self.assertFalse(runner.is_complete(self.project, task))
        run, value = self.complete(task)
        self.assertTrue(runner.is_complete(self.project, task))
        value["optimizer_updates"] = 5119
        atomic_json(run / "complete.json", value)
        with self.assertRaises(ValueError):
            runner.is_complete(self.project, task)
        value["optimizer_updates"] = 5120
        atomic_json(run / "complete.json", value)
        (run / "evaluations/summary.json").unlink()
        with self.assertRaises(ValueError):
            runner.is_complete(self.project, task)

    def test_classical_complete_is_not_neural_update(self):
        task = self.task(family="classical", phase="final")
        self.complete(task)
        self.assertTrue(runner.is_complete(self.project, task))

    def test_failed_task_does_not_cancel_final_or_other_family(self):
        tasks = [self.task("failed"), self.task("good-final", phase="final"), self.task("csp", family="classical")]
        launched = []

        def popen(command, **kwargs):
            task_id = command[command.index("--task-id") + 1]
            launched.append(task_id)
            if task_id != "failed":
                self.complete(next(t for t in tasks if t["id"] == task_id))
            return FakeProcess(1 if task_id == "failed" else 0)

        value = runner.Runner(self.project, popen=popen, environ=self.env, poll_seconds=0)
        self.assertEqual(value.pool(tasks), 0)
        self.assertEqual(set(launched), {"failed", "good-final", "csp"})
        self.assertEqual(value.completed_count, 2)
        self.assertEqual([f["task_id"] for f in value.failures], ["failed"])
        # A later invocation skips completed final/classical work, retrying only failed.
        launched.clear()
        again = runner.Runner(self.project, popen=popen, environ=self.env, poll_seconds=0)
        again.pool(tasks)
        self.assertEqual(launched, ["failed"])

    def test_submission_one_node_two_gpu_shape_and_dedup(self):
        calls = []
        paths = {"training_python": sys.executable}
        plan = {"fingerprint": "f" * 64, "task_counts": {"total": 630}}
        for folder in ("logs", "logs/slurm"):
            (self.project / folder).mkdir(parents=True, exist_ok=True)

        def command(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "456\n" if args[0] == "sbatch" else "", "")

        with patch.object(launch, "prepare_project", return_value=(paths, plan)), patch(
                "hpcmi.github_sync.confirm_credentials", return_value=Path("/private/token")) as credentials:
            result = launch.submit(self.project, command=command, sync_starter=lambda *a: 789)
            self.assertEqual(result["job_id"], "456")
            credentials.assert_called_once_with(launch.REPOSITORY, self.project.name, force=True, require_verified=True)
        sbatch = next(c for c in calls if c[0] == "sbatch")
        for value in ("--nodes=1", "--ntasks=1", "--gres=gpu:2", "--cpus-per-task=24", "--mem=128G", "--partition=hpc_gpu"):
            self.assertIn(value, sbatch)
        self.assertFalse(any("--array" in arg for arg in sbatch))
        calls.clear()

        def existing(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "456|p1-comp|RUNNING|" + str(self.project) + "\n", "")

        with patch.object(launch, "prepare_project", return_value=(paths, plan)), patch(
                "hpcmi.github_sync.confirm_credentials", return_value=Path("/private/token")) as credentials:
            result = launch.submit(self.project, command=existing, sync_starter=lambda *a: 789)
            self.assertEqual(result["status"], "EXISTING_ALLOCATION_REUSED")
            credentials.assert_called_once_with(launch.REPOSITORY, self.project.name, force=False, require_verified=False)
        self.assertEqual([a[0] for a in calls], ["squeue"])

    def test_shell_requeue_is_only_preemption_and_exit75(self):
        shell = (ROOT / "slurm/single_job.sh").read_text()
        self.assertIn('if [ "$cancel_code" -ne 0 ]; then exit "$cancel_code"; fi', shell)
        self.assertIn('[ "$usr1_requested" -eq 1 ] && [ "$runner_code" -eq 75 ]', shell)
        self.assertEqual(shell.count('scontrol requeue "${SLURM_JOB_ID:?}"'), 1)
        self.assertNotIn("sbatch", shell)

    def test_preparation_preserves_venv_python_path_without_install(self):
        base = Path(self.temp.name) / "base"
        data = Path(self.temp.name) / "prepared"
        atomic_json(base / "config/paths.json", {"data_dir": str(data)})
        atomic_json(base / "state/data_prepared.json", {"status": "complete", "data_dir": str(data), "fingerprint": "fixed"})
        interpreter = Path(self.temp.name) / "venv/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(sys.executable)
        (self.project / "config/paths.json").unlink()
        registry = types.SimpleNamespace(fingerprint="fixed")
        with patch("hpcmi.data.Registry", return_value=registry), patch("compmi.plan.create_plan", return_value={"total": 630}):
            paths, _ = launch.prepare_project(self.project, base, str(interpreter))
        self.assertEqual(paths["training_python"], str(interpreter))
        self.assertNotEqual(paths["training_python"], str(interpreter.resolve()))


if __name__ == "__main__":
    unittest.main()
