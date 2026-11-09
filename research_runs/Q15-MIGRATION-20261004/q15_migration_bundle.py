"""Hash-only custody of the committed Q15 source models and external epochs.

This module uses only Python's standard library and local Git. It never imports
an EEG loader, deserializes a checkpoint, runs a fit, or computes predictions.
The outer archive has a fixed allowlist; the Git bundle preserves the pinned
public repository history, including historical research evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

BASE_COMMIT = "782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc"
SCIENTIFIC_REVISION = "271af288a2f3863430ab80e3145c2dee9bd5571d"
ORIGIN_JOB_ID = "20261004T005335Z-9b3bce30277a"
ORIGIN_POD_ID = "hvjo2yy3m3wamh"
ORIGIN_URL = "https://github.com/jackzhu119/cross-subject-mi-eeg.git"
BUNDLE_REF = "refs/heads/q15-migration-baseline"
KIND = "q15_validated_source_and_epochs"
MAX_BYTES = 8 * 1024**3
MAX_MANIFEST_BYTES = 1024**2
CHUNK_BYTES = 1024**2
DATASETS = {"Cho2017": 52, "Lee2019_MI": 54}
MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
SEEDS = (20260924, 20260925, 20260926)
SOURCE_ROOT = "results/Q15-E005"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
TRANSPORT_RECEIPT_KEYS = {"status", "object_key", "bytes", "full_get_verified", "probe",
                          "raw_originals_verified", "raw_originals", "ready_for_continuation",
                          "new_source_fits", "origin_source_fits", "target_fits", "pod_stop_requested"}


class MigrationError(RuntimeError):
    """A safe, machine-readable rejection, without subprocess or secret output."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise MigrationError(code, message)


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _decode_json(data: bytes) -> object:
    try:
        return json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise MigrationError("invalid_json", "JSON is malformed or has duplicate keys") from exc


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _regular(path: Path) -> None:
    # Checking ancestors prevents a symlinked directory from escaping an allowlist.
    for part in (path, *path.parents):
        _require(not part.is_symlink(), "unsafe_path", "Symlinked paths are forbidden")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise MigrationError("missing_file", "A required regular file is unavailable") from exc
    _require(stat.S_ISREG(mode), "unsafe_path", "Only regular files are permitted")


def sha256_stream(stream, *, limit: int | None = None) -> tuple[str, int]:
    """Hash a stream in bounded chunks, returning its digest and byte count."""
    digest, count = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
        count += len(block)
        _require(limit is None or count <= limit, "size_limit", "Content exceeds its size limit")
        digest.update(block)
    return digest.hexdigest(), count


def sha256_file(path: Path | str) -> str:
    path = Path(path).absolute()
    _regular(path)
    with path.open("rb") as stream:
        return sha256_stream(stream)[0]


def _file_record(path: Path, archive_path: str) -> dict:
    _regular(path)
    with path.open("rb") as stream:
        digest, size = sha256_stream(stream, limit=MAX_BYTES)
    return {"path": archive_path, "bytes": size, "sha256": digest}


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    # Local operations only; errors deliberately omit Git's potentially private output.
    command = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
               "-c", "credential.helper=",
               "-c", "protocol.file.allow=always", "-C", str(repo), *args]
    result = subprocess.run(command, input=input_bytes, capture_output=True, check=False,
                            env=_git_environment())
    _require(result.returncode == 0, "git_failed", "A required local Git operation failed")
    return result.stdout


def _git_environment() -> dict:
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_TERMINAL_PROMPT="0")
    return environment


def _blob(repo: Path, base: str, name: str) -> bytes:
    data = _git(repo, "show", f"{base}:{name}")
    _require(len(data) <= MAX_MANIFEST_BYTES, "size_limit", "A provenance JSON exceeds its limit")
    return data


def _git_sha256(repo: Path, base: str, name: str) -> str:
    command = ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo),
               "show", f"{base}:{name}"]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          env=_git_environment()) as process:
        assert process.stdout is not None
        digest, _ = sha256_stream(process.stdout, limit=MAX_BYTES)
        _require(process.wait() == 0, "git_failed", "A committed artifact is unavailable")
    return digest


def _fields(record: dict, expected: dict, code: str) -> None:
    _require(isinstance(record, dict) and all(
        type(record.get(key)) is type(value) and record.get(key) == value
        for key, value in expected.items()), code, "A provenance gate differs from the frozen baseline")


def _source_artifact_paths() -> set[str]:
    names = {"run_config.json", "source_files.json", "source_metadata.csv",
             "source_audit.csv", "source_stage_complete.json"}
    for model in MODELS:
        base = f"{model}/all_source"
        names.add(f"{base}/selection.json")
        fits = [f"inner_{fold:02d}" for fold in range(1, 5)]
        fits += [f"final_seed_{seed}" for seed in SEEDS]
        names.update(f"{base}/{fit}/{name}" for fit in fits
                     for name in ("manifest.json", "curve.json", "checkpoint.pt"))
    names.update({"CSP4_LDA/all_source/manifest.json", "CSP4_LDA/all_source/model.joblib"})
    return {f"{SOURCE_ROOT}/pre_fit_freeze.json"} | {
        f"{SOURCE_ROOT}/source/{name}" for name in names}


