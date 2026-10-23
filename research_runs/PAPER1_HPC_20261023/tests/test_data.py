"""Synthetic-only tests: import resume, correct roles, corruption and interruption."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from hpcmi import data


def make_npz(path, dataset="bnci", subject="BNCI001", bad=None):
    n = 4
    X = np.random.default_rng(21).normal(size=(n, 3, 18, 320)).astype(np.float32)
    y = np.array([0, 1, 0, 1], dtype=np.int64)
    official = {"bnci": "BNCI2014_001", "yang": "Yang2025_2C", "dreyer": "Dreyer2023"}[dataset]
    rows = [{"dataset": official, "subject": subject, "session": "session-1",
             "run": "run-" + str(i // 2 + 1), "trial_id": subject + "/trial-" + str(i), "y": int(y[i])}
            for i in range(n)]
    if bad == "duplicate":
        rows[-1]["trial_id"] = rows[0]["trial_id"]
    if bad == "nonfinite":
        X[0, 0, 0, 0] = np.nan
    audit = {"dataset": official, "subject": subject, "provider_subject": 1,
             "status": "PASS_FRESH18_SUBJECT_INPUTS", "channels": data.CHANNELS,
             "sample_rate_hz": 160, "view_order": ["broad", "mu", "beta"], "units": "dimensionless",
             "normalization": {"scope": "single_trial_only_no_cross_trial_or_subject_statistics",
                               "apply_scale_to": ["broad", "mu", "beta"],
                               "scale": "same_trial_broad_view_root_mean_square_over_18_channels_and_320_samples",
                               "center": "subtract_each_view_each_channel_temporal_mean_after_crop",
                               "output_unit": "dimensionless"},
             "n_trials": n, "X_sha256": data._array_sha(X), "y_sha256": data._array_sha(y),
             "metadata_sha256": data._hash_object(rows)}
    if bad == "hash":
        audit["X_sha256"] = "0" * 64
    payload = {"X": X, "y": y, "audit_json": np.array(json.dumps(audit)),
               "metadata_json": np.array([json.dumps(row) for row in rows])}
    payload.update({k: np.array([row[k] for row in rows]) for k in ["dataset", "subject", "session", "run", "trial_id"]})
    np.savez_compressed(path, **payload)
    return X, y


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.npz"
        self.X, self.y = make_npz(self.source)
        self.config = self.root / "sources.json"
        self.output = self.root / "prepared"
        self.write_config()

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, extra=None):
        groups = [{"dataset": "bnci", "role": "source", "paths": [str(self.source)],
                   "expected_subjects": 1, "expected_trials": 4}]
        if extra:
            groups.append(extra)
        self.config.write_text(json.dumps({"schema_version": 1, "preprocessing_id": "synthetic-test-v1", "datasets": groups}))

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return data.prepare(self.config, self.output)

    def test_exact_import_memmap_and_external_role(self):
        external = self.root / "external.npz"
        make_npz(external, "dreyer", "A01")
        self.write_config({"dataset": "dreyer", "role": "external", "paths": [str(external)]})
        manifest = self.prepare()
        registry = data.Registry(self.output)
        self.assertEqual(registry.fingerprint, manifest["fingerprint"])
        self.assertEqual(registry.source_ids, ["bnci__BNCI001"])
        self.assertEqual(registry.external_ids, ["dreyer__A01"])
        person = registry.load_person("bnci__BNCI001")
        self.assertIsInstance(person["X"], np.memmap)
        np.testing.assert_array_equal(person["X"], self.X)
        np.testing.assert_array_equal(person["y"], self.y)
        self.assertEqual(len(set(person["sessions"])), 2)
        self.assertIs(person, registry.load_person("bnci__BNCI001"))
        registry.ensure_source(registry.source_ids)
        with self.assertRaises(ValueError):
            registry.ensure_source(registry.external_ids)

    def test_resume_uses_receipts_not_full_npz_scan(self):
        first = self.prepare()
        with patch.object(data, "_read_eligible", side_effect=AssertionError("Unnecessary NPZ reread")), \
                patch.object(data, "_file_sha", side_effect=AssertionError("Unnecessary SHA scan")):
            second = self.prepare()
            data.Registry(self.output)
        self.assertEqual(first, second)
        status = json.loads((self.output / "prepare_status.json").read_text())
        self.assertEqual(status["reused_people"], 1)

    def test_changed_input_or_output_stops_without_overwrite(self):
        self.prepare()
        previous = (self.output / "manifest.json").read_bytes()
        stat = self.source.stat()
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000))
        with self.assertRaisesRegex(ValueError, "Previously imported input"):
            self.prepare()
        self.assertEqual((self.output / "manifest.json").read_bytes(), previous)
        x_path = self.output / "people/bnci__BNCI001/X.npy"
        stat = x_path.stat()
        os.utime(x_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000))
        with self.assertRaisesRegex(ValueError, "Prepared file changed"):
            data.Registry(self.output)

    def test_invalid_arrays_and_metadata_never_complete(self):
        for problem in ["hash", "nonfinite", "duplicate"]:
            with self.subTest(problem=problem):
                make_npz(self.source, bad=problem)
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse((self.output / "manifest.json").exists())
                self.assertEqual(list((self.output / "imports").glob("*.json")), [])

    def test_interrupted_partial_import_resumes_one_person(self):
        original = data._atomic_json
        def fail_before_receipt(path, value):
            if Path(path).parent.name == "imports":
                raise OSError("Synthetic interruption before person commit")
            original(path, value)
        with patch.object(data, "_atomic_json", side_effect=fail_before_receipt):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertTrue((self.output / "people/bnci__BNCI001/X.npy").exists())
        self.assertFalse((self.output / "manifest.json").exists())
        self.prepare()
        person = data.Registry(self.output).load_person("bnci__BNCI001")
        np.testing.assert_array_equal(person["X"], self.X)
        self.assertEqual(len(list((self.output / "imports").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
