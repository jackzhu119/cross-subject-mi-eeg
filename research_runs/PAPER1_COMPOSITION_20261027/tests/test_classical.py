"""Synthetic checks only: no EEG download, target selection or GPU import."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared")]
from compmi import classical as c


SETTINGS = {"method": "weighted_csp_rlda", "components": 4,
            "csp_shrinkage": .1, "lda_shrinkage": .1}


def config():
    return {"science_version": "synthetic-classical-v1", "input_shape": [3, 18, 320],
            "classical": SETTINGS.copy(), "eval_batch_size": 128, "heartbeat_seconds": 30}


def person(name, cohort, count=24, role="source", seed=1):
    rng = np.random.default_rng(seed)
    y = np.arange(count, dtype=np.int64) % 2
    broad = rng.normal(size=(count, 18, 320)).astype(np.float32)
    broad[y == 0, 0] *= 3
    broad[y == 1, 1] *= 3
    broad -= broad.mean(axis=2, keepdims=True)
    X = np.stack((broad, broad * .3, broad * .2), axis=1)
    return {"id": name, "dataset": cohort, "role": role, "X": X, "y": y,
            "sessions": ["session/" + str(i // (count // 2)) for i in range(count)],
            "trial_ids": [name + "/trial-" + str(i) for i in range(count)]}


class FakeRegistry:
    def __init__(self, entries, model_path=None):
        self.by_id = {row["id"]: row for row in entries}
        self.fingerprint = "synthetic-prepared-data-sha"
        self.model_path = model_path
        self.reads = []

    def ensure_source(self, ids):
        if len(ids) != len(set(ids)) or any(self.by_id[p]["role"] != "source" for p in ids):
            raise ValueError("source only")

    def load_person(self, name):
        if self.by_id[name]["role"] == "external" and self.model_path is not None:
            if not self.model_path.is_file():
                raise AssertionError("Target EEG opened before a saved source model")
        self.reads.append(name)
        return self.by_id[name]


class QuietProgress:
    def __init__(self):
        self.processed = 0

    def emit(self, *args, **kwargs):
        pass


class NoStop:
    def check(self):
        pass


def task(phase="final"):
    return {"id": "synthetic-classical", "family": "classical", "method": "weighted_csp_rlda",
            "seed": 0, "phase": phase, "fold": None, "cell_id": "s60-all", "pool": "s60",
            "subset": None, "regime": "all", "train_ids": ["bnci__a", "bnci__b", "yang__c"],
            "validation_ids": [], "test_ids": ["dreyer__d"],
            "train_trials_file": "state/trialsets/synthetic.json", "train_trials_sha256": "a" * 64}


def registry(model_path=None):
    return FakeRegistry([person("bnci__a", "bnci", 16), person("bnci__b", "bnci", 40, seed=2),
                         person("yang__c", "yang", 24, seed=3),
                         person("dreyer__d", "dreyer", 24, "external", seed=4)], model_path)


def whitelist(reg):
    return {p: np.arange(len(reg.by_id[p]["y"]), dtype=np.int64)
            for p in ("bnci__a", "bnci__b", "yang__c")}


class ClassicalTests(unittest.TestCase):
    def test_equal_cohort_person_weights_and_covariance(self):
        reg, t = registry(), task()
        self.assertEqual(c.source_weights(reg, t["train_ids"]),
                         {"bnci__a": .25, "bnci__b": .25, "yang__c": .5})
        with tempfile.TemporaryDirectory() as folder:
            model = c.fit_model(reg, t, whitelist(reg), Path(folder), {"test": 1}, config(), NoStop(), QuietProgress())
        expected = np.zeros((2, 18, 18))
        for p, weight in c.source_weights(reg, t["train_ids"]).items():
            entry = reg.by_id[p]
            for label in (0, 1):
                x = entry["X"][entry["y"] == label, 0]
                expected[label] += weight * c.trial_covariance_sum(x) / len(x)
        np.testing.assert_allclose(model["class_covariances"], expected, atol=1e-14)
        # Trial counts are deliberately 16/40/24; trial-pooling is a different estimator.
        pooled = sum(c.trial_covariance_sum(reg.by_id[p]["X"][reg.by_id[p]["y"] == 0, 0])
                     for p in t["train_ids"]) / 40
        self.assertGreater(float(np.max(np.abs(pooled - expected[0]))), 1e-5)

    def test_whitelist_excludes_unselected_trials_and_external(self):
        reg, t = registry(), task()
        selected = {p: values[:8] for p, values in whitelist(reg).items()}
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = c.fit_model(reg, t, selected, Path(first), {"test": 1}, config(), NoStop(), QuietProgress())
            for p in t["train_ids"]:
                # Invalid unused data must never enter any covariance/feature batch.
                reg.by_id[p]["X"][8:] = np.nan
            b = c.fit_model(reg, t, selected, Path(second), {"test": 1}, config(), NoStop(), QuietProgress())
        for key in a:
            np.testing.assert_array_equal(a[key], b[key])
        self.assertNotIn("dreyer__d", reg.reads)
        bad = {**selected, "dreyer__d": np.arange(8)}
        with self.assertRaisesRegex(ValueError, "does not match"):
            c.validate_whitelist(reg, t["train_ids"], bad)
        with self.assertRaisesRegex(ValueError, "source only"):
            c.validate_whitelist(reg, ["dreyer__d"], {"dreyer__d": np.arange(8)})
        for values in ([0, 0, 1], [False, 1], [-1, 0, 1], [0, 2, 4]):
            bad = {**selected, "bnci__a": values}
            with self.assertRaises(ValueError):
                c.validate_whitelist(reg, t["train_ids"], bad)

    def test_numeric_model_classifies_and_binds_identity(self):
        reg, t = registry(), task()
        identity = {"test": "numeric-model"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.npz"
            c.fit_model(reg, t, whitelist(reg), Path(folder), identity, config(), NoStop(), QuietProgress())
            model = c.load_model(path, identity)
            with np.load(path, allow_pickle=False) as saved:
                self.assertTrue(all(not saved[key].dtype.hasobject for key in saved.files))
            target = reg.by_id["dreyer__d"]
            logits = c.predict(model, target["X"][:, 0])
            self.assertGreater(float((logits.argmax(1) == target["y"]).mean()), .9)
            counts = c.metric_row(target["y"], logits)
            self.assertEqual(counts["n"], 24)
            with self.assertRaisesRegex(ValueError, "identity changed"):
                c.load_model(path, {"test": "different"})
            with self.assertRaisesRegex(ValueError, "Object arrays"):
                c.atomic_npz(Path(folder) / "unsafe.npz", x=np.asarray([{}], dtype=object))

    def test_source_stage_resumes_without_recomputing_completed_person(self):
        reg, t = registry(), task()
        original_save = c.atomic_npz
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def stop_after_save(path, **arrays):
                original_save(path, **arrays)
                if Path(path).name == "source_covariances.npz":
                    raise c.RequestedStop(75)
            with patch.object(c, "atomic_npz", side_effect=stop_after_save):
                with self.assertRaises(c.RequestedStop):
                    c.fit_model(reg, t, whitelist(reg), root, {"test": 1}, config(), NoStop(), QuietProgress())
            with patch.object(c, "trial_covariance_sum", wraps=c.trial_covariance_sum) as covariance:
                c.fit_model(reg, t, whitelist(reg), root, {"test": 1}, config(), NoStop(), QuietProgress())
                self.assertEqual(covariance.call_count, 4)  # Two remaining people times two classes.

    def test_worker_failed_evaluation_reuses_fit_and_session_shards(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / "config").mkdir()
            (project / "config/study.json").write_text(json.dumps(config()))
            (project / "config/paths.json").write_text(json.dumps({"data_dir": folder}))
            t = task()
            (project / "tasks.json").write_text(json.dumps([t]))
            run_dir = project / "outputs/runs" / t["id"]
            reg = registry(run_dir / "model.npz")
            fake_plan = types.ModuleType("compmi.plan")
            fake_plan.task_trialset = lambda project, task, registry: whitelist(registry)
            original_predict = c.predict
            calls = []
            def fail_second(model, x):
                calls.append(len(x))
                if len(calls) == 2:
                    raise RuntimeError("synthetic interrupted second session")
                return original_predict(model, x)
            with patch.dict(sys.modules, {"compmi.plan": fake_plan}), patch.object(c, "Registry", return_value=reg), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with patch.object(c, "predict", side_effect=fail_second):
                    self.assertEqual(c.run_task(project, t["id"]), 1)
                self.assertTrue((run_dir / "model.npz").is_file())
                before = c.file_sha(run_dir / "model.npz")
                self.assertEqual(len(list(run_dir.glob("evaluations/**/*.npz"))), 1)
                with patch.object(c, "fit_model", side_effect=AssertionError("must not repeat fit")), patch.object(c, "predict", wraps=original_predict) as prediction:
                    self.assertEqual(c.run_task(project, t["id"]), 0)
                    self.assertEqual(prediction.call_count, 1)
                self.assertEqual(before, c.file_sha(run_dir / "model.npz"))
                done = json.loads((run_dir / "complete.json").read_text())
                self.assertEqual(done["optimizer_updates"], 0)
                self.assertEqual(done["classical_fits_completed"], 1)
                with patch.object(c, "fit_model", side_effect=AssertionError("must skip completed task")), patch.object(c, "predict", side_effect=AssertionError("must skip completed evaluation")):
                    self.assertEqual(c.run_task(project, t["id"]), 0)
                with patch.object(c, "Signals") as signals:
                    signals.return_value.check.side_effect = c.RequestedStop(143)
                    # Remove only completion marker to exercise signal handling; durable model/shards stay.
                    (run_dir / "complete.json").unlink()
                    self.assertEqual(c.run_task(project, t["id"]), 143)
                self.assertTrue((run_dir / "error.json").exists())  # Original failure retained.

    def test_fingerprint_and_contract_changes_are_not_silent(self):
        reg, t, cfg = registry(), task(), config()
        before = c.science_fingerprint(cfg, t, reg)
        altered = copy.deepcopy(t)
        altered["train_trials_sha256"] = "b" * 64
        self.assertNotEqual(before, c.science_fingerprint(cfg, altered, reg))
        altered = copy.deepcopy(t)
        altered["train_ids"] = altered["train_ids"][::-1]
        self.assertNotEqual(before, c.science_fingerprint(cfg, altered, reg))
        cfg["classical"]["lda_shrinkage"] = .2
        with self.assertRaisesRegex(ValueError, "fixed CSP/RLDA"):
            c.science_fingerprint(cfg, t, reg)

    def test_import_does_not_load_torch_or_scipy(self):
        environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / "shared"))))
        result = subprocess.run([sys.executable, "-c", "import sys; import compmi.classical; assert 'torch' not in sys.modules; assert 'scipy' not in sys.modules; print('numpy-only')"],
                                env=environment, capture_output=True, text=True, check=True)
        self.assertIn("numpy-only", result.stdout)


if __name__ == "__main__":
    unittest.main()
