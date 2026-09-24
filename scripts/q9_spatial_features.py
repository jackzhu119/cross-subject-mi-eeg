"""Source-fitted Q9-E003 spatial projections for fixed mu/beta EEG epochs.

This module never estimates a parameter from evaluation epochs. Callers must
provide complete subject IDs and disjoint train/evaluation indices; the
partition helper enforces a subject-level holdout for inner and outer LOSO.
Input EEG is in volts, as returned by ``load_configured_epochs``. Outputs are
source-standardized, dimensionless float32 tensors shaped (trials, 16, time).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import numpy as np

Method = Literal["csp8", "pca8"]


def _validate_pair(mu: np.ndarray, beta: np.ndarray, *, n_components: int) -> None:
    if mu.ndim != 3 or mu.shape != beta.shape:
        raise ValueError("Mu and beta must have matching (trials, channels, time) shapes")
    if not (0 < n_components <= mu.shape[1]):
        raise ValueError("Invalid number of projected channels")
    if mu.shape[0] < 1 or mu.shape[2] < 2:
        raise ValueError("Insufficient trials or samples")
    if not np.isfinite(mu).all() or not np.isfinite(beta).all():
        raise ValueError("Nonfinite input EEG")


def _canonical_signs(filters: np.ndarray) -> np.ndarray:
    """Resolve eigenvector/CSP sign ambiguity by each row's largest coefficient."""
    pivot = np.argmax(np.abs(filters), axis=1)
    signs = np.sign(filters[np.arange(filters.shape[0]), pivot])
    signs[signs == 0] = 1.0
    return filters * signs[:, None]