def _bnci_inventory(repo: Path, base: str) -> dict[str, dict]:
    rows = _decode_json(_blob(repo, base, "research_runs/Q8-E001/results/source_files.json"))
    _require(isinstance(rows, list), "bnci_inventory", "Frozen BNCI inventory is malformed")
    expected = {f"A{subject:02d}{session}.mat" for subject in range(1, 10)
                for session in ("E", "T")}
    inventory = {}
    for row in rows:
        _require(isinstance(row, dict), "bnci_inventory", "Frozen BNCI row is malformed")
        name = PurePosixPath(row.get("path", "")).name
        _require(name in expected and name not in inventory and type(row.get("bytes")) is int
                 and row["bytes"] > 0 and isinstance(row.get("sha256"), str)
                 and SHA256.fullmatch(row["sha256"]) is not None,
                 "bnci_inventory", "Frozen BNCI original inventory differs")
        inventory[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
    _require(set(inventory) == expected, "bnci_inventory", "Exactly 18 BNCI originals are required")
    return inventory


def _verify_source_baseline(repo: Path, base: str) -> None:
    """Verify the independently validated, committed 14 + 1 source ledger."""
    report = _decode_json(_blob(repo, base, f"{SOURCE_ROOT}/source_validation.json"))
    _fields(report, {"schema_version": 1, "status": "source_validated_non_authorizing",
                     "passed": True, "deep_fit_count": 14, "shallow_fit_count": 1,
                     "source_only": True, "target_fits": 0,
                     "external_prediction_authorized": False,
                     "external_predictions_computed": False,
                     "counts": {"deep_inner": 8, "deep_final": 6, "shallow": 1,
                                "predictions": 0}}, "source_not_validated")
    artifacts = report.get("artifact_sha256")
    _require(isinstance(artifacts, dict) and set(artifacts) == _source_artifact_paths(),
             "source_not_validated", "Source artifact inventory is incomplete or contains extras")
    for name, digest in artifacts.items():
        _require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None
                 and _git_sha256(repo, base, name) == digest,
                 "source_hash_mismatch", "A committed source artifact changed")
    completion_path = f"{SOURCE_ROOT}/source/source_stage_complete.json"
    completion = _decode_json(_blob(repo, base, completion_path))
    _fields(completion, {"status": "fits_complete_pending_independent_source_validation",
                         "deep_fit_count": 14, "shallow_fit_count": 1,
                         "external_predictions_computed": False,
                         "external_prediction_authorized": False}, "source_not_validated")
    for key, name in {"pre_fit_freeze_sha256": f"{SOURCE_ROOT}/pre_fit_freeze.json",
                      "source_files_sha256": f"{SOURCE_ROOT}/source/source_files.json",
                      "source_metadata_sha256": f"{SOURCE_ROOT}/source/source_metadata.csv",
                      "source_audit_sha256": f"{SOURCE_ROOT}/source/source_audit.csv",
                      "source_run_config_sha256": f"{SOURCE_ROOT}/source/run_config.json",
                      "source_stage_complete_sha256": completion_path}.items():
        _require(report.get(key) == artifacts[name], "source_hash_mismatch",
                 "Source report references inconsistent artifacts")
    checkpoints = report.get("checkpoints")
    _require(isinstance(checkpoints, dict) and set(checkpoints) == set(MODELS),
             "source_not_validated", "Source final checkpoint inventory differs")
    for model in MODELS:
        _require(isinstance(checkpoints[model], dict)
                 and set(checkpoints[model]) == {str(seed) for seed in SEEDS},
                 "source_not_validated", "Source final seeds differ")
        for seed in SEEDS:
            name = f"{SOURCE_ROOT}/source/{model}/all_source/final_seed_{seed}/checkpoint.pt"
            _require(checkpoints[model][str(seed)] == artifacts[name],
                     "source_hash_mismatch", "Source final checkpoint hash differs")
    csp = f"{SOURCE_ROOT}/source/CSP4_LDA/all_source/model.joblib"
    _require(report.get("csp_model_sha256") == artifacts[csp], "source_hash_mismatch",
             "Source shallow model hash differs")
    # Every fit's own checkpoint/curve hash must also match the independent ledger.
    for name in artifacts:
        if name.endswith("/manifest.json"):
            fit = _decode_json(_blob(repo, base, name))
            _fields(fit, {"status": "complete"}, "source_not_validated")
            folder = name.rsplit("/", 1)[0]
            for key, suffix in (("model_sha256", "model.joblib"),) if "/CSP4_LDA/" in name else (
                    ("checkpoint_sha256", "checkpoint.pt"), ("curve_sha256", "curve.json")):
                _require(fit.get(key) == artifacts[f"{folder}/{suffix}"],
                         "source_hash_mismatch", "A fit manifest disagrees with independent validation")
    frozen = _bnci_inventory(repo, base)
    source_inventory = _decode_json(_blob(repo, base, f"{SOURCE_ROOT}/source/source_files.json"))
    _require(isinstance(source_inventory, dict) and set(source_inventory) == {"files"},
             "bnci_inventory", "Source BNCI inventory schema differs")
    source_rows = source_inventory["files"]
    _require(isinstance(source_rows, list) and len(source_rows) == 18,
             "bnci_inventory", "Source BNCI inventory is incomplete")
    actual = {row.get("filename"): {key: row.get(key) for key in ("bytes", "sha256")}
              for row in source_rows if isinstance(row, dict)}
    _require(actual == frozen, "bnci_inventory", "Source originals differ from frozen Q8")


