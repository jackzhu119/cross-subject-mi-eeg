"""Resumable Q15 cloud execution, with immutable gates before every fit/prediction.

Credentials remain in the inherited process environment. Only explicit public
artifact allowlists enter GitHub. Raw MAT, epoch NPZ and secret files never do.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
MAX_PUBLIC_FILE = 40 * 1024**2
MAX_PUBLIC_BATCH = 150 * 1024**2
JOB_RE = re.compile(r"[A-Za-z0-9_-]{1,80}")
PINNED_PATHS = ["scripts", "src", "pyproject.toml", "requirements-paper-cu128.txt",
                "requirements-q15-runtime.txt",
                "research_runs/PAPER_RELEASE_20260927", "research_runs/Q14-E001/CONFIG.json",
                "research_runs/Q8-E001/results/source_files.json",
                "research_runs/Q8-E001/results/trial_metadata.csv",
                "research_runs/Q15-PREPARATION/transport_inventory.json",
                "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json",
                "research_runs/Q15-EXECUTION-20261003/INDEPENDENT_METHOD_REVIEW.md",
                "research_runs/Q15-EXECUTION-20261003/evidence"]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class FullJobError(RuntimeError):
    def __init__(self, code):
        self.safe_code = code
        super().__init__(code)


def safe_code(exc):
    if isinstance(exc, FullJobError):
        return exc.safe_code
    value = getattr(exc, "safe_code", None)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
        return value
    if isinstance(exc, urllib.error.HTTPError):
        return "github_http_" + str(exc.code)
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z0-9_]{1,64}", name) else "unexpected_error"


def startup_failure(exc):
    previous_fits_possible = (ROOT / "results/Q15-E005/source").exists()
    return {"status": "resume_blocked" if previous_fits_possible else "not_started",
            "error_code": safe_code(exc),
            "fits_started": None if previous_fits_possible else 0,
            "target_fits": 0}


def now():
    return datetime.now(UTC).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".q15-status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def git(*arguments):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("GH_TOKEN", "GITHUB_TOKEN", "RUNPOD_API_KEY")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", "-C", str(ROOT), *arguments],
                            capture_output=True,
                            env=environment, check=False)
    if result.returncode:
        raise FullJobError("local_git_operation_failed")
    return result.stdout


def github_request(token, method, path, payload=None):
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    request = urllib.request.Request("https://api.github.com/" + path, method=method, data=data,
        headers={"Authorization": "Bearer " + token, "User-Agent": "q15-full-cloud/20261003",
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read(64 * 1024**2)
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise FullJobError("github_http_" + str(exc.code)) from None
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise FullJobError("github_network_unavailable") from None
        time.sleep(attempt + 1)
    raise FullJobError("github_retry_exhausted")


def publication_path(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise FullJobError("public_artifact_path_unsafe")
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    if any(part in ("raw", "epochs", ".git", ".venv", "credentials", ".q15-cloud")
           for part in PurePosixPath(relative).parts):
        raise FullJobError("raw_or_private_publication_rejected")
    if path.suffix not in (".json", ".csv", ".pt", ".joblib", ".md", ".py", ".txt", ".toml"):
        raise FullJobError("public_artifact_extension_rejected")
    if path.stat().st_size > MAX_PUBLIC_FILE:
        raise FullJobError("public_artifact_too_large")
    return relative


class Publisher:
    """Atomic Git database commits, non-force branch updates, full blob readback."""
    def __init__(self, token, branch, state_path, api=github_request):
        if not re.fullmatch(r"q15/run-[A-Za-z0-9_-]{1,80}", branch):
            raise FullJobError("publication_branch_invalid")
        self.token, self.branch, self.state_path, self.api = token, branch, Path(state_path), api
        self.prefix = "repos/" + REPOSITORY + "/"
        self.head = git("rev-parse", "HEAD").decode().strip()
        self.receipts = []
        if self.state_path.is_file():
            saved = json.loads(self.state_path.read_text())
            if saved.get("branch") != branch:
                raise FullJobError("publication_resume_branch_mismatch")
            self.receipts = saved.get("receipts", [])
            if not isinstance(self.receipts, list):
                raise FullJobError("publication_resume_state_invalid")
            for receipt in self.receipts:
                if (not isinstance(receipt, dict) or receipt.get("readback_verified") is not True
                        or receipt.get("branch") != branch
                        or not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("commit", "")))):
                    raise FullJobError("publication_resume_receipt_invalid")
            if self.receipts and self.receipts[-1]["commit"] != self.head:
                raise FullJobError("publication_resume_local_head_mismatch")

    def verify_access(self):
        repo = self.api(self.token, "GET", self.prefix.rstrip("/"))
        if repo.get("full_name") != REPOSITORY or repo.get("permissions", {}).get("push") is not True:
            raise FullJobError("github_repository_write_access_unverified")
        if self.receipts:
            remote = self.api(self.token, "GET", self.prefix + "git/ref/heads/" + self.branch)
            if remote.get("object", {}).get("sha") != self.head:
                raise FullJobError("publication_resume_remote_head_mismatch")

    def commit(self, paths, message):
        paths = sorted({Path(path) for path in paths})
        if not paths:
            raise FullJobError("publication_empty_allowlist")
        content, total = {}, 0
        for path in paths:
            relative = publication_path(path)
            body = path.read_bytes()
            for secret_name in ("GH_TOKEN", "GITHUB_TOKEN", "RUNPOD_API_KEY",
                                "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
                secret = os.environ.get(secret_name, "")
                if secret and secret.encode() in body:
                    raise FullJobError("credential_in_public_artifact_rejected")
            total += len(body)
            content[relative] = body
        if total > MAX_PUBLIC_BATCH:
            raise FullJobError("public_batch_too_large")
        current = self.api(self.token, "GET", self.prefix + "git/commits/" + self.head)
        entries, hashes, blob_ids = [], {}, {}
        for relative, body in sorted(content.items()):
            blob = self.api(self.token, "POST", self.prefix + "git/blobs",
                            {"content": base64.b64encode(body).decode(), "encoding": "base64"})
            entries.append({"path": relative, "mode": "100644", "type": "blob", "sha": blob["sha"]})
            hashes[relative] = hashlib.sha256(body).hexdigest()
            blob_ids[relative] = blob["sha"]
        tree = self.api(self.token, "POST", self.prefix + "git/trees",
                        {"base_tree": current["tree"]["sha"], "tree": entries})
        commit = self.api(self.token, "POST", self.prefix + "git/commits",
                          {"message": message, "tree": tree["sha"], "parents": [self.head]})["sha"]
        ref_path = self.prefix + "git/refs/heads/" + self.branch
        try:
            previous = self.api(self.token, "GET", self.prefix + "git/ref/heads/" + self.branch)
        except FullJobError as exc:
            if exc.safe_code != "github_http_404":
                raise
            self.api(self.token, "POST", self.prefix + "git/refs",
                     {"ref": "refs/heads/" + self.branch, "sha": commit})
        else:
            if previous.get("object", {}).get("sha") != self.head:
                raise FullJobError("github_branch_concurrent_change")
            self.api(self.token, "PATCH", ref_path, {"sha": commit, "force": False})
        remote = self.api(self.token, "GET", self.prefix + "git/ref/heads/" + self.branch)
        if remote.get("object", {}).get("sha") != commit:
            raise FullJobError("github_commit_ref_readback_failed")
        committed = self.api(self.token, "GET", self.prefix + "git/commits/" + commit)
        if committed.get("tree", {}).get("sha") != tree["sha"]:
            raise FullJobError("github_commit_tree_readback_failed")
        inventory = self.api(self.token, "GET", self.prefix + "git/trees/" + tree["sha"] + "?recursive=1")
        if inventory.get("truncated") is not False or not isinstance(inventory.get("tree"), list):
            raise FullJobError("github_commit_tree_inventory_incomplete")
        mappings = {item.get("path"): item for item in inventory["tree"]}
        for relative, blob_id in blob_ids.items():
            item = mappings.get(relative, {})
            if item.get("type") != "blob" or item.get("mode") != "100644" or item.get("sha") != blob_id:
                raise FullJobError("github_commit_artifact_mapping_mismatch")
        for relative, digest in hashes.items():
            readback = self.api(self.token, "GET", self.prefix + "git/blobs/" + blob_ids[relative])
            if readback.get("encoding") != "base64":
                raise FullJobError("github_blob_readback_encoding_invalid")
            body = base64.b64decode(readback["content"])
            if hashlib.sha256(body).hexdigest() != digest:
                raise FullJobError("github_blob_readback_hash_mismatch")
        git("fetch", "--quiet", "origin", commit)
        # Change only HEAD/index. Raw arrays and uncommitted output files are preserved.
        git("reset", "--mixed", commit)
        if git("rev-parse", "HEAD").decode().strip() != commit:
            raise FullJobError("local_committed_gate_readback_failed")
        for relative, digest in hashes.items():
            if hashlib.sha256(git("show", "HEAD:" + relative)).hexdigest() != digest:
                raise FullJobError("local_committed_artifact_mismatch")
        self.head = commit
        receipt = {"commit": commit, "branch": self.branch, "readback_verified": True,
                   "artifact_sha256": hashes, "updated_at_utc": now(),
                   "url": "https://github.com/" + REPOSITORY + "/commit/" + commit}
        self.receipts.append(receipt)
        atomic_json(self.state_path, {"branch": self.branch, "receipts": self.receipts})
        return receipt


def workspace_allocated_bytes(root):
    total, seen = 0, set()
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
        for name in files:
            info = (Path(directory) / name).lstat()
            if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in seen:
                seen.add((info.st_dev, info.st_ino))
                total += info.st_blocks * 512
    return total


def preflight(args, publisher):
    from q15_cloud.q15_cloud_job import current_pod_id, runpod_request
    if sys.version_info[:2] != (3, 12):
        raise FullJobError("pinned_python_312_runtime_unavailable")
    if not os.environ.get("GH_TOKEN") or not os.environ.get("RUNPOD_API_KEY"):
        raise FullJobError("github_and_runpod_credentials_required")
    if git("remote", "get-url", "origin").decode().strip() != "https://github.com/" + REPOSITORY + ".git":
        raise FullJobError("repository_origin_mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise FullJobError("code_revision_invalid")
    # New receipts/output commits may advance HEAD; executable/protocol bytes stay pinned.
    if git("diff", args.revision, "--", *PINNED_PATHS):
        raise FullJobError("pinned_execution_code_or_contract_changed")
    if git("ls-files", "--others", "--exclude-standard", "--", *PINNED_PATHS):
        raise FullJobError("untracked_execution_code_or_contract_rejected")
    for name in ("raw_dir", "bnci_dir", "epoch_dir", "control_dir"):
        path = Path(getattr(args, name))
        if not path.is_absolute() or path.resolve().is_relative_to(ROOT.resolve()):
            raise FullJobError("private_data_or_control_directory_unsafe")
    publisher.verify_access()
    pod_id = current_pod_id()
    pod = runpod_request(os.environ["RUNPOD_API_KEY"], pod_id)
    capacity = pod.get("disk_capacity_gb")
    if not isinstance(capacity, (int, float)) or isinstance(capacity, bool) or not math.isfinite(capacity):
        raise FullJobError("workspace_purchased_quota_unverified")
    # df reports a shared storage pool. Use purchased quota minus actual allocation.
    allocated = workspace_allocated_bytes(Path(args.workspace))
    needed = 25 * 1024**3
    if capacity * 10**9 - allocated < needed:
        raise FullJobError("workspace_quota_headroom_below_25_gib")
    import torch
    if torch.__version__ != "2.8.0+cu128" or torch.version.cuda != "12.8" or not torch.cuda.is_available():
        raise FullJobError("pinned_cuda_runtime_unavailable")
    if importlib.metadata.version("torchaudio") != "2.8.0+cu128":
        raise FullJobError("pinned_torchaudio_runtime_unavailable")
    requirements = ROOT / "requirements-q15-runtime.txt"
    versions = {}
    for line in requirements.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
        if match is None:
            raise FullJobError("runtime_requirement_not_exact_pin")
        name, expected = match.groups()
        actual = importlib.metadata.version(name)
        if actual != expected:
            raise FullJobError("pinned_runtime_distribution_mismatch")
        versions[name] = actual
    if torch.ones(1, device="cuda").item() != 1:
        raise FullJobError("gpu_computation_probe_failed")
    # Exercise the exact two neural architectures on zeros before any raw EEG
    # loading, optimizer construction, fit, or scientific prediction.
    source = importlib.import_module("q15_source")
    config = source.derive_config()
    with torch.inference_mode():
        for name in source.MODELS:
            model = source._build_model(name, config, torch.device("cuda")).eval()
            shape = (2, 21, 320) if name == "BROAD_EEGNET" else (2, 2, 21, 320)
            output = model(torch.zeros(shape, device="cuda"))
            if tuple(output.shape) != (2, 2) or not torch.isfinite(output).all().item():
                raise FullJobError("cuda_architecture_zero_input_probe_failed")
            del model, output
    torch.cuda.empty_cache()
    return {"pod_id": pod_id, "disk_capacity_gb": capacity,
            "allocated_workspace_bytes": allocated, "gpu_computation_verified": True,
            "torch_version": torch.__version__, "runtime_cuda": torch.version.cuda,
            "runtime_distributions": versions,
            "cuda_zero_input_architecture_probe_verified": True,
            "eeg_loaded_for_runtime_probe": False}


def source_artifacts(report):
    records = report.get("artifact_sha256")
    if not isinstance(records, dict) or not records:
        raise FullJobError("source_validator_artifact_allowlist_missing")
    paths = []
    for relative, digest in records.items():
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not relative.startswith("results/Q15-E005/"):
            raise FullJobError("source_artifact_allowlist_unsafe")
        path = ROOT / relative
        publication_path(path)
        if sha(path) != digest:
            raise FullJobError("source_validated_artifact_hash_changed")
        paths.append(path)
    paths.append(ROOT / "results/Q15-E005/source_validation.json")
    return paths


def external_artifacts(report):
    # Independent validator supplies the exact JSON/CSV inventory it replayed.
    records = report.get("artifact_sha256")
    if not isinstance(records, dict) or not records:
        raise FullJobError("external_validator_artifact_allowlist_missing")
    paths = []
    for relative, digest in records.items():
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not relative.startswith("results/Q15-EXTERNAL/"):
            raise FullJobError("external_artifact_allowlist_unsafe")
        path = ROOT / relative
        if path.suffix not in (".json", ".csv", ".md"):
            raise FullJobError("external_array_publication_rejected")
        publication_path(path)
        if sha(path) != digest:
            raise FullJobError("external_validated_artifact_hash_changed")
        paths.append(path)
    paths.append(ROOT / "results/Q15-EXTERNAL/validation_report.json")
    return paths


def run(args, publisher, job):
    # An interrupted fit has an unknown count until independent validation.
    # Never overwrite a resumed run's progress with a claim of zero fits.
    prior_path = job / "job_status.json"
    prior = json.loads(prior_path.read_text()) if prior_path.is_file() else {}
    resumed_fitting = (prior.get("source_fit_execution_started") is True
                       or (ROOT / "results/Q15-E005/source").exists())
    state = {"schema_version": 1, "job_id": args.job_id, "supervisor_pid": os.getpid(),
             "status": "preflight_running",
             "fits_started": None if resumed_fitting else 0, "target_fits": 0,
             "source_fit_execution_started": resumed_fitting,
             "predictions_computed": bool(prior.get("predictions_computed", False)),
             "scientific_validation_passed": False, "updated_at_utc": now()}
    status_path = job / "job_status.json"
    public_status = ROOT / "research_runs/Q15-EXECUTION-20261003/jobs" / args.job_id / "job_status.json"

    def stage(name, **fields):
        state.update({"status": name, "updated_at_utc": now(), **fields})
        atomic_json(status_path, state)
        atomic_json(public_status, state)
        print(json.dumps({"stage": name, "fits_started": state["fits_started"],
                          "target_fits": 0, "updated_at_utc": state["updated_at_utc"]}), flush=True)

    pod_verified = False
    try:
        stage("preflight_running")
        preflight_result = preflight(args, publisher)
        pod_verified = True
        stage("preflight_passed", startup_verified=True, **preflight_result)
        preparation = importlib.import_module("q15_cloud.q15_prepare")
        provenance = json.loads((ROOT / "research_runs/Q8-E001/results/source_files.json").read_text())
        if len(provenance) != 18:
            raise FullJobError("bnci_source_inventory_invalid")
        stage("bnci_originals_verifying")
        originals = [preparation.fetch_bnci(row, Path(args.bnci_dir)) for row in provenance]
        source_receipt = public_status.parent / "bnci_source_receipt.json"
        atomic_json(source_receipt, {"schema_version": 1, "files": originals,
                                    "n_files": 18, "target_fits": 0,
                                    "fits_started": state["fits_started"]})
        stage("bnci_raw_metadata_auditing")
        context = importlib.import_module("mi_eeg.data.q15_context")
        source_audit = context.audit_bnci_source(Path(args.bnci_dir))
        if (source_audit.get("status") != "source_metadata_passed_non_authorizing"
                or source_audit.get("n_files") != 18
                or source_audit.get("target_fits") != 0
                or source_audit.get("source_training_authorized") is not False):
            raise FullJobError("bnci_raw_metadata_audit_not_passed")
        source_audit_path = public_status.parent / "bnci_metadata_audit.json"
        atomic_json(source_audit_path, source_audit)
        stage("real_external_metadata_auditing")
        real = importlib.import_module("q15_real_metadata")
        source = importlib.import_module("q15_source")
        manifests = real.build_manifests(Path(args.raw_dir), ROOT / "results/Q15-METADATA")
        if set(manifests) != {"Cho2017", "Lee2019_MI"}:
            raise FullJobError("both_real_cohort_manifests_required")
        receipts = {}
        for dataset, manifest in manifests.items():
            manifest = Path(manifest)
            receipt = real.audit_inventory(manifest)
            if (receipt.get("status") != "metadata_passed_non_authorizing"
                    or receipt.get("target_fits") != 0
                    or receipt.get("synthetic_fixture") is not False
                    or receipt.get("source_training_authorized") is not False
                    or receipt.get("external_prediction_authorized") is not False):
                raise FullJobError("real_metadata_audit_not_passed")
            receipts[dataset] = Path(source.AUDIT_RECEIPTS[dataset])
            atomic_json(receipts[dataset], receipt)
        stage("real_audits_passed_before_freeze", raw_metadata_audits_passed=True,
              physical_voltage_calibration_verified=False,
              analysis_input_unit_convention="native_numeric_as_microvolts")
        # Include every byte-level protocol/dependency input in this first
        # pre-fit publication; the next commit contains only the prepared freeze.
        protocol_paths = [source.CONTRACT, source.CONTRACT_CHECKER, source.Q14_CONFIG,
                          source.Q8_SOURCE_PROVENANCE, source.DEPENDENCY_SPEC,
                          source.BNCI_LOADER, source.EEGNET_HELPER, source.METADATA_AUDITOR,
                          source.SOURCE_SCRIPT, Path(source.q14_source.__file__),
                          ROOT / "requirements-q15-runtime.txt",
                          ROOT / "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json",
                          ROOT / "scripts/q15_real_metadata.py",
                          ROOT / "scripts/q15_preprocess_external.py",
                          ROOT / "src/mi_eeg/data/q15_context.py",
                          ROOT / "src/mi_eeg/models/q15_csp.py"]
        publisher.commit([source_receipt, source_audit_path, public_status, *protocol_paths,
                          *map(Path, manifests.values()), *receipts.values()],
                         "Audit all Q15 originals before source fitting: " + args.job_id)
        stage("pre_fit_freeze_preparing")
        freeze = source.prepare_freeze()
        publisher.commit([freeze, public_status], "Freeze Q15 preprocessing before all source fits: " + args.job_id)
        source._verify_committed_freeze()
        stage("source_fitting", preprocessing_contract_frozen=True,
              source_fit_execution_started=True, fits_started=None,
              fits_count_status="pending_independent_source_validation")
        source.run_source(Path(args.bnci_dir), "cuda")
        stage("independent_source_validation_running")
        validator = importlib.import_module("q15_validate_source")
        validation = validator.validate_source()
        if validation.get("passed") is not True or validation.get("deep_fit_count") != 14 or validation.get("shallow_fit_count") != 1:
            raise FullJobError("independent_source_validation_not_passed")
        stage("source_validated", fits_started=15, fits_count_status="independently_verified_complete",
              deep_fit_count=14, shallow_fit_count=1)
        publisher.commit([*source_artifacts(validation), public_status],
                         "Publish independently validated Q15 source checkpoints: " + args.job_id)
        stage("external_epoch_preparation_no_predictions")
        preprocess = importlib.import_module("q15_preprocess_external")
        epoch_manifests = preprocess.prepare_epochs(receipts, Path(args.epoch_dir))
        if set(epoch_manifests) != set(receipts):
            raise FullJobError("both_complete_epoch_manifests_required")
        # Manifests are tiny provenance only; array paths point outside the public repository.
        tracked_manifests = {}
        for dataset, path in epoch_manifests.items():
            checked = preprocess.validate_epoch_manifest(Path(path))
            target = ROOT / "results/Q15-EXTERNAL/manifests" / (dataset + ".json")
            atomic_json(target, checked)
            # Validate the exact public manifest bytes before the freeze.
            if preprocess.validate_epoch_manifest(target) != checked:
                raise FullJobError("published_epoch_manifest_replay_mismatch")
            tracked_manifests[dataset] = target
        publisher.commit([*tracked_manifests.values(), public_status],
                         "Commit Q15 epoch provenance before external inference: " + args.job_id)
        external = importlib.import_module("q15_external")
        stage("inference_freeze_preparing_no_predictions")
        inference_freeze = external.prepare_freeze(tracked_manifests)
        publisher.commit([inference_freeze, public_status],
                         "Freeze Q15 source checkpoints and external inference before predictions: " + args.job_id)
        external.verify_freeze(tracked_manifests)
        stage("external_inference_running", inference_contract_frozen=True)
        external.run_external(tracked_manifests, "cuda")
        stage("independent_raw_prediction_replay_running", predictions_computed=True)
        independent = importlib.import_module("q15_validate_external")
        result = independent.validate_external(tracked_manifests, device_name="cuda", write_report=True)
        if result.get("passed") is not True or result.get("target_fits") != 0:
            raise FullJobError("independent_external_validation_not_passed")
        stage("completed_with_calibration_limitations", scientific_validation_passed=True,
              calibration_limitations=["raw_voltage_calibration_not_independently_verified",
                                       "cho_original_hardware_reference_not_verified",
                                       "hardware_cue_latency_not_verified"],
              shutdown_status="pending_verified_publication_then_stop")
        publisher.commit([*external_artifacts(result), public_status],
                         "Complete Q15 with independently replayed external results and calibration limitations: " + args.job_id)
    except Exception as exc:  # noqa: BLE001 - redact every failure before public status
        failed_stage = state["status"]
        stage("failed_or_blocked", error_code=safe_code(exc), failed_stage=failed_stage,
              scientific_validation_passed=False,
              shutdown_status="pending_verified_failure_publication_then_stop")
        try:
            publisher.commit([public_status], "Record Q15 execution failure without false completion: " + args.job_id)
        except Exception as backup_exc:  # noqa: BLE001 - failed backup forbids a stop
            stage("failed_backup_manual_attention_required", backup_error_code=safe_code(backup_exc),
                  shutdown_status="not_requested_backup_unverified")
            return 1
    if not pod_verified:
        stage("manual_attention_required", shutdown_status="not_requested_pod_identity_unverified")
        return 1
    try:
        from q15_cloud.q15_cloud_job import current_pod_id, runpod_request
        current = current_pod_id()
        if current != state.get("pod_id"):
            raise FullJobError("pod_changed_before_stop")
        runpod_request(os.environ["RUNPOD_API_KEY"], current)
        if not publisher.receipts or publisher.receipts[-1].get("readback_verified") is not True:
            raise FullJobError("final_publication_not_verified_stop_forbidden")
        receipt = runpod_request(os.environ["RUNPOD_API_KEY"], current, "POST", "/stop")
        atomic_json(job / "stop_api_receipt.json", {**receipt, "physical_shutdown_confirmed": False})
        print(json.dumps({"stage": "stop_api_accepted", "physical_shutdown_confirmed": False}), flush=True)
    except Exception as exc:  # noqa: BLE001 - redact every failure before public status
        stage("manual_stop_required", stop_error_code=safe_code(exc), shutdown_status="stop_unconfirmed")
        try:
            publisher.commit([public_status], "Record unconfirmed Q15 Pod stop: " + args.job_id)
        except Exception as backup_exc:  # noqa: BLE001 - failed backup forbids a stop
            stage("manual_stop_required", shutdown_status="stop_unconfirmed",
                  stop_status_backup_verified=False, backup_error_code=safe_code(backup_exc))
        return 1
    return 0 if state.get("scientific_validation_passed") else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--workspace", default="/workspace")
    parser.add_argument("--raw-dir", default="/workspace/q15-data/raw")
    parser.add_argument("--bnci-dir", default="/workspace/q15-data/raw/BNCI2014_001")
    parser.add_argument("--epoch-dir", default="/workspace/q15-data/epochs")
    parser.add_argument("--control-dir", default="/workspace/.q15-cloud")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if not JOB_RE.fullmatch(args.job_id):
        raise FullJobError("job_id_invalid")
    if Path(args.control_dir).resolve() != (Path(args.workspace) / ".q15-cloud").resolve():
        raise FullJobError("alternate_active_supervisor_lock_forbidden")
    job = Path(args.workspace) / "q15-execution/jobs" / args.job_id
    job.mkdir(parents=True, exist_ok=True)
    publisher = Publisher(os.environ.get("GH_TOKEN", ""), "q15/run-" + args.job_id,
                          job / "github_publication_receipt.json")
    from q15_cloud.q15_cloud_job import acquire_job_lock
    # Outside run()/failure/stop handling: a duplicate can never stop the active Pod.
    with acquire_job_lock(Path(args.control_dir) / "active.lock"):
        if args.check_only:
            result = preflight(args, publisher)
            print(json.dumps({"status": "full_q15_preflight_passed_no_fits", "fits_started": 0,
                              "target_fits": 0, **result}), flush=True)
            return 0
        return run(args, publisher, job)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - redact every failure before public status
        print(json.dumps(startup_failure(exc)), flush=True)
        raise SystemExit(1) from None
