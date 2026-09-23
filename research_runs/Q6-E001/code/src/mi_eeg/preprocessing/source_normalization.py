"""Source-only per-channel scaling for the Q6-E001 EEGNet ablation.

The caller supplies explicit training trial indices.  Statistics are computed
over those trials and their time samples, independently for each EEG channel;
validation and target trials are never used to fit the transform.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch


@dataclass(frozen=True)
class ChannelStandardizer:
    mean_microvolts: np.ndarray
    std_microvolts: np.ndarray
    n_trials: int
    n_time_samples: int
    train_subjects: tuple[int, ...]
    sample_ids_sha256: str

    def receipt(self, *, fold: str, stage: str, inner_fold: int | None) -> dict:
        return {
            "fold": fold,
            "stage": stage,
            "inner_fold": inner_fold,
            "method": "per_channel_source_train_zscore",
            "fit_axes": ["trials", "time"],
            "variance_ddof": 0,
            "statistics_dtype": "float64",
            "application_dtype": "float32",
            "zero_variance_policy": "raise_if_std_below_1e-6_microvolts",
            "n_train_trials": self.n_trials,
            "n_time_samples_per_trial": self.n_time_samples,
            "n_samples_per_channel": self.n_trials * self.n_time_samples,
            "train_subjects": list(self.train_subjects),
            "ordered_train_sample_ids_sha256": self.sample_ids_sha256,
            "channel_mean_microvolts": self.mean_microvolts.tolist(),
            "channel_std_microvolts": self.std_microvolts.tolist(),
            "target_fitted_transform": False,
        }


def _ordered_sample_ids_hash(ids: list[str]) -> str:
    # Length-prefixing makes the serialization unambiguous even if an ID
    # unexpectedly contains a delimiter.
    digest = hashlib.sha256()
    for sample_id in ids:
        encoded = sample_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def fit_source_channel_standardizer(
    signal_microvolts: np.ndarray,
    metadata: pd.DataFrame,
    train_indices: np.ndarray,
    expected_train_subjects: list[int],
    *,
    min_std_microvolts: float = 1e-6,
) -> ChannelStandardizer:
    """Fit 22 channel moments from the specified source-train trials only."""
    signal = np.asarray(signal_microvolts)
    if signal.ndim != 3 or signal.shape[1:] != (22, 750):
        raise ValueError(f"Expected (trials, 22, 750) EEG, got {signal.shape}")
    if len(metadata) != len(signal) or not {"subject", "sample_id"}.issubset(metadata):
        raise ValueError("Metadata must align with signal and contain subject/sample_id")
    indices = np.asarray(train_indices)
    if indices.ndim != 1 or not np.issubdtype(indices.dtype, np.integer) or not len(indices):
        raise ValueError("Training indices must be a nonempty one-dimensional integer array")
    if len(np.unique(indices)) != len(indices) or indices.min() < 0 or indices.max() >= len(signal):
        raise ValueError("Training indices must be unique and in range")
    expected = tuple(sorted(expected_train_subjects))
    if not expected or len(set(expected)) != len(expected):
        raise ValueError("Expected source subjects must be unique and nonempty")
    fit_meta = metadata.iloc[indices]
    observed = tuple(sorted(int(s) for s in fit_meta.subject.unique()))
    if observed != expected:
        raise ValueError(f"Fitted subjects {observed} differ from source-train set {expected}")
    # Require all, and only, trials from those train subjects.  A partial or
    # hand-picked fit population would silently change the protocol.
    required = np.flatnonzero(metadata.subject.isin(expected).to_numpy())
    if not np.array_equal(np.sort(indices), required):
        raise ValueError("Training indices are not the complete source-train population")
    if fit_meta.sample_id.duplicated().any():
        raise ValueError("Duplicate source trial IDs in standardizer fit")
    selected = signal[indices]
    if not np.isfinite(selected).all():
        raise ValueError("Non-finite source training EEG")
    means = selected.mean(axis=(0, 2), dtype=np.float64)
    stds = selected.std(axis=(0, 2), dtype=np.float64, ddof=0)
    if not np.isfinite(means).all() or not np.isfinite(stds).all():
        raise ValueError("Non-finite source-only channel statistics")
    if not np.isfinite(min_std_microvolts) or min_std_microvolts <= 0:
        raise ValueError("Minimum standard deviation must be finite and positive")
    if np.any(stds < min_std_microvolts):
        raise ValueError("A source EEG channel has near-zero variance")
    return ChannelStandardizer(
        mean_microvolts=means,
        std_microvolts=stds,
        n_trials=len(indices),
        n_time_samples=signal.shape[2],
        train_subjects=observed,
        sample_ids_sha256=_ordered_sample_ids_hash(fit_meta.sample_id.astype(str).tolist()),
    )


def apply_channel_standardizer(signal_microvolts: torch.Tensor, fitted: ChannelStandardizer) -> torch.Tensor:
    """Apply fixed source statistics; never estimate moments on input trials."""
    if signal_microvolts.ndim != 3 or tuple(signal_microvolts.shape[1:]) != (22, 750):
        raise ValueError(f"Expected (trials, 22, 750) EEG, got {tuple(signal_microvolts.shape)}")
    center = torch.as_tensor(fitted.mean_microvolts, device=signal_microvolts.device, dtype=signal_microvolts.dtype)
    scale = torch.as_tensor(fitted.std_microvolts, device=signal_microvolts.device, dtype=signal_microvolts.dtype)
    transformed = (signal_microvolts - center[None, :, None]) / scale[None, :, None]
    if not torch.isfinite(transformed).all():
        raise FloatingPointError("Non-finite source-standardized EEG")
    return transformed