def verify_source_baseline(repo, base_commit=BASE_COMMIT) -> dict:
    """Read-only verification of the pinned public checkout and source models.

    This entry point works without an old Pod or migration archive. It verifies
    committed source evidence and opaque checkpoint bytes without loading EEG
    or deserializing any model. Call it on a clean public checkout before the
    scientific runtime imports create local caches or progress artifacts.
    """
    repo = Path(repo).absolute()
    _require(isinstance(base_commit, str) and base_commit == BASE_COMMIT
             and COMMIT.fullmatch(base_commit) is not None,
             "wrong_baseline", "Only the immutable source baseline is permitted")
    _git(repo, "merge-base", "--is-ancestor", SCIENTIFIC_REVISION, base_commit)
    _verify_source_baseline(repo, base_commit)
    _verify_repo(repo, base_commit)
    report = _decode_json(_blob(repo, base_commit, f"{SOURCE_ROOT}/source_validation.json"))
    return {"schema_version": 1, "status": "public_source_baseline_verified",
            "code_base_commit": base_commit, "scientific_revision": SCIENTIFIC_REVISION,
            "origin_job_id": ORIGIN_JOB_ID, "origin_pod_id": ORIGIN_POD_ID,
            "source_fit_count": 15, "deep_fit_count": 14, "shallow_fit_count": 1,
            "new_source_fits": 0, "target_fits": 0,
            "source_validation_sha256": _git_sha256(
                repo, base_commit, f"{SOURCE_ROOT}/source_validation.json"),
            "verified_source_artifacts": len(report["artifact_sha256"]),
            "bnci_files": _bnci_inventory(repo, base_commit)}


def _archive_allowlist() -> set[str]:
    names = {"repository.bundle"}
    for dataset, count in DATASETS.items():
        names.add(f"epochs/{dataset}/epoch_manifest.json")
        names.update(f"epochs/{dataset}/s{subject:02d}.{suffix}"
                     for subject in range(1, count + 1) for suffix in ("npz", "csv"))
    names.update(f"raw/BNCI2014_001/A{subject:02d}{session}.mat"
                 for subject in range(1, 10) for session in ("E", "T"))
    return names


def _safe_archive_name(name: str) -> None:
    _require(isinstance(name, str) and bool(name) and "\\" not in name
             and "\x00" not in name and not name.startswith("/")
             and all(part not in ("", ".", "..") for part in name.split("/")),
             "unsafe_archive", "Archive paths must be canonical relative paths")
    _require(name in _archive_allowlist() | {"migration_manifest.json"},
             "unexpected_member", "Archive contains content outside the fixed allowlist")


def _epoch_sources(repo: Path, base: str, epoch_dir: Path) -> list[tuple[Path, dict]]:
    result = []
    for dataset, count in DATASETS.items():
        committed = _blob(repo, base, f"results/Q15-EXTERNAL/manifests/{dataset}.json")
        manifest = _decode_json(committed)
        _fields(manifest, {"schema_version": 1, "dataset": dataset,
                           "status": "epochs_verified_non_authorizing", "target_fits": 0,
                           "predictions_computed": False,
                           "expected_subject_ids": list(range(1, count + 1))}, "epoch_manifest")
        original = epoch_dir / dataset / "epoch_manifest.json"
        record = _file_record(original, f"epochs/{dataset}/epoch_manifest.json")
        _require(record["sha256"] == hashlib.sha256(committed).hexdigest(),
                 "epoch_manifest", "Original epoch manifest differs from the committed copy")
        result.append((original, record))
        rows = manifest.get("subjects")
        _require(isinstance(rows, list) and [row.get("subject") for row in rows
                 if isinstance(row, dict)] == list(range(1, count + 1)),
                 "epoch_manifest", "Epoch person inventory is incomplete or reordered")
        for subject, row in enumerate(rows, 1):
            for path_key, hash_key, suffix in (("npz_path", "npz_sha256", "npz"),
                                                ("metadata_path", "metadata_sha256", "csv")):
                source = epoch_dir / dataset / f"s{subject:02d}.{suffix}"
                # The committed absolute paths are provenance. A portable copy may
                # live elsewhere, but its dataset/person filename must be identical.
                recorded = PurePosixPath(row.get(path_key, ""))
                _require(recorded.is_absolute() and recorded.parts[-2:] == (dataset, source.name),
                         "epoch_manifest", "Epoch file identity differs from the committed manifest")
                item = _file_record(source, f"epochs/{dataset}/{source.name}")
                _require(item["sha256"] == row.get(hash_key), "epoch_hash_mismatch",
                         "An external epoch or metadata file differs from its committed hash")
                result.append((source, item))
    return result


