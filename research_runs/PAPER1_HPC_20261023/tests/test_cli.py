"""Orchestration integration tests with no scheduler, network, EEG, or GPU."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hpcmi import cli
from hpcmi.common import atomic_json, exclusive_lock, read_json


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "paper1-test"
        self.paths = cli.setup(self.project, sys.executable, prep_python=sys.executable)
        self.study = read_json(self.project / "config/study.json")
        self.tasks = [self.task("dev-a"), self.task("dev-b", method="tail_consistency")]
        atomic_json(self.project / "tasks.json", self.tasks)
        self.patchers = ExitStack()
        self.mocks = {}
        for module, name, value in (
            ("hpcmi.slurm", "auxiliary_state", {"state": "NOT_SUBMITTED", "job_id": None, "record": None}),
            ("hpcmi.slurm", "submit_auxiliary", "101"),
            ("hpcmi.slurm", "active_task_ids", set()),
            ("hpcmi.slurm", "task_scheduler_states", {}),
            ("hpcmi.slurm", "submit_task_array", "102"),
            ("hpcmi.plan", "create_plan", {"fingerprint": "test-plan"}),
            ("hpcmi.plan", "append_final_tasks", []),
            ("hpcmi.analysis", "analyze", {"status": "complete"}),
        ):
            self.mocks[name] = self.patchers.enter_context(patch(module + "." + name, return_value=value))

    def tearDown(self):
        self.patchers.close()
        self.tmp.cleanup()

    @staticmethod
    def task(identifier, phase="development", method="erm", seed=20261031):
        return {"id": identifier, "phase": phase, "method": method, "seed": seed,
                "fold": 0 if phase == "development" else None,
                "train_ids": ["source-a"], "validation_ids": ["source-b"] if phase == "development" else [],
                "test_ids": ["source-c"] if phase == "development" else ["target-a"],
                **({"selected_epoch": 4} if phase == "final" else {})}

    def prepared(self):
        atomic_json(self.project / "state/data_prepared.json", {
            "status": "complete", "data_dir": self.paths["data_dir"], "fingerprint": "data-fingerprint",
            "source_people": 60, "external_people": 87})

    def smoke(self, **overrides):
        metadata = {"python": "3.12.3", "torch": "2.5.1+cu121", "numpy": "2.2.6", "executable": sys.executable}
        atomic_json(self.project / "state/training_metadata.json", metadata)
        identity = {k: metadata[k] for k in ("python", "torch", "numpy")}
        identity.update(cuda_build="12.1", architecture=self.study["architecture"],
                        input_shape=self.study["input_shape"], device_type="cuda",
                        capability=[8, 0], device_name="NVIDIA A100-SXM4-80GB", driver="not_observed")
        from hpcmi.common import canonical_hash
        result = {"status": "passed", "synthetic_only": True, "new_scientific_fits": 0,
                  "gpu_verified": True, "forward_backward_save_restore": True,
                  "identity": identity, "fingerprint": canonical_hash(identity), **overrides}
        atomic_json(self.project / "state/gpu_smoke.json", result)

    def complete(self, task, **overrides):
        directory = self.project / "outputs/runs" / task["id"]
        variants = ["outer_best"] if task["phase"] == "development" else ["fixed40", "source_selected"]
        evaluations = {}
        for variant in variants:
            relative = "evaluations/" + variant + "/summary.json"
            evaluations[variant] = relative
            atomic_json(directory / relative, {"variant": variant, "model_sha256": "example",
                                              "people": [{"id": task["test_ids"][0]}]})
        result = {"status": "complete", "complete": True, "task_id": task["id"], "id": task["id"],
                  "phase": task["phase"], "method": task["method"], "seed": task["seed"],
                  "fold": task["fold"], "best_epoch": 4, "selected_epoch": task.get("selected_epoch"),
                  "global_step": 5120, "optimizer_updates": 5120, "epochs_completed": 40,
                  "fingerprint": "science-fingerprint", "evaluations": evaluations, **overrides}
        atomic_json(directory / "complete.json", result)
        return directory

    def ready(self):
        self.prepared()
        self.smoke()

    def test_initial_stage_submits_cpu_preparation_only(self):
        result = cli.controller_tick(self.project)
        self.assertEqual(result["stage"], "data_preprocessing")
        self.assertEqual(self.mocks["submit_auxiliary"].call_args.args[1], "prep")
        self.mocks["submit_task_array"].assert_not_called()
        self.mocks["create_plan"].assert_not_called()

    def test_failed_preparation_is_not_automatically_resubmitted(self):
        self.mocks["auxiliary_state"].return_value = {"state": "FAILED", "job_id": "100", "record": {}}
        result = cli.controller_tick(self.project)
        self.assertTrue(result["manual_resume_required"])
        self.mocks["submit_auxiliary"].assert_not_called()

    def test_prepared_data_next_submits_smoke_once(self):
        self.prepared()
        result = cli.controller_tick(self.project)
        self.assertEqual(result["stage"], "once_per_runtime_gpu_smoke")
        self.assertEqual(self.mocks["submit_auxiliary"].call_args.args[1], "smoke")
        self.mocks["submit_task_array"].assert_not_called()

    def test_bad_prepared_or_cpu_only_smoke_receipt_never_allows_training(self):
        self.prepared()
        self.smoke(gpu_verified=False)
        with self.assertRaisesRegex(ValueError, "GPU smoke"):
            cli.controller_tick(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_smoke_from_changed_runtime_is_not_silently_reused(self):
        self.ready()
        path = self.project / "state/gpu_smoke.json"
        smoke = read_json(path)
        smoke["identity"]["torch"] = "2.4.0"
        from hpcmi.common import canonical_hash
        smoke["fingerprint"] = canonical_hash(smoke["identity"])
        atomic_json(path, smoke)
        with self.assertRaises(ValueError):
            cli.controller_tick(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_smoke_cpu_identity_does_not_prove_gpu_training_runtime(self):
        self.ready()
        path = self.project / "state/gpu_smoke.json"
        smoke = read_json(path)
        smoke["identity"]["device_type"] = "cpu"
        from hpcmi.common import canonical_hash
        smoke["fingerprint"] = canonical_hash(smoke["identity"])
        atomic_json(path, smoke)
        with self.assertRaises(ValueError):
            cli.controller_tick(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_existing_active_array_keeps_other_tasks_running(self):
        self.ready()
        self.mocks["active_task_ids"].return_value = {"dev-b"}
        self.mocks["task_scheduler_states"].return_value = {"dev-a": "FAILED", "dev-b": "RUNNING"}
        result = cli.controller_tick(self.project)
        self.assertEqual(result["stage"], "training_or_evaluation")
        self.mocks["submit_task_array"].assert_not_called()

    def test_background_never_resurrects_failed_cancelled_or_unknown(self):
        self.ready()
        for state in ("CANCELLED", "FAILED", "UNKNOWN", "TIMEOUT"):
            with self.subTest(state=state):
                self.mocks["task_scheduler_states"].return_value = {t["id"]: state for t in self.tasks}
                result = cli.controller_tick(self.project)
                self.assertEqual(result["stage"], "manual_resume_required")
        self.mocks["submit_task_array"].assert_not_called()

    def test_manual_resume_submits_only_missing_task(self):
        self.ready()
        self.complete(self.tasks[0])
        self.mocks["task_scheduler_states"].return_value = {"dev-a": "COMPLETED", "dev-b": "CANCELLED"}
        result = cli.controller_tick(self.project, explicit_resume=True)
        self.assertEqual(result["stage"], "array_submitted")
        self.assertEqual(self.mocks["submit_task_array"].call_args.args[1], ["dev-b"])
        self.mocks["append_final_tasks"].assert_not_called()

    def test_new_independent_task_can_start_without_reviving_cancelled_task(self):
        self.ready()
        self.mocks["task_scheduler_states"].return_value = {"dev-a": "CANCELLED"}
        cli.controller_tick(self.project)
        self.assertEqual(self.mocks["submit_task_array"].call_args.args[1], ["dev-b"])

    def test_complete_development_unlocks_final_phase_once(self):
        self.ready()
        for task in self.tasks:
            self.complete(task)
        final = self.task("final-a", "final")
        def append(_):
            atomic_json(self.project / "tasks.json", self.tasks + [final])
            return [final]
        self.mocks["append_final_tasks"].side_effect = append
        self.mocks["task_scheduler_states"].return_value = {t["id"]: "COMPLETED" for t in self.tasks}
        result = cli.controller_tick(self.project)
        self.assertEqual(result["stage"], "array_submitted")
        self.assertEqual(self.mocks["submit_task_array"].call_args.args[1], ["final-a"])
        self.mocks["append_final_tasks"].assert_called_once()

    def test_complete_final_analyzes_without_submitting(self):
        self.ready()
        final = self.task("final-a", "final")
        tasks = self.tasks + [final]
        atomic_json(self.project / "tasks.json", tasks)
        for task in tasks:
            self.complete(task)
        result = cli.controller_tick(self.project)
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["completed_fits"], 3)
        self.mocks["analyze"].assert_called_once_with(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_wrong_task_completion_is_not_a_completed_fit(self):
        self.ready()
        self.complete(self.tasks[0], task_id="wrong-task")
        with self.assertRaisesRegex(ValueError, "completion"):
            cli.controller_tick(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_missing_saved_evaluation_is_not_a_completed_fit(self):
        self.ready()
        directory = self.complete(self.tasks[0])
        (directory / "evaluations/outer_best/summary.json").unlink()
        with self.assertRaises(ValueError):
            cli.controller_tick(self.project)
        self.mocks["submit_task_array"].assert_not_called()

    def test_partial_analysis_cannot_mark_whole_study_complete(self):
        self.ready()
        for task in self.tasks:
            self.complete(task)
        self.mocks["analyze"].return_value = {"status": "partially_complete"}
        result = cli.controller_tick(self.project)
        self.assertNotEqual(result["stage"], "complete")
        self.mocks["submit_task_array"].assert_not_called()

    def test_duplicate_controller_process_does_not_tick_or_submit(self):
        with exclusive_lock(self.project / "state/controller_daemon.lock"):
            with patch("hpcmi.cli.controller_tick") as tick:
                self.assertEqual(cli.controller(self.project), 0)
                tick.assert_not_called()

    def test_launch_validates_github_authorization_before_any_submission(self):
        self.ready()
        args = SimpleNamespace(project=str(self.project), python=sys.executable, raw_dir=None,
                               data_dir=None, prep_python=None, repository=cli.REPOSITORY, wheelhouse=None)
        events = []
        def credentials(*args, **kwargs):
            events.append("credentials")
            return Path(self.tmp.name) / "private-token"
        def tick(*args, **kwargs):
            self.assertEqual(events, ["credentials"])
            events.append("tick")
            return {"stage": "array_submitted"}
        with patch("hpcmi.cli.runtime_metadata", return_value={"python": "3.12.3", "torch": "2.5.1+cu121", "numpy": "2.2.6"}), \
             patch("hpcmi.github_sync.confirm_credentials", side_effect=credentials), \
             patch("hpcmi.cli.controller_tick", side_effect=tick), \
             patch("hpcmi.cli._daemon") as daemon:
            self.assertEqual(cli.launch(args), 0)
            self.assertEqual(events, ["credentials", "tick"])
            self.assertEqual(daemon.call_count, 2)


if __name__ == "__main__":
    unittest.main()