def _fit_pca(data: np.ndarray, n_components: int) -> tuple[np.ndarray, np.ndarray]:
    """Channel-covariance PCA, with a global source-only channel mean."""
    n_trials, n_chans, n_times = data.shape
    # A sum-of-cross-products calculation bounds peak memory at one trial
    # block rather than materializing every source sample as a giant matrix.
    channel_sum = np.zeros(n_chans, dtype=np.float64)
    cross = np.zeros((n_chans, n_chans), dtype=np.float64)
    for start in range(0, n_trials, 32):
        block = np.asarray(data[start : start + 32], dtype=np.float64)
        matrix = block.transpose(1, 0, 2).reshape(n_chans, -1)
        channel_sum += matrix.sum(axis=1)
        cross += matrix @ matrix.T
    n_samples = n_trials * n_times
    mean = channel_sum / n_samples
    covariance = (cross - n_samples * np.outer(mean, mean)) / (n_samples - 1)
    covariance = (covariance + covariance.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(-eigenvalues, kind="stable")[:n_components]
    filters = _canonical_signs(eigenvectors[:, order].T.copy())
    return filters, mean


def _fit_csp(
    data: np.ndarray, labels: np.ndarray, n_components: int
) -> tuple[np.ndarray, np.ndarray]:
    """Q4 multiclass MNE CSP settings, retaining time-series spatial output."""
    from mne.decoding import CSP

    csp = CSP(
        n_components=n_components,
        reg="oas",
        log=None,
        cov_est="concat",
        transform_into="csp_space",
        norm_trace=False,
        rank="full",
        component_order="mutual_info",
    )
    csp.fit(np.asarray(data, dtype=np.float64), labels)
    filters = _canonical_signs(np.asarray(csp.filters_[:n_components], dtype=np.float64))
    return filters, np.zeros(data.shape[1], dtype=np.float64)


def _project(data: np.ndarray, filters: np.ndarray, channel_mean: np.ndarray) -> np.ndarray:
    centered = np.asarray(data, dtype=np.float64) - channel_mean[None, :, None]
    return np.einsum("kc,nct->nkt", filters, centered, optimize=True)


@dataclass(frozen=True)
class FittedSpatialPair:
    """Immutable projection and source-only post-projection standardization."""

    method: Method
    fit_subjects: tuple[int, ...]
    fit_sample_ids_sha256: str | None
    n_source_trials: int
    filters_mu: np.ndarray
    filters_beta: np.ndarray
    channel_mean_mu: np.ndarray
    channel_mean_beta: np.ndarray
    projected_mean_mu: np.ndarray
    projected_mean_beta: np.ndarray
    projected_scale_mu: np.ndarray
    projected_scale_beta: np.ndarray

    def transform(self, mu: np.ndarray, beta: np.ndarray) -> np.ndarray:
        _validate_pair(mu, beta, n_components=self.filters_mu.shape[0])
        if mu.shape[1] != self.filters_mu.shape[1]:
            raise ValueError("Input channel count differs from fitted spatial filters")
        projected = []
        for data, filters, channel_mean, mean, scale in (
            (
                mu,
                self.filters_mu,
                self.channel_mean_mu,
                self.projected_mean_mu,
                self.projected_scale_mu,
            ),
            (
                beta,
                self.filters_beta,
                self.channel_mean_beta,
                self.projected_mean_beta,
                self.projected_scale_beta,
            ),
        ):
            values = _project(data, filters, channel_mean)
            values = (values - mean[None, :, None]) / scale[None, :, None]
            projected.append(values.astype(np.float32))
        result = np.concatenate(projected, axis=1)
        if not np.isfinite(result).all():
            raise AssertionError("Nonfinite spatial features")
        return result

    def receipt(self) -> dict:
        """Auditable transform parameters and a canonical parameter hash."""
        arrays = {
            key: getattr(self, key).astype("<f8", copy=False)
            for key in (
                "filters_mu",
                "filters_beta",
                "channel_mean_mu",
                "channel_mean_beta",
                "projected_mean_mu",
                "projected_mean_beta",
                "projected_scale_mu",
                "projected_scale_beta",
            )
        }
        digest = hashlib.sha256()
        for key in sorted(arrays):
            digest.update(key.encode("utf-8") + b"\0")
            digest.update(np.ascontiguousarray(arrays[key]).tobytes())
        return {
            "method": self.method,
            "fit_subjects": list(self.fit_subjects),
            "fit_sample_ids_sha256": self.fit_sample_ids_sha256,
            "n_source_trials": self.n_source_trials,
            "n_components_per_band": int(self.filters_mu.shape[0]),
            "projected_channel_order": [
                f"mu_{i + 1:02d}" for i in range(self.filters_mu.shape[0])
            ]
            + [f"beta_{i + 1:02d}" for i in range(self.filters_beta.shape[0])],
            "parameter_sha256": digest.hexdigest(),
            "parameters": {key: value.tolist() for key, value in arrays.items()},
        }


def fit_projector_pair(
    mu_source: np.ndarray,
    beta_source: np.ndarray,
    y_source: np.ndarray,
    source_subjects: np.ndarray,
    *,
    method: Method,
    n_components: int = 8,
    source_sample_ids: np.ndarray | None = None,
) -> FittedSpatialPair:
    """Fit on arrays *already restricted* to source-training trials only.

    Prefer ``fit_source_only_pair`` when the full trial arrays are available;
    it checks disjoint subject identities before slicing the fit inputs.
    """
    _validate_pair(mu_source, beta_source, n_components=n_components)
    if len(mu_source) < 2:
        raise ValueError("Spatial fit needs at least two source trials")
    y_source = np.asarray(y_source)
    subjects = np.asarray(source_subjects)
    if len(y_source) != len(mu_source) or len(subjects) != len(mu_source):
        raise ValueError("Source labels/subjects and EEG are misaligned")
    if method not in {"csp8", "pca8"} or n_components != 8:
        raise ValueError("Q9-E003 permits only the predeclared CSP8 or PCA8 methods")
    if len(np.unique(subjects)) < 2:
        raise ValueError("Spatial fit needs at least two source subjects")
    if method == "csp8" and len(np.unique(y_source)) != 4:
        raise ValueError("Four-class CSP needs all four labels in the source partition")
    if source_sample_ids is not None:
        ids = np.asarray(source_sample_ids, dtype=str)
        if len(ids) != len(mu_source) or len(np.unique(ids)) != len(ids):
            raise ValueError("Source sample IDs must be unique and aligned")
        id_sha = hashlib.sha256("\n".join(ids.tolist()).encode("utf-8")).hexdigest()
    else:
        id_sha = None
    fit = _fit_csp if method == "csp8" else lambda x, y, n: _fit_pca(x, n)
    filters_mu, mean_mu = fit(mu_source, y_source, n_components)
    filters_beta, mean_beta = fit(beta_source, y_source, n_components)
    projected_mu = _project(mu_source, filters_mu, mean_mu)
    projected_beta = _project(beta_source, filters_beta, mean_beta)
    mu_mean = projected_mu.mean(axis=(0, 2))
    beta_mean = projected_beta.mean(axis=(0, 2))
    mu_scale = projected_mu.std(axis=(0, 2))
    beta_scale = projected_beta.std(axis=(0, 2))
    if np.any(mu_scale <= 0) or np.any(beta_scale <= 0):
        raise ValueError("A source-fitted projected channel has zero variance")
    return FittedSpatialPair(
        method=method,
        fit_subjects=tuple(sorted(int(value) for value in np.unique(subjects))),
        fit_sample_ids_sha256=id_sha,
        n_source_trials=len(mu_source),
        filters_mu=filters_mu,
        filters_beta=filters_beta,
        channel_mean_mu=mean_mu,
        channel_mean_beta=mean_beta,
        projected_mean_mu=mu_mean,
        projected_mean_beta=beta_mean,
        projected_scale_mu=mu_scale,
        projected_scale_beta=beta_scale,
    )


def fit_source_only_pair(
    mu_all: np.ndarray,
    beta_all: np.ndarray,
    y_all: np.ndarray,
    subject_all: np.ndarray,
    train_idx: np.ndarray,
    eval_idx: np.ndarray,
    *,
    method: Method,
    sample_ids: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, FittedSpatialPair]:
    """Partition-checking entry point for every inner and final Q9-E003 fit."""
    train_idx = np.asarray(train_idx, dtype=np.int64)
    eval_idx = np.asarray(eval_idx, dtype=np.int64)
    subjects = np.asarray(subject_all)
    y_all = np.asarray(y_all)
    _validate_pair(mu_all, beta_all, n_components=8)
    if len(subjects) != len(mu_all) or len(y_all) != len(mu_all):
        raise ValueError("Full-array labels/subjects and EEG are misaligned")
    if not len(train_idx) or not len(eval_idx):
        raise ValueError("Empty source-training or evaluation partition")
    if (
        np.any(train_idx < 0)
        or np.any(eval_idx < 0)
        or np.any(train_idx >= len(mu_all))
        or np.any(eval_idx >= len(mu_all))
        or len(np.unique(train_idx)) != len(train_idx)
        or len(np.unique(eval_idx)) != len(eval_idx)
        or np.intersect1d(train_idx, eval_idx).size
    ):
        raise ValueError("Invalid or overlapping train/evaluation trial indices")
    train_subjects = set(subjects[train_idx].tolist())
    eval_subjects = set(subjects[eval_idx].tolist())
    if train_subjects & eval_subjects:
        raise ValueError("A held-out evaluation subject appears in the spatial fit")
    ids = None if sample_ids is None else np.asarray(sample_ids, dtype=str)
    if ids is not None and len(ids) != len(mu_all):
        raise ValueError("Full-array sample IDs are misaligned")
    projector = fit_projector_pair(
        mu_all[train_idx],
        beta_all[train_idx],
        y_all[train_idx],
        subjects[train_idx],
        method=method,
        source_sample_ids=None if ids is None else ids[train_idx],
    )
    return (
        projector.transform(mu_all[train_idx], beta_all[train_idx]),
        projector.transform(mu_all[eval_idx], beta_all[eval_idx]),
        projector,
    )