class _HashingReader:
    def __init__(self, stream):
        self.stream, self.digest, self.count = stream, hashlib.sha256(), 0

    def read(self, size=-1):
        block = self.stream.read(size)
        self.digest.update(block)
        self.count += len(block)
        return block


def _add_verified_file(archive: tarfile.TarFile, path: Path, record: dict) -> None:
    _regular(path)
    header = tarfile.TarInfo(record["path"])
    header.size, header.mode, header.mtime = record["bytes"], 0o600, 0
    with path.open("rb") as stream:
        reader = _HashingReader(stream)
        archive.addfile(header, reader)
        _require(reader.count == record["bytes"] and reader.digest.hexdigest() == record["sha256"]
                 and stream.read(1) == b"", "source_changed",
                 "A file changed while the archive was being written")


def export_bundle(repo, epoch_dir, bnci_dir, out_path, base_commit=BASE_COMMIT,
                  origin_job_id=ORIGIN_JOB_ID, origin_pod_id=ORIGIN_POD_ID) -> dict:
    """Create an uncompressed, verified archive without mutating the active repo."""
    repo, epoch_dir, bnci_dir = (Path(path).absolute() for path in (repo, epoch_dir, bnci_dir))
    out_path = Path(out_path).absolute()
    _require(base_commit == BASE_COMMIT and COMMIT.fullmatch(base_commit) is not None,
             "wrong_baseline", "Only the immutable export baseline is permitted")
    _require(origin_job_id == ORIGIN_JOB_ID and origin_pod_id == ORIGIN_POD_ID,
             "wrong_origin", "Origin job and Pod identities differ from the validated snapshot")
    _require(not out_path.exists() and not out_path.is_symlink(), "destination_exists",
             "The archive output path already exists")
    for parent in out_path.parents:
        _require(not parent.is_symlink(), "unsafe_path", "Archive output parents must not be symlinked")
    _require(_git(repo, "rev-parse", f"{base_commit}^{{commit}}").decode().strip() == base_commit,
             "wrong_baseline", "Export baseline is unavailable")
    _verify_source_baseline(repo, base_commit)
    sources = _epoch_sources(repo, base_commit, epoch_dir)
    for name, expected in sorted(_bnci_inventory(repo, base_commit).items()):
        path = bnci_dir / name
        record = _file_record(path, f"raw/BNCI2014_001/{name}")
        _require(all(record[key] == expected[key] for key in ("bytes", "sha256")),
                 "bnci_hash_mismatch", "A BNCI original differs from frozen Q8")
        sources.append((path, record))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = None
    with tempfile.TemporaryDirectory(prefix="q15-export-") as temporary:
        temporary = Path(temporary)
        bare = temporary / "repository.git"
        bare.mkdir()
        _git(bare, "init", "--bare", "--quiet")
        origin = ORIGIN_URL if _git(repo, "rev-parse", "--is-shallow-repository").strip() == b"true" else str(repo)
        # A shallow origin cannot produce a self-contained bundle. Fetch complete
        # public ancestry into this disposable bare repo, never unshallow the Pod.
        _git(bare, "fetch", "--quiet", "--no-tags", origin, base_commit)
        _git(bare, "merge-base", "--is-ancestor", SCIENTIFIC_REVISION, base_commit)
        _git(bare, "update-ref", BUNDLE_REF, base_commit)
        bundle = temporary / "repository.bundle"
        _git(bare, "bundle", "create", str(bundle), BUNDLE_REF)
        verifier = temporary / "bundle-verifier"
        verifier.mkdir()
        _git(verifier, "init", "--quiet")
        _git(verifier, "bundle", "verify", str(bundle))
        sources.append((bundle, _file_record(bundle, "repository.bundle")))
        sources.sort(key=lambda pair: pair[1]["path"])
        _require(sum(record["bytes"] for _, record in sources) <= MAX_BYTES,
                 "size_limit", "Migration content exceeds 8 GiB")
        entries = {record["path"]: record for _, record in sources}
        manifest = {"schema_version": 1, "kind": KIND, "origin_job_id": origin_job_id,
                    "origin_pod_id": origin_pod_id, "scientific_revision": SCIENTIFIC_REVISION,
                    "code_base_commit": base_commit, "source_fit_count": 15,
                    "repo_bundle": dict(entries["repository.bundle"]),
                    "epoch_manifests": {dataset: {
                        "path": f"epochs/{dataset}/epoch_manifest.json",
                        "sha256": entries[f"epochs/{dataset}/epoch_manifest.json"]["sha256"]}
                        for dataset in DATASETS}, "files": list(entries.values()),
                    "created_at_utc": datetime.now(UTC).isoformat()}
        validate_manifest(manifest)
        data = _json_bytes(manifest)
        descriptor, temporary_output = tempfile.mkstemp(prefix=".q15-export-", dir=out_path.parent)
        os.close(descriptor)
        try:
            with tarfile.open(temporary_output, "w", format=tarfile.USTAR_FORMAT) as archive:
                header = tarfile.TarInfo("migration_manifest.json")
                header.size, header.mode, header.mtime = len(data), 0o600, 0
                archive.addfile(header, io.BytesIO(data))
                for path, record in sources:
                    _add_verified_file(archive, path, record)
            for path, record in sources:
                _require(_file_record(path, record["path"]) == record, "source_changed",
                         "A source file changed during archive packaging")
            # Hard-link publication refuses a concurrently created destination.
            os.link(temporary_output, out_path)
        finally:
            Path(temporary_output).unlink(missing_ok=True)
    return manifest


