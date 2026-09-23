"""Synthetic evidence that Q6 scaling is fitted only on source-train EEG."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from mi_eeg.preprocessing.source_normalization import (
    apply_channel_standardizer,
    fit_source_channel_standardizer,
)


@pytest.fixture
def synthetic_eeg() -> tuple[np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(901)
    metadata = pd.DataFrame(
        [{"subject": subject, "sample_id": f"s{subject}_t{trial}"}
         for subject in range(1, 10) for trial in range(2)]
    )
    eeg = rng.normal(size=(18, 22, 750)).astype(np.float32)
    eeg *= np.arange(1, 23, dtype=np.float32)[None, :, None]
    eeg += metadata.subject.to_numpy(dtype=np.float32)[:, None, None]
    return eeg, metadata


def _indices(meta: pd.DataFrame, subjects: list[int]) -> np.ndarray:
    return np.flatnonzero(meta.subject.isin(subjects).to_numpy())


def test_inner_fit_ignores_validation_and_target_perturbations(synthetic_eeg) -> None:
    signal, meta = synthetic_eeg
    train_subjects = [2, 3, 4, 5, 6, 7]
    indices = _indices(meta, train_subjects)
    original = fit_source_channel_standardizer(signal, meta, indices, train_subjects)
    changed = signal.copy()
    changed[_indices(meta, [1, 8, 9])] += 100_000.0
    again = fit_source_channel_standardizer(changed, meta, indices, train_subjects)
    np.testing.assert_array_equal(original.mean_microvolts, again.mean_microvolts)
    np.testing.assert_array_equal(original.std_microvolts, again.std_microvolts)
    assert original.n_trials == 12
    assert original.train_subjects == tuple(train_subjects)
    assert original.sample_ids_sha256 == again.sample_ids_sha256


def test_final_fit_ignores_target_and_normalizes_source_channels(synthetic_eeg) -> None:
    signal, meta = synthetic_eeg
    sources = list(range(1, 9))
    indices = _indices(meta, sources)
    fitted = fit_source_channel_standardizer(signal, meta, indices, sources)
    changed = signal.copy()
    changed[_indices(meta, [9])] *= -999.0
    recomputed = fit_source_channel_standardizer(changed, meta, indices, sources)
    np.testing.assert_array_equal(fitted.mean_microvolts, recomputed.mean_microvolts)
    np.testing.assert_array_equal(fitted.std_microvolts, recomputed.std_microvolts)
    transformed = apply_channel_standardizer(torch.from_numpy(signal), fitted).numpy()
    np.testing.assert_allclose(transformed[indices].mean(axis=(0, 2)), 0, atol=2e-6)
    np.testing.assert_allclose(transformed[indices].std(axis=(0, 2)), 1, atol=2e-6)
    # Applying a source-fitted transform need not zero-center target trials.
    assert np.max(np.abs(transformed[_indices(meta, [9])].mean(axis=(0, 2)))) > 0.01


def test_partial_or_wrong_subject_fit_is_rejected(synthetic_eeg) -> None:
    signal, meta = synthetic_eeg
    with pytest.raises(ValueError, match="complete source-train population"):
        fit_source_channel_standardizer(signal, meta, _indices(meta, [1, 2])[:-1], [1, 2])
    with pytest.raises(ValueError, match="differ from source-train"):
        fit_source_channel_standardizer(signal, meta, _indices(meta, [1, 2]), [2, 3])
    with pytest.raises(ValueError, match="unique and in range"):
        fit_source_channel_standardizer(signal, meta, np.array([0, 0]), [1])


def test_zero_variance_channel_raises(synthetic_eeg) -> None:
    signal, meta = synthetic_eeg
    signal = signal.copy()
    signal[:, 3, :] = 0
    with pytest.raises(ValueError, match="near-zero variance"):
        fit_source_channel_standardizer(signal, meta, _indices(meta, [1, 2]), [1, 2])
