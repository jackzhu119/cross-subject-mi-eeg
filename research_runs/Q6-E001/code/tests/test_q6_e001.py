"""Q6 protocol drift and completed-fold checkpoint safety tests."""

from __future__ import annotations

import json

import pytest

from scripts.run_q6_e001 import (
    CONFIG,
    Q5_CONFIG,
    _complete_fold_dir,
    _expected_fold_files,
    assert_single_factor_protocol,
)


def test_q6_changes_only_declared_normalization() -> None:
    q6 = json.loads(CONFIG.read_text(encoding="utf-8"))
    q5 = json.loads(Q5_CONFIG.read_text(encoding="utf-8"))
    assert_single_factor_protocol(q6, q5)
    q6["training"]["final_seeds"] = [1, 2, 3]
    with pytest.raises(ValueError, match="training differs"):
        assert_single_factor_protocol(q6, q5)


def test_completed_fold_must_have_all_receipts(tmp_path) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    directory = tmp_path / "folds/loso_s1"
    directory.mkdir(parents=True)
    (directory / "status.json").write_text('{"status": "complete"}', encoding="utf-8")
    with pytest.raises(AssertionError, match="missing artifacts"):
        _complete_fold_dir(tmp_path, "loso_s1", config)
    for name in _expected_fold_files(config):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()
    assert _complete_fold_dir(tmp_path, "loso_s1", config) == directory


def test_failed_attempt_is_preserved_on_retry(tmp_path) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    directory = tmp_path / "folds/loso_s1"
    directory.mkdir(parents=True)
    (directory / "status.json").write_text('{"status": "failed"}', encoding="utf-8")
    assert _complete_fold_dir(tmp_path, "loso_s1", config) is None
