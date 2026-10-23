"""One synthetic end-to-end wiring check; no EEG, scheduler, network or GPU.

Thirty miniature CPU tasks exercise the real planner, worker, checkpoint writer,
evaluator, source-only final selection, statistical analyzer and progress
collector. An in-memory Registry stand-in reduces input to [4,3,3,64]; the real
NPZ/manifest importer has its own tests. Production study.json is never changed.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from hpcmi import analysis, data, plan, worker
from hpcmi.checkpoint import canonical_hash
from hpcmi.github_sync import collect_progress


class SyntheticRegistry:
    """Deterministic interface fixture, explicitly not scientific EEG input."""
    def __init__(self, unused_directory):
        rng = np.random.default_rng(20261023)
        self.entries, self.values = [], {}
        for dataset, count, role in [("bnci", 5, "source"), ("yang", 5, "source"), ("dreyer", 2, "external")]:
            for index in range(count):
                person = dataset + "__synthetic%02d" % index
                self.entries.append({"id": person, "dataset": dataset, "role": role, "n_trials": 4})
                self.values[person] = {"X": rng.standard_normal((4, 3, 3, 64)).astype(np.float32),
                    "y": np.array([0, 1, 0, 1], dtype=np.int64),
                    "trial_ids": [person + "/trial%02d" % t for t in range(4)],
                    "sessions": ["session1/run1", "session1/run1", "session2/run1", "session2/run1"],
                    "dataset": dataset, "id": person, "role": role}
        self.by_id = {entry["id"]: entry for entry in self.entries}
        self.source_ids = [p["id"] for p in self.entries if p["role"] == "source"]
        self.external_ids = [p["id"] for p in self.entries if p["role"] == "external"]
        self.fingerprint = canonical_hash({"fixture": "synthetic-e2e-only-v1", "shape": [4, 3, 3, 64], "people": self.entries})

    def ensure_source(self, ids):
        if len(set(ids)) != len(ids) or any(self.by_id[x]["role"] != "source" for x in ids):
            raise ValueError("Synthetic fixture source identity error")

    def load_person(self, person):
        return self.values[person]


class EndToEndTests(unittest.TestCase):
    def test_plan_train_select_evaluate_analyze_and_collect(self):
        with tempfile.TemporaryDirectory(prefix="paper1-synthetic-e2e-") as temporary:
            project = Path(temporary) / "synthetic-paper1-only"
            (project / "config").mkdir(parents=True)
            study = {"science_version": "SYNTHETIC_E2E_NOT_EEG_v1", "methods": list(plan.METHODS),
                "input_shape": [3, 3, 64], "source_folds": 5, "split_seed": 731,
                "validation_seeds": [111], "final_seeds": [222],
                "expected_source_counts": {"bnci": 5, "yang": 5},
                "epochs": 1, "updates_per_epoch": 1, "subjects_per_batch": 2,
                "trials_per_class": 1, "batch_size": 4, "torch_threads": 1,
                "checkpoint_seconds": 180, "heartbeat_seconds": 30, "eval_batch_size": 4,
                "learning_rate": .001, "amp": False,
                "architecture": {"F1": 2, "D": 1, "F2": 2, "kernel_length": 8, "dropout": .25},
                "objective": {"tail_weight": .5, "tail_fraction": .5, "consistency_weight": .1, "groupdro_eta": .01},
                "bootstrap_replicates": 32, "permutation_replicates": 32, "analysis_seed": 919}
            (project / "config/study.json").write_text(json.dumps(study))
            # Patch only the input interface; every execution/output component is real.
            with patch.object(data, "Registry", SyntheticRegistry), patch.object(plan, "Registry", SyntheticRegistry), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                frozen = plan.create_plan(project)
                self.assertEqual(frozen["development_task_count"], 25)
                self.assertEqual(frozen["final_task_count"], 5)
                development = json.loads((project / "tasks.json").read_text())
                for task in development:
                    self.assertEqual(worker.run_task(project, task["id"], "cpu"), 0, task["id"])
                final = plan.append_final_tasks(project)
                self.assertEqual(len(final), 5)
                selection = json.loads((project / "state/selection.json").read_text())
                self.assertFalse(selection["target_outcomes_read"])
                self.assertEqual(set(selection["selected_epochs"].values()), {1})
                for task in final:
                    self.assertEqual(worker.run_task(project, task["id"], "cpu"), 0, task["id"])
                # Analysis/progress must consume saved predictions and summaries only.
                with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("Analysis attempted another model update")), \
                        patch.object(worker, "evaluate", side_effect=AssertionError("Analysis attempted inference")):
                    result = analysis.analyze(project)
                    progress = collect_progress(project)
                    self.assertEqual(worker.run_task(project, development[0]["id"], "cpu"), 0)
                self.assertEqual(plan.append_final_tasks(project), [])
            self.assertEqual(result["status"], "complete")
            self.assertEqual(set(result["domains"]), {"nested_outer", "external_fixed40", "external_source_selected"})
            self.assertEqual(result["domains"]["nested_outer"]["n_participants"], 10)
            self.assertEqual(result["domains"]["external_fixed40"]["n_participants"], 2)
            self.assertFalse(result["domains"]["external_fixed40"]["independent_external_confirmation"])
            self.assertEqual(result["new_model_fits"], 0)
            self.assertEqual(result["new_model_inference"], 0)
            self.assertEqual(progress["counts"], {"planned": 30, "observed": 30, "completed": 30, "failed": 0})
            summaries = list((project / "outputs/runs").glob("*/complete.json"))
            self.assertEqual(len(summaries), 30)
            self.assertEqual(sum(json.loads(p.read_text())["optimizer_updates"] for p in summaries), 30)
            self.assertEqual(sum(json.loads(p.read_text())["epochs_completed"] for p in summaries), 30)
            for path in summaries:
                row = json.loads(path.read_text())
                self.assertEqual(row["status"], "complete")
                self.assertTrue(row["complete"])
                for relative in row["evaluations"].values():
                    self.assertTrue((path.parent / relative).is_file())
            self.assertEqual(json.loads((project / "config/study.json").read_text()), study)


if __name__ == "__main__":
    unittest.main()
