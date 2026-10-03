"""Synthetic algebra for the fixed CAR coordinates, without classifier fitting."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import clone

from mi_eeg.models.q15_csp import FixedCARBasis


def test_fixed_basis_spans_exactly_the_complete_21_channel_car_subspace():
    basis = FixedCARBasis().basis
    assert basis.shape == (20, 21)
    assert basis.flags.writeable is False
    np.testing.assert_allclose(basis @ basis.T, np.eye(20), rtol=0, atol=5e-16)
    np.testing.assert_allclose(basis @ np.ones(21), 0, rtol=0, atol=3e-16)
    projector = np.eye(21) - np.ones((21, 21)) / 21
    np.testing.assert_allclose(basis.T @ basis, projector, rtol=0, atol=5e-16)
    assert np.linalg.matrix_rank(basis) == 20


def test_projection_is_lossless_in_car_space_and_removes_only_common_offset():
    rng = np.random.default_rng(20261003)
    raw = rng.normal(size=(3, 21, 320))
    car = raw - raw.mean(axis=1, keepdims=True)
    adapter = FixedCARBasis()
    projected = adapter.transform(car)
    assert projected.shape == (3, 20, 320)
    assert projected.dtype == np.float64
    restored = np.einsum("ca,nat->nct", adapter.basis.T, projected)
    np.testing.assert_allclose(restored, car, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(adapter.transform(raw), projected, rtol=2e-14, atol=2e-14)
    with_common_signal = car + np.sin(np.arange(320))[None, None, :] * 500
    np.testing.assert_allclose(adapter.transform(with_common_signal), projected, rtol=0, atol=3e-13)
    assert np.linalg.matrix_rank(np.cov(projected[0])) == 20
    assert np.linalg.matrix_rank(np.cov(car[0])) == 20
    np.testing.assert_allclose(np.linalg.norm(projected), np.linalg.norm(car), rtol=1e-15)


def test_fitting_checks_input_but_estimates_no_eeg_dependent_state():
    rng = np.random.default_rng(17)
    source = rng.normal(size=(2, 21, 320))
    target = rng.normal(size=(3, 21, 320)) * 500 + 200
    adapter = FixedCARBasis()
    before = adapter.basis.copy()
    assert adapter.fit(source, np.array([1, 2])) is adapter
    assert vars(adapter) == {"n_channels": 21}
    np.testing.assert_array_equal(adapter.basis, before)
    np.testing.assert_array_equal(adapter.transform(target), FixedCARBasis().transform(target))
    np.testing.assert_array_equal(clone(adapter).basis, before)


def test_basis_property_is_not_reassignable_and_returned_mutation_cannot_change_coordinates():
    adapter = FixedCARBasis()
    original = adapter.basis.copy()
    with pytest.raises(AttributeError):
        adapter.basis = np.zeros((20, 21))
    returned = adapter.basis
    if returned.flags.writeable:
        returned[:] = 0
    else:
        with pytest.raises(ValueError):
            returned[:] = 0
    np.testing.assert_array_equal(adapter.basis, original)


@pytest.mark.parametrize("values", [
    np.zeros((21, 320)), np.zeros((1, 20, 320)), np.zeros((1, 21, 319)),
    np.full((1, 21, 320), np.nan), np.full((1, 21, 320), np.inf),
])
@pytest.mark.parametrize("method", ["fit", "transform"])
def test_invalid_shape_and_nonfinite_input_cannot_reach_csp(values, method):
    with pytest.raises(ValueError, match="finite Q15"):
        getattr(FixedCARBasis(), method)(values)


def test_different_channel_count_is_not_an_undeclared_reference_amendment():
    adapter = FixedCARBasis(n_channels=20)
    with pytest.raises(ValueError, match="declared 21-channel reference"):
        _ = adapter.basis
    with pytest.raises(ValueError, match="declared 21-channel reference"):
        adapter.transform(np.zeros((1, 21, 320)))
