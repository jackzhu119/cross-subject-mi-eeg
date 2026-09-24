"""Fast contract checks; no external data download or GPU is needed."""

from __future__ import annotations

import json
from pathlib import Path

import mne
import numpy as np
import pandas as pd
import pytest
from scipy.signal import resample_poly

from scripts import q14_external, q14_source, q14_validate

CONFIG = json.loads(q14_source.CONFIG.read_text(encoding="utf-8"))


def test_declared_channels_match_frozen_bnci_and_official_montage() -> None:
    expected = json.loads(pd.read_csv(q14_source.Q8_AUDIT).iloc[0]["eeg_channel_names"])
    assert CONFIG["channels"] == expected
    assert len(expected) == len(set(expected)) == 22
    # PhysioNet's official montage PDF (linked in protocol) independently
    # enumerates these names; runtime EDF headers are checked separately.


def test_source_partitions_are_disjoint_and_fit_arithmetic() -> None:
    e001 = list(q14_source.partitions("e001", CONFIG))
    assert len(e001) == 9
    assert {target[0] for _, _, _, target in e001} == set(range(1, 10))
    for label, source, groups, target in e001:
        assert len(source) == 8 and len(groups) == 4
        assert sorted(subject for group in groups for subject in group) == source
        assert not (set(source) & set(target))
        for group in groups:
            assert len(group) == 2 and len(set(source) - set(group)) == 6
    e002 = list(q14_source.partitions("e002", CONFIG))
    assert len(e002) == 1
    assert e002[0][1] == list(range(1, 10)) and e002[0][3] == []
    assert sorted(subject for group in e002[0][2] for subject in group) == list(range(1, 10))
    assert len(e001) * (4 + 3) * 2 == 126
    assert len(e001) == 9  # Shallow outer fits.
    assert len(e002[0][2]) * 2 + 3 * 2 == 14


def test_resampling_and_cue_window_shape() -> None:
    source = np.zeros((2, 22, 750), dtype=np.float32)
    common = resample_poly(
        source, CONFIG["source_resample_up"], CONFIG["source_resample_down"], axis=2
    )
    assert common.shape == (2, 22, 480)
    assert CONFIG["source_trial_start_s"] - 2.0 == CONFIG["cue_relative_start_s"]
    assert CONFIG["source_trial_stop_exclusive_s"] - 2.0 == CONFIG["cue_relative_stop_exclusive_s"]


def test_mean_rank_rule_uses_all_four_source_folds_and_first_tie() -> None:
    curves = {}
    for fold in range(1, 5):
        values = [3.0] * 40
        values[4] = 0.1
        values[5] = 0.1
        curves[fold] = [{"epoch": index + 1, "val_ce": value} for index, value in enumerate(values)]
    assert q14_source.mean_rank_epoch(curves, 40) == 5
    with pytest.raises(AssertionError):
        q14_source.mean_rank_epoch({1: curves[1]}, 40)


def test_external_window_filter_fixed_shape_on_synthetic_eeg() -> None:
    sfreq = 160
    n_times = sfreq * 10
    signal = np.zeros((22, n_times), dtype=float)
    t = np.arange(n_times) / sfreq
    signal += 1e-6 * np.sin(2 * np.pi * 10 * t)
    raw = mne.io.RawArray(signal, mne.create_info(CONFIG["channels"], sfreq, "eeg"), verbose=False)
    raw.set_annotations(
        mne.Annotations(onset=[1.0, 5.0], duration=[0, 0], description=["T1", "T2"])
    )
    events, _ = mne.events_from_annotations(
        raw, event_id=CONFIG["external_event_map"], verbose=False
    )
    values, labels = q14_external._event_epochs(raw, CONFIG, "broad", events)
    assert values.shape == (2, 22, 480)
    assert labels.tolist() == [1, 2]
    assert np.isfinite(values).all()


def test_external_scoring_rejects_wrong_label_and_bad_probabilities() -> None:
    expected = [("physio_s001_r04_t001", 4, 1, 160, 1), ("physio_s001_r04_t002", 4, 2, 800, 2)]
    frame = pd.DataFrame(
        {
            "sample_id": [r[0] for r in expected],
            "run": [4, 4],
            "trial": [1, 2],
            "event_sample": [160, 800],
            "label": [1, 2],
            "p_left": [0.8, 0.3],
            "p_right": [0.2, 0.7],
            "predicted_label": [1, 2],
        }
    )
    scores = []
    q14_validate._validate_external_subset(frame, expected, 1, "BROAD_EEGNET", 20260924, scores)
    assert scores[0]["balanced_accuracy"] == 1.0
    bad = frame.copy()
    bad.loc[1, "label"] = 1
    with pytest.raises(AssertionError):
        q14_validate._validate_external_subset(bad, expected, 1, "BROAD_EEGNET", 20260924, [])
    bad = frame.copy()
    bad.loc[1, "p_right"] = 0.8
    with pytest.raises(AssertionError):
        q14_validate._validate_external_subset(bad, expected, 1, "BROAD_EEGNET", 20260924, [])


def test_freeze_is_hard_gate_before_external_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(q14_external, "E002_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        q14_external.verify_freeze(CONFIG)


def test_official_checksum_parser_requires_full_versioned_edf_coverage() -> None:
    fixture = "\n".join(
        f"{'a' * 64} S{subject:03d}/S{subject:03d}R{run:02d}.edf"
        for subject in range(1, 110)
        for run in (4, 8, 12)
    )
    parsed = q14_external.parse_official_checksums(fixture)
    assert len(parsed) == 327 and parsed["S001R04.edf"] == "a" * 64
    with pytest.raises(AssertionError):
        q14_external.parse_official_checksums(fixture.splitlines()[0])
    wrong_run = fixture.replace("S001/S001R04.edf", "S001/S001R03.edf")
    with pytest.raises(AssertionError, match="predeclared imagery EDF coverage"):
        q14_external.parse_official_checksums(wrong_run)