def validate_manifest(manifest: dict) -> dict[str, dict]:
    """Validate the complete pinned outer schema and return the file inventory."""
    keys = {"schema_version", "kind", "origin_job_id", "origin_pod_id", "scientific_revision",
            "code_base_commit", "source_fit_count", "repo_bundle", "epoch_manifests", "files",
            "created_at_utc"}
    _require(isinstance(manifest, dict) and set(manifest) == keys, "invalid_manifest",
             "Migration manifest schema differs")
    _fields(manifest, {"schema_version": 1, "kind": KIND, "origin_job_id": ORIGIN_JOB_ID,
                      "origin_pod_id": ORIGIN_POD_ID, "scientific_revision": SCIENTIFIC_REVISION,
                      "code_base_commit": BASE_COMMIT, "source_fit_count": 15}, "invalid_manifest")
    try:
        timestamp = datetime.fromisoformat(manifest["created_at_utc"])
    except (ValueError, TypeError) as exc:
        raise MigrationError("invalid_manifest", "Creation timestamp is invalid") from exc
    _require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0,
             "invalid_manifest", "Creation timestamp must be in UTC")
    rows = manifest["files"]
    _require(isinstance(rows, list) and len(rows) == len(_archive_allowlist()),
             "invalid_manifest", "Migration file count differs from the complete allowlist")
    inventory = {}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {"path", "bytes", "sha256"},
                 "invalid_manifest", "File inventory row schema differs")
        _safe_archive_name(row["path"])
        _require(row["path"] != "migration_manifest.json" and row["path"] not in inventory
                 and type(row["bytes"]) is int and 0 < row["bytes"] <= MAX_BYTES
                 and isinstance(row["sha256"], str) and SHA256.fullmatch(row["sha256"]) is not None,
                 "invalid_manifest", "File inventory contains invalid or duplicate content")
        inventory[row["path"]] = row
    _require(set(inventory) == _archive_allowlist()
             and sum(row["bytes"] for row in rows) <= MAX_BYTES,
             "invalid_manifest", "Migration content inventory differs or exceeds its limit")
    _require(manifest["repo_bundle"] == inventory["repository.bundle"],
             "invalid_manifest", "Repository bundle references inconsistent content")
    expected = {dataset: {"path": f"epochs/{dataset}/epoch_manifest.json",
                         "sha256": inventory[f"epochs/{dataset}/epoch_manifest.json"]["sha256"]}
                for dataset in DATASETS}
    _require(manifest["epoch_manifests"] == expected, "invalid_manifest",
             "Epoch manifests reference inconsistent content")
    return inventory


