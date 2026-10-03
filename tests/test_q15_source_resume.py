"""Resume provenance tests with doubles only; no EEG, model fit, or live API."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from scripts import q15_source as source


@pytest.fixture
def reusable_source(tmp_path, monkeypatch):
    output, freeze = tmp_path / "source-output", tmp_path / "freeze.json"
    freeze.write_text('{"synthetic_test_fixture":true}\n')
    monkeypatch.setattr(source, "OUTPUT", output)
    monkeypatch.setattr(source, "FREEZE", freeze)
    monkeypatch.setattr(source, "_verify_committed_freeze", lambda: {
        "contract_sha256": "a" * 64, "runner_sha256": "b" * 64,
    })
    monkeypatch.setattr(source.q14_source, "source_file_receipt", lambda _: [])
    monkeypatch.setattr(source.q14_source, "runtime_receipt", lambda: {
        "synthetic_test_fixture": True,
    })
    loaded = []

    def load_fixture(*_):
        loaded.append(True)
        arrays = {name: np.zeros((9, 21, 320), dtype=np.float32)
                  for name in ("broad", "mu", "beta")}
        meta = pd.DataFrame({
            "sample_id": [f"synthetic-source-{subject}" for subject in range(1, 10)],
            "subject": range(1, 10), "label": [1] * 9,
        })
        return arrays, meta, pd.DataFrame({"synthetic_test_fixture": [True]})

    monkeypatch.setattr(source, "load_source", load_fixture)
    reused = []

    def verified_fixture(path, required):
        reused.append((str(path), dict(required)))
        path.mkdir(parents=True, exist_ok=True)
        rows = [{"epoch": epoch, "train_ce": 1.0,
                 "val_ce": 1.0 if "validation_subjects" in required else None}
                for epoch in range(1, required["epochs"] + 1)]
        source.q14_source.atomic_json(path / "curve.json", {"epochs": rows})
        return rows

    monkeypatch.setattr(source.q14_source, "_verify_fit", verified_fixture)
    monkeypatch.setattr(source, "_fit_deep", lambda *_, **__: pytest.fail(
        "All fixture fits are verified and must be reused; no fit may begin"
    ))
    csp_reused = []
    monkeypatch.setattr(source, "_fit_csp", lambda *_, **__: csp_reused.append(True))
    return output, freeze, loaded, reused, csp_reused


def test_source_rerun_preserves_receipt_bytes_pinned_by_inference(reusable_source):
    output, _, loaded, reused, csp_reused = reusable_source
    source.run_source(output.parent / "synthetic-raw", "cpu")
    receipt = output / "source/source_stage_complete.json"
    first_bytes, first_sha = receipt.read_bytes(), source._sha(receipt)
    first_time = json.loads(first_bytes)["completed_at_utc"]
    assert datetime.fromisoformat(first_time).tzinfo is not None
    assert len(reused) == 14 and len(csp_reused) == 1
    source.run_source(output.parent / "synthetic-raw", "cpu")
    assert receipt.read_bytes() == first_bytes
    assert source._sha(receipt) == first_sha
    assert len(reused) == 28 and len(csp_reused) == 2 and len(loaded) == 2


@pytest.mark.parametrize("defect", [
    "missing_fit_count", "wrong_fit_count", "wrong_protocol", "wrong_status",
    "target_outcomes", "extra_field", "missing_timestamp", "malformed_timestamp",
    "timezone_missing", "timestamp_nontext",
])
def test_incomplete_or_changed_completion_blocks_before_loading(reusable_source, defect):
    output, freeze, loaded, reused, _ = reusable_source
    root = output / "source"
    receipt = source._source_stage_completion(root, source._sha(freeze), write=True)
    value = json.loads(receipt.read_text())
    if defect == "missing_fit_count":
        value.pop("deep_fit_count")
    elif defect == "wrong_fit_count":
        value["deep_fit_count"] = 13
    elif defect == "wrong_protocol":
        value["pre_fit_freeze_sha256"] = "c" * 64
    elif defect == "wrong_status":
        value["status"] = "incomplete"
    elif defect == "target_outcomes":
        value["external_predictions_computed"] = True
    elif defect == "extra_field":
        value["extra_fit_count"] = 1
    elif defect == "missing_timestamp":
        value.pop("completed_at_utc")
    elif defect == "malformed_timestamp":
        value["completed_at_utc"] = "not-a-time"
    elif defect == "timezone_missing":
        value["completed_at_utc"] = "2026-10-03T10:00:00"
    else:
        value["completed_at_utc"] = 0
    receipt.write_text(json.dumps(value))
    before = receipt.read_bytes()
    with pytest.raises(AssertionError, match="source completion"):
        source.run_source(output.parent / "synthetic-raw", "cpu")
    assert loaded == [] and reused == [] and receipt.read_bytes() == before


def test_read_only_completion_probe_does_not_claim_success(tmp_path):
    receipt = source._source_stage_completion(tmp_path, "a" * 64, write=False)
    assert not receipt.exists()
    source._source_stage_completion(tmp_path, "a" * 64, write=True)
    recorded = json.loads(receipt.read_text())
    timestamp = datetime.fromisoformat(recorded["completed_at_utc"])
    assert timestamp.utcoffset() == datetime.now(UTC).utcoffset()


def test_symlinked_completion_cannot_release_resume(tmp_path):
    saved = tmp_path / "existing"
    saved.mkdir()
    original = source._source_stage_completion(saved, "a" * 64, write=True)
    root = tmp_path / "source"
    root.mkdir()
    (root / original.name).symlink_to(original)
    with pytest.raises(AssertionError, match="symlinked"):
        source._source_stage_completion(root, "a" * 64, write=False)
