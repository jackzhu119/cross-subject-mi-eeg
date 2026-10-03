"""Fixed orthonormal coordinates for the rank-20, 21-channel CAR subspace.

This basis is defined from channel count, never estimated from source or target
EEG. It lets full-rank CSP operate on 20 nonsingular coordinates after CAR.
"""
import numpy as np
from scipy.linalg import helmert
from sklearn.base import BaseEstimator, TransformerMixin


class FixedCARBasis(BaseEstimator, TransformerMixin):
    def __init__(self, n_channels=21):
        self.n_channels = n_channels

    @property
    def basis(self):
        if self.n_channels != 21:
            raise ValueError("Q15 requires the declared 21-channel reference space")
        basis = helmert(21, full=False)
        basis.setflags(write=False)
        return basis

    def fit(self, X, y=None):
        self._check(X)
        return self

    def _check(self, X):
        if np.asarray(X).ndim != 3 or np.asarray(X).shape[1:] != (21, 320) or not np.isfinite(X).all():
            raise ValueError("Expected finite Q15 [trials,21,320] input")

    def transform(self, X):
        self._check(X)
        return np.einsum("ac,nct->nat", self.basis, np.asarray(X, dtype=np.float64))