def _preflight_tar(archive_path: Path) -> None:
    """Inspect fixed-size headers before tarfile can allocate extension payloads."""
    total, seen, archive_size = 0, set(), archive_path.stat().st_size
    with archive_path.open("rb") as stream:
        while True:
            header = stream.read(512)
            _require(len(header) == 512, "unsafe_archive", "Archive is truncated or lacks its terminator")
            if header == b"\0" * 512:
                _require(archive_size - stream.tell() >= 512, "unsafe_archive",
                         "Archive lacks its complete terminator")
                for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
                    _require(not any(block), "unsafe_archive", "Archive contains nonzero trailing content")
                break
            _require(header[156:157] in (b"0", b"\0")
                     and not header[345:500].strip(b"\0"), "unsafe_archive",
                     "Archive extensions and nonregular raw headers are forbidden")
            try:
                name = header[:100].split(b"\0", 1)[0].decode("utf-8")
                size_field = header[124:136].strip(b"\0 ")
                _require(bool(size_field) and all(byte in b"01234567" for byte in size_field),
                         "unsafe_archive", "Archive size must use a bounded octal header")
                size = int(size_field, 8)
            except (UnicodeError, ValueError) as exc:
                raise MigrationError("unsafe_archive", "Archive header is malformed") from exc
            _safe_archive_name(name)
            _require(name not in seen, "duplicate_member", "Archive repeats a member")
            seen.add(name)
            total += size
            _require(total <= MAX_BYTES + MAX_MANIFEST_BYTES
                     and len(seen) <= len(_archive_allowlist()) + 1,
                     "size_limit", "Archive exceeds migration limits")
            if name == "migration_manifest.json":
                _require(0 < size <= MAX_MANIFEST_BYTES, "size_limit", "Manifest size exceeds its limit")
            next_header = stream.tell() + ((size + 511) // 512) * 512
            _require(next_header <= archive_size, "unsafe_archive", "Archive member is truncated")
            stream.seek(next_header)


def _extract_verified(archive_path: Path, staging: Path) -> tuple[dict, bytes]:
    _preflight_tar(archive_path)
    try:
        with tarfile.open(archive_path, "r:") as archive:
            members, seen, total = [], set(), 0
            for member in archive:
                _safe_archive_name(member.name)
                _require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE)
                         and not member.pax_headers, "unsafe_archive",
                         "Only plain regular archive members are permitted")
                _require(member.name not in seen, "duplicate_member", "Archive repeats a member")
                seen.add(member.name)
                _require(member.size >= 0, "unsafe_archive", "Archive member size is invalid")
                total += member.size
                _require(total <= MAX_BYTES + MAX_MANIFEST_BYTES
                         and len(seen) <= len(_archive_allowlist()) + 1,
                         "size_limit", "Archive exceeds migration limits")
                members.append(member)
            _require(seen == _archive_allowlist() | {"migration_manifest.json"},
                     "missing_member", "Archive content inventory is incomplete")
            header = next(member for member in members if member.name == "migration_manifest.json")
            _require(0 < header.size <= MAX_MANIFEST_BYTES, "size_limit",
                     "Migration manifest exceeds its size limit")
            with archive.extractfile(header) as stream:
                data = stream.read(MAX_MANIFEST_BYTES + 1)
            manifest = _decode_json(data)
            inventory = validate_manifest(manifest)
            for member in members:
                if member.name == "migration_manifest.json":
                    continue
                expected = inventory[member.name]
                _require(member.size == expected["bytes"], "member_hash_mismatch",
                         "Archive member byte count differs from its inventory")
                path = staging / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                digest, count = hashlib.sha256(), 0
                with archive.extractfile(member) as source, path.open("xb") as target:
                    for block in iter(lambda: source.read(CHUNK_BYTES), b""):
                        count += len(block)
                        digest.update(block)
                        target.write(block)
                _require(count == expected["bytes"] and digest.hexdigest() == expected["sha256"],
                         "member_hash_mismatch", "Archive content hash differs from its inventory")
            return manifest, data
    except (tarfile.TarError, EOFError) as exc:
        raise MigrationError("unsafe_archive", "Archive is malformed or compressed") from exc


def _restore_git(bundle: Path, destination: Path, manifest: dict) -> None:
    destination.mkdir()
    _git(destination, "init", "--quiet")
    _git(destination, "bundle", "verify", str(bundle))
    heads = _git(destination, "bundle", "list-heads", str(bundle)).decode().splitlines()
    _require(heads == [f"{manifest['code_base_commit']} {BUNDLE_REF}"],
             "wrong_baseline", "Git bundle must contain only the pinned baseline reference")
    _git(destination, "fetch", "--quiet", "--no-tags", str(bundle), BUNDLE_REF)
    _git(destination, "checkout", "--quiet", "--detach", manifest["code_base_commit"])
    _git(destination, "remote", "add", "origin", ORIGIN_URL)
    _verify_source_baseline(destination, manifest["code_base_commit"])
    _verify_repo(destination, manifest["code_base_commit"])


def _paths(workspace: Path) -> dict[str, Path]:
    return {"repo": workspace / "q15-execution/repo",
            "raw_dir": workspace / "q15-data/raw/BNCI2014_001",
            "epoch_dir": workspace / "q15-data/epochs",
            "manifest": workspace / "q15-migration/migration_manifest.json"}


