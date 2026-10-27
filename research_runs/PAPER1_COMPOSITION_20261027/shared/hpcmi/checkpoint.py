"""Small persistent I/O primitives and two-generation checkpoints.

Only files emitted by this program should be loaded as torch checkpoints. File
fsync and same-directory os.replace are used; directory fsync and hard links are
not prerequisites on the cluster's shared storage.
"""
from __future__ import annotations
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import traceback


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def atomic_npz(path, **arrays):
    import numpy as np
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        stream.seek(0)
        stream.truncate()
        stream.write(str(os.getpid()) + "\n")
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class ContractMismatch(RuntimeError):
    pass


def save_checkpoint(directory, payload):
    """A crash during rotation leaves at least the previous complete generation."""
    import torch
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="checkpoint.", suffix=".tmp", dir=str(directory))
    latest, previous = directory / "latest.pt", directory / "previous.pt"
    try:
        with os.fdopen(fd, "wb") as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if latest.exists():
            os.replace(latest, previous)
        os.replace(temporary, latest)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    atomic_json(directory / "checkpoint_status.json", {
        "saved_at_utc": utc_now(), "global_step": payload["global_step"],
        "epoch": payload["epoch"], "step_in_epoch": payload["step_in_epoch"],
        "fingerprint": payload["fingerprint"], "generations": ["latest.pt", "previous.pt"],
    })


def load_checkpoint(directory, expected_fingerprint):
    """Recover a damaged newest write from previous; never mask contract changes."""
    import torch
    directory = Path(directory)
    failures = []
    candidates = [directory / "latest.pt", directory / "previous.pt"]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
            if payload.get("fingerprint") != expected_fingerprint:
                raise ContractMismatch("Scientific configuration/data/task differs from checkpoint; use a new experiment version")
            required = {"model", "optimizer", "scheduler", "scaler", "rng", "sampler", "objective", "epoch", "step_in_epoch", "global_step", "best_model", "best_epoch", "validation_history"}
            if not required.issubset(payload):
                raise ValueError("Incomplete checkpoint payload")
            if failures:
                # Preserve the bad file rather than rotating it over the good backup.
                for failure in failures:
                    bad = directory / failure["file"]
                    if bad.exists():
                        preserved = directory / (bad.name + ".unreadable-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
                        os.replace(bad, preserved)
                        failure["preserved_as"] = preserved.name
                atomic_json(directory / ("recovery-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json"), {
                    "recovered_at_utc": utc_now(), "loaded": path.name, "failures": failures,
                })
            return payload
        except ContractMismatch:
            raise
        except Exception:
            failures.append({"file": path.name, "traceback": traceback.format_exc()})
    if failures:
        atomic_json(directory / ("load-failure-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json"), {"failed_at_utc": utc_now(), "failures": failures})
        raise RuntimeError("Both available checkpoint generations failed to load; retained for inspection")
    return None
