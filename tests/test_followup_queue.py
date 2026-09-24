"""No-network checks for the detached Q10-gated Q11/Q14 supervisor."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import followup_queue as queue


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_q10_gate_requires_both_independent_markers_and_correct_publication(
    tmp_path: Path,
) -> None:
    _json(tmp_path / "Q10-QUEUE/batch_status.json", {"status": "complete_validated"})
    _json(tmp_path / "Q10-E001/validation_report.json",
          {"status": "passed_scientific_checks"})
    passed, reason = queue._q10_scientific_ready(tmp_path)
    assert not passed and "Q10-A001" in reason
    _json(tmp_path / "Q10-A001/validation_report.json",
          {"status": "passed_scientific_artifact_validation"})
    assert queue._q10_scientific_ready(tmp_path) == (True, "validated")
    _json(tmp_path / "Q10-BATCH/publish_status.json",
          {"status": "pushed", "experiment_dir": "results/Q10-A001"})
    assert not queue._publication_ok(tmp_path, "Q10-BATCH", "Q10-E001")
    _json(tmp_path / "Q10-BATCH/publish_status.json",
          {"status": "pushed_with_skipped_files", "experiment_dir": "results/Q10-E001"})
    assert queue._publication_ok(tmp_path, "Q10-BATCH", "Q10-E001")


def test_q10_failure_stops_before_any_followup(tmp_path: Path) -> None:
    _json(tmp_path / "Q10-QUEUE/batch_status.json", {"status": "failed_stopped"})
    with pytest.raises(RuntimeError, match="Q10 stopped"):
        queue._wait_q10(tmp_path, sys.executable, {}, 1, 1, 0, 0)


def test_publisher_rechecks_artifacts_even_after_prior_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _json(tmp_path / "Q11-BATCH/publish_status.json",
          {"status": "pushed", "experiment_dir": "results/Q11-E001"})
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"status":"pushed"}')

    monkeypatch.setattr(queue.subprocess, "run", fake_run)
    assert queue._publish(sys.executable, tmp_path, "Q11-BATCH", "Q11-E001", {}, 1, 0)
    assert len(calls) == 1


def test_q11_q14_completion_requires_independent_external_zero_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    matrix = tmp_path / "research_runs/Q11-E001/MATRIX.json"
    code = tmp_path / "scripts/fake_q11.py"
    _json(matrix, {"frozen": True})
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text("# frozen\n", encoding="utf-8")
    _json(tmp_path / "Q11-BATCH/batch_manifest.json",
          {"matrix_sha256": queue._sha256(matrix),
           "code_sha256": {"scripts/fake_q11.py": queue._sha256(code)}})
    _json(tmp_path / "Q11-BATCH/batch_status.json", {"status": "complete_validated"})
    assert not queue._q11_validated(tmp_path)
    _json(tmp_path / "Q11-E001/validation_report.json",
          {"status": "passed_scientific_checks"})
    assert queue._q11_validated(tmp_path)
    _json(tmp_path / "Q14-BATCH/completion_receipt.json",
          {"status": "complete_external_validated"})
    _json(tmp_path / "Q14-E001/validation_report.json", {"passed": True})
    _json(tmp_path / "Q14-E002/source/validation_report.json", {"passed": True})
    paths = {
        "config_sha256": tmp_path / "research_runs/Q14-E001/CONFIG.json",
        "source_runner_sha256": tmp_path / "scripts/q14_source.py",
        "external_runner_sha256": tmp_path / "scripts/q14_external.py",
        "batch_runner_sha256": tmp_path / "scripts/q14_batch.py",
        "validator_sha256": tmp_path / "scripts/q14_validate.py",
        "contract_tests_sha256": tmp_path / "tests/test_q14_external_protocol.py",
        "metadata_audit_sha256": tmp_path / "research_runs/Q14-E001/METADATA_AUDIT.json",
        "source_validation_report_sha256":
            tmp_path / "Q14-E002/source/validation_report.json",
        "q14_e001_validation_report_sha256":
            tmp_path / "Q14-E001/validation_report.json",
    }
    for field, path in paths.items():
        if path.is_file():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(field + "\n", encoding="utf-8")
    freeze = {"status": "FROZEN_BEFORE_EXTERNAL_DATA_ACCESS"}
    freeze.update({field: queue._sha256(path) for field, path in paths.items()})
    freeze_file = tmp_path / "Q14-E002/freeze_receipt.json"
    _json(freeze_file, freeze)
    _json(tmp_path / "Q14-E002/external/validation_report.json",
          {"status": "independent_external_validation_passed", "external_target_fit_count": 1,
           "source_freeze_sha256": queue._sha256(freeze_file)})
    assert not queue._q14_validated(tmp_path)
    _json(tmp_path / "Q14-E002/external/validation_report.json",
          {"status": "independent_external_validation_passed", "external_target_fit_count": 0,
           "source_freeze_sha256": queue._sha256(freeze_file)})
    assert queue._q14_validated(tmp_path)


def test_failed_stage_receipt_and_log_survive_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    results = tmp_path / "results"
    folder = results / "Q14-QUEUE"
    folder.mkdir(parents=True)
    marker = results / "marker.json"
    verify = lambda _results: marker.is_file()
    with pytest.raises(RuntimeError, match="independent validation missing"):
        queue._stage("synthetic", [sys.executable, "-c", "raise SystemExit(7)"],
                     results, folder, {}, verify)
    failed = queue._read(folder / "synthetic_stage_receipt.json")
    assert failed["status"] == "failed_stopped"
    assert failed["attempts"][0]["exit_code"] == 7
    command = [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ok')"]
    queue._stage("synthetic", command, results, folder, {}, verify)
    complete = queue._read(folder / "synthetic_stage_receipt.json")
    assert complete["status"] == "complete"
    assert [item["exit_code"] for item in complete["attempts"]] == [7, 0]
    assert "ATTEMPT 1" in (folder / "synthetic.log").read_text(encoding="utf-8")
    assert "ATTEMPT 2" in (folder / "synthetic.log").read_text(encoding="utf-8")


def test_interrupted_stage_attempt_is_kept_on_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    results = tmp_path / "results"
    folder = results / "Q14-QUEUE"
    _json(folder / "synthetic_stage_receipt.json",
          {"status": "running", "stage": "synthetic", "attempts": [],
           "current_attempt": 1, "started_at_utc": "2026-01-01T00:00:00+00:00"})
    marker = results / "marker.txt"
    queue._stage("synthetic",
                 [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ok')"],
                 results, folder, {}, lambda _results: marker.is_file())
    receipt = queue._read(folder / "synthetic_stage_receipt.json")
    assert receipt["status"] == "complete"
    assert receipt["attempts"][0]["status"] == "interrupted_without_exit_receipt"
    assert receipt["attempts"][1]["attempt"] == 2


def test_plan_does_not_create_queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["followup_queue.py", "--bnci-data-dir",
                                         str(tmp_path / "raw"), "--physionet-data-dir",
                                         str(tmp_path / "external"), "--plan-only"])
    assert queue.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["planned_new_deep_fits"] == 392
    assert plan["planned_new_shallow_fits"] == 10
    assert plan["Q14_E001_E002"]["external_target_fits"] == 0
    assert not (tmp_path / "results").exists()
