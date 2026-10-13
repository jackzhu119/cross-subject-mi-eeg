#!/usr/bin/env python3
"""Software gate tests; no acquisition, model fits or target scores."""
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dreyer_access", ROOT / "scripts/acquire_dreyer_runs.py")
ACCESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACCESS)


class AccessGateTests(unittest.TestCase):
    def test_exact_174_run_plan_is_metadata_only(self):
        rows, plan = ACCESS.verified_manifest_and_plan()
        self.assertEqual(len(rows), 174)
        self.assertEqual(sum(row["size"] for row in rows), 2515343396)
        self.assertEqual(plan["canonical19_order"], ACCESS.COMMON19)
        self.assertFalse(plan["model_training_enabled"])
        self.assertFalse(plan["model_inference_enabled"])

    def test_modified_provider_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed_manifest.json"
            path.write_bytes(ACCESS.MANIFEST_PATH.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "not_pinned"):
                ACCESS.verified_manifest_and_plan(manifest_path=path)

    def test_modified_channel_plan_is_rejected(self):
        plan = json.loads(ACCESS.PLAN_PATH.read_text())
        plan["canonical19_order"][0], plan["canonical19_order"][1] = plan["canonical19_order"][1], plan["canonical19_order"][0]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed_plan.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "canonical19_order"):
                ACCESS.verified_manifest_and_plan(plan_path=path)

    def test_zero_is_not_false_for_plan_model_gate(self):
        plan = json.loads(ACCESS.PLAN_PATH.read_text())
        plan["model_inference_enabled"] = 0
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrong_bool.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "model_inference_enabled"):
                ACCESS.verified_manifest_and_plan(plan_path=path)

    def test_unsigned_author_template_is_not_confirmation(self):
        with self.assertRaisesRegex(ValueError, "unresolved"):
            ACCESS.author_gate(ROOT / "AUTHOR_DREYER_PRIOR_USE_TEMPLATE.json")

    def test_missing_author_file_is_not_confirmation(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            ACCESS.author_gate(None)

    def test_null_or_zero_author_fact_is_not_confirmed_false(self):
        for wrong in [None, 0, "false"]:
            declaration = {"status": "AUTHOR_CONFIRMED", "dataset": "Dreyer2023", "provider_dataset_id": "nm000250",
                           "provider_manifest_sha256": ACCESS.PINNED_SHA256,
                           "prior_proposed_decoder_results_inspected_or_used": wrong}
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "fake_author.json"
                path.write_text(json.dumps(declaration))
                with self.assertRaisesRegex(ValueError, "unresolved"):
                    ACCESS.author_gate(path)

    def test_no_full_git_commit_is_rejected_before_git_read(self):
        with mock.patch.object(ACCESS.subprocess, "run", side_effect=AssertionError("git must not run")):
            with self.assertRaisesRegex(ValueError, "full_registration"):
                ACCESS.committed_plan_gate("short")

    def test_valid_sha_with_different_committed_plan_is_rejected(self):
        fake = mock.Mock(returncode=0, stdout=b"a different plan")
        with mock.patch.object(ACCESS.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "not_identical"):
                ACCESS.committed_plan_gate("1" * 40)

    def test_default_cli_does_not_touch_raw_or_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary) / "dry.json"
            with mock.patch("sys.argv", ["acquire_dreyer_runs.py", "--receipt", str(receipt)]), \
                    mock.patch.object(ACCESS, "import_header_module", side_effect=AssertionError("no raw access")), \
                    mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network")), \
                    contextlib.redirect_stdout(io.StringIO()):
                ACCESS.main()
            result = json.loads(receipt.read_text())
            self.assertEqual(result["operation"], "metadata_only_dry_run")
            self.assertEqual(result["raw_bytes_downloaded_now"], 0)
            self.assertEqual(result["files"], [])
            self.assertEqual(result["target_predictions"], 0)
            self.assertFalse(result["confirmatory_model_evaluation_authorized"])

    def test_download_without_author_fails_before_any_raw_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary) / "blocked.json"
            with mock.patch("sys.argv", ["acquire_dreyer_runs.py", "--download", "--receipt", str(receipt)]), \
                    mock.patch.object(ACCESS, "import_header_module", side_effect=AssertionError("no raw access")), \
                    mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network")), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    ACCESS.main()
            self.assertEqual(error.exception.code, 1)
            result = json.loads(receipt.read_text())
            self.assertEqual(result["raw_bytes_downloaded_now"], 0)
            self.assertEqual(result["files"], [])
            self.assertIn("BLOCKED", result["status"])
            self.assertFalse(result["original_gdf_equivalence_verified"])

    def test_real_bounded_subset_preserves_source_edf_units_and_mapping(self):
        receipt = json.loads((ROOT / "evidence/dreyer_access_metadata_receipt.json").read_text())
        module = ACCESS.import_header_module()
        row = next(row for row in json.loads(ACCESS.MANIFEST_PATH.read_text()) if row["path"] == receipt["files"][0]["path"])
        path = Path(receipt["files"][0]["cache_path"])
        if not path.is_file():
            self.skipTest("bounded raw cache unavailable; never auto-download in tests")
        result = ACCESS.audit_one(row, path, module)
        self.assertEqual(result["cue_counts"], {"769": 20, "770": 20})
        self.assertEqual(result["header_units"], "uV")
        self.assertEqual(result["sampling_hz"], 512)
        self.assertFalse(result["signal_only_qc_complete"])
        self.assertFalse(result["original_gdf_equivalence_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
