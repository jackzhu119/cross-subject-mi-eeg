"""Pooled source-subject EOG regression with a frozen target transform."""

from __future__ import annotations

import numpy as np


def fit_eog_coefficients(
    eeg: np.ndarray, eog: np.ndarray, ridge_fraction: float = 1e-4
) -> tuple[np.ndarray, dict[str, float]]:
    """Fit a 3-to-22 linear map on source trials only.

    Both arrays must have been filtered identically and have shape
    (trials, channels, samples). The design is centered within each trial.
    """

    if eeg.ndim != 3 or eog.ndim != 3:
        raise ValueError("EEG and EOG must be three-dimensional")
    if eeg.shape[0] != eog.shape[0] or eeg.shape[2] != eog.shape[2]:
        raise ValueError("EEG and EOG trial/time dimensions differ")
    if eeg.shape[1] != 22 or eog.shape[1] != 3:
        raise ValueError("Expected 22 EEG and 3 EOG channels")
    if ridge_fraction < 0:
        raise ValueError("ridge_fraction must be nonnegative")
    centered_eeg = eeg.astype(np.float64) - eeg.mean(axis=2, keepdims=True)
    centered_eog = eog.astype(np.float64) - eog.mean(axis=2, keepdims=True)
    ee = np.einsum("nkt,njt->kj", centered_eog, centered_eog, optimize=True)
    ey = np.einsum("nkt,nct->kc", centered_eog, centered_eeg, optimize=True)
    penalty = ridge_fraction * float(np.trace(ee)) / eog.shape[1]
    coefficients = np.linalg.solve(ee + penalty * np.eye(3), ey)
    if not np.isfinite(coefficients).all():
        raise AssertionError("EOG regression produced nonfinite coefficients")
    info = {
        "ridge_fraction": float(ridge_fraction),
        "ridge_penalty": float(penalty),
        "design_condition_number": float(np.linalg.cond(ee + penalty * np.eye(3))),
        "coefficient_rms": float(np.sqrt(np.mean(coefficients**2))),
        "coefficient_max_abs": float(np.max(np.abs(coefficients))),
    }
    return coefficients, info


def apply_eog_coefficients(
    eeg: np.ndarray, eog: np.ndarray, coefficients: np.ndarray
) -> np.ndarray:
    """Subtract the EOG-predicted component without refitting on target data."""

    if coefficients.shape != (3, 22):
        raise ValueError("Expected a frozen 3-by-22 coefficient matrix")
    if eeg.shape[0] != eog.shape[0] or eeg.shape[2] != eog.shape[2]:
        raise ValueError("EEG and EOG trial/time dimensions differ")
    centered_eog = eog - eog.mean(axis=2, keepdims=True)
    predicted = np.einsum("nkt,kc->nct", centered_eog, coefficients, optimize=True)
    corrected = eeg - predicted
    if not np.isfinite(corrected).all():
        raise AssertionError("Corrected EEG contains nonfinite samples")
    return corrected.astype(np.float32)


def mean_abs_cross_correlation(eeg: np.ndarray, eog: np.ndarray) -> float:
    """Descriptive 22-by-3 correlation of pooled centered samples."""

    centered_eeg = eeg.astype(np.float64) - eeg.mean(axis=2, keepdims=True)
    centered_eog = eog.astype(np.float64) - eog.mean(axis=2, keepdims=True)
    xy = np.einsum("nct,nkt->ck", centered_eeg, centered_eog, optimize=True)
    xx = np.einsum("nct,nct->c", centered_eeg, centered_eeg, optimize=True)
    yy = np.einsum("nkt,nkt->k", centered_eog, centered_eog, optimize=True)
    denominator = np.sqrt(xx[:, None] * yy[None, :])
    correlation = xy / np.maximum(denominator, np.finfo(float).tiny)
    return float(np.mean(np.abs(correlation)))
