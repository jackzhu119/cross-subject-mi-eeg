"""Real PyTorch CPU tests of the new runner, using synthetic inputs exclusively.

Tests exercise actual EEGNet forward/backward/Adam/checkpoint operations and a
small complete source-selection/external-statistics workflow. All intermediate
models and scores live in temporary directories and are removed after testing.
No dataset is downloaded, no EEG result is produced, and no figure is created.
"""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from p1_common import atomic_json, canonical_hash, read_json, sha256_file
import p1_runner as runner
import p1_train as train


def synthetic_person(key, *, n_trials=8, role="source", seed=100):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_trials, 3, 18, 320)).astype(np.float64)
    x -= x.mean(axis=-1, keepdims=True)
    x /= np.sqrt(np.mean(x[:, 0] ** 2, axis=(1, 2)))[:, None, None, None]
    x = x.astype(np.float32)
    y = np.arange(n_trials, dtype=np.int64) % 2
    trial_ids = np.array([f"{key}/SYNTHETIC/trial-{i:03d}" for i in range(n_trials)])
    digest = hashlib.sha256(x.tobytes() + y.tobytes() + "|".join(trial_ids).encode()).hexdigest()
    return {"X": x, "y": y, "trial_id": trial_ids, "dataset": key.split(":")[0],
            "subject": key, "role": role, "input_sha256": digest}


def smoke_config():
    config = copy.deepcopy(read_json(runner.DEFAULT_CONFIG))
    config.update({
        "protocol_id": "SYNTHETIC_SOFTWARE_SMOKE_NOT_EEG_RESULTS",
        "evidence_scope": "synthetic_only",
        "traditional_baseline": {"enabled": False},
        "source_levels": {"S9": {"bnci": 2, "yang": 0}, "S29": {"bnci": 2, "yang": 2},
                          "S60": {"bnci": 2, "yang": 4}},
        "source_folds": 2, "validation_seeds": [101, 202], "final_seeds": [303, 404],
        "epochs": 2, "fixed_epoch": 1, "updates_per_epoch": 1, "batch_size": 4,
        "bootstrap_replicates": 100, "bootstrap_seed": 808,
        "nominal_validation_trajectories": 24, "nominal_final_trajectories": 12,
        "nominal_total_trajectories": 36, "nominal_selected_external_conditions": 96,
        "nominal_external_prediction_rows": 1536,
        "limitations": ["SYNTHETIC SOFTWARE TEST ONLY. These are not EEG scientific results."],
    })
    config["target"] = {**config["target"], "subjects": 4, "trials_per_subject": 4}
    config["source_trial_counts_expected"] = {level: sum(counts.values()) * 8
                                              for level, counts in config["source_levels"].items()}
    return config


