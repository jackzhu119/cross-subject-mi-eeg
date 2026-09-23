"""Small synthetic checks for fixed Fourier-band feature construction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_spectral_artifact_study import welch_log_bandpower


def test_welch_features_shape_and_frequency_localization() -> None:
    protocol = json.loads((ROOT / "configs" / "p3_spectral_artifact_protocol.json").read_text())
    time = np.arange(750) / 250.0
    X = np.zeros((2, 22, 750), dtype=np.float32)
    X[0, 0] = 1e-5 * np.sin(2 * np.pi * 10 * time)
    X[1, 0] = 1e-5 * np.sin(2 * np.pi * 18 * time)
    features = welch_log_bandpower(X, protocol)
    assert features.shape == (2, 88)
    assert np.isfinite(features).all()
    assert features[0, 0] > features[0, 22]
    assert features[0, 0] > features[0, 44]
    assert features[1, 44] > features[1, 0]
    assert features[1, 44] > features[1, 66]


def test_welch_features_deterministic() -> None:
    protocol = json.loads((ROOT / "configs" / "p3_spectral_artifact_protocol.json").read_text())
    X = np.random.default_rng(7).normal(size=(3, 22, 750)).astype(np.float32) * 1e-6
    assert np.array_equal(welch_log_bandpower(X, protocol), welch_log_bandpower(X, protocol))
