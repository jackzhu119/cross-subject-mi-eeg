"""Frozen PAPER1 official-source to R2 transfer only; no signal processing.

All raw bytes and runtime evidence stay outside the repository. A verified
small-object R2 probe gates every run, including resumed runs. Existing remote
objects are skipped only after a complete streaming SHA256 readback.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

COMMIT = "23aec28407468b5d3d4b9b15450e84dc616bfd54"
REPOSITORY = Path("/workspace/cross-subject-mi-eeg")
BUNDLE_REL = "research_runs/PAPER1_HPC_20261023"
DEFAULT_STATE = Path("/workspace/paper1-archive-state")
PREFIX = "paper1-hpc-20261023/frozen-inputs-v1"
EXPECTED = {"bnci": (18, 779873919), "yang": (312, 68044344823),
            "dreyer": (174, 2515343396)}
CHUNK = 8 * 1024 * 1024


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class TransferError(RuntimeError):
    def __init__(self, category, evidence=None):
        self.category = category
        self.evidence = evidence or {}
        super().__init__(category)


def safe_failure(error):
    if isinstance(error, TransferError):
        return {"category": error.category, **error.evidence}
    # These fields are numeric/type metadata, never exception messages or URLs.
    detail = {"error_class": type(error).__name__}
    status = getattr(error, "http_status", None)
    if not isinstance(status, int):
        status = getattr(error, "code", None)
    if isinstance(status, int) and 100 <= status <= 599:
        detail["http_status"] = status
    if isinstance(getattr(error, "evidence", None), dict):
        detail["failure_detail"] = error.evidence
    causes = []
    seen = {id(error)}
    cause = getattr(error, "__cause__", None)
    while isinstance(cause, BaseException) and id(cause) not in seen and len(causes) < 5:
        seen.add(id(cause))
        item = {"error_class": type(cause).__name__}
        status = getattr(cause, "http_status", getattr(cause, "code", None))
        if isinstance(status, int) and 100 <= status <= 599:
            item["http_status"] = status
        causes.append(item)
        cause = getattr(cause, "__cause__", None)
    if causes:
        detail["causes"] = causes
    return detail


def statuses(value):
    """Find typed HTTP status in safe nested adapter evidence."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "http_status" and isinstance(item, int):
                yield item
            elif isinstance(item, (dict, list)):
                yield from statuses(item)
    elif isinstance(value, list):
        for item in value:
            yield from statuses(item)


def git_output(repo, *arguments):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def frozen_preflight(repo=REPOSITORY):
    """Hash every tracked file in the fixed run package against the commit."""
    repo = Path(repo).resolve()
    if git_output(repo, "rev-parse", "HEAD").decode().strip() != COMMIT:
        raise TransferError("fixed_commit_mismatch")
    names = git_output(repo, "ls-tree", "-r", "--name-only", COMMIT, "--", BUNDLE_REL).decode().splitlines()
    if not names:
        raise TransferError("frozen_run_package_missing")
    hashes = {}
    for relative in names:
        path = repo / relative
        if path.is_symlink() or not path.is_file():
            raise TransferError("frozen_package_file_missing_or_symlink", {"path": relative})
        expected = hashlib.sha256(git_output(repo, "show", COMMIT + ":" + relative)).hexdigest()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise TransferError("frozen_package_hash_mismatch", {"path": relative})
        hashes[relative] = expected
    bundle = repo / BUNDLE_REL
    with (bundle / "download_entries.tsv").open(newline="") as stream:
        entries = list(csv.DictReader(stream, delimiter="\t"))
    if len(entries) != 504:
        raise TransferError("frozen_entry_count_mismatch")
    seen = set()
    for row in entries:
        path = row["path_under_raw"]
        if (path in seen or Path(path).is_absolute() or ".." in Path(path).parts
                or path.split("/", 1)[0] != row["dataset"]):
            raise TransferError("unsafe_or_duplicate_frozen_path")
        seen.add(path)
    for dataset, (count, size) in EXPECTED.items():
        rows = [r for r in entries if r["dataset"] == dataset]
        if len(rows) != count or sum(int(r["native_bytes"]) for r in rows) != size:
            raise TransferError("frozen_dataset_totals_mismatch", {"dataset": dataset})
    yang = [r for r in entries if r["dataset"] == "yang"]
    if (sum(int(r["compressed_bytes"]) for r in yang) != 43981251776
            or sum(bool(r["sha256"]) for r in yang) != 306
            or sum(bool(r["crc32"]) for r in yang) != 312):
        raise TransferError("frozen_yang_integrity_contract_mismatch")
    expected_lines = (bundle / "SHA256SUMS.expected").read_text().splitlines()
    checksum_map = dict(line.split(None, 1)[::-1] for line in expected_lines)
    checksum_map = {path.strip(): digest for path, digest in checksum_map.items()}
    if len(checksum_map) != 498 or checksum_map != {r["path_under_raw"]: r["sha256"] for r in entries if r["sha256"]}:
        raise TransferError("frozen_sha_manifest_disagrees")
    report = {"status": "frozen_preflight_verified", "commit": COMMIT,
              "package_files_hashed": len(hashes), "package_sha256": hashes,
              "input_count": 504, "native_bytes": 71339562138,
              "yang_selected_compressed_bytes": 43981251776,
              "python": sys.version.split()[0]}
    return entries, report


