"""Immutable run-directory guards and startup source snapshots."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path


def require_new_run_directory(output: Path) -> None:
    """Refuse to overwrite successful, failed, or interrupted run evidence."""
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"Output is not empty; choose a new run ID: {output}")
    output.mkdir(parents=True, exist_ok=True)


def capture_startup_provenance(root: Path, output: Path) -> dict:
    """Archive source/config/test files and the dependency lock as they exist now.

    This is used only for future runs; it must never be backdated into old runs.
    """
    destination = output / "provenance" / "source"
    destination.mkdir(parents=True, exist_ok=False)
    paths = [root / "pyproject.toml", root / "uv.lock"]
    paths.extend(
        root / name
        for name in (
            "requirements-cloud.txt",
            "README_CLOUD.md",
            "check_gpu.py",
            "setup_gpu.sh",
            "run_gpu.sh",
        )
        if (root / name).is_file()
    )
    for folder, suffix in (
        ("scripts", ".py"),
        ("src/mi_eeg", ".py"),
        ("tests", ".py"),
        ("configs", ".json"),
    ):
        paths.extend(sorted((root / folder).rglob(f"*{suffix}")))
    records = []
    for path in paths:
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        archived = destination / relative
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, archived)
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(archived.read_bytes()).hexdigest(),
                "bytes": archived.stat().st_size,
            }
        )
    versions = {}
    for name in (
        "mne",
        "moabb",
        "numpy",
        "scipy",
        "pandas",
        "scikit-learn",
        "matplotlib",
        "threadpoolctl",
        "torch",
        "torchaudio",
        "braindecode",
        "skorch",
    ):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "command": sys.argv,
        "python": sys.version,
        "platform": platform.platform(),
        "versions": versions,
        "source_files": records,
        "scope": "Files on disk at this run startup; not a retrospective record for earlier experiments",
    }
    (output / "provenance" / "manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def check_declared_constants(actual: dict, expected: dict, prefix: str = "protocol") -> None:
    """Legacy fixed scripts reject changes to unsupported declared parameters."""
    for key, value in expected.items():
        location = f"{prefix}.{key}"
        if key not in actual:
            raise ValueError(f"Missing {location}")
        if isinstance(value, dict):
            check_declared_constants(actual[key], value, location)
        elif actual[key] != value:
            raise ValueError(
                f"Fixed legacy implementation requires {location}={value!r}; got {actual[key]!r}"
            )
