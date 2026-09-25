"""Synthetic custody tests: no PhysioNet download, classifier, or GPU required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import q14_r1_migration as migration
from scripts.q14_source import sha256


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, dict):
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path.write_bytes(data)


@pytest.fixture
def custody(tmp_path: Path, monkeypatch):
    origin = tmp_path / "original"
    result = tmp_path / "r1"
    source = tmp_path / "source"
    data = tmp_path / "edf"
    config_file = tmp_path / "config.json"
    config = {"external_runs": [4, 8, 12], "models": ["BROAD_EEGNET", "MU_BETA_SHARED", "CSP4_LDA"]}
    _write(config_file, config)
    _write(source / "freeze_receipt.json", {"frozen_at_utc": "2026-09-24T00:00:00+00:00"})
    monkeypatch.setattr(migration, "ORIGINAL", origin)
    monkeypatch.setattr(migration, "RESULT", result)
    monkeypatch.setattr(migration, "E002_ROOT", source)
    monkeypatch.setattr(migration, "CONFIG", config_file)
    now = {"python": "3.12", "platform": migration.EXPECTED_NEW_PLATFORM, "packages": {"torch": "2"}}
    before = {**now, "platform": migration.EXPECTED_OLD_PLATFORM}
    monkeypatch.setattr(migration, "runtime_receipt", lambda: now)
    manifest_lines = []
    for subject in range(1, 110):
        for run in config["external_runs"]:
            name = f"S{subject:03d}R{run:02d}.edf"
            if subject <= 55:
                path = data / name
                _write(path, f"fake-edf-{subject}-{run}".encode())
                digest = sha256(path)
            else:
                digest = "0" * 64
            manifest_lines.append(f"{digest} S{subject:03d}/{name}")
    _write(origin / "physionet_SHA256SUMS.txt", ("\n".join(manifest_lines) + "\n").encode())
    freeze_sha = sha256(source / "freeze_receipt.json")
    run_config = {
        "experiment_id": "Q14-E002",
        "config_sha256": sha256(config_file),
        "freeze_receipt_sha256": freeze_sha,
        "runner_sha256": sha256(migration.ROOT / "scripts/q14_external.py"),
        "data_dir": str(data.resolve()),
        "device": "cuda",
        "subjects": list(range(1, 110)),
        "runs": config["external_runs"],
        "official_checksum_manifest_sha256": sha256(origin / "physionet_SHA256SUMS.txt"),
        "runtime": before,
    }
    _write(origin / "run_config.json", run_config)
    for subject in range(1, 56):
        folder = origin / f"subject_{subject:03d}"
        _write(folder / "predictions.csv", f"opaque target predictions {subject}".encode())
        files = []
        for run in config["external_runs"]:
            path = data / f"S{subject:03d}R{run:02d}.edf"
            files.append(
                {
                    "subject": subject,
                    "run": run,
                    "filename": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
        _write(
            folder / "receipt.json",
            {
                "status": "complete",
                "subject": subject,
                "source_models": config["models"],
                "external_target_fit_count": 0,
                "freeze_receipt_sha256": freeze_sha,
                "official_checksum_manifest_sha256": run_config["official_checksum_manifest_sha256"],
                "predictions_sha256": sha256(folder / "predictions.csv"),
                "n_trials": 1,
                "n_prediction_rows": 7,
                "edf_files": files,
                "completed_at_utc": "2026-09-25T00:00:00+00:00",
            },
        )
    return {"origin": origin, "result": result, "source": source, "data": data, "config": config,
            "freeze_sha": freeze_sha, "now": now}


def test_hash_only_migration_and_byte_identical_copy(custody):
    audit = migration.audit_origin(custody["data"], "cuda", custody["config"], custody["freeze_sha"])
    assert audit["n_original_subjects"] == 55
    assert audit["target_outcomes_scored_during_migration"] is False
    custody["result"].mkdir()
    first = audit["original_subjects_hash_verified"][0]
    migration._atomic_subject_copy(1, first)
    migration._atomic_subject_copy(1, first)  # restart verifies, never rewrites
    for filename in ("receipt.json", "predictions.csv"):
        assert (custody["result"] / "subject_001" / filename).read_bytes() == (
            custody["origin"] / "subject_001" / filename
        ).read_bytes()


def test_migration_rejects_runtime_drift_beyond_exact_kernel(custody):
    run_file = custody["origin"] / "run_config.json"
    run = json.loads(run_file.read_text())
    run["runtime"]["packages"]["torch"] = "different"
    _write(run_file, run)
    with pytest.raises(AssertionError, match="runtime fields except platform"):
        migration.audit_origin(custody["data"], "cuda", custody["config"], custody["freeze_sha"])
    run["runtime"]["packages"]["torch"] = "2"
    run["runtime"]["platform"] = "Linux-6.1.0-generic-x86_64-with-glibc2.35"
    _write(run_file, run)
    with pytest.raises(AssertionError, match="only the audited"):
        migration.audit_origin(custody["data"], "cuda", custody["config"], custody["freeze_sha"])


def test_migration_rejects_corrupt_original_edf_or_prediction(custody):
    path = custody["data"] / "S001R04.edf"
    _write(path, b"changed EDF bytes")
    with pytest.raises(AssertionError, match="S001R04.edf"):
        migration.audit_origin(custody["data"], "cuda", custody["config"], custody["freeze_sha"])
    _write(path, b"fake-edf-1-4")
    prediction = custody["origin"] / "subject_001/predictions.csv"
    _write(prediction, b"changed prediction bytes")
    with pytest.raises(AssertionError, match="receipt predictions_sha256"):
        migration.audit_origin(custody["data"], "cuda", custody["config"], custody["freeze_sha"])
