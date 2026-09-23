"""Small reproducibility helpers shared by future experiments."""

from __future__ import annotations

import random

import numpy as np

DEFAULT_SEED = 20260920


def set_global_seed(seed: int = DEFAULT_SEED) -> None:
    """Seed Python and NumPy.

    PyTorch seeding will be added only when the project reaches the deep
    learning phase, so Phase 1-4 do not depend on PyTorch.
    """

    # Python hash randomization is set at interpreter startup, not by assigning
    # PYTHONHASHSEED here. These algorithms do not rely on hash iteration order.
    random.seed(seed)
    np.random.seed(seed)
