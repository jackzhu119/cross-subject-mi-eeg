"""One-time eligible-v3 NPZ import and lightweight, read-only training registry.

This module requires NumPy only. It never downloads EEG, filters signals, guesses
labels, selects trials, or derives source/target roles from filenames.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

import numpy as np


CHANNELS = ["Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1",
            "Cz", "C2", "C4", "C6", "CP3", "CP1", "CP2", "CP4", "Pz"]
INPUT_SHAPE = [3, 18, 320]
DATASET_ALIASES = {"bnci": "bnci", "BNCI2014_001": "bnci", "yang": "yang",
                   "Yang2025_2C": "yang", "dreyer": "dreyer", "Dreyer2023": "dreyer"}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _hash_object(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_sha(value):
    value = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    # This header exactly follows the archived eligible-v3 array-hash function.
    digest.update(json.dumps({"shape": list(value.shape), "dtype": value.dtype.str},
                             sort_keys=True).encode())
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def _stat(path):
    value = Path(path).stat()
    return {"bytes": value.st_size, "mtime_ns": value.st_mtime_ns}


def _atomic(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _atomic_json(path, value):
    payload = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False).encode() + b"\n"
    _atomic(path, lambda stream: stream.write(payload))


def _child(root, relative):
    p = Path(relative)
    _require(not p.is_absolute() and ".." not in p.parts, "Data manifest contains a non-relative path")
    result = (Path(root) / p).resolve()
    _require(result.is_relative_to(Path(root).resolve()), "Data file escapes data directory")
    return result


def _read_eligible(path, dataset):
    """Read and verify one original cached person once, without importing old code."""
    with np.load(path, allow_pickle=False) as archive:
        needed = {"X", "y", "metadata_json", "audit_json", "dataset", "subject",
                  "session", "run", "trial_id"}
        _require(needed.issubset(archive.files), "Expected eligible-v3 per-person NPZ keys: " + str(sorted(needed)))
        X, y = archive["X"], archive["y"]
        audit = json.loads(archive["audit_json"].item())
        rows = [json.loads(value) for value in archive["metadata_json"].tolist()]
        _require(DATASET_ALIASES.get(audit.get("dataset")) == dataset, "Explicit dataset differs from archived dataset")
        _require(audit.get("status") == "PASS_FRESH18_SUBJECT_INPUTS", "Input is not a completed eligible-v3 cache")
        _require(audit.get("channels") == CHANNELS and audit.get("sample_rate_hz") == 160,
                 "Input montage or sampling frequency differs from the new study input contract")
        _require(audit.get("view_order") == ["broad", "mu", "beta"] and audit.get("units") == "dimensionless",
                 "Expected dimensionless broad/mu/beta views")
        normalization = audit.get("normalization", {})
        _require(normalization.get("scope") == "single_trial_only_no_cross_trial_or_subject_statistics"
                 and normalization.get("apply_scale_to") == ["broad", "mu", "beta"]
                 and normalization.get("scale") == "same_trial_broad_view_root_mean_square_over_18_channels_and_320_samples"
                 and normalization.get("center") == "subtract_each_view_each_channel_temporal_mean_after_crop"
                 and normalization.get("output_unit") == "dimensionless",
                 "Input normalization does not match the explicit single-trial scale contract")
        _require(X.dtype == np.float32 and list(X.shape) == [len(rows)] + INPUT_SHAPE
                 and len(rows) > 0 and np.isfinite(X).all(), "Invalid/non-finite eligible-v3 X")
        _require(y.dtype == np.int64 and y.shape == (len(rows),)
                 and set(np.unique(y).tolist()) == {0, 1}, "Expected nonempty integer binary labels with both classes")
        _require(y.tolist() == [row["y"] for row in rows], "NPZ labels and original metadata disagree")
        _require(audit.get("n_trials") == len(rows), "Archived trial count disagrees")
        _require(_array_sha(X) == audit.get("X_sha256") and _array_sha(y) == audit.get("y_sha256")
                 and _hash_object(rows) == audit.get("metadata_sha256"), "Original NPZ array/metadata SHA256 mismatch")
        subject = str(audit.get("subject", ""))
        _require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", subject)), "Invalid archived subject identifier")
        _require(all(str(row["subject"]) == subject and DATASET_ALIASES.get(row["dataset"]) == dataset
                     for row in rows), "Mixed participant or dataset in one NPZ")
        for key in ["dataset", "subject", "session", "run", "trial_id"]:
            _require(archive[key].tolist() == [row[key] for row in rows], "Archived column differs: " + key)
        trial_ids = [str(row["trial_id"]) for row in rows]
        _require(len(set(trial_ids)) == len(trial_ids), "Duplicate physical trial identifiers")
        _require(all(str(row["session"]) and str(row["run"]) for row in rows), "Missing original session/run")
        sessions = [str(row["session"]) + "/" + str(row["run"]) for row in rows]
        return X, y, rows, audit, subject, trial_ids, sessions


def _expanded_inputs(config, config_dir):
    _require(config.get("schema_version") == 1, "input_sources.json schema_version must be 1")
    _require(bool(config.get("preprocessing_id")), "Explicit preprocessing_id is required")
    groups = config.get("datasets", [])
    _require(isinstance(groups, list) and groups, "Explicit dataset/role/path groups are required")
    expanded, seen_paths, seen_datasets = [], set(), set()
    for group in groups:
        dataset, role = group.get("dataset"), group.get("role")
        _require(dataset in {"bnci", "yang", "dreyer"}, "Expected explicit bnci/yang/dreyer dataset")
        _require(role == {"bnci": "source", "yang": "source", "dreyer": "external"}[dataset],
                 "This study fixes BNCI/Yang as source and Dreyer as external")
        _require(dataset not in seen_datasets, "Dataset must be listed once")
        seen_datasets.add(dataset)
        if "paths" in group:
            paths = [Path(value).expanduser() for value in group["paths"]]
            paths = [p if p.is_absolute() else config_dir / p for p in paths]
        else:
            folder = Path(group["directory"]).expanduser()
            folder = folder if folder.is_absolute() else config_dir / folder
            pattern = group.get("pattern", "sub-*.npz")
            _require("/" not in pattern and "\\" not in pattern, "Pattern must select files within one directory")
            paths = sorted(folder.glob(pattern))
        paths = [p.resolve(strict=True) for p in paths]
        _require(bool(paths), "No NPZ inputs found for " + dataset)
        if "expected_subjects" in group:
            _require(len(paths) == group["expected_subjects"], "Participant file count differs for " + dataset)
        for path in paths:
            _require(path.is_file() and path.suffix == ".npz", "Expected an existing NPZ file")
            _require(path not in seen_paths, "Same NPZ assigned more than once")
            seen_paths.add(path)
            expanded.append((dataset, role, path, group))
    return expanded


def _entry_file_check(root, entry):
    for name, identity in entry["files"].items():
        path = _child(root, identity["path"])
        _require(_stat(path) == {k: identity[k] for k in ("bytes", "mtime_ns")},
                 "Prepared file changed or is incomplete: " + str(identity["path"]))


def _fingerprint(manifest):
    # Output timestamps and locations do not change the scientific identity.
    rows = []
    for entry in manifest["subjects"]:
        rows.append({key: entry[key] for key in ["id", "dataset", "role", "n_trials"]}
                    | {"files": {k: v["sha256"] for k, v in sorted(entry["files"].items())}})
    return _hash_object({"preprocessing_id": manifest["preprocessing_id"], "input_shape": manifest["input_shape"],
                         "sfreq": manifest["sfreq"], "subjects": rows})


def prepare(config_path, output_dir):
    """Idempotent person-wise import. A completed person's input/output stats are reused."""
    config_path = Path(config_path).resolve(strict=True)
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text())
    config_hash = _hash_object(config)
    expanded = _expanded_inputs(config, config_path.parent)
    subjects, physical_ids, all_trial_ids = [], set(), set()
    reused = 0
    for index, (dataset, role, source_path, group) in enumerate(expanded):
        # The receipt key names a file, not a guessed participant or role.
        source_key = hashlib.sha256(str(source_path).encode()).hexdigest()[:24]
        receipt_path = root / "imports" / (source_key + ".json")
        before = _stat(source_path)
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text())
            _require(receipt["config_sha256"] == config_hash and receipt["input_stat"] == before,
                     "Previously imported input/config changed; preserve this cache and use a new output version")
            entry = receipt["entry"]
            _entry_file_check(root, entry)
            ids = json.loads(_child(root, entry["trial_ids"]).read_text())
            reused += 1
        else:
            input_sha = _file_sha(source_path)
            X, y, rows, audit, subject, ids, sessions = _read_eligible(source_path, dataset)
            _require(before == _stat(source_path), "NPZ changed while it was being imported")
            _require((dataset, subject) not in physical_ids, "Same physical participant imported under two paths")
            _require(not all_trial_ids.intersection(ids), "Physical trial identifiers overlap between inputs")
            person_id = dataset + "__" + subject
            folder = root / "people" / person_id
            entry = {"id": person_id, "dataset": dataset, "role": role, "subject": subject,
                     "provider_subject": audit.get("provider_subject"), "n_trials": len(y),
                     "x": str((folder / "X.npy").relative_to(root)),
                     "y": str((folder / "y.npy").relative_to(root)),
                     "trial_ids": str((folder / "trial_ids.json").relative_to(root)),
                     "sessions": str((folder / "sessions.json").relative_to(root)),
                     "metadata": str((folder / "metadata.json").relative_to(root)),
                     "original_audit": str((folder / "original_audit.json").relative_to(root)), "files": {}}
            _atomic(_child(root, entry["x"]), lambda stream: np.save(stream, X, allow_pickle=False))
            _atomic(_child(root, entry["y"]), lambda stream: np.save(stream, y, allow_pickle=False))
            for name, value in [("trial_ids", ids), ("sessions", sessions), ("metadata", rows), ("original_audit", audit)]:
                _atomic_json(_child(root, entry[name]), value)
            for name in ["x", "y", "trial_ids", "sessions", "metadata", "original_audit"]:
                path = _child(root, entry[name])
                entry["files"][name] = {"path": entry[name], **_stat(path), "sha256": _file_sha(path)}
            receipt = {"status": "PERSON_IMPORTED_AND_VERIFIED", "completed_at_utc": _utc(),
                       "config_sha256": config_hash, "input_path": str(source_path), "input_stat": before,
                       "input_sha256": input_sha, "entry": entry}
            _atomic_json(receipt_path, receipt)
        physical = (entry["dataset"], entry["subject"])
        _require(physical not in physical_ids, "Same physical participant imported under two paths")
        _require(not all_trial_ids.intersection(ids), "Physical trial identifiers overlap between inputs")
        physical_ids.add(physical)
        all_trial_ids.update(ids)
        subjects.append(entry)
        progress = {"stage": "importing_cached_inputs", "completed_people": index + 1,
                    "total_people": len(expanded), "reused_people": reused, "updated_at_utc": _utc(),
                    "new_model_fits": 0}
        _atomic_json(root / "prepare_status.json", progress)
        print(json.dumps(progress), flush=True)
    for group in config["datasets"]:
        if "expected_trials" in group:
            actual = sum(x["n_trials"] for x in subjects if x["dataset"] == group["dataset"])
            _require(actual == group["expected_trials"], "Trial inventory differs for " + group["dataset"])
    subjects.sort(key=lambda x: x["id"])
    manifest = {"schema_version": 1, "preprocessing_id": config["preprocessing_id"],
                "input_shape": INPUT_SHAPE, "sfreq": 160, "view_order": ["broad", "mu", "beta"],
                "channels": CHANNELS, "config_sha256": config_hash, "subjects": subjects}
    manifest["fingerprint"] = _fingerprint(manifest)
    _atomic_json(root / "manifest.json", manifest)
    _atomic_json(root / "prepare_status.json", {"stage": "prepared", "completed_people": len(subjects),
                 "reused_people": reused, "fingerprint": manifest["fingerprint"], "updated_at_utc": _utc(),
                 "new_model_fits": 0})
    return manifest


