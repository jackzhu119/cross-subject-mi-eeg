"""Synthetic-only checks for the locked Q9-A001 spectral control."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "q9_spatial_psd.py"
SPEC = importlib.util.spec_from_file_location("q9_spatial_psd", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
q9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q9)


def _synthetic_epochs() -> tuple[np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(19)
    t = np.arange(750) / 250.0
    trials, rows = [], []
    for subject in range(1, 10):
        for label in range(1, 5):
            for repeat in range(2):
                values = rng.normal(0, 0.1, (22, 750))
                values[0] += label * np.sin(2 * np.pi * 10 * t)
                values[1] += (5 - label) * np.sin(2 * np.pi * 20 * t)
                trials.append(values.astype(np.float32))
                rows.append(
                    {
                        "sample_id": f"s{subject:02d}_label{label}_rep{repeat}",
                        "subject": subject,
                        "session": "0train" if repeat == 0 else "1test",
                        "run": 1,
                        "trial": len(rows),
                        "label": label,
                        "artifact_flagged": False,
                    }
                )
    return np.stack(trials), pd.DataFrame(rows)


def test_welch_fixed_bins_and_channel_major_order() -> None:
    t = np.arange(750) / 250.0
    data = np.zeros((2, 22, 750), dtype=np.float32)
    data[0, 0] = np.sin(2 * np.pi * 10 * t)
    data[1, 0] = np.sin(2 * np.pi * 20 * t)
    features = q9.welch_psd44(data, batch_size=1)
    assert features.shape == (2, 44)
    assert q9.FEATURE_NAMES[:4] == ("ch01_mu", "ch01_beta", "ch02_mu", "ch02_beta")
    assert features[0, 0] > features[0, 1] + 5
    assert features[1, 1] > features[1, 0] + 5
    assert np.allclose(features[:, 2:], -12.0)


@pytest.mark.parametrize("model", q9.MODELS)
def test_target_values_cannot_change_source_fit(model: str) -> None:
    data, meta = _synthetic_epochs()
    features = q9.welch_psd44(data)
    source = np.flatnonzero(meta.subject.to_numpy() != 9)
    target = np.flatnonzero(meta.subject.to_numpy() == 9)
    args = (
        meta.label.to_numpy(),
        meta.subject.to_numpy(),
        source,
        target,
    )
    _, _, receipt = q9.fit_predict_source_only(
        features, *args, model=model, sample_ids=meta.sample_id.to_numpy()
    )
    corrupted = features.copy()
    corrupted[target] += 1000.0
    _, _, second = q9.fit_predict_source_only(
        corrupted, *args, model=model, sample_ids=meta.sample_id.to_numpy()
    )
    assert receipt == second
    with pytest.raises(ValueError, match="wholly unseen"):
        q9.fit_predict_source_only(
            features,
            meta.label.to_numpy(),
            meta.subject.to_numpy(),
            np.concatenate([source, target[:1]]),
            target[1:],
            model=model,
            sample_ids=meta.sample_id.to_numpy(),
        )


def test_loso_resume_keeps_completed_fold_bytes(tmp_path: Path) -> None:
    data, meta = _synthetic_epochs()
    config = {"synthetic_test": True}
    q9.run_psd_loso(data, meta, tmp_path, config=config)
    first = tmp_path / "folds" / "target_s01" / "predictions.csv"
    original = first.read_bytes()
    q9.run_psd_loso(data, meta, tmp_path, config=config)
    assert first.read_bytes() == original
    status = __import__("json").loads((tmp_path / "status.json").read_text())
    assert status["status"] == "complete"
    assert status["completed_shallow_fits"] == 18
    predictions = pd.read_csv(tmp_path / "predictions.csv")
    assert len(predictions) == len(meta) * 2
    for (subject, model), part in predictions.groupby(["subject", "model"]):
        assert len(part) == 8
        assert set(part.y_true) == {1, 2, 3, 4}
    with pytest.raises(RuntimeError, match="changed configuration"):
        q9.run_psd_loso(data, meta, tmp_path, config={"synthetic_test": False})
