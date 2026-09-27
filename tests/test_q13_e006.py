"""CPU-only gates for the versioned Q13-E006 duration amendment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import q13_e006
from scripts.run_eegnet import sha256_file


def test_q5_source_only_epochs_reconstructed_from_original_inner_curves() -> None:
    assert q13_e006.selected_epochs_from_q5() == {
        "1": 27, "2": 1, "3": 2, "4": 10, "5": 13,
        "6": 7, "7": 6, "8": 1, "9": 7,
    }


def test_mat_identity_rejects_missing_and_duplicate_files() -> None:
    rows = [
        {"path": f"/cache/A{subject:02d}{session}.mat",
         "bytes": 100 + subject, "sha256": f"{subject}{session}"}
        for subject in range(1, 10) for session in ("T", "E")
    ]
    identity = q13_e006.file_identity(rows)
    assert len(identity) == 18
    with pytest.raises(AssertionError, match="18"):
        q13_e006.file_identity(rows[:-1])
    with pytest.raises(AssertionError, match="duplicated"):
        q13_e006.file_identity(rows[:-1] + [rows[0]])


def test_historical_training_code_requires_byte_identical_git_blobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scripts" / "locked.py"
    source.parent.mkdir()
    source.write_bytes(b"original training implementation\n")
    monkeypatch.setattr(q13_e006, "ROOT", tmp_path)
    monkeypatch.setattr(q13_e006, "TRAINING_CODE_PATHS", ("scripts/locked.py",))
    monkeypatch.setattr(q13_e006, "HISTORICAL_Q5_SELECTION_PATHS", ())
    real_run = subprocess.run

    def historical_blob(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=b"original training implementation\n")

    monkeypatch.setattr(q13_e006.subprocess, "run", historical_blob)
    head = {"git_head": "a" * 40}
    assert q13_e006.assert_historical_training_sources(head)["scripts/locked.py"]
    source.write_bytes(b"changed training implementation\n")
    with pytest.raises(RuntimeError, match="source/archive differs"):
        q13_e006.assert_historical_training_sources(head)
    monkeypatch.setattr(q13_e006.subprocess, "run", real_run)
    with pytest.raises(RuntimeError, match="valid historical Git HEAD"):
        q13_e006.assert_historical_training_sources({"git_head": None})


def test_build_config_changes_only_versioned_identity_schedule_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_root = tmp_path / "Q8_FIXED20"
    fixed_root.mkdir()
    (fixed_root / "run_config.json").write_text('{"frozen":true}', encoding="utf-8")
    monkeypatch.setattr(q13_e006, "FIXED", fixed_root)
    prior = {
        "experiment_id": "Q13-E001", "condition": "Q8_FIXED20",
        "method": "Q8_BROAD", "preprocessing": {"bands": {"broad": [4, 40]}},
        "architecture": {"name": "EEGNet"}, "training": {"final_seeds": [20260924, 20260925, 20260926]},
        "selected_epochs_by_target": {str(s): 20 for s in range(1, 10)},
        "source_only_selection_provenance": {"q5_validation_sha256": "frozen"},
        "runner_sha256": "original", "data_dir": "/original/cache",
    }
    chosen = {str(s): s for s in range(1, 10)}
    amended = q13_e006.build_config(tmp_path / "data", prior, chosen)
    assert amended["experiment_id"] == "Q13-E006"
    assert amended["condition"] == "Q8_RAW_CE_MATCHED"
    assert amended["selected_epochs_by_target"] == chosen
    for field in ("method", "preprocessing", "architecture", "training"):
        assert amended[field] == prior[field]
    assert amended["source_only_selection_provenance"]["selection_rule"].endswith("raw_CE")
    assert amended["fixed20_config_sha256"]
    assert prior["selected_epochs_by_target"] == {str(s): 20 for s in range(1, 10)}


def test_execute_fails_closed_without_cuda_or_full_q13_scientific_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(q13_e006.torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="working CUDA"):
        q13_e006.preflight(tmp_path)
    monkeypatch.setattr(q13_e006.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(q13_e006, "assert_committed_amendment", lambda: "frozen_commit")
    report = tmp_path / "validation_report.json"
    status = tmp_path / "batch_status.json"
    report.write_text(json.dumps({"status": "artifact_only_not_scientific_pass",
                                  "checkpoint_replays": 0}), encoding="utf-8")
    status.write_text(json.dumps({"status": "complete_validated"}), encoding="utf-8")
    monkeypatch.setattr(q13_e006, "VALIDATION", report)
    monkeypatch.setattr(q13_e006, "BATCH_STATUS", status)
    with pytest.raises(RuntimeError, match="Full Q13 scientific validation"):
        q13_e006.preflight(tmp_path)


def test_amendment_matrix_is_additive_not_a_rewrite_of_837_fit_q13() -> None:
    original = json.loads((q13_e006.ROOT / "research_runs/Q13-PREP-20260926/MATRIX.json")
                          .read_text(encoding="utf-8"))
    amendment = json.loads(q13_e006.MATRIX.read_text(encoding="utf-8"))
    assert original["total_new_deep_fits"] == 837
    assert original["experiments"][0]["id"] == "Q13-E001"
    assert amendment["experiment_id"] == "Q13-E006"
    assert amendment["new_final_fits"] == 27
    assert amendment["new_inner_fits"] == amendment["target_fits"] == 0


def test_preflight_rejects_runtime_and_raw_data_mismatch_before_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = tmp_path / "Q8_FIXED20"
    fixed.mkdir()
    (fixed / "run_config.json").write_text(json.dumps({
        "experiment_id": "Q13-E001", "condition": "Q8_FIXED20", "method": "Q8_BROAD",
        "shared_mean_logits": False,
        "selected_epochs_by_target": {str(s): 20 for s in range(1, 10)},
        "runner_sha256": sha256_file(Path(q13_e006.q13_neural.__file__)),
        "source_only_selection_provenance": {
            "q5_config_sha256": sha256_file(q13_e006.ROOT / "results/Q5-E001/config.json"),
            "q5_selection_sha256": sha256_file(q13_e006.Q5_SELECTION),
            "q5_validation_sha256": sha256_file(q13_e006.ROOT / "results/Q5-E001/validation_report.json"),
        },
    }), encoding="utf-8")
    (fixed / "status.json").write_text(json.dumps({"status": "complete",
                                                   "completed_final_fits": 27}), encoding="utf-8")
    files = [{"path": f"/frozen/A{s:02d}{part}.mat", "bytes": 10,
              "sha256": f"{s}{part}"} for s in range(1, 10) for part in ("T", "E")]
    (fixed / "source_files.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    historical = {"packages": {"torch": "2.8.0"}, "torch_cuda_runtime": "12.8",
                  "cuda_device_name": "matched-card"}
    (fixed / "environment.json").write_text(json.dumps(historical), encoding="utf-8")
    report = tmp_path / "validation_report.json"
    report.write_text(json.dumps({"status": "passed", "checkpoint_replays": 837}),
                      encoding="utf-8")
    batch = tmp_path / "batch_status.json"
    batch.write_text(json.dumps({"status": "complete_validated"}), encoding="utf-8")
    monkeypatch.setattr(q13_e006, "FIXED", fixed)
    monkeypatch.setattr(q13_e006, "VALIDATION", report)
    monkeypatch.setattr(q13_e006, "BATCH_STATUS", batch)
    monkeypatch.setattr(q13_e006, "assert_committed_amendment", lambda: "committed")
    monkeypatch.setattr(q13_e006, "assert_historical_training_sources", lambda *_args: {})
    monkeypatch.setattr(q13_e006.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(q13_e006.q9, "_versions", lambda: {
        **historical, "packages": {"torch": "2.14.0"}})
    with pytest.raises(RuntimeError, match="Runtime mismatch"):
        q13_e006.preflight(tmp_path)
    monkeypatch.setattr(q13_e006.q9, "_versions", lambda: historical)
    altered = [dict(row) for row in files]
    altered[0]["sha256"] = "changed"
    monkeypatch.setattr(q13_e006, "source_files", lambda *_args: altered)
    with pytest.raises(RuntimeError, match="MAT files differ"):
        q13_e006.preflight(tmp_path)
