"""Synthetic-only queue/receipt tests. No EEG, CUDA, or target metrics."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.q9_batch import build_manifest, safe_name, sha256
from scripts.q9_validate_batch import validate


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _matrix(path: Path) -> None:
    _write(path, {
        "conditions": [
            {"experiment_id": "Q9-E001", "name": "MID_8_30", "inner_fits": 36, "final_fits": 27},
            {"experiment_id": "Q9-E002", "name": "MID_8_30_Q8_EPOCHS", "inner_fits": 0, "final_fits": 27},
        ],
        "shallow_controls": [
            {"experiment_id": "Q9-A001", "name": "PSD44_LDA", "source_fits": 9},
            {"experiment_id": "Q9-A001", "name": "PSD44_LINEAR_SVM", "source_fits": 9},
        ],
    })


def test_manifest_is_ordered_and_explicit_about_unrun_conditions(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    _matrix(matrix)
    templates = {"neural": ["{python}", "runner.py", "--condition", "{condition}",
                            "--phase", "{phase}"],
                 "psd": ["{python}", "psd.py", "--out", "{output_root}/Q9-A001"]}
    manifest = build_manifest(matrix, templates,
                              ["MID_8_30", "PSD44_LDA", "PSD44_LINEAR_SVM"],
                              tmp_path / "data", tmp_path / "results", "cuda", "python")
    assert [(item["condition"], item["phase"]) for item in manifest["jobs"]] == [
        ("MID_8_30", "selection"), ("MID_8_30", "final"),
        ("PSD44_both", "source_fits"),
    ]
    assert manifest["unselected_planned_conditions"] == ["MID_8_30_Q8_EPOCHS"]
    assert manifest["jobs"][0]["completion_value"] == "frozen_before_Q9_target_inference"
    assert "--condition" in manifest["jobs"][0]["argv"]


def test_guardrails_reject_bad_batch(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    _matrix(matrix)
    templates = {"neural": ["{python}"], "psd": ["{python}"]}
    with pytest.raises(ValueError, match="together"):
        build_manifest(matrix, templates, ["PSD44_LDA"], tmp_path, tmp_path, "cuda", "python")
    with pytest.raises(ValueError, match="CUDA"):
        build_manifest(matrix, templates, ["MID_8_30"], tmp_path, tmp_path, "cpu", "python")
    with pytest.raises(ValueError, match="Unsafe"):
        safe_name("../../private")


def test_batch_validator_checks_receipts_and_hashes(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    _matrix(matrix)
    output = tmp_path / "results"
    templates = {"neural": ["python", "runner.py", "--condition", "{condition}",
                            "--phase", "{phase}"],
                 "psd": ["python", "psd.py"]}
    manifest = build_manifest(matrix, templates, ["MID_8_30"],
                              tmp_path / "data", output, "cuda", "python")
    batch = output / "Q9-BATCH"
    _write(batch / "batch_manifest.json", manifest)
    selection = output / "Q9-E001/MID_8_30/selection.csv"
    selection.parent.mkdir(parents=True)
    selection.write_text("subject,selected_epochs\n1,10\n", encoding="utf-8")
    _write(selection.parent / "selection_provenance.json", {
        "status": "frozen_before_Q9_target_inference",
        "selection_sha256": sha256(selection), "inner_fits": 36,
    })
    predictions = selection.parent / "predictions.csv"
    with predictions.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["subject", "seed"])
        for subject in range(1, 10):
            for seed in (20260924, 20260925, 20260926):
                writer.writerows([(subject, seed)] * 576)
    _write(selection.parent / "status.json", {
        "status": "complete", "completed_final_fits": 27,
    })
    for job in manifest["jobs"]:
        folder = batch / "jobs" / job["job_id"]
        folder.mkdir(parents=True)
        log = folder / "run.log"
        log.write_text("synthetic completion\n", encoding="utf-8")
        _write(folder / "status.json", {
            "status": "complete", "exit_code": 0,
            "argv": job["argv"], "log_sha256": sha256(log),
            "completion_status_sha256": sha256(Path(job["completion_status"])),
        })
    passed = validate(batch)
    assert passed["status"] == "passed_orchestration_only"
    assert passed["jobs_complete"] == 2
    assert passed["scientific_validation"] == "not_performed_by_this_batch_validator"
    (batch / "jobs" / manifest["jobs"][0]["job_id"] / "run.log").write_text("changed", encoding="utf-8")
    failed = validate(batch)
    assert failed["status"] == "failed"
    assert any("log hash" in item for item in failed["errors"])
