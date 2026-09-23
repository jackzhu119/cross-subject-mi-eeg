"""Fit-boundary and multiclass score regressions for the formal baseline."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.run_fourclass_filterbank import classification_metrics, fit_classifier


def test_fourclass_metrics_are_not_binary() -> None:
    truth = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    prediction = np.array([1, 2, 2, 2, 3, 4, 4, 4])
    result = classification_metrics(truth, prediction, [1, 2, 3, 4])
    assert result["accuracy"] == pytest.approx(0.75)
    assert result["balanced_accuracy"] == pytest.approx(0.75)
    assert result["macro_f1"] == pytest.approx(0.7333333333333334)
    assert result["cohen_kappa"] == pytest.approx(2 / 3)


def test_target_rows_cannot_change_source_fitted_selector_or_scaler() -> None:
    rng = np.random.default_rng(919)
    features = rng.normal(size=(80, 12))
    y = np.tile([1, 2, 3, 4], 20)
    train, test = np.arange(64), np.arange(64, 80)
    config = {
        "seed": 919,
        "mi_selection": {"discrete_features": False, "n_neighbors": 3},
        "lda": {"solver": "lsqr", "shrinkage": "auto"},
        "svm": {"kernel": "linear", "C": 1.0},
    }
    model = {"name": "test", "classifier": "lda", "select_k": 4}
    _, receipt_a = fit_classifier(features, y, train, test, model, config)
    changed = features.copy()
    changed[test] += rng.normal(loc=500, scale=30, size=changed[test].shape)
    changed_y = y.copy()
    changed_y[test] = 4
    _, receipt_b = fit_classifier(changed, changed_y, train, test, model, config)
    assert receipt_a == receipt_b
    with pytest.raises(ValueError, match="overlap"):
        fit_classifier(features, y, np.arange(65), test, model, config)
