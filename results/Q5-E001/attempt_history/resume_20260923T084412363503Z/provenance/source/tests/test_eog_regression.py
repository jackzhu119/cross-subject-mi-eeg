"""Synthetic checks for source-fitted EOG regression."""

from __future__ import annotations

import numpy as np
import pytest

from mi_eeg.preprocessing.eog_regression import (
    apply_eog_coefficients,
    fit_eog_coefficients,
    mean_abs_cross_correlation,
)


def test_regression_removes_known_linear_eog_mixture() -> None:
    rng = np.random.default_rng(4)
    eog = rng.normal(scale=1e-5, size=(20, 3, 100)).astype(np.float32)
    neural = rng.normal(scale=1e-6, size=(20, 22, 100)).astype(np.float32)
    true_coefficients = rng.normal(scale=0.2, size=(3, 22))
    eeg = neural + np.einsum("nkt,kc->nct", eog, true_coefficients).astype(np.float32)
    learned, qc = fit_eog_coefficients(eeg, eog)
    corrected = apply_eog_coefficients(eeg, eog, learned)
    assert learned.shape == (3, 22)
    assert qc["design_condition_number"] > 0
    assert mean_abs_cross_correlation(corrected, eog) < 0.1 * mean_abs_cross_correlation(eeg, eog)
    assert np.sqrt(np.mean((corrected - neural) ** 2)) < 0.2 * np.sqrt(np.mean((eeg - neural) ** 2))


def test_regression_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="22 EEG"):
        fit_eog_coefficients(np.zeros((2, 21, 100)), np.zeros((2, 3, 100)))
