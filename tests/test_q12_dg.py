"""CPU-only synthetic Q12 safety checks; no EEG result or GPU claim."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from scripts import q12_batch, q12_dg, validate_q12


def _toy_source_data() -> tuple[torch.Tensor, pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(711)
    x = torch.from_numpy(rng.normal(size=(12, 22, 10)).astype("float32"))
    meta = pd.DataFrame({"subject": [1] * 4 + [2] * 4 + [3] * 4,
                         "sample_id": [f"trial-{i}" for i in range(12)]})
    return x, meta, np.arange(8, dtype=np.int64)


def test_q12_matrix_and_batch_order(tmp_path: Path) -> None:
    conditions = q12_dg.matrix_conditions()
    assert len(conditions) == 6
    assert sum(row["inner_fits"] + row["final_fits"] for row in conditions.values()) == 378
    manifest = q12_batch.build_manifest(tmp_path / "data", tmp_path / "results", "python")
    assert manifest["selected_fit_counts"] == {
        "deep_inner": 216, "deep_final": 162, "shallow_source": 0}
    assert [job["phase"] for job in manifest["jobs"]] == ["selection"] * 6 + ["final"] * 6
    assert {job["completion_value"] for job in manifest["jobs"][:6]} == {
        "frozen_before_Q12_target_inference"}


def test_q12_publish_requires_repository_results(tmp_path: Path) -> None:
    q12_batch.validate_publish_destination(q12_batch.ROOT / "results")
    with pytest.raises(ValueError, match="repository's results"):
        q12_batch.validate_publish_destination(tmp_path / "results")


def test_source_whitener_excludes_held_out_person() -> None:
    x, meta, train = _toy_source_data()
    receipt = q12_dg.fit_source_whitener(x, meta, train, [1, 2])
    observed = np.asarray(receipt["spatial_weight"])
    x_changed = x.clone()
    x_changed[8:] *= 10000
    changed = q12_dg.fit_source_whitener(x_changed, meta, train, [1, 2])
    assert np.array_equal(observed, np.asarray(changed["spatial_weight"]))
    assert receipt["ordered_train_sample_ids_sha256"] == changed["ordered_train_sample_ids_sha256"]
    assert receipt["target_fitted_transform"] is False
    assert torch.isfinite(q12_dg.apply_source_whitener(x, receipt)).all()
    with pytest.raises(ValueError, match="all and only"):
        q12_dg.fit_source_whitener(x, meta, np.arange(12), [1, 2])
    with pytest.raises(ValueError, match="all and only"):
        q12_dg.fit_source_whitener(x, meta, train[:-1], [1, 2])


def test_validator_rechecks_whitening_source_inventory() -> None:
    x, meta, train = _toy_source_data()
    receipt = q12_dg.fit_source_whitener(x, meta, train, [1, 2])
    matrix = validate_q12.check_whitener(receipt, meta, subjects=[1, 2])
    assert matrix.shape == (22, 22)
    tampered = copy.deepcopy(receipt)
    tampered["ordered_train_sample_ids_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="fit boundaries"):
        validate_q12.check_whitener(tampered, meta, subjects=[1, 2])


def test_training_augmentation_shapes_and_locked_ranges() -> None:
    batch = torch.ones(1000, 22, 4)
    torch.manual_seed(31)
    gain = q12_dg.training_augmentation(
        batch, "gain_perturb", {"gain_low": 0.8, "gain_high": 1.2})
    assert gain.shape == batch.shape
    assert float(gain.min()) >= 0.8 and float(gain.max()) <= 1.2
    torch.manual_seed(31)
    dropout = q12_dg.training_augmentation(
        batch, "channel_dropout", {"channel_dropout_probability": 0.10})
    assert dropout.unique().numel() == 2
    assert float(dropout.min()) == 0.0
    assert float(dropout.max()) == pytest.approx(1.0 / 0.9)
    with pytest.raises(AssertionError, match="Unfrozen"):
        q12_dg.training_augmentation(batch, "channel_dropout",
                                     {"channel_dropout_probability": 0.5})
    with pytest.raises(ValueError, match="Not a Q12"):
        q12_dg.training_augmentation(batch, "none", {})


def test_group_dro_and_balanced_erm_have_same_sampling_budget() -> None:
    x = torch.zeros(20, 2, 4)
    y = torch.as_tensor([0] * 10 + [1] * 10, dtype=torch.long)
    meta = pd.DataFrame({"subject": [1] * 10 + [2] * 10,
                         "sample_id": [f"g-{i}" for i in range(20)]})
    indices = np.arange(20, dtype=np.int64)
    base = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(8, 2))
    with torch.no_grad():
        base[-1].weight.zero_()
        base[-1].bias[:] = torch.tensor([2.0, -2.0])
    initial = torch.full((2,), -np.log(2), dtype=torch.float64)
    results = []
    for method in ("balanced_erm", "group_dro"):
        torch.manual_seed(88)
        model = copy.deepcopy(base)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.0)
        ce, updated = q12_dg._balanced_group_epoch(
            model, optimizer, x, y, meta, indices, [1, 2], 8, method, initial.clone())
        results.append((ce, updated.exp().numpy()))
    assert results[0][0] == pytest.approx(results[1][0])
    assert results[0][1] == pytest.approx([0.5, 0.5])
    assert results[1][1][1] > results[1][1][0]
    assert sum(results[1][1]) == pytest.approx(1.0)


def test_q12_settings_lock_resumption(tmp_path: Path) -> None:
    output = tmp_path / "results" / "Q12-E001" / "SOURCE_GROUP_DRO"
    output.mkdir(parents=True)
    config = q12_dg.settings("SOURCE_GROUP_DRO", tmp_path / "data", output)
    assert config["method"] == "group_dro"
    assert config["target_fitted_transform"] is False
    assert q12_dg.settings("SOURCE_GROUP_DRO", tmp_path / "data", output) == config
    path = output / "run_config.json"
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["method_parameters"]["group_step_size"] = 0.5
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(AssertionError, match="mixed-protocol"):
        q12_dg.settings("SOURCE_GROUP_DRO", tmp_path / "data", output)
