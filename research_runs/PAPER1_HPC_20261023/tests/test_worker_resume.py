"""Synthetic CPU checks of continuation and scientific task boundaries.

Run with the target API's CPU Torch build; no EEG, Slurm, credentials or GPU fits.
"""
import contextlib
import io
import json
import math
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from hpcmi import checkpoint, data, worker
from hpcmi.models import build_model, three_view_logits
from hpcmi.objectives import Objective, METHODS
from test_data import make_npz


def tree_equal(test, left, right):
    if isinstance(left, torch.Tensor):
        test.assertTrue(torch.equal(left, right), "Tensor differs after continuation")
    elif isinstance(left, np.ndarray):
        np.testing.assert_array_equal(left, right)
    elif isinstance(left, dict):
        test.assertEqual(set(left), set(right))
        for key in left:
            tree_equal(test, left[key], right[key])
    elif isinstance(left, (list, tuple)):
        test.assertEqual(len(left), len(right))
        for a, b in zip(left, right):
            tree_equal(test, a, b)
    else:
        test.assertEqual(left, right)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        groups = []
        for dataset, subjects, role in [("bnci", ["B1", "B2", "B3"], "source"),
                                         ("yang", ["Y1"], "source"), ("dreyer", ["D1"], "external")]:
            paths = []
            for subject in subjects:
                path = self.root / (subject + ".npz")
                make_npz(path, dataset, subject)
                paths.append(str(path))
            groups.append({"dataset": dataset, "role": role, "paths": paths})
        config = self.root / "source-config.json"
        config.write_text(json.dumps({"schema_version": 1, "preprocessing_id": "synthetic-worker-tests-v1", "datasets": groups}))
        with contextlib.redirect_stdout(io.StringIO()):
            data.prepare(config, self.root / "prepared")
        self.config = {"science_version": "SYNTHETIC_ONLY_v1", "input_shape": [3, 18, 320],
            "epochs": 2, "updates_per_epoch": 3, "subjects_per_batch": 2, "trials_per_class": 1,
            "batch_size": 4, "torch_threads": 1, "checkpoint_seconds": 99999, "heartbeat_seconds": 0,
            "eval_batch_size": 2, "amp": False,
            "architecture": {"F1": 2, "D": 1, "F2": 2, "kernel_length": 8, "dropout": .25},
            "objective": {"tail_weight": .5, "tail_fraction": .5, "consistency_weight": .1, "groupdro_eta": .01}}
        self.task = {"id": "synthetic", "phase": "development", "method": "tail_consistency", "seed": 821,
            "train_ids": ["bnci__B1", "yang__Y1"], "validation_ids": ["bnci__B2"],
            "test_ids": ["bnci__B3"], "fold": 0}

    def tearDown(self):
        self.temp.cleanup()

    def project(self, name, task=None):
        folder = self.root / name
        (folder / "config").mkdir(parents=True)
        (folder / "config/study.json").write_text(json.dumps(self.config))
        (folder / "config/data_path.json").write_text(json.dumps({"data_dir": str(self.root / "prepared")}))
        (folder / "tasks.json").write_text(json.dumps([task or self.task]))
        return folder

    def run_task(self, project, stop=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return worker.run_task(project, "synthetic", "cpu", stop)

    def state(self, project):
        return torch.load(project / "outputs/runs/synthetic/checkpoints/latest.pt", map_location="cpu", weights_only=False)

    def test_all_methods_mid_epoch_resume_exact(self):
        for method in METHODS:
            with self.subTest(method=method):
                task = dict(self.task, method=method)
                uninterrupted = self.project("continuous-" + method, task)
                interrupted = self.project("resumed-" + method, task)
                self.assertEqual(self.run_task(uninterrupted), 0)
                self.assertEqual(self.run_task(interrupted, 2), 75)
                before = self.state(interrupted)
                self.assertEqual(before["global_step"], 2)
                self.assertEqual(before["step_in_epoch"], 2)
                self.assertEqual(self.run_task(interrupted), 0)
                a, b = self.state(uninterrupted), self.state(interrupted)
                for key in ["model", "optimizer", "scheduler", "scaler", "rng", "sampler", "objective", "epoch", "step_in_epoch", "global_step", "best_model", "best_epoch", "validation_history", "training_history"]:
                    tree_equal(self, a[key], b[key])
                self.assertEqual(b["global_step"], 6)
                latest = interrupted / "outputs/runs/synthetic/checkpoints/latest.pt"
                timestamp = latest.stat().st_mtime_ns
                self.assertEqual(self.run_task(interrupted), 0)
                self.assertEqual(latest.stat().st_mtime_ns, timestamp)

    def test_signal_checkpoint_and_cancellation_dominates_requeue(self):
        project = self.project("signal")
        original = worker.Progress.emit
        sent = []
        def emit(progress, stage, *args, **kwargs):
            original(progress, stage, *args, **kwargs)
            if stage == "training" and progress.global_step == 1 and not sent:
                sent.append(True)
                os.kill(os.getpid(), signal.SIGUSR1)
                os.kill(os.getpid(), signal.SIGTERM)
        with patch.object(worker.Progress, "emit", emit):
            self.assertEqual(self.run_task(project), 143)
        self.assertEqual(self.state(project)["global_step"], 1)
        status = json.loads((project / "outputs/runs/synthetic/status.json").read_text())
        self.assertFalse(status["automatic_requeue_requested"])
        self.assertEqual(status["stage"], "cancelled_checkpointed")
        self.assertEqual(self.run_task(project), 0)
        self.assertEqual(self.state(project)["global_step"], 6)

    def test_external_evaluation_failure_resumes_without_optimizer_update(self):
        task = dict(self.task, phase="final", validation_ids=[], test_ids=["dreyer__D1"], selected_epoch=1)
        project = self.project("eval-retry", task)
        original = worker.atomic_npz
        saved = []
        def fail_second_session(path, **arrays):
            if "fixed40" in str(path):
                if saved:
                    raise OSError("Synthetic evaluation disk interruption")
                saved.append(Path(path))
            return original(path, **arrays)
        with patch.object(worker, "atomic_npz", fail_second_session):
            self.assertEqual(self.run_task(project), 1)
        self.assertEqual(self.state(project)["global_step"], 6)
        saved_time = saved[0].stat().st_mtime_ns
        with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("Training repeated during evaluation resume")):
            self.assertEqual(self.run_task(project), 0)
        self.assertEqual(saved[0].stat().st_mtime_ns, saved_time)
        complete = json.loads((project / "outputs/runs/synthetic/complete.json").read_text())
        self.assertEqual(set(complete["evaluations"]), {"fixed40", "source_selected"})
        self.assertTrue(complete["complete"])
        for relative in complete["evaluations"].values():
            row = json.loads((project / "outputs/runs/synthetic" / relative).read_text())["people"][0]
            self.assertEqual(row["n"], 4)
            self.assertEqual(row["n_left"], 2)
            self.assertEqual(row["n_right"], 2)
            self.assertEqual(row["ba"], (row["recall_left"] + row["recall_right"]) / 2)

    def test_corrupt_latest_falls_back_and_keeps_bad_bytes(self):
        project = self.project("corruption")
        self.assertEqual(self.run_task(project, 2), 75)
        folder = project / "outputs/runs/synthetic/checkpoints"
        (folder / "latest.pt").write_bytes(b"deliberately incomplete synthetic checkpoint")
        self.assertEqual(self.run_task(project), 0)
        bad = list(folder.glob("latest.pt.unreadable-*"))
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0].read_bytes(), b"deliberately incomplete synthetic checkpoint")
        self.assertTrue(list(folder.glob("recovery-*.json")))

    def test_science_change_and_missing_checkpoint_do_not_reset(self):
        project = self.project("contract")
        self.assertEqual(self.run_task(project, 2), 75)
        config_path = project / "config/study.json"
        modified = dict(self.config, learning_rate=.002)
        config_path.write_text(json.dumps(modified))
        self.assertEqual(self.run_task(project), 1)
        self.assertEqual(self.state(project)["global_step"], 2)
        config_path.write_text(json.dumps(self.config))
        folder = project / "outputs/runs/synthetic/checkpoints"
        (folder / "latest.pt").unlink()
        (folder / "previous.pt").unlink()
        self.assertEqual(self.run_task(project), 1)
        self.assertFalse((folder / "latest.pt").exists())
        (folder / "checkpoint_status.json").unlink()
        self.assertEqual(self.run_task(project), 1)
        self.assertFalse((folder / "latest.pt").exists())

    def test_target_identity_cannot_train_or_select(self):
        task = dict(self.task, train_ids=["dreyer__D1", "yang__Y1"])
        project = self.project("target-leak", task)
        with patch.object(torch.optim.Adam, "step", side_effect=AssertionError("Target used in fit")):
            self.assertEqual(self.run_task(project), 1)
        self.assertFalse((project / "outputs/runs/synthetic/checkpoints/latest.pt").exists())

    def test_convex_tail_scale_and_groupdro_inclusion_correction(self):
        logits = [torch.tensor([[0., 0.], [0., 0.]], requires_grad=True) for _ in range(3)]
        labels = torch.tensor([0, 1])
        groups = torch.tensor([0, 1])
        for method in ["erm", "tail", "consistency", "tail_consistency"]:
            objective = Objective(method, 2, self.config, "cpu")
            value, _ = objective(logits, labels, groups)
            self.assertAlmostEqual(value.item(), math.log(2), places=6)
        objective = Objective("groupdro", 4, self.config, "cpu", [.5, .5, .25, .25])
        value, _ = objective(logits, labels, groups)
        self.assertAlmostEqual(value.item(), math.log(2), places=6)
        # 2 observed groups, old q=.25, pi=.5: estimated risk is exactly CE.
        self.assertGreater(objective.log_q[0].item(), objective.log_q[2].item())
        self.assertEqual(objective.state_dict()["inclusion_probabilities"].tolist(), [.5, .5, .25, .25])

    def test_groupdro_prior_inclusion_and_duplicate_aggregation(self):
        registry = data.Registry(self.root / "prepared")
        config = dict(self.config, subjects_per_batch=8, batch_size=16)
        sampler = worker.BalancedSampler(registry, registry.source_ids, config, 2)
        for person in registry.source_ids:
            expected = 1 - (2/3)**4 if person.startswith("bnci") else 1.
            prior = 1/12 if person.startswith("bnci") else 1/4
            for label in [0, 1]:
                g = sampler.group_index[person, label]
                self.assertAlmostEqual(sampler.inclusion_probabilities[g], expected)
                self.assertAlmostEqual(sampler.group_prior[g], prior)
        args = ("groupdro", 8, config, "cpu", sampler.inclusion_probabilities, sampler.group_prior)
        a, b = Objective(*args), Objective(*args)
        logits = torch.tensor([[.2, -.3], [.4, .9]], requires_grad=True)
        labels, groups = torch.tensor([0, 1]), torch.tensor([0, 1])
        loss, _ = a([logits]*3, labels, groups)
        repeated = logits.repeat_interleave(3, dim=0)
        other, _ = b([repeated]*3, labels.repeat_interleave(3), groups.repeat_interleave(3))
        self.assertTrue(torch.allclose(loss, other))
        self.assertTrue(torch.allclose(a.log_q, b.log_q))
        # Enumerate one of two Yang people per batch: HT risk averages to the
        # equal-cohort reference risk although group inclusion is unequal.
        conf = {"objective": {"groupdro_eta": 0.}}
        pi, prior = [1., 1., .5, .5, .5, .5], [.25, .25, .125, .125, .125, .125]
        ce = torch.tensor([.4, .5, .6, .7, .8, .9])
        estimates = []
        for selected in [[0, 1, 2, 3], [0, 1, 4, 5]]:
            selected = torch.tensor(selected)
            chosen_ce = ce[selected]
            z = torch.stack([torch.zeros(4), torch.log(torch.expm1(chosen_ce))], dim=1)
            value, _ = Objective("groupdro", 6, conf, "cpu", pi, prior)([z]*3, torch.zeros(4, dtype=torch.long), selected)
            estimates.append(value)
        self.assertAlmostEqual(torch.stack(estimates).mean().item(), (ce * torch.tensor(prior)).sum().item(), places=6)

    def test_shared_forward_bn_exposure_and_inference_immutability(self):
        worker.configure(self.config, "cpu")
        model = build_model(self.config, "cpu")
        before = [int(m.num_batches_tracked) for m in model.modules() if isinstance(m, torch.nn.BatchNorm2d)]
        three_view_logits(model, torch.randn(4, 3, 18, 320))
        after = [int(m.num_batches_tracked) for m in model.modules() if isinstance(m, torch.nn.BatchNorm2d)]
        self.assertEqual(after, [value + 1 for value in before])
        model.eval()
        digest = worker.model_hash(model)
        with torch.inference_mode():
            model(torch.randn(4, 18, 320))
        self.assertEqual(worker.model_hash(model), digest)


if __name__ == "__main__":
    unittest.main()