def _verify_repo(repo: Path, base: str) -> None:
    _require(repo.is_dir() and not repo.is_symlink() and (repo / ".git").is_dir()
             and not (repo / ".git").is_symlink(), "destination_conflict",
             "Existing repository is not a regular Git checkout")
    _require(_git(repo, "rev-parse", "HEAD").decode().strip() == base
             and _git(repo, "remote", "get-url", "origin").decode().strip() == ORIGIN_URL,
             "destination_conflict", "Existing repository identity differs")
    expected = set()
    for entry in _git(repo, "ls-tree", "-r", "-z", base).split(b"\0"):
        if not entry:
            continue
        attributes, encoded_name = entry.split(b"\t", 1)
        mode, kind, object_hash = attributes.decode().split()
        name = encoded_name.decode()
        _require(kind == "blob" and mode in ("100644", "100755"), "unsafe_repository",
                 "Repository tree contains a symlink or nonregular object")
        expected.add(name)
        path = repo / name
        _regular(path)
        digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
                digest.update(block)
        _require(digest.hexdigest() == object_hash, "destination_conflict",
                 "Existing repository file content differs from the pinned baseline")
    actual = set()
    for directory, dirs, files in os.walk(repo, followlinks=False):
        if Path(directory) == repo:
            dirs[:] = [name for name in dirs if name != ".git"]
        _require(not any((Path(directory) / name).is_symlink() for name in dirs),
                 "unsafe_path", "Existing repository contains a symlinked directory")
        actual.update((Path(directory) / name).relative_to(repo).as_posix() for name in files)
    _require(actual == expected, "destination_conflict", "Existing repository contains extra files")
    _git(repo, "diff", "--quiet", "--cached", base, "--")


def validate_restored_paths(workspace, manifest: dict) -> bool:
    """Hash-check canonical data paths and the exact repository checkout."""
    inventory = validate_manifest(manifest)
    paths = _paths(Path(workspace).absolute())
    _verify_repo(paths["repo"], manifest["code_base_commit"])
    for root_key, prefix in (("epoch_dir", "epochs/"), ("raw_dir", "raw/BNCI2014_001/")):
        root = paths[root_key]
        expected = {name[len(prefix):]: row for name, row in inventory.items() if name.startswith(prefix)}
        _require(root.is_dir() and not root.is_symlink(), "destination_conflict",
                 "Canonical data directory is unavailable")
        actual = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            _require(not any((Path(directory) / name).is_symlink() for name in dirs),
                     "unsafe_path", "Existing data contains a symlinked directory")
            actual.update((Path(directory) / name).relative_to(root).as_posix() for name in files)
        _require(actual == set(expected), "destination_conflict", "Existing data file inventory differs")
        for name, row in expected.items():
            _require(_file_record(root / name, row["path"]) == row, "destination_conflict",
                     "Existing data content differs from the migration inventory")
    return True


