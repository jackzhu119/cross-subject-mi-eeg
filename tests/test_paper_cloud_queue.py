"""CPU-only orchestration checks; these tests never start EEG fits or a GPU."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import paper_cloud_queue


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_plan_is_fixed_and_has_no_q14_retraining(tmp_path: Path) -> None:
    plan = paper_cloud_queue.build_manifest("python", tmp_path / "raw", tmp_path / "edf")
    assert [row["id"] for row in plan["stages"]] == [
        "Q14_PORTABLE_VALIDATION", "Q12", "Q13"]
    assert [row["new_deep_fits"] for row in plan["stages"]] == [0, 378, 837]
    assert plan["total_new_deep_fits"] == 1215
    assert plan["q14_validation_only"] is True
    assert plan["automatic_shutdown"] is False
    assert all("--execute" in row["argv"] for row in plan["stages"])
    assert all("--publish" in row["argv"] for row in plan["stages"][1:])
    assert "q14_r2_portable_finalize.py" in plan["stages"][0]["argv"][1]
    assert plan["stages"][0]["failure_policy"].startswith("record_and_continue")
    assert len(plan["source_sha256"]) == len(paper_cloud_queue.SOURCE_FILES)
    assert all(len(value) == 64 for value in plan["source_sha256"].values())


def test_child_commands_preserve_virtualenv_python_path(tmp_path: Path) -> None:
    interpreter = tmp_path / ".venv-paper" / "bin" / "python"
    plan = paper_cloud_queue.build_manifest(
        str(interpreter), tmp_path / "raw", tmp_path / "edf")
    assert plan["python"] == str(interpreter.absolute())
    assert all(row["argv"][0] == str(interpreter.absolute()) for row in plan["stages"])
    assert paper_cloud_queue.BATCH.name == "Q12-PAPERQUEUE2"


@pytest.mark.parametrize("stage_name,expected_status,counts", [
    ("Q12", "passed_scientific_checks", {"inner_fits": 216, "final_fits": 162}),
    ("Q13", "passed", {"checkpoint_replays": 837}),
])
def test_scientific_receipt_requires_full_validation(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage_name: str,
        expected_status: str, counts: dict) -> None:
    monkeypatch.setattr(paper_cloud_queue, "ROOT", tmp_path)
    stage = next(row for row in paper_cloud_queue.stages(
        "python", tmp_path / "raw", tmp_path / "edf")
                 if row["id"] == stage_name)
    batch_path = tmp_path / stage["batch_status"]
    report_path = tmp_path / stage["scientific_report"]
    _write(batch_path, {"status": "complete_validated"})
    _write(report_path, {"status": expected_status, **counts})
    receipt = paper_cloud_queue.check_scientific_receipt(stage)
    assert len(receipt["batch_status_sha256"]) == 64
    assert len(receipt["scientific_report_sha256"]) == 64
    _write(report_path, {"status": "artifact_only_not_scientific_pass", **counts})
    with pytest.raises(RuntimeError, match="scientific report did not pass"):
        paper_cloud_queue.check_scientific_receipt(stage)


def test_missing_fit_replays_block_q13(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paper_cloud_queue, "ROOT", tmp_path)
    stage = paper_cloud_queue.stages("python", tmp_path / "raw", tmp_path / "edf")[2]
    _write(tmp_path / stage["batch_status"], {"status": "complete_validated"})
    _write(tmp_path / stage["scientific_report"],
           {"status": "passed", "checkpoint_replays": 836})
    with pytest.raises(RuntimeError, match="checkpoint replay count"):
        paper_cloud_queue.check_scientific_receipt(stage)


def test_q14_requires_official_edf_and_publication(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paper_cloud_queue, "ROOT", tmp_path)
    stage = paper_cloud_queue.stages("python", tmp_path / "raw", tmp_path / "edf")[0]
    _write(tmp_path / stage["batch_status"], {"status": "complete_validated"})
    _write(tmp_path / stage["scientific_report"], {
        "passed": True, "validation_attempt_id": "Q14-E002R2V1",
        "n_subjects": 109, "n_verified_official_edf_files": 327,
        "external_target_fit_count": 0,
    })
    completion = tmp_path / "results/Q14-R2PORT/completion_receipt.json"
    _write(completion, {"github_published": True})
    assert len(paper_cloud_queue.check_scientific_receipt(stage)["scientific_report_sha256"]) == 64
    _write(completion, {"github_published": False})
    with pytest.raises(RuntimeError, match="publication receipt"):
        paper_cloud_queue.check_scientific_receipt(stage)