class Progress:
    def __init__(self, state, interval=45):
        self.state = Path(state)
        self.interval = interval
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.row = {"event": "transfer_progress", "started_at_utc": utc_now(),
                    "source_bytes_received_run": 0, "uploaded_bytes_run": 0,
                    "readback_bytes_run": 0, "completed_count": 0,
                    "completed_native_bytes": 0, "current_file": None, "phase": "initializing",
                    "status": "not_started"}

    def set(self, **values):
        with self.lock:
            self.row.update(values)

    def add(self, key, count):
        with self.lock:
            self.row[key] += count

    def emit(self):
        with self.lock:
            row = {**self.row, "observed_at_utc": utc_now()}
        with (self.state / "progress.jsonl").open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        atomic_json(self.state / "progress.json", row)
        atomic_json(self.state / "status.json", row)
        print(json.dumps(row, sort_keys=True), flush=True)

    def _run(self):
        while not self.stop.wait(self.interval):
            self.emit()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if hasattr(self, "thread"):
            self.thread.join(timeout=2)
        self.emit()


class Transfer:
    def __init__(self, state, entries, acquire, adapter, client, bucket, *, keep_local=False):
        self.state = Path(state).resolve()
        self.state.mkdir(parents=True, exist_ok=True)
        self.raw = self.state / "raw"
        if self.raw.is_symlink():
            raise TransferError("unsafe_raw_directory_symlink")
        self.raw.mkdir(exist_ok=True)
        self.entries = entries
        self.acquire, self.adapter = acquire, adapter
        self.client, self.bucket = client, bucket
        self.keep_local = keep_local
        self.records = {}
        ledger = self.state / "completion.jsonl"
        if ledger.exists():
            for number, line in enumerate(ledger.read_text().splitlines(), 1):
                try:
                    record = json.loads(line)
                except ValueError:
                    raise TransferError("completion_ledger_invalid", {"line": number}) from None
                if record.get("path_under_raw"):
                    self.records[record["path_under_raw"]] = record
        self.progress = Progress(self.state)
        self.write_manifest()

    def write_manifest(self):
        fields = ["dataset", "path_under_raw", "key", "source", "native_bytes",
                  "expected_sha256", "expected_crc32", "actual_sha256", "actual_crc32",
                  "status", "stream_readback_verified", "completed_at_utc"]
        temporary = self.state / "manifest.tsv.tmp"
        count = size = 0
        with temporary.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fields, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            for entry in self.entries:
                record = self.records.get(entry["path_under_raw"], {})
                row = {"dataset": entry["dataset"], "path_under_raw": entry["path_under_raw"],
                       "key": PREFIX + "/" + entry["path_under_raw"], "source": entry["download_entry"],
                       "native_bytes": entry["native_bytes"], "expected_sha256": entry["sha256"],
                       "expected_crc32": entry["crc32"], "status": "pending", **record}
                writer.writerow(row)
                if row["status"] == "archive_verified" and row.get("stream_readback_verified"):
                    count += 1
                    size += int(entry["native_bytes"])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.state / "manifest.tsv")
        self.progress.set(completed_count=count, completed_native_bytes=size)
        atomic_json(self.state / "summary.json", {"updated_at_utc": utc_now(), "commit": COMMIT,
                    "prefix": PREFIX, "total_inputs": len(self.entries), "completed_count": count,
                    "completed_native_bytes": size, "pending_or_failed_count": len(self.entries) - count,
                    "complete": count == len(self.entries)})

    def record(self, entry, **values):
        row = {"path_under_raw": entry["path_under_raw"], "commit": COMMIT,
               "native_bytes": int(entry["native_bytes"]), "source": entry["download_entry"],
               "key": PREFIX + "/" + entry["path_under_raw"], "expected_sha256": entry["sha256"],
               "expected_crc32": entry["crc32"], "recorded_at_utc": utc_now(), **values}
        with (self.state / "completion.jsonl").open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.records[entry["path_under_raw"]] = row
        self.write_manifest()

    def callback(self):
        previous = {}
        def update(stage, cumulative):
            if stage in ("upload", "readback"):
                delta = cumulative - previous.get(stage, 0)
                if delta < 0:
                    raise TransferError("nonmonotonic_archive_progress")
                self.progress.add("uploaded_bytes_run" if stage == "upload" else "readback_bytes_run", delta)
                previous[stage] = cumulative
            self.progress.set(phase=stage, current_stage_bytes=cumulative)
        return update

    def resume_remote(self, entry):
        old = self.records.get(entry["path_under_raw"], {})
        if (old.get("status") != "archive_verified" or old.get("commit") != COMMIT
                or old.get("native_bytes") != int(entry["native_bytes"])
                or old.get("key") != PREFIX + "/" + entry["path_under_raw"]
                or old.get("expected_sha256") != entry["sha256"]
                or old.get("expected_crc32") != entry["crc32"]
                or entry["sha256"] and old.get("actual_sha256") != entry["sha256"]
                or entry["crc32"] and old.get("actual_crc32") != entry["crc32"]
                or not re.fullmatch(r"[0-9a-f]{64}", old.get("actual_sha256", ""))):
            return False
        callback = self.callback()
        result = self.adapter.verify_remote(self.client, self.bucket, old["key"],
                    expected_size=int(entry["native_bytes"]), expected_sha256=old["actual_sha256"],
                    progress=lambda n: callback("readback", n))
        if result["status"] == "remote_verified":
            self.record(entry, status="archive_verified", actual_sha256=old["actual_sha256"],
                        actual_crc32=old.get("actual_crc32"), stream_readback_verified=True,
                        completed_at_utc=result["completed_at_utc"], resumed_existing_remote=True,
                        readback_evidence=result)
            return True
        self.record(entry, status="remote_reverification_failed", stream_readback_verified=False,
                    readback_evidence=result)
        if set(statuses(result)) & {401, 403}:
            raise TransferError("r2_authorization_denied", result)
        # Only confirmed absence permits a replacement. Other failures retain data.
        if 404 in set(statuses(result)):
            return False
        raise TransferError("remote_reverification_failed", result)

    def ensure_space(self, entry):
        free = shutil.disk_usage(self.raw).free
        needed = 2 * int(entry["native_bytes"]) + 1024 ** 3
        if free < needed:
            raise TransferError("insufficient_local_disk", {"available_bytes": free, "required_bytes": needed})

    def upload(self, entry, target):
        self.progress.set(phase="local_verification")
        result = self.adapter.archive_file(self.client, self.bucket, target,
                    PREFIX + "/" + entry["path_under_raw"], expected_size=int(entry["native_bytes"]),
                    expected_sha256=entry["sha256"] or None, expected_crc32=entry["crc32"] or None,
                    progress=self.callback())
        passed = (result["status"] == "archive_verified" and result.get("safe_to_remove_local") is True
                  and result.get("stream_readback_verified") is True)
        local = result.get("local", {})
        self.record(entry, status="archive_verified" if passed else "archive_failed",
                    actual_sha256=local.get("sha256"), actual_crc32=local.get("crc32"),
                    stream_readback_verified=passed, completed_at_utc=result.get("completed_at_utc"),
                    archive_evidence=result)
        if not passed:
            category = "r2_authorization_denied" if set(statuses(result)) & {401, 403} else "r2_archive_failed"
            raise TransferError(category, result)
        if not self.keep_local:
            resolved = target.resolve()
            if not resolved.is_relative_to(self.raw.resolve()) or target.is_symlink():
                raise TransferError("unsafe_local_cleanup_path")
            try:
                target.unlink()
            except OSError as error:
                # The verified remote completion remains valid even when local
                # cleanup fails. Preserve its full acceptance evidence.
                atomic_json(self.state / "local_cleanup_failure.json", {
                    "path_under_raw": entry["path_under_raw"], **safe_failure(error)})

    def run(self):
        self.progress.set(status="running", phase="r2_probe")
        self.progress.emit()
        self.progress.start()
        try:
            probe = self.adapter.probe(self.client, self.bucket, prefix=PREFIX)
            atomic_json(self.state / "r2_probe.json", probe)
            if probe.get("status") != "probe_verified":
                raise TransferError("r2_probe_failed", probe)
            self.acquire.configure_download_trust()
            failures = []
            for dataset in ("yang", "bnci", "dreyer"):
                try:
                    self.dataset(dataset)
                except Exception as error:
                    detail = safe_failure(error)
                    failures.append({"dataset": dataset, "failure": detail})
                    atomic_json(self.state / "failures.json", failures)
                    # Any R2 or unexplained error stops transport; source denials
                    # stop this dataset and allow independent official datasets.
                    if isinstance(error, TransferError) or not (set(statuses(detail)) & {401, 403}):
                        raise
            if failures:
                raise TransferError("official_source_datasets_incomplete", {"failures": failures})
            self.progress.set(status="complete", phase="complete", current_file=None)
        except Exception as error:
            self.progress.set(status="blocked", failure=safe_failure(error))
            raise
        finally:
            self.write_manifest()
            self.progress.close()

    def dataset(self, dataset):
        root = self.raw / dataset
        if root.is_symlink():
            raise TransferError("unsafe_dataset_directory_symlink", {"dataset": dataset})
        root.mkdir(exist_ok=True)
        entries = [r for r in self.entries if r["dataset"] == dataset]
        reader = archive = None
        original_open = self.acquire.open_object
        runner = self
        @contextmanager
        def counted_open(*args, **kwargs):
            with original_open(*args, **kwargs) as response:
                class Response:
                    def __getattr__(self, name):
                        return getattr(response, name)
                    def read(self, count=-1):
                        block = response.read(count)
                        runner.progress.add("source_bytes_received_run", len(block))
                        return block
                yield Response()
        self.acquire.open_object = counted_open
        if dataset == "yang":
            inventory, pins = self.acquire.yang_pins()
        else:
            inventory = json.loads((self.acquire.VENDOR / "config" / (dataset + "_manifest.json")).read_text())
            pins = inventory["files"]
        by_path = {row["path"]: row for row in pins}
        try:
            for entry in entries:
                self.progress.set(current_file=entry["path_under_raw"], phase="resume_check", current_stage_bytes=0)
                try:
                    if self.resume_remote(entry):
                        continue
                    self.ensure_space(entry)
                    relative = entry["path_under_raw"].split("/", 1)[1]
                    row = by_path[relative]
                    target = self.acquire.safe_child(root, relative)
                    self.progress.set(phase="download")
                    if dataset == "yang":
                        if self.acquire.verified_existing(root, row) is None:
                            if not self.acquire._compressed_ready(root, row, inventory):
                                if reader is None:
                                    reader, archive, attestation, directory = self.acquire.open_yang_archive()
                                    if self.acquire._archive_identity(attestation) != self.acquire._archive_identity(inventory):
                                        raise TransferError("yang_live_directory_identity_mismatch")
                                    atomic_json(self.state / "yang_directory_attestation.json", attestation)
                                    (self.state / "yang_central_directory.bin").write_bytes(directory)
                                    original_get = reader._get_range
                                    def counted_get(start, count):
                                        before = reader.bytes_received
                                        try:
                                            return original_get(start, count)
                                        finally:
                                            self.progress.add("source_bytes_received_run", reader.bytes_received - before)
                                    self.progress.add("source_bytes_received_run", reader.bytes_received)
                                    reader._get_range = counted_get
                                    members = {i.filename: i for i in self.acquire.selected_yang_members(archive)}
                                self.acquire._download_yang_compressed(reader, members[row["path"]], row, root, inventory=inventory)
                            self.progress.set(phase="native_crc_sha_verification")
                            self.acquire._publish_yang_compressed(row, root)
                    else:
                        self.acquire.transfer_object(root, row, nemar=dataset == "dreyer", attempts=1)
                    self.upload(entry, target)
                except Exception as error:
                    self.record(entry, status="failed", stream_readback_verified=False, failure=safe_failure(error))
                    raise
        finally:
            self.acquire.open_object = original_open
            if archive is not None:
                archive.close()
            if reader is not None:
                reader.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Preflight without any network operation")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--keep-local", action="store_true")
    args = parser.parse_args(argv)
    if args.offline and not args.preflight:
        parser.error("--offline is available only with --preflight")
    state = args.state_dir.resolve()
    if not state.is_relative_to(Path("/workspace")) or state.is_relative_to(REPOSITORY):
        parser.error("State must be outside the checkout and beneath /workspace")
    state.mkdir(parents=True, exist_ok=True)
    try:
        with (state / "transfer.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise TransferError("another_transfer_holds_lock") from None
            entries, report = frozen_preflight()
            report["disk_free_bytes"] = shutil.disk_usage(state).free
            atomic_json(state / "frozen_preflight.json", report)
            # Always publish the complete inventory, including pending rows;
            # offline preflight must not make an empty archive look complete.
            Transfer(state, entries, None, None, None, None)
            if args.offline:
                print(json.dumps({k: v for k, v in report.items() if k != "package_sha256"}, sort_keys=True))
                return 0
            adapter = importlib.import_module("r2_archive")
            client, bucket = adapter.environment_client()
            if args.preflight:
                probe = adapter.probe(client, bucket, prefix=PREFIX)
                atomic_json(state / "r2_probe.json", probe)
                print(json.dumps(probe, sort_keys=True))
                return 0 if probe.get("status") == "probe_verified" else 2
            sys.path.insert(0, str(REPOSITORY / BUNDLE_REL))
            acquire = importlib.import_module("hpcmi.acquire")
            Transfer(state, entries, acquire, adapter, client, bucket, keep_local=args.keep_local).run()
            return 0
    except Exception as error:
        row = {"status": "transfer_stopped", "observed_at_utc": utc_now(), **safe_failure(error)}
        atomic_json(state / "last_failure.json", row)
        try:
            current = json.loads((state / "status.json").read_text())
        except (OSError, ValueError):
            current = {}
        atomic_json(state / "status.json", {**current, "status": "blocked",
                    "observed_at_utc": utc_now(), "failure": safe_failure(error)})
        print(json.dumps(row, sort_keys=True), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
