"""Synthetic-only conventional baseline orchestration and source-gate checks."""
from copy import deepcopy
import csv
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from p1_common import canonical_hash, read_json, sha256_file
import p1_csp_task as task
from selftest_csp import synthetic_person


class CSPTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p1-csp-task-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.sources = {
            "synthetic_source_a": synthetic_person(11, 7, "synthetic_bnci"),
            "synthetic_source_b": synthetic_person(12, 8, "synthetic_yang"),
            "synthetic_source_c": synthetic_person(13, 9, "synthetic_yang"),
        }
        keys = list(self.sources)
        self.reg = {"levels": {"S9": keys[:1], "S29": keys[:2], "S60": keys}}
        self.config = {"traditional_baseline": {"enabled": True},
                       "final_seeds": [20261013, 20261014, 20261015],
                       "target": {"subjects": 2, "trials_per_subject": 8},
                       "bootstrap_replicates": 100, "bootstrap_seed": 20261017}
        self.identity = {"fixture": "synthetic_only_no_real_EEG"}
        self.freeze = {"source_only": True, "execution_identity": self.identity,
                       "source_input_hashes": {k: v["input_sha256"] for k, v in self.sources.items()}}
        self.freeze["freeze_sha256"] = canonical_hash(self.freeze)
        self.status = lambda *args, **kwargs: None

    def fitted(self):
        return task.fit_baselines(self.config, self.reg, self.sources, self.freeze,
                                  self.run, self.identity, self.status)

    def targets(self):
        result = {}
        for seed in (31, 32):
            person = synthetic_person(seed, 4, "synthetic_bnci", role="external")
            # The adapter requires the registered target name; these arrays are
            # generated here, with no real target EEG files or scores accessed.
            person["dataset"] = "dreyer"
            person["trial_id"] = [f"synthetic_trial_{i}" for i in range(8)]
            result[f"synthetic_external_{seed}"] = person
        return result

    def test_nine_source_fits_and_resume_without_refitting(self):
        with patch.object(task, "fit", wraps=task.fit) as fit_call:
            manifest = self.fitted()
            self.assertEqual(fit_call.call_count, 9)
        self.assertEqual(manifest["n_conventional_fits"], 9)
        expected = {(level, seed) for level in self.reg["levels"] for seed in self.config["final_seeds"]}
        self.assertEqual({(r["source_level"], r["seed"]) for r in manifest["fits"]}, expected)
        before = {r["path"]: sha256_file(r["path"]) for r in manifest["fits"]}
        with patch.object(task, "fit", side_effect=AssertionError("resume refitted a source model")):
            self.assertEqual(self.fitted(), manifest)
        self.assertEqual(before, {p: sha256_file(p) for p in before})
        self.assertEqual(task.require_baselines(self.config, self.reg, self.freeze, self.run), manifest)

    def test_changed_source_hash_blocks_before_any_fit(self):
        self.sources["synthetic_source_a"]["input_sha256"] = "0" * 64
        with patch.object(task, "fit") as fit_call:
            with self.assertRaisesRegex(ValueError, "source inputs differ"):
                self.fitted()
            fit_call.assert_not_called()

    def test_missing_and_changed_model_and_freeze_are_rejected(self):
        manifest = self.fitted()
        path = Path(manifest["fits"][0]["path"])
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            task.require_baselines(self.config, self.reg, self.freeze, self.run)
        path.write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "differs from its frozen file"):
            task.require_baselines(self.config, self.reg, self.freeze, self.run)
        path.write_bytes(original)
        wrong = deepcopy(self.freeze)
        wrong["freeze_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "same frozen source-only"):
            task.require_baselines(self.config, self.reg, wrong, self.run)
        wrong = deepcopy(self.freeze)
        wrong["execution_identity"] = {"fixture": "different"}
        with self.assertRaisesRegex(ValueError, "same frozen source-only"):
            task.require_baselines(self.config, self.reg, wrong, self.run)

    def test_unmocked_missing_source_freeze_blocks_before_prediction(self):
        with patch.object(task, "predict") as prediction:
            with self.assertRaises(FileNotFoundError):
                task.evaluate_baselines(self.config, self.reg, self.targets(), self.freeze, self.run, self.status)
            prediction.assert_not_called()

    def test_synthetic_evaluation_is_complete_paired_and_descriptive(self):
        self.fitted()
        with patch("p1_runner.require_source_freeze") as source_gate:
            report = task.evaluate_baselines(self.config, self.reg, self.targets(), self.freeze, self.run, self.status)
            source_gate.assert_called_once_with(self.run, self.freeze, self.config)
        self.assertEqual(report["prediction_rows"], 9 * 2 * 8)
        self.assertEqual(report["n_conventional_fits"], 9)
        self.assertEqual(report["comparisons"], [])
        self.assertEqual(report["role"], "separate_descriptive_conventional_baseline")
        self.assertEqual(report["diagnostics"]["n_subjects"], 2)
        self.assertEqual(report["diagnostics"]["n_seeds"], 3)
        self.assertEqual(report["diagnostics"]["n_hypothesis_tests"], 0)
        self.assertNotIn("Holm", report["diagnostics"]["secondary"])
        self.assertTrue(report["diagnostics"]["complete_paired_grid"])
        self.assertEqual(len(report["per_subject_metrics"]), 3 * 2)
        with gzip.open(self.run / "results/csp_external_predictions.csv.gz", "rt") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 144)
        self.assertEqual({(r["source_level"], r["seed"]) for r in rows},
                         {(level, str(seed)) for level in self.reg["levels"] for seed in self.config["final_seeds"]})
        self.assertEqual({r["pipeline"] for r in rows}, {"CSP_LDA"})
        self.assertEqual(read_json(self.run / "results/csp_report.json"), report)

    def test_corrupt_model_blocks_evaluation_even_if_neural_gate_mocked(self):
        manifest = self.fitted()
        Path(manifest["fits"][0]["path"]).unlink()
        with patch("p1_runner.require_source_freeze"), patch.object(task, "predict") as prediction:
            with self.assertRaises(FileNotFoundError):
                task.evaluate_baselines(self.config, self.reg, self.targets(), self.freeze, self.run, self.status)
            prediction.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
