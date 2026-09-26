"""Narrow CSV round-trip comparison for Q14-R2 prediction aggregates.

The aggregate was assembled from the immutable per-subject CSV files and
serialized a second time. Numeric probabilities can change in their last
decimal place on that second serialization; trial identity and decisions may
not change. This module deliberately has no EDF or GPU dependency so the
published prediction files can be regression-tested offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PROBABILITY_COLUMNS = ("p_left", "p_right")
# Published Q14-R2 CSV strings differ by at most 2e-16. This fixed absolute
# bound covers the observed double-serialization error and is many orders of
# magnitude below the smallest recorded binary decision margin (1.621e-05).
CSV_ROUNDTRIP_ATOL = 5e-16


def assert_aggregate_matches_subjects(
    reconstructed: pd.DataFrame, aggregate: pd.DataFrame
) -> None:
    """Require exact rows/decisions and narrowly bounded probability drift."""

    if list(reconstructed.columns) != list(aggregate.columns):
        raise AssertionError("Aggregate prediction columns or column order changed")
    if len(reconstructed) != len(aggregate):
        raise AssertionError("Aggregate prediction row count changed")
    if not set(PROBABILITY_COLUMNS).issubset(reconstructed.columns):
        raise AssertionError("Aggregate prediction probabilities are missing")

    discrete = [column for column in reconstructed if column not in PROBABILITY_COLUMNS]
    pd.testing.assert_frame_equal(
        reconstructed[discrete],
        aggregate[discrete],
        check_dtype=False,
        check_exact=True,
    )
    for column in PROBABILITY_COLUMNS:
        source = reconstructed[column].to_numpy(dtype=np.float64)
        saved = aggregate[column].to_numpy(dtype=np.float64)
        if not np.isfinite(source).all() or not np.isfinite(saved).all():
            raise AssertionError(f"Non-finite aggregate probability: {column}")
        np.testing.assert_allclose(
            source,
            saved,
            rtol=0.0,
            atol=CSV_ROUNDTRIP_ATOL,
            equal_nan=False,
            err_msg=f"Aggregate {column} differs beyond CSV round-trip precision",
        )
