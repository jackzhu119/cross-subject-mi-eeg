"""Synthetic-only CSP baseline validation; never reads target EEG or scores."""
from collections import Counter, defaultdict
from pathlib import Path
import tempfile
import unittest

import numpy as np

import p1_csp as csp


def synthetic_person(seed, n_per_class, dataset, role="source"):
    rng = np.random.default_rng(seed)
    y = np.repeat([0, 1], n_per_class).astype(np.int64)
    X = rng.normal(size=(len(y), 18, 320))
    time = np.arange(320) / 160
    for trial, label in enumerate(y):
        # Two deliberately distinct source spatial variance patterns, not a real result.
        channel = 7 if label == 0 else 11
        X[trial, channel] += 5 * np.sin(2 * np.pi * 10 * time + rng.uniform(0, 2 * np.pi))
    X -= X.mean(axis=1, keepdims=True)
    X -= X.mean(axis=-1, keepdims=True)
    X /= np.sqrt(np.mean(X ** 2, axis=(1, 2), keepdims=True))
    X = np.stack((X, X * .8, X * .6), axis=1).astype(np.float32)
    return {"X": X, "y": y, "dataset": dataset, "role": role, "input_sha256": csp._array_hash(X)}


class CSPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Unequal trial counts test that source subject/cohort weighting matters.
        cls.sources = {
            "person_a": synthetic_person(101, 12, "synthetic_bnci"),
            "person_b": synthetic_person(202, 23, "synthetic_yang"),
        }
        cls.model = csp.fit(cls.sources, seed=20261013)

    def test_known_synthetic_signal_and_probability_class_order(self):
        held_out = synthetic_person(303, 9, "synthetic_bnci", role="external")
        before = csp.model_hash(self.model)
        probabilities = csp.predict(self.model, held_out["X"])
        self.assertEqual(probabilities.shape, (18, 2))
        np.testing.assert_allclose(probabilities.sum(axis=1), 1.0, atol=1e-14)
        np.testing.assert_array_equal(probabilities.argmax(axis=1), held_out["y"])
        self.assertEqual(csp.model_hash(self.model), before)

    def test_covariance_is_equal_person_not_trial_pooled(self):
        # Independent np.cov formula (ddof cancels after trace normalization).
        expected_by_person = []
        H = self.model.projection
        for person in self.sources.values():
            means = []
            for label in (0, 1):
                matrices = []
                for trial in person["X"][person["y"] == label, 0]:
                    cov = np.cov(H @ trial.astype(np.float64), bias=False)
                    matrices.append(cov / np.trace(cov))
                means.append(np.mean(matrices, axis=0))
            expected_by_person.append(means)
        np.testing.assert_allclose(self.model.class_covariances, np.mean(expected_by_person, axis=0), rtol=1e-12, atol=1e-13)
        np.testing.assert_allclose(np.trace(self.model.class_covariances, axis1=1, axis2=2), [1, 1], atol=1e-13)

    def test_fixed_hierarchical_sampling_balance_with_unequal_cohort_sizes(self):
        sources = {
            "a": {"dataset": "synthetic_bnci", "y": np.array([0, 1, 0, 1])},
            "b": {"dataset": "synthetic_yang", "y": np.array([0, 1, 0, 1])},
            "c": {"dataset": "synthetic_yang", "y": np.array([0, 1, 0, 1])},
            "d": {"dataset": "synthetic_yang", "y": np.array([0, 1, 0, 1])},
        }
        features = {key: np.arange(16).reshape(4, 4) + i for i, key in enumerate(sources)}
        X, y, counts, identity = csp._balanced_feature_resample(features, sources, 20261013)
        self.assertEqual(X.shape, (8192, 4))
        self.assertEqual(Counter(y.tolist()), {0: 4096, 1: 4096})
        by_cell = defaultdict(list)
        for row in counts:
            by_cell[row["cohort"], row["class"]].append(row["sampled_rows"])
        for values in by_cell.values():
            self.assertEqual(sum(values), 2048)
            self.assertLessEqual(max(values) - min(values), 1)
        again = csp._balanced_feature_resample(features, sources, 20261013)
        self.assertEqual(identity, again[3])
        np.testing.assert_array_equal(X, again[0])

    def test_numeric_npz_roundtrip_and_fixed_seed_repeat(self):
        repeated = csp.fit(dict(reversed(list(self.sources.items()))), seed=20261013)
        self.assertEqual(csp.model_hash(self.model), csp.model_hash(repeated))
        with tempfile.TemporaryDirectory(prefix="p1-csp-test-") as folder:
            path = Path(folder) / "parameters.npz"
            receipt = csp.save_model(self.model, path)
            restored = csp.load_model(path)
            self.assertEqual(receipt["model_sha256"], csp.model_hash(restored))
            np.testing.assert_array_equal(csp.predict(restored, self.sources["person_a"]["X"]),
                                          csp.predict(self.model, self.sources["person_a"]["X"]))
            with np.load(path, allow_pickle=False) as archive:
                self.assertTrue(all(archive[name].dtype.kind != "O" for name in archive.files))

    def test_actual_external_names_and_roles_are_rejected(self):
        for change in ({"role": "external"}, {"dataset": "dreyer"}):
            bad = {"person_a": {**self.sources["person_a"], **change}}
            with self.assertRaisesRegex(ValueError, "non-source|external/unregistered"):
                csp.fit(bad)
        with self.assertRaises(ValueError):
            self.model.lda_coef[0, 0] = 1


if __name__ == "__main__":
    unittest.main(verbosity=2)