def silent_call(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


class TrainingWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        train.configure_runtime("cpu")
        torch.set_num_threads(1)

    def assert_same_tree(self, left, right):
        if torch.is_tensor(left):
            self.assertTrue(torch.equal(left, right), "resumed tensor differs")
        elif isinstance(left, np.ndarray):
            np.testing.assert_array_equal(left, right)
        elif isinstance(left, dict):
            self.assertEqual(set(left), set(right))
            for key in left:
                self.assert_same_tree(left[key], right[key])
        elif isinstance(left, (tuple, list)):
            self.assertEqual(len(left), len(right))
            for a, b in zip(left, right):
                self.assert_same_tree(a, b)
        else:
            self.assertEqual(left, right)

    def test_continuous_and_resumed_next_update_are_exact_for_both_pipelines(self):
        config = smoke_config()
        config["updates_per_epoch"] = 2
        source = {key: synthetic_person(key, seed=i + 40)
                  for i, key in enumerate(("bnci:001", "yang:001"))}
        valid = {"bnci:002": synthetic_person("bnci:002", seed=99)}
        identity = {"scope": "SYNTHETIC_ONLY", "test": "continuous_vs_resume"}
        with tempfile.TemporaryDirectory(prefix="p1-neural-resume-test-") as temporary:
            for pipeline in ("BROAD", "MU_BETA_SHARED"):
                full = Path(temporary)/pipeline/"continuous"
                interrupted = Path(temporary)/pipeline/"interrupted"
                arguments = dict(seed=20261017, pipeline=pipeline, source_level="SYNTHETIC",
                                 fold=0, execution_identity=identity, device="cpu")
                silent_call(train.train_trajectory, config, source, valid, full, **arguments)
                silent_call(train.train_trajectory, config, source, valid, interrupted,
                            stop_after_epoch=1, **arguments)
                self.assertFalse((interrupted/"complete.json").exists())
                initial, _ = train.load_checkpoint(interrupted)
                self.assertEqual(initial["updates"], 2)
                silent_call(train.train_trajectory, config, source, valid, interrupted, **arguments)
                expected, _ = train.load_checkpoint(full)
                actual, receipt = train.load_checkpoint(interrupted)
                for field in ("model", "optimizer", "rng", "validation_rows", "training_mean_ce",
                              "contract", "contract_hash", "epoch", "updates"):
                    self.assert_same_tree(expected[field], actual[field])
                self.assertEqual(actual["updates"], 4)
                self.assertEqual(actual["parameter_count"], 1714)
                self.assertTrue(read_json(interrupted/"complete.json")["complete"])
                # A completed rerun must not add an optimizer update or rewrite a checkpoint.
                before_sha = receipt["sha256"]
                silent_call(train.train_trajectory, config, source, valid, interrupted, **arguments)
                _, after = train.load_checkpoint(interrupted)
                self.assertEqual(before_sha, after["sha256"])
                changed = copy.deepcopy(config)
                changed["learning_rate"] *= 2
                with self.assertRaisesRegex(RuntimeError, "configuration, data or code changed"):
                    silent_call(train.train_trajectory, changed, source, valid, interrupted, **arguments)

    def test_external_eval_does_not_change_parameters_or_batchnorm(self):
        config = smoke_config()
        person = synthetic_person("dreyer:001", n_trials=4, role="external", seed=77)
        for pipeline in ("BROAD", "MU_BETA_SHARED"):
            train.seed_all(710)
            model = train.build_model(config, "cpu")
            before = train.model_hash(model)
            first = train.predict(model, person, pipeline, "cpu", batch_size=2)
            second = train.predict(model, person, pipeline, "cpu", batch_size=2)
            self.assertEqual(before, train.model_hash(model))
            np.testing.assert_array_equal(first, second)
            self.assertEqual(first.shape, (4, 2))
            self.assertFalse(model.training)

    def test_external_data_and_physical_person_aliases_fail_before_fit(self):
        config = smoke_config()
        source = {"bnci:001": synthetic_person("bnci:001")}
        external = synthetic_person("dreyer:001", role="external")
        arguments = dict(seed=7, pipeline="BROAD", source_level="SYNTHETIC", fold=0,
                         execution_identity={"scope": "SYNTHETIC_ONLY"}, device="cpu")
        with tempfile.TemporaryDirectory(prefix="p1-fit-isolation-test-") as folder:
            with self.assertRaisesRegex(ValueError, "registered source"):
                train.train_trajectory(config, source, {"dreyer:001": external}, folder, **arguments)
            forged_role = dict(external, role="source")
            with self.assertRaisesRegex(ValueError, "registered source"):
                train.train_trajectory(config, source, {"dreyer:001": forged_role}, folder, **arguments)
            with self.assertRaisesRegex(ValueError, "physical person overlap"):
                train.train_trajectory(config, source, {"renamed-alias": source["bnci:001"]}, folder, **arguments)
            with self.assertRaisesRegex(ValueError, "overlap"):
                train.train_trajectory(config, source, source, folder, **arguments)
            self.assertFalse((Path(folder)/"latest.json").exists())
        with self.assertRaisesRegex(ValueError, "external dataset"):
            train.HierarchicalSampler({"dreyer:001": forged_role}, 7)

    def test_hierarchical_sampler_balances_datasets_not_pooled_people(self):
        people = {}
        for key in ("bnci:001", "yang:001", "yang:002", "yang:003"):
            person = synthetic_person(key, n_trials=4)
            person["X"].fill(1 if key.startswith("bnci") else 2)
            people[key] = person
        sampler = train.HierarchicalSampler(people, 713)
        dataset_values, labels = [], []
        for _ in range(8):
            x, y = sampler.batch(64)
            dataset_values.extend(x[:, 0, 0, 0].tolist())
            labels.extend(y.tolist())
        self.assertAlmostEqual(np.mean(np.array(dataset_values) == 1), .5, delta=.08)
        self.assertAlmostEqual(np.mean(labels), .5, delta=.08)

    def test_formal_registry_is_nested_dataset_stratified_and_person_grouped(self):
        config = read_json(runner.DEFAULT_CONFIG)
        first = runner.registry(config)
        self.assertEqual(first, runner.registry(copy.deepcopy(config)))
        self.assertEqual([len(first["levels"][level]) for level in ("S9", "S29", "S60")], [9, 29, 60])
        self.assertTrue(set(first["levels"]["S9"]) < set(first["levels"]["S29"]) < set(first["levels"]["S60"]))
        for keys in first["levels"].values():
            self.assertFalse(any(key.startswith("dreyer") for key in keys))
            for dataset in {key.split(":")[0] for key in keys}:
                sizes = [sum(key.startswith(dataset + ":") and first["fold_map"][key] == fold for key in keys)
                         for fold in range(5)]
                self.assertGreaterEqual(min(sizes), 1)
                self.assertLessEqual(max(sizes) - min(sizes), 1)
        self.assertFalse(first["uses_external_labels"])
        bad = copy.deepcopy(config)
        bad["source_levels"]["S9"]["bnci"] = 10
        with self.assertRaisesRegex(ValueError, "source count"):
            runner.registry(bad)

    def test_source_metric_ce_is_stable_and_binary_labels_are_required(self):
        result = train.metrics_from_logits(np.array([0, 1]), np.full((2, 2), 1e20))
        self.assertAlmostEqual(result["ce"], np.log(2))
        self.assertEqual(result["ba"], .5)
        self.assertEqual(result["min_recall"], 0)
        with self.assertRaisesRegex(ValueError, "integer binary labels"):
            train.metrics_from_logits(np.array([0., 1.]), np.zeros((2, 2)))

    def test_checkpoint_wrong_epoch_name_and_corruption_are_rejected(self):
        config = smoke_config()
        source = {"bnci:001": synthetic_person("bnci:001")}
        with tempfile.TemporaryDirectory(prefix="p1-checkpoint-integrity-test-") as folder:
            silent_call(train.train_trajectory, config, source, {}, folder, seed=3, pipeline="BROAD",
                        source_level="SYNTHETIC", fold="all_source", execution_identity={"synthetic": True}, device="cpu")
            folder = Path(folder)
            receipt = read_json(folder/"epoch_002.json")
            atomic_json(folder/"epoch_001.json", receipt)
            with self.assertRaisesRegex(RuntimeError, "checksum/name mismatch"):
                train.load_checkpoint(folder, 1)
            altered = {**receipt, "path": "../epoch_002.pt"}
            atomic_json(folder/"latest.json", altered)
            with self.assertRaisesRegex(RuntimeError, "checksum/name mismatch"):
                train.load_checkpoint(folder)
            atomic_json(folder/"latest.json", receipt)
            with (folder/"epoch_002.pt").open("ab") as stream:
                stream.write(b"SYNTHETIC_CORRUPTION_TEST")
            with self.assertRaisesRegex(RuntimeError, "checksum/name mismatch"):
                train.load_checkpoint(folder)

    def test_complete_synthetic_runner_freeze_gates_and_statistics(self):
        config = smoke_config()
        reg = runner.registry(config)
        keys = reg["levels"]["S60"]
        people = {key: synthetic_person(key, seed=500 + index) for index, key in enumerate(keys)}
        targets = {f"dreyer:{i:03d}": synthetic_person(f"dreyer:{i:03d}", n_trials=4,
                                                        role="external", seed=800 + i) for i in range(1, 5)}
        identity = {"scope": "SYNTHETIC_ONLY", "test": "full_new_runner_closure"}
        status = []
        update = lambda stage, **details: status.append({"stage": stage, **details})
        with tempfile.TemporaryDirectory(prefix="p1-full-synthetic-runner-") as folder:
            run = Path(folder)
            with self.assertRaises(FileNotFoundError):
                runner.external_evaluate(config, targets, {}, run, update, "cpu")
            self.assertFalse((run/"results/external_predictions.csv.gz.tmp").exists())
            freeze = silent_call(runner.run_source_validation, config, reg, people, run, identity, update, "cpu")
            self.assertEqual(freeze["complete_validation_trajectories"], 24)
            with self.assertRaises(FileNotFoundError):
                runner.require_source_freeze(run, freeze, config)
            completion = silent_call(runner.run_final_fits, config, reg, people, freeze, run, identity, update, "cpu")
            self.assertEqual(completion["complete_final_trajectories"], 12)
            runner.require_source_freeze(run, freeze, config)
            with self.assertRaisesRegex(ValueError, "subject inventory"):
                runner.external_evaluate(config, dict(list(targets.items())[:3]), freeze, run, update, "cpu")
            mislabeled = {key: dict(person, role="source") for key, person in targets.items()}
            with self.assertRaisesRegex(ValueError, "explicitly external"):
                runner.external_evaluate(config, mislabeled, freeze, run, update, "cpu")
            report = silent_call(runner.external_evaluate, config, targets, freeze, run, update, "cpu")
            self.assertEqual(report["protocol_id"], config["protocol_id"])
            self.assertEqual(report["prediction_rows"], 1536)
            self.assertEqual(report["diagnostics"]["n_subjects"], 4)
            self.assertEqual(report["diagnostics"]["n_seeds"], 2)
            self.assertEqual(report["diagnostics"]["n_conditions"], 48)
            self.assertEqual(report["diagnostics"]["bootstrap_seed"], 808)
            self.assertEqual(len(report["comparisons"]), 4)
            self.assertEqual(len(report["per_subject_metrics"]), 48 * 4)
            # Editing evidence or actual checkpoint bytes must close the target gate.
            curves = run/"results/source_validation_curves.csv"
            old = curves.read_bytes()
            curves.write_bytes(old + b"\n")
            with self.assertRaisesRegex(ValueError, "validation evidence changed"):
                runner.require_source_freeze(run, freeze, config)
            curves.write_bytes(old)
            checkpoint = runner.fit_folder(run, "final", "S9", "BROAD", config["final_seeds"][0])/"epoch_002.pt"
            with checkpoint.open("ab") as stream:
                stream.write(b"SYNTHETIC_CORRUPTION_TEST")
            with self.assertRaisesRegex(RuntimeError, "checksum/name mismatch"):
                runner.require_source_freeze(run, freeze, config)
        self.assertTrue(any(row["stage"] == "EXTERNAL_EVALUATION" for row in status))


if __name__ == "__main__":
    print("SYNTHETIC CPU SOFTWARE TESTS ONLY — no real EEG results or figures")
    unittest.main(verbosity=2)
