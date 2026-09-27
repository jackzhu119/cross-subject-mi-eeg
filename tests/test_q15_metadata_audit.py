"""Q15 metadata-only audit tests using tiny synthetic raw JSON fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/q15_metadata_audit.py"
SPEC = importlib.util.spec_from_file_location("q15_metadata_audit", MODULE)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def _make_fixture(tmp_path: Path, dataset: str) -> tuple[Path, dict]:
    plan = json.loads(audit.CONTRACT_PATH.read_text(encoding="utf-8"))
    channels = plan["new_source_arm"]["channels"]
    spec = next(row for row in plan["metadata_audits"] if row["dataset"] == dataset)
    files = []
    for subject in range(1, spec["expected_subjects"] + 1):
        for session in range(1, spec["expected_sessions_per_subject"] + 1):
            file_id = f"s{subject:02d}_session{session}_offline_MI"
            raw_path = tmp_path / (file_id + ".json")
            rate = 1000 if dataset == "Lee2019_MI" else 512
            raw = {
                "file_id": file_id, "subject": subject, "session": str(session),
                "run": "offline_MI", "run_role": (
                    "offline_train" if dataset == "Lee2019_MI" else "offline_labeled"
                ),
                "channels": channels + ["Oz"], "sampling_rate_hz": rate,
                "native_physical_unit": "uV", "loader_output_unit": "V",
                "unit_conversion": "multiply by 1e-6", "reference": "nasion",
                "cue_origin": "MI_cue_onset", "task": "left_right_motor_imagery",
                "labeled": True, "label_map": {"left_hand": 2, "right_hand": 1},
                "available_cue_window_s": [0.0, 4.0 if dataset == "Lee2019_MI" else 3.0],
                "task_duration_s": 4.0 if dataset == "Lee2019_MI" else 3.0,
                "signal_n_samples": 10 * rate,
                "events": [
                    {"onset_sample": rate, "label": "left_hand"},
                    {"onset_sample": 5 * rate, "label": "right_hand"},
                ],
            }
            _write_json(raw_path, raw)
            files.append({
                "file_id": file_id, "path": str(raw_path),
                "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                "adapter": "synthetic_json_v1", "subject": subject,
                "session": str(session), "run": "offline_MI",
            })
    manifest = {
        "schema_version": 1, "dataset": dataset,
        "provider_version": "synthetic-v1", "loader_version": "fixture-v1",
        "license": "test-only", "provider_inventory_source": "synthetic fixture inventory",
        "expected_file_ids": [entry["file_id"] for entry in files], "files": files,
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path, manifest


@pytest.mark.parametrize("dataset,expected_subjects,expected_files", [
    ("Lee2019_MI", 54, 108), ("Cho2017", 52, 52),
])
def test_metadata_only_fixture_pass_never_authorizes_real_inference(
    tmp_path, dataset, expected_subjects, expected_files
):
    manifest_path, _ = _make_fixture(tmp_path, dataset)
    result = audit.audit_manifest(manifest_path, synthetic_fixture=True)
    assert result["status"] == "metadata_passed_non_authorizing_synthetic_fixture"
    assert result["n_subjects"] == expected_subjects
    assert result["n_files"] == expected_files
    assert result["raw_hashes_verified"] is True
    assert result["provider_inventory_verified"] is False
    assert result["external_prediction_authorized"] is False
    assert result["model_predictions_computed"] is False
    assert all(Path(item["path"]).is_absolute() for item in result["files"])


def test_unreviewed_real_adapter_fails_closed_after_hashing(tmp_path):
    manifest_path, _ = _make_fixture(tmp_path, "Cho2017")
    result = audit.audit_manifest(manifest_path, synthetic_fixture=False)
    assert result["status"] == "blocked_raw_adapter_unverified"
    assert result["raw_hashes_verified"] is True
    assert result["external_prediction_authorized"] is False


def test_cli_persists_non_authorizing_blocked_receipt(tmp_path):
    manifest_path, _ = _make_fixture(tmp_path, "Cho2017")
    output_path = tmp_path / "metadata_audit_receipt.json"
    completed = subprocess.run(
        [sys.executable, str(MODULE), "--manifest", str(manifest_path),
         "--output", str(output_path)],
        check=True, capture_output=True, text=True,
    )
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert "blocked_raw_adapter_unverified" in completed.stdout
    assert result["status"] == "blocked_raw_adapter_unverified"
    assert result["auditor_sha256"] == audit._sha256(MODULE)
    assert result["provider_manifest_path"] == str(manifest_path.resolve())
    assert result["provider_manifest_sha256"] == audit._sha256(manifest_path)
    assert result["external_prediction_authorized"] is False


def test_missing_manifest_still_produces_blocked_receipt(tmp_path):
    missing = tmp_path / "absent_manifest.json"
    result = audit.audit_manifest(missing)
    assert result["status"] == "blocked_invalid_manifest_or_metadata"
    assert result["provider_manifest_sha256"] is None
    assert result["external_prediction_authorized"] is False
    assert result["blocking_reasons"]


def test_raw_hash_mismatch_blocks(tmp_path):
    manifest_path, manifest = _make_fixture(tmp_path, "Cho2017")
    manifest["files"][0]["sha256"] = "0" * 64
    _write_json(manifest_path, manifest)
    result = audit.audit_manifest(manifest_path, synthetic_fixture=True)
    assert result["status"] == "blocked_raw_integrity"
    assert result["raw_hashes_verified"] is False


@pytest.mark.parametrize("mutation", [
    lambda raw: raw["channels"].remove("C3"),
    lambda raw: raw.update(cue_origin="trial_start"),
    lambda raw: raw.update(task_duration_s=2.0),
    lambda raw: raw.update(run_role="online_test"),
    lambda raw: raw.update(events=[{"onset_sample": 1000, "label": "left_hand"}]),
])
def test_metadata_incompatibility_blocks_even_with_updated_file_hash(tmp_path, mutation):
    manifest_path, manifest = _make_fixture(tmp_path, "Lee2019_MI")
    raw_path = Path(manifest["files"][0]["path"])
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    mutation(raw)
    _write_json(raw_path, raw)
    manifest["files"][0]["sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    _write_json(manifest_path, manifest)
    result = audit.audit_manifest(manifest_path, synthetic_fixture=True)
    assert result["status"] == "blocked_incompatible_metadata"
    assert result["external_prediction_authorized"] is False


def test_missing_expected_file_blocks(tmp_path):
    manifest_path, manifest = _make_fixture(tmp_path, "Cho2017")
    manifest["files"].pop()
    _write_json(manifest_path, manifest)
    result = audit.audit_manifest(manifest_path, synthetic_fixture=True)
    assert result["status"] == "blocked_invalid_manifest_or_metadata"
    assert result["external_prediction_authorized"] is False