def restore_bundle(archive, destination_workspace, expected_archive_sha256) -> dict:
    """Verify every byte before publishing the snapshot at the canonical paths."""
    archive, workspace = Path(archive).absolute(), Path(destination_workspace).absolute()
    _require(isinstance(expected_archive_sha256, str)
             and SHA256.fullmatch(expected_archive_sha256) is not None,
             "archive_hash_mismatch", "An expected archive SHA256 is required")
    _regular(archive)
    _require(archive.stat().st_size <= MAX_BYTES + 16 * MAX_MANIFEST_BYTES,
             "size_limit", "Archive exceeds its total byte limit")
    _require(sha256_file(archive) == expected_archive_sha256, "archive_hash_mismatch",
             "Archive SHA256 differs from the supplied custody hash")
    for parent in (workspace, *workspace.parents):
        _require(not parent.is_symlink(), "unsafe_path", "Destination parents must not be symlinked")
    paths = _paths(workspace)
    with tempfile.TemporaryDirectory(prefix="q15-restore-") as temporary:
        staging = Path(temporary)
        manifest, manifest_bytes = _extract_verified(archive, staging)
        staged_repo = staging / "checkout"
        _restore_git(staging / "repository.bundle", staged_repo, manifest)
        _epoch_sources(staged_repo, manifest["code_base_commit"], staging / "epochs")
        for name, expected in _bnci_inventory(staged_repo, manifest["code_base_commit"]).items():
            record = _file_record(staging / "raw/BNCI2014_001" / name,
                                  f"raw/BNCI2014_001/{name}")
            _require(all(record[key] == expected[key] for key in ("bytes", "sha256")),
                     "bnci_hash_mismatch", "Restored BNCI original differs from frozen Q8")
        # Recheck the archive after reading it to detect concurrent replacement.
        _require(sha256_file(archive) == expected_archive_sha256, "source_changed",
                 "Archive changed while restoration was being verified")
        targets = (paths["repo"], paths["epoch_dir"], paths["raw_dir"])
        custody_target = workspace / "q15-migration"
        for target in (*targets, custody_target):
            for part in (target, *target.parents):
                _require(not part.is_symlink(), "unsafe_path", "Destination paths must not be symlinked")
            _require(not target.exists() or target.is_dir(), "destination_conflict",
                     "A destination directory path is occupied by a file")
        custody_names = {path.name for path in custody_target.iterdir()} if custody_target.exists() else set()
        _require(custody_names <= {"jobs", "migration_manifest.json", "restore_receipt.json"},
                 "destination_conflict", "Existing custody directory contains unrelated files")
        jobs = custody_target / "jobs"
        _require(not jobs.exists() or jobs.is_dir(), "destination_conflict",
                 "Migration job directory path is occupied by a file")
        _require(not jobs.is_symlink(), "unsafe_path", "Migration job directory must not be symlinked")
        existing = [target for target in targets if target.exists() and any(target.iterdir())]
        if existing:
            _require(len(existing) == len(targets), "destination_conflict",
                     "A partially occupied destination cannot be overwritten")
            validate_restored_paths(workspace, manifest)
            _regular(paths["manifest"])
            _require(paths["manifest"].read_bytes() == manifest_bytes, "destination_conflict",
                     "Existing custody manifest differs")
            receipt_path = workspace / "q15-migration/restore_receipt.json"
            _regular(receipt_path)
            receipt = _decode_json(receipt_path.read_bytes())
            expected = _receipt(manifest, manifest_bytes, expected_archive_sha256, paths)
            _fields(receipt, {key: value for key, value in expected.items()
                              if key != "restored_at_utc"}, "destination_conflict")
            _require(set(receipt) - set(expected) <= TRANSPORT_RECEIPT_KEYS,
                     "destination_conflict", "Existing receipt schema differs")
            return receipt
        _require(not custody_names & {"migration_manifest.json", "restore_receipt.json"},
                 "destination_conflict", "A partially occupied custody directory cannot be overwritten")
        # All archive hashes and the source ledger have passed before these writes.
        # Stage on the destination filesystem so the final directory moves are atomic.
        workspace.mkdir(parents=True, exist_ok=True)
        publication = Path(tempfile.mkdtemp(prefix=".q15-publish-", dir=workspace))
        published = []
        try:
            for source, target in ((staged_repo, publication / "repo"),
                                   (staging / "epochs", publication / "epochs"),
                                   (staging / "raw/BNCI2014_001", publication / "bnci")):
                shutil.copytree(source, target)
            custody = publication / "custody"
            custody.mkdir()
            (custody / "migration_manifest.json").write_bytes(manifest_bytes)
            receipt = _receipt(manifest, manifest_bytes, expected_archive_sha256, paths)
            (custody / "restore_receipt.json").write_bytes(_json_bytes(receipt))
            for source, target in ((publication / "repo", paths["repo"]),
                                   (publication / "epochs", paths["epoch_dir"]),
                                   (publication / "bnci", paths["raw_dir"])):
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.rmdir()  # Refuses nonempty paths, including a concurrent writer.
                os.rename(source, target)
                published.append(target)
            custody_target.mkdir(parents=True, exist_ok=True)
            for name in ("migration_manifest.json", "restore_receipt.json"):
                target = custody_target / name
                # A hard link publishes a complete regular file atomically and
                # refuses to overwrite any concurrently created custody record.
                os.link(custody / name, target)
                published.append(target)
            return receipt
        except BaseException:
            for target in reversed(published):
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            raise
        finally:
            shutil.rmtree(publication, ignore_errors=True)


def _receipt(manifest: dict, manifest_bytes: bytes, archive_sha: str, paths: dict) -> dict:
    return {"schema_version": 1, "kind": f"{KIND}_restore",
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "archive_sha256": archive_sha, "code_base_commit": manifest["code_base_commit"],
            "scientific_revision": manifest["scientific_revision"],
            "origin_job_id": manifest["origin_job_id"], "origin_pod_id": manifest["origin_pod_id"],
            "source_fit_count": 15, "source_only_reuse": True, "paths_verified": True,
            "paths": {key: str(value) for key, value in paths.items()},
            "restored_at_utc": datetime.now(UTC).isoformat()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--repo", type=Path, default=Path("/workspace/q15-execution/repo"))
    export.add_argument("--epoch-dir", type=Path, default=Path("/workspace/q15-data/epochs"))
    export.add_argument("--bnci-dir", type=Path, default=Path("/workspace/q15-data/raw/BNCI2014_001"))
    export.add_argument("--output", "--out-path", type=Path, required=True)
    export.add_argument("--base-commit", default=BASE_COMMIT)
    export.add_argument("--origin-job-id", default=ORIGIN_JOB_ID)
    export.add_argument("--origin-pod-id", default=ORIGIN_POD_ID)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination-workspace", type=Path, default=Path("/workspace"))
    restore.add_argument("--expected-archive-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            result = export_bundle(args.repo, args.epoch_dir, args.bnci_dir, args.output,
                                   args.base_commit, args.origin_job_id, args.origin_pod_id)
        else:
            result = restore_bundle(args.archive, args.destination_workspace,
                                    args.expected_archive_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except MigrationError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": "operation_failed", "message": type(exc).__name__}),
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
