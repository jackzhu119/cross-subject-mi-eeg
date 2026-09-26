"""CPU-only Q13 protocol/unit tests; no training or cloud access."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from mi_eeg.models.eegnet_training import predict_probabilities
from scripts import q9_neural, q13_batch, q13_neural
from scripts.validate_q13 import (
    _replay_checkpoint,
    condition_specs,
    raw_ce_from_original_curves,
    validate_prediction,
)

ROOT = Path(__file__).resolve().parents[1]


def test_q13_matrix_counts_and_no_target_fitting() -> None:
    matrix = json.loads((ROOT / "research_runs/Q13-PREP-20260926/MATRIX.json").read_text(
        encoding="utf-8"))
    assert matrix["total_new_deep_fits"] == 837
    assert matrix["total_new_inner_fits"] == 0
    assert matrix["target_fits"] == 0
    assert matrix["common_training"]["target_data_for_fitting_selection_normalization"] is False
    jobs = q13_batch.plan()
    assert len(jobs) == 13
    assert sum(job["expected_fits"] for job in jobs) == 837
    assert [job["experiment_id"] for job in jobs] == (
        ["Q13-E001"] * 3 + ["Q13-E004"] * 6 + ["Q13-E005"] * 4)


def test_q13_publish_requires_repository_results(tmp_path: Path) -> None:
    q13_batch.validate_publish_destination(ROOT / "results")
    with pytest.raises(ValueError, match="repository's results"):
        q13_batch.validate_publish_destination(tmp_path / "results")


@pytest.mark.parametrize("target", range(1, 10))
@pytest.mark.parametrize("k", (2, 4, 6))
def test_source_windows_balanced_and_independently_reconstructed(target: int, k: int) -> None:
    windows = q13_neural.source_windows(target, k)
    assert len(windows) == 4
    assert [f"k{k}_start{start}" for start, _ in windows] == [
        subset for subset, _, _ in condition_specs(f"Q8_SRC{k}", target)]
    assert all(len(source) == k and target not in source and len(set(source)) == k
               for _, source in windows)
    others = [s for s in range(1, 10) if s != target]
    assert {s: sum(s in subset for _, subset in windows) for s in others} == {
        s: k // 2 for s in others}


def test_fit_indices_and_session_manifest_exclude_target() -> None:
    meta = pd.DataFrame([
        {"subject": subject, "session": session, "sample_id": f"{subject}_{session}_{trial}"}
        for subject in range(1, 10) for session in ("0train", "1test")
        for trial in range(288)
    ])
    subset = q13_neural.source_windows(5, 2)[0][1]
    train, test = q13_neural.fit_indices(meta, 5, subset, None)
    assert len(train) == 1152 and len(test) == 576
    assert set(meta.iloc[train].subject) == set(subset)
    assert set(meta.iloc[test].subject) == {5}
    session_train, session_test = q13_neural.fit_indices(
        meta, 5, tuple(s for s in range(1, 10) if s != 5), "0train")
    assert len(session_train) == 2304 and len(session_test) == 576
    assert set(meta.iloc[session_train].session) == {"0train"}
    manifest = q13_neural.fit_manifest(meta, 5, subset, None, 20260924, train, 20)
    assert manifest.n_used_for_fit.sum() == 1152
    assert (manifest[manifest.subject == 5].role == "target_test").all()
    assert (manifest[manifest.role == "source_excluded"].n_used_for_fit == 0).all()


def test_raw_ce_rule_has_earliest_tie_and_rejects_nonfinite() -> None:
    curves = [pd.DataFrame({"epoch": np.arange(1, 41),
                            "val_ce": np.ones(40)}) for _ in range(4)]
    assert q13_neural.raw_ce_epoch(curves) == 1
    curves[0].loc[0, "val_ce"] = np.nan
    with pytest.raises(AssertionError, match="nonfinite"):
        q13_neural.raw_ce_epoch(curves)


def test_original_q9_inner_curves_and_q5_reuse_gates() -> None:
    q13_neural._check_q5_reuse()
    chosen, hashes = q13_neural.q9_source_only_epochs()
    assert len(chosen) == 9 and len(hashes) == 36
    assert all(chosen[str(s)] == raw_ce_from_original_curves(s) for s in range(1, 10))


def _prediction_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = np.repeat(np.arange(1, 5), 144)
    reference = pd.DataFrame({
        "sample_id": [f"target_trial_{n}" for n in range(576)],
        "subject": 5, "session": ["0train"] * 288 + ["1test"] * 288,
        "run": np.repeat(np.arange(12), 48), "trial": np.tile(np.arange(1, 49), 12),
        "label": labels, "event_sample": np.arange(576) * 100,
        "artifact_flagged": [False] * 576,
    })
    frame = reference.copy()
    frame["condition"] = "Q8_SRC2"
    frame["subset_id"] = "k2_start0"
    frame["train_subjects"] = "1|2"
    frame["source_session"] = "both"
    frame["seed"] = 20260924
    frame["selected_epochs"] = 20
    frame["y_true"] = labels
    frame["y_pred"] = labels
    for cls in range(1, 5):
        frame[f"p_class_{cls}"] = (labels == cls).astype(float)
    return frame, reference


def test_independent_q13_prediction_validation() -> None:
    frame, reference = _prediction_fixture()
    args = {"target": 5, "seed": 20260924, "condition": "Q8_SRC2",
            "subset_id": "k2_start0", "source": (1, 2),
            "source_session": None, "selected_epochs": 20}
    audited = validate_prediction(frame, reference, **args)
    assert audited["balanced_accuracy"] == 1.0
    assert audited["zero_recall_classes"] == 0
    frame.loc[0, "p_class_1"] = 0.8
    with pytest.raises(AssertionError, match="probabilities"):
        validate_prediction(frame, reference, **args)


def test_q13_checkpoint_replay_detects_changed_probability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch.manual_seed(17)
    device = torch.device("cpu")
    signal = torch.randn(576, 1, 4)
    reference = pd.DataFrame({
        "subject": [5] * 576, "sample_id": [f"t{i}" for i in range(576)]
    })
    model = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(4, 4))
    monkeypatch.setattr(q9_neural, "_build_model", lambda config, device: (
        torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(4, 4)).to(device)
    ))
    torch.save({"target_subject": 5, "seed": 20260924,
                "train_subjects": [1, 2], "selected_epochs": 20,
                "model_state": model.state_dict()}, tmp_path / "checkpoint.pt")
    probabilities = predict_probabilities(model, signal, np.arange(576), 64)
    frame = reference.copy()
    frame["y_pred"] = probabilities.argmax(axis=1) + 1
    for class_index in range(4):
        frame[f"p_class_{class_index + 1}"] = probabilities[:, class_index]
    kwargs = {"target": 5, "seed": 20260924, "source": (1, 2),
              "selected": 20, "device": device}
    _replay_checkpoint(tmp_path, {"training": {"batch_size": 64}}, signal,
                       reference, frame, **kwargs)
    changed = frame.copy()
    changed.loc[0, "p_class_1"] += 0.01
    with pytest.raises(AssertionError, match="checkpoint replay"):
        _replay_checkpoint(tmp_path, {"training": {"batch_size": 64}}, signal,
                           reference, changed, **kwargs)
