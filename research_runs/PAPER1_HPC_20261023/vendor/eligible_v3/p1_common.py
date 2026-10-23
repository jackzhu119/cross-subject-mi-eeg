"""Shared, atomic local I/O for the frozen Paper1 expansion protocol."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_child(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe archive/manifest path: {relative}")
    out = (root / rel).resolve()
    if not out.is_relative_to(root):
        raise ValueError(f"Path leaves data directory: {relative}")
    return out


@contextlib.contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise RuntimeError("This experiment is already running. Inspect status.json / run.log.") from e
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()) + "\n")
        f.flush()
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def code_manifest(bundle):
    bundle = Path(bundle)
    paths = sorted(list(bundle.glob("*.py")) + list(bundle.glob("*.sh")) +
                   list(bundle.glob("requirements*.txt")) + list((bundle / "config").glob("*.json")) +
                   [bundle/"pyproject.toml", bundle/"uv.lock"])
    return {str(p.relative_to(bundle)): sha256_file(p) for p in paths if p.is_file()}


def log(message):
    print(f"[{utc_now()}] {message}", flush=True)
