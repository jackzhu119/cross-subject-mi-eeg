"""Synthetic-only source-fit and shape checks for Q9-E003 projections."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "q9_spatial_features.py"
SPEC = importlib.util.spec_from_file_location("q9_spatial_features", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
q9 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = q9
SPEC.loader.exec_module(q9)


def _synthetic_pair() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(233)
    t = np.arange(250) / 250.0
    mu, beta, labels, subjects, ids = [], [], [], [], []
    for subject in (1, 2, 3):
        for label in (1, 2, 3, 4):
            for repeat in range(4):
                one = rng.normal(0, 1e-6, (22, 250))
                two = rng.normal(0, 1e-6, (22, 250))
                one[(label - 1) * 2] += 3e-6 * np.sin(2 * np.pi * 10 * t)
                two[(label - 1) * 2 + 1] += 3e-6 * np.sin(2 * np.pi * 20 * t)
                mu.append(one.astype(np.float32))
                beta.append(two.astype(np.float32))
                labels.append(label)
                subjects.append(subject)
                ids.append(f"s{subject}_class{label}_{repeat}")
    return np.stack(mu), np.stack(beta), np.array(labels), np.array(subjects), np.array(ids)


@pytest.mark.parametrize("method", ("pca8", "csp8"))
def test_source_only_spatial_fit_and_receipt(method: str) -> None:
    mu, beta, y, subjects, ids = _synthetic_pair()
    train = np.flatnonzero(subjects != 3)
    test = np.flatnonzero(subjects == 3)
    train_values, target_values, model = q9.fit_source_only_pair(
        mu, beta, y, subjects, train, test, method=method, sample_ids=ids
    )
    assert train_values.shape == (len(train), 16, 250)
    assert target_values.shape == (len(test), 16, 250)
    assert np.isfinite(train_values).all() and np.isfinite(target_values).all()
    assert model.fit_subjects == (1, 2)
    receipt = model.receipt()
    assert receipt["n_source_trials"] == len(train)
    assert len(receipt["projected_channel_order"]) == 16
    assert len(receipt["parameter_sha256"]) == 64
    altered_mu, altered_beta = mu.copy(), beta.copy()
    altered_mu[test] += 0.001
    altered_beta[test] -= 0.001
    _, _, refit = q9.fit_source_only_pair(
        altered_mu, altered_beta, y, subjects, train, test, method=method, sample_ids=ids
    )
    assert refit.receipt() == receipt
    with pytest.raises(ValueError, match="held-out evaluation subject"):
        q9.fit_source_only_pair(
            mu,
            beta,
            y,
            subjects,
            np.concatenate([train, test[:1]]),
            test[1:],
            method=method,
            sample_ids=ids,
        )
