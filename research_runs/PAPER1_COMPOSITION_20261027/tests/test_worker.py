"""Small synthetic CPU checks; no real EEG, downloads, credentials or GPU fits."""
import contextlib
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from compmi import worker


class SyntheticRegistry:
    def __init__(self):
        self.fingerprint = "f" * 64
        self.by_id = {}
        self.entries = {}
        for dataset, names, role in (("bnci", ("B1", "B2", "B3", "B4"), "source"),
                                      ("yang", ("Y1", "Y2", "Y3", "Y4"), "source"),
                                      ("dreyer", ("D1",), "external")):
            for name in names:
                person = dataset + "__" + name
                self.by_id[person] = {"dataset": dataset, "role": role}
                self.entries[person] = {"id": person, "dataset": dataset, "role": role,
                    "X": np.random.default_rng(len(self.entries) + 400).normal(size=(4, 3, 18, 320)).astype(np.float32),
                    "y": np.array([0, 1, 0, 1], dtype=np.int64),
                    "trial_ids": [person + "/t" + str(i) for i in range(4)],
                    "sessions": ["one", "one", "two", "two"]}
        self.source_ids = [key for key, row in self.by_id.items() if row["role"] == "source"]
        self.external_ids = [key for key, row in self.by_id.items() if row["role"] == "external"]

    def ensure_source(self, ids):
        if not ids or len(ids) != len(set(ids)) or any(self.by_id[person]["role"] != "source" for person in ids):
            raise ValueError("Not unique source people")

    def load_person(self, person):
        return self.entries[person]


