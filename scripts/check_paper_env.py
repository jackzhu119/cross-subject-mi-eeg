"""Fail closed on paper-stage package mismatch or unusable CUDA."""

from __future__ import annotations

import importlib.metadata
import sys

EXPECTED = {
    "torch": "2.8.0",
    "torchaudio": "2.8.0",
    "braindecode": "1.5.1",
    "mne": "1.13.2",
    "moabb": "1.7.2",
    "numpy": "2.3.2",
    "scipy": "1.18.1",
    "scikit-learn": "1.9.1",
    "pandas": "3.0.6",
    "matplotlib": "3.11.2",
    "skorch": "1.4.0",
    "threadpoolctl": "3.7.0",
}


def package_mismatches(observed: dict[str, str]) -> dict[str, tuple[str, str | None]]:
    """Return mismatched required versions without touching an installed runtime."""
    return {
        name: (expected, observed.get(name))
        for name, expected in EXPECTED.items()
        if (observed.get(name, "").split("+")[0] != expected
            if name in {"torch", "torchaudio"}
            else observed.get(name) != expected)
    }


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print(f"ERROR: Python 3.12 required, observed {sys.version.split()[0]}")
        return 2
    observed = {}
    for name in EXPECTED:
        try:
            observed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    mismatches = package_mismatches(observed)
    if mismatches:
        for name, (expected, actual) in mismatches.items():
            print(f"ERROR: {name}: expected {expected}, observed {actual or 'missing'}")
        return 2

    import torch
    import torchaudio  # import checks the native extension/CUDA pairing
    from braindecode.models import EEGNet  # noqa: F401 - real model import smoke check

    for name, version in (("torch", torch.__version__),
                          ("torchaudio", torchaudio.__version__)):
        if version.split("+")[0] != "2.8.0":
            print(f"ERROR: {name} runtime version must be 2.8.0, observed {version}")
            return 2
        suffix = version.partition("+")[2]
        if suffix and suffix != "cu128":
            print(f"ERROR: {name} CUDA build suffix must be cu128, observed {version}")
            return 2
    if torch.version.cuda != "12.8":
        print(f"ERROR: torch CUDA runtime must be 12.8, observed {torch.version.cuda}")
        return 2
    if not torch.cuda.is_available():
        print("ERROR: torch.cuda.is_available() is false")
        return 2
    sample = torch.ones((8, 8), device="cuda")
    if not torch.isfinite(sample @ sample).all().item():
        print("ERROR: CUDA matrix operation returned non-finite values")
        return 2
    torch.cuda.synchronize()
    print(f"Paper CUDA runtime passed: {torch.__version__}; {torch.cuda.get_device_name(0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
