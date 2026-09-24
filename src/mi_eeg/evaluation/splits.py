"""Leakage-auditable deterministic splits for BNCI2014_001 trial metadata."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"sample_id", "subject", "session", "run", "trial", "label"}


def validate_metadata(meta: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS.difference(meta.columns)
    if missing:
        raise ValueError(f"Missing metadata columns: {sorted(missing)}")
    if meta["sample_id"].duplicated().any():
        raise ValueError("sample_id must be unique")


def iter_within_session(meta: pd.DataFrame) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """Leave one whole run out within each subject/session."""

    validate_metadata(meta)
    for (subject, session), group in meta.groupby(["subject", "session"], sort=True):
        runs = sorted(group["run"].unique())
        if len(runs) < 2:
            raise ValueError(f"Need at least two runs: subject={subject} session={session}")
        for held_run in runs:
            test_idx = group.index[group["run"] == held_run].to_numpy()
            train_idx = group.index[group["run"] != held_run].to_numpy()
            _assert_disjoint(train_idx, test_idx)
            yield f"within_s{subject}_{session}_run{held_run}", train_idx, test_idx


def iter_cross_session(meta: pd.DataFrame) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """Train on each subject's 0train session; test on that subject's 1test."""

    validate_metadata(meta)
    for subject, group in meta.groupby("subject", sort=True):
        train_idx = group.index[group["session"] == "0train"].to_numpy()
        test_idx = group.index[group["session"] == "1test"].to_numpy()
        if not len(train_idx) or not len(test_idx):
            raise ValueError(f"Both sessions are required for subject {subject}")
        _assert_disjoint(train_idx, test_idx)
        yield f"cross_session_s{subject}", train_idx, test_idx


def iter_loso(meta: pd.DataFrame) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """Leave both sessions of one subject wholly unseen during fitting."""

    validate_metadata(meta)
    subjects = sorted(meta["subject"].unique())
    if len(subjects) < 2:
        raise ValueError("Need at least two subjects for LOSO")
    for held_subject in subjects:
        train_idx = meta.index[meta["subject"] != held_subject].to_numpy()
        test_idx = meta.index[meta["subject"] == held_subject].to_numpy()
        _assert_disjoint(train_idx, test_idx)
        if set(meta.loc[train_idx, "subject"]).intersection(meta.loc[test_idx, "subject"]):
            raise AssertionError("Subject leaked across LOSO split")
        yield f"loso_s{held_subject}", train_idx, test_idx


def _assert_disjoint(train_idx: np.ndarray, test_idx: np.ndarray) -> None:
    if not len(train_idx) or not len(test_idx):
        raise ValueError("Empty training or test split")
    if np.intersect1d(train_idx, test_idx).size:
        raise AssertionError("Train/test index overlap")