class Registry:
    """Load only metadata/stat at startup; arrays open on demand and are cached."""
    def __init__(self, data_dir):
        self.root = Path(data_dir).resolve(strict=True)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        _require(self.manifest.get("schema_version") == 1 and self.manifest.get("input_shape") == INPUT_SHAPE
                 and self.manifest.get("sfreq") == 160, "Unexpected prepared-data manifest schema")
        self.entries = self.manifest["subjects"]
        self.fingerprint = _fingerprint(self.manifest)
        _require(self.fingerprint == self.manifest.get("fingerprint"), "Prepared-data manifest identity changed")
        self.by_id = {entry["id"]: entry for entry in self.entries}
        _require(len(self.by_id) == len(self.entries) > 0, "Empty or duplicate participant registry")
        self.source_ids = [entry["id"] for entry in self.entries if entry["role"] == "source"]
        self.external_ids = [entry["id"] for entry in self.entries if entry["role"] == "external"]
        _require(len(self.source_ids) + len(self.external_ids) == len(self.entries), "Unknown data role")
        for entry in self.entries:
            _entry_file_check(self.root, entry)
        self._loaded = {}

    def ensure_source(self, ids):
        _require(len(ids) == len(set(ids)) and all(self.by_id[k]["role"] == "source" for k in ids),
                 "Training/selection may contain registered source participants only")

    def load_person(self, person_id):
        if person_id not in self._loaded:
            entry = self.by_id[person_id]
            _entry_file_check(self.root, entry)
            X = np.load(_child(self.root, entry["x"]), mmap_mode="r", allow_pickle=False)
            y = np.load(_child(self.root, entry["y"]), mmap_mode="r", allow_pickle=False)
            ids = json.loads(_child(self.root, entry["trial_ids"]).read_text())
            sessions = json.loads(_child(self.root, entry["sessions"]).read_text())
            n = entry["n_trials"]
            _require(X.dtype == np.float32 and list(X.shape) == [n] + INPUT_SHAPE
                     and y.dtype == np.int64 and y.shape == (n,) and len(ids) == len(sessions) == n,
                     "Prepared input header or metadata length changed")
            self._loaded[person_id] = {"X": X, "y": y, "trial_ids": ids, "sessions": sessions,
                                      "dataset": entry["dataset"], "id": person_id, "role": entry["role"]}
        return self._loaded[person_id]