def tree_equal(test, left, right):
    if isinstance(left, torch.Tensor):
        test.assertTrue(torch.equal(left, right), "Tensor differs after continuation")
    elif isinstance(left, np.ndarray):
        np.testing.assert_array_equal(left, right)
    elif isinstance(left, dict):
        test.assertEqual(set(left), set(right))
        for key in left:
            tree_equal(test, left[key], right[key])
    elif isinstance(left, (tuple, list)):
        test.assertEqual(len(left), len(right))
        for a, b in zip(left, right):
            tree_equal(test, a, b)
    else:
        test.assertEqual(left, right)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = SyntheticRegistry()
        self.ids = ["bnci__B1", "bnci__B2", "yang__Y1", "yang__Y2"]
        self.whitelist = {person: [0, 1] for person in self.ids}
        self.config = {"science_version": "SYNTHETIC_COMPOSITION_TEST", "epochs": 2, "updates_per_epoch": 3,
                       "subjects_per_batch": 4, "trials_per_class": 16, "batch_size": 128,
                       "torch_threads": 1, "heartbeat_seconds": 0, "checkpoint_seconds": 99999,
                       "eval_batch_size": 2, "amp": False,
                       "architecture": {"F1": 2, "D": 1, "F2": 2, "kernel_length": 8, "dropout": .25},
                       "objective": {"tail_weight": .5, "tail_fraction": .5}}
        self.task = {"id": "synthetic", "family": "neural", "phase": "development", "method": "erm",
                     "cell_id": "S60-all", "pool": "S60", "subset": None, "regime": "all", "seed": 821,
                     "fold": 0, "train_ids": self.ids, "validation_ids": [], "test_ids": ["bnci__B3"],
                     "train_trials_file": "state/trialsets/synthetic.json", "train_trials_sha256": "1" * 64}

    def tearDown(self):
        self.temp.cleanup()

    def project(self, name, task=None):
        project = self.root / name
        (project / "config").mkdir(parents=True)
        (project / "config/study.json").write_text(json.dumps(self.config))
        (project / "config/paths.json").write_text(json.dumps({"data_dir": str(self.root / "fake-data")}))
        (project / "tasks.json").write_text(json.dumps([task or self.task]))
        return project

    def run_task(self, project, stop=None, whitelist=None):
        with patch.object(worker, "Registry", return_value=self.registry), \
                patch("compmi.plan.task_trialset", return_value=whitelist or self.whitelist), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return worker.run_task(project, "synthetic", "cpu", stop)

    def state(self, project):
        return torch.load(project / "outputs/runs/synthetic/checkpoints/latest.pt", map_location="cpu", weights_only=False)

    def test_batch_is_distinct_eight_groups_and_uses_only_fixed_trialset(self):
        for ids in (self.ids, ["bnci__B1", "bnci__B2", "bnci__B3", "bnci__B4"]):
            indices = {person: [0, 1] for person in ids}
            sampler = worker.TrialsetSampler(self.registry, ids, self.config, 12, indices)
            x, y, groups = sampler.batch()
            self.assertEqual(tuple(x.shape), (128, 3, 18, 320))
            self.assertEqual(torch.bincount(groups).tolist(), [16] * 8)
            self.assertEqual(torch.bincount(y).tolist(), [64, 64])
            for person in ids:
                for label in (0, 1):
                    group = sampler.group_index[person, label]
                    expected = torch.from_numpy(self.registry.entries[person]["X"][label])
                    self.assertTrue(torch.equal(x[groups == group], expected.repeat(16, 1, 1, 1)))
            state = sampler.state_dict()
            resumed = worker.TrialsetSampler(self.registry, ids, self.config, 12, indices)
            resumed.load_state_dict(state)
            for a, b in zip(sampler.batch(), resumed.batch()):
                self.assertTrue(torch.equal(a, b))
            changed = worker.TrialsetSampler(self.registry, ids, self.config, 12, {person: [2, 3] for person in ids})
            with self.assertRaisesRegex(ValueError, "different training trial whitelist"):
                changed.load_state_dict(state)

    def test_mid_epoch_resume_matches_and_completed_task_skips(self):
        for method in ("erm", "tail"):
            task = dict(self.task, method=method)
            continuous = self.project("continuous-" + method, task)
            resumed = self.project("resumed-" + method, task)
            self.assertEqual(self.run_task(continuous), 0)
            self.assertEqual(self.run_task(resumed, 2), 75)
            self.assertEqual(self.state(resumed)["step_in_epoch"], 2)
            self.assertEqual(self.run_task(resumed), 0)
            left, right = self.state(continuous), self.state(resumed)
            for key in ("model", "optimizer", "scheduler", "scaler", "rng", "sampler", "objective", "epoch",
                        "step_in_epoch", "global_step", "training_history", "validation_history"):
                tree_equal(self, left[key], right[key])
            self.assertEqual(right["global_step"], 6)
            self.assertEqual(right["validation_history"], [])
            done = json.loads((resumed / "outputs/runs/synthetic/complete.json").read_text())
            self.assertEqual(set(done["evaluations"]), {"outer_fixed40"})
            self.assertFalse(done["epoch_selection"])
            timestamp = (resumed / "outputs/runs/synthetic/checkpoints/latest.pt").stat().st_mtime_ns
            with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("Completed fit repeated")):
                self.assertEqual(self.run_task(resumed), 0)
            self.assertEqual((resumed / "outputs/runs/synthetic/checkpoints/latest.pt").stat().st_mtime_ns, timestamp)

    def test_final_evaluation_failure_resumes_without_any_optimizer_step(self):
        task = dict(self.task, phase="final", test_ids=["dreyer__D1"])
        project = self.project("evaluation-resume", task)
        original = worker.evaluate
        def fail_after_first_shard(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("Synthetic failure after held-out evaluation")
        with patch.object(worker, "evaluate", fail_after_first_shard):
            self.assertEqual(self.run_task(project), 1)
        self.assertEqual(self.state(project)["global_step"], 6)
        shards = sorted((project / "outputs/runs/synthetic/evaluations/fixed40").glob("*/*.npz"))
        self.assertEqual(len(shards), 2)
        before = [(path, path.stat().st_mtime_ns) for path in shards]
        with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("Training repeated while resuming evaluation")):
            self.assertEqual(self.run_task(project), 0)
        self.assertEqual([(path, path.stat().st_mtime_ns) for path in shards], before)
        done = json.loads((project / "outputs/runs/synthetic/complete.json").read_text())
        self.assertEqual(set(done["evaluations"]), {"fixed40"})

    def test_trialset_change_missing_checkpoint_and_target_training_do_not_reset(self):
        project = self.project("contract")
        self.assertEqual(self.run_task(project, 2), 75)
        changed = dict(self.task, train_trials_sha256="2" * 64)
        (project / "tasks.json").write_text(json.dumps([changed]))
        self.assertEqual(self.run_task(project), 1)
        self.assertEqual(self.state(project)["global_step"], 2)
        (project / "tasks.json").write_text(json.dumps([self.task]))
        checkpoints = project / "outputs/runs/synthetic/checkpoints"
        (checkpoints / "latest.pt").unlink()
        (checkpoints / "previous.pt").unlink()
        self.assertEqual(self.run_task(project), 1)
        self.assertFalse((checkpoints / "latest.pt").exists())
        bad = dict(self.task, train_ids=["bnci__B1", "bnci__B2", "yang__Y1", "dreyer__D1"])
        leaked = self.project("target", bad)
        with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("External input reached training")):
            self.assertEqual(self.run_task(leaked), 1)
        self.assertFalse((leaked / "outputs/runs/synthetic/checkpoints/latest.pt").exists())

    def test_sigterm_dominates_requested_requeue_and_keeps_checkpoint(self):
        state = worker.SignalState()
        state.handler(signal.SIGUSR1, None)
        state.handler(signal.SIGTERM, None)
        with self.assertRaises(worker.RequestedStop) as found:
            state.check()
        self.assertEqual(found.exception.code, 143)


if __name__ == "__main__":
    unittest.main()
