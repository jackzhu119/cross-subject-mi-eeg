"""Continue validated Q15 source and restored epochs on a new RunPod identity.

This operational entrypoint loads the frozen runner from the RESTORED repository.
There is deliberately no source-fitting or epoch-writing execution path.
Credentials are read only from the new process environment, never from old jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCIENTIFIC_REVISION = "271af288a2f3863430ab80e3145c2dee9bd5571d"
CODE_BASE_COMMIT = "782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc"
ORIGIN_JOB_ID = "20261004T005335Z-9b3bce30277a"
ORIGIN_POD_ID = "hvjo2yy3m3wamh"
JOB_RE = re.compile(r"[A-Za-z0-9_-]{1,80}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
DATASETS = {"Cho2017": 52, "Lee2019_MI": 54}
ARCHIVE_RESTORE_KIND = "q15_validated_source_and_epochs_restore"
R2_RESTORE_KIND = "q15_committed_source_and_epochs_restore"
R2_RESTORE_METHOD = "pinned_github_source_r2_raw_regenerated_epochs"
CALIBRATION_LIMITATIONS = ["raw_voltage_calibration_not_independently_verified",
                          "cho_original_hardware_reference_not_verified",
                          "hardware_cue_latency_not_verified"]


class ContinuationError(RuntimeError):
    def __init__(self, code):
        self.safe_code = code
        super().__init__(code)


def safe_code(exc):
    value = getattr(exc, "safe_code", None)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
        return value
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z0-9_]{1,64}", name) else "unexpected_error"


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContinuationError("duplicate_json_key_rejected")
            result[key] = value
        return result

    def reject_constant(value):
        raise ContinuationError("nonfinite_json_rejected")

    path = Path(path)
    if path.resolve() != path or not path.is_file():
        raise ContinuationError("required_receipt_or_artifact_missing")
    result = json.loads(path.read_text(), object_pairs_hook=unique_object,
                        parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ContinuationError("json_object_required")
    return result


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_arguments(args):
    workspace = Path(args.workspace)
    if not workspace.is_absolute() or workspace.is_symlink():
        raise ContinuationError("workspace_path_unsafe")
    args.workspace = str(workspace.resolve())
    workspace = Path(args.workspace)
    args.repo = workspace / "q15-execution/repo"
    args.raw_dir = str(workspace / "q15-data/raw")
    args.bnci_dir = str(workspace / "q15-data/raw/BNCI2014_001")
    args.epoch_dir = str(workspace / "q15-data/epochs")
    args.control_dir = str(workspace / ".q15-cloud")
    expected_receipt = workspace / "q15-migration/restore_receipt.json"
    if args.restore_receipt is not None and Path(args.restore_receipt) != expected_receipt:
        raise ContinuationError("alternate_restore_receipt_forbidden")
    args.restore_receipt = expected_receipt
    if not JOB_RE.fullmatch(args.job_id) or args.job_id == ORIGIN_JOB_ID:
        raise ContinuationError("fresh_continuation_job_id_required")
    if args.revision != SCIENTIFIC_REVISION:
        raise ContinuationError("original_scientific_revision_required")
    return args


def validate_restore_receipt(args):
    receipt = read_json(args.restore_receipt)
    expected = {"schema_version": 1,
                "code_base_commit": CODE_BASE_COMMIT, "scientific_revision": SCIENTIFIC_REVISION,
                "origin_job_id": ORIGIN_JOB_ID, "origin_pod_id": ORIGIN_POD_ID,
                "source_fit_count": 15, "source_only_reuse": True, "paths_verified": True,
                "raw_originals_verified": 160, "ready_for_continuation": True}
    if any(type(receipt.get(key)) is not type(value) or receipt.get(key) != value
           for key, value in expected.items()):
        raise ContinuationError("restore_receipt_not_ready_or_identity_mismatch")
    kind = receipt.get("kind")
    if kind == ARCHIVE_RESTORE_KIND:
        required_hashes = ("manifest_sha256", "archive_sha256")
    elif kind == R2_RESTORE_KIND:
        proofs = {"restore_method": R2_RESTORE_METHOD,
                  "repository_baseline_verified": True, "bnci_originals_verified": 18,
                  "epoch_person_count": 106}
        if any(type(receipt.get(key)) is not type(value) or receipt.get(key) != value
               for key, value in proofs.items()):
            raise ContinuationError("r2_restore_proof_missing_or_invalid")
        if "archive_sha256" in receipt:
            raise ContinuationError("r2_restore_archive_identity_forbidden")
        required_hashes = ("manifest_sha256",)
    else:
        raise ContinuationError("restore_receipt_kind_unsupported")
    for name in required_hashes:
        if not SHA256_RE.fullmatch(str(receipt.get(name, ""))):
            raise ContinuationError("restore_receipt_hash_invalid")
    manifest_path = Path(args.workspace) / "q15-migration/migration_manifest.json"
    expected_paths = {"repo": str(args.repo), "raw_dir": args.bnci_dir,
                      "epoch_dir": args.epoch_dir, "manifest": str(manifest_path)}
    if receipt.get("paths") != expected_paths:
        raise ContinuationError("restored_canonical_paths_mismatch")
    for directory in (args.repo, Path(args.raw_dir), Path(args.bnci_dir), Path(args.epoch_dir)):
        if directory.resolve() != directory or not directory.is_dir():
            raise ContinuationError("restored_canonical_directory_missing_or_symlinked")
    manifest = read_json(manifest_path)
    if manifest_path.resolve() != manifest_path or sha(manifest_path) != receipt["manifest_sha256"]:
        raise ContinuationError("restored_manifest_hash_changed")
    for name in ("schema_version", "code_base_commit", "scientific_revision", "origin_job_id",
                 "origin_pod_id", "source_fit_count"):
        if type(manifest.get(name)) is not type(expected[name]) or manifest.get(name) != expected[name]:
            raise ContinuationError("restored_manifest_identity_mismatch")
    if kind == R2_RESTORE_KIND:
        validate_regenerated_manifest(args, manifest)
    return receipt


def validate_regenerated_manifest(args, manifest):
    """Bind R2-only reconstruction to the original committed source artifacts."""
    expected = {"kind": "q15_committed_source_and_epochs",
                "restore_method": R2_RESTORE_METHOD, "bnci_original_count": 18,
                "raw_original_count": 160, "epoch_person_count": 106}
    if any(type(manifest.get(key)) is not type(value) or manifest.get(key) != value
           for key, value in expected.items()):
        raise ContinuationError("regenerated_manifest_proof_missing_or_invalid")
    if "archive_sha256" in manifest or "repo_bundle" in manifest:
        raise ContinuationError("regenerated_manifest_archive_identity_forbidden")
    artifacts = manifest.get("source_artifacts")
    source_report = read_json(args.repo / "results/Q15-E005/source_validation.json")
    if (not isinstance(artifacts, dict) or not artifacts
            or artifacts != source_report.get("artifact_sha256")):
        raise ContinuationError("regenerated_source_artifact_inventory_mismatch")
    for name, digest in artifacts.items():
        relative = Path(name)
        if (not isinstance(name, str) or relative.is_absolute() or ".." in relative.parts
                or not name.startswith("results/Q15-E005/")
                or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
            raise ContinuationError("regenerated_source_artifact_identity_invalid")
        artifact = args.repo / relative
        if artifact.resolve() != artifact or not artifact.is_file() or sha(artifact) != digest:
            raise ContinuationError("regenerated_source_artifact_hash_changed")
    manifests = manifest.get("epoch_manifests")
    if not isinstance(manifests, dict) or set(manifests) != set(DATASETS):
        raise ContinuationError("regenerated_epoch_manifest_inventory_mismatch")
    for dataset in DATASETS:
        row = manifests[dataset]
        relative = f"epochs/{dataset}/epoch_manifest.json"
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or row.get("path") != relative or not isinstance(row.get("sha256"), str)
                or not SHA256_RE.fullmatch(row["sha256"])):
            raise ContinuationError("regenerated_epoch_manifest_identity_invalid")
        committed = args.repo / "results/Q15-EXTERNAL/manifests" / (dataset + ".json")
        local = Path(args.epoch_dir) / dataset / "epoch_manifest.json"
        if (committed.resolve() != committed or local.resolve() != local
                or not committed.is_file() or not local.is_file()
                or sha(committed) != row["sha256"] or sha(local) != row["sha256"]):
            raise ContinuationError("regenerated_epoch_manifest_hash_changed")


def _git(repo, *arguments):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("GH_TOKEN", "GITHUB_TOKEN", "RUNPOD_API_KEY",
                                  "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", "-C", str(repo), *arguments], env=environment,
                            capture_output=True, check=False)
    if result.returncode:
        raise ContinuationError("restored_git_operation_failed")
    return result.stdout


def _reject_foreign_scientific_modules(repo):
    for name, module in tuple(sys.modules.items()):
        if (name in ("scripts", "q15_source", "q15_external", "q15_validate_source",
                     "q15_validate_external", "q15_preprocess_external", "q15_cloud")
                or name.startswith(("scripts.q15_", "q15_cloud.", "mi_eeg"))):
            file = getattr(module, "__file__", None)
            if file and not Path(file).resolve().is_relative_to(repo.resolve()):
                raise ContinuationError("foreign_scientific_module_already_loaded")
            for directory in getattr(module, "__path__", ()):
                if not Path(directory).resolve().is_relative_to(repo.resolve()):
                    raise ContinuationError("foreign_scientific_package_already_loaded")


def load_restored_full(args):
    """Never use the release checkout's runner or cached scientific modules."""
    repo = Path(args.repo)
    if repo.is_symlink() or not repo.is_dir():
        raise ContinuationError("restored_repository_missing_or_unsafe")
    path = repo / "scripts/q15_cloud/q15_full_job.py"
    if path.resolve() != path or not path.is_file():
        raise ContinuationError("restored_frozen_runner_missing")
    if _git(repo, "show", CODE_BASE_COMMIT + ":scripts/q15_cloud/q15_full_job.py") != path.read_bytes():
        raise ContinuationError("restored_frozen_runner_changed")
    _reject_foreign_scientific_modules(repo)
    spec = importlib.util.spec_from_file_location("q15_restored_full_job", path)
    if spec is None or spec.loader is None:
        raise ContinuationError("restored_frozen_runner_unavailable")
    full = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(full)
    if Path(full.ROOT).resolve() != repo.resolve():
        raise ContinuationError("restored_runner_root_mismatch")
    return full


def restored_module(full, name):
    module = full.importlib.import_module(name)
    relative = ("scripts/" + name.replace(".", "/") + ".py")
    if Path(module.__file__).resolve() != (full.ROOT / relative).resolve():
        raise ContinuationError("scientific_module_outside_restored_repository")
    _reject_foreign_scientific_modules(Path(full.ROOT))
    return module


def verify_continuation_head(args, full, publisher):
    head = full.git("rev-parse", "HEAD").decode().strip()
    if head == CODE_BASE_COMMIT:
        return
    receipts = publisher.receipts
    if (not receipts or receipts[-1].get("readback_verified") is not True
            or receipts[-1].get("branch") != "q15/run-" + args.job_id
            or receipts[-1].get("commit") != head):
        raise ContinuationError("unreceipted_restored_repository_head")
    # Require remote equality before entering any failure-publication handler.
    # A rejected starting HEAD must never acquire legitimacy from a failure
    # commit on a new branch. No old publication receipt is ever consulted.
    publisher.verify_access()


def verify_reused_science(args, full):
    source = restored_module(full, "q15_source")
    source._verify_committed_freeze()
    report_path = full.ROOT / "results/Q15-E005/source_validation.json"
    source._assert_committed_unchanged(report_path)
    recorded = read_json(report_path)
    required = {"status": "source_validated_non_authorizing", "passed": True,
                "deep_fit_count": 14, "shallow_fit_count": 1, "target_fits": 0,
                "source_only": True, "external_prediction_authorized": False,
                "external_predictions_computed": False}
    if any(type(recorded.get(key)) is not type(value) or recorded.get(key) != value
           for key, value in required.items()):
        raise ContinuationError("original_source_validation_not_passed")
    validator = restored_module(full, "q15_validate_source")
    reproduced = validator.validate_source(full.ROOT / "results/Q15-E005", write_report=False)
    if reproduced != recorded:
        raise ContinuationError("original_source_validation_not_reproduced")
    preprocess = restored_module(full, "q15_preprocess_external")
    manifests = {}
    for dataset, count in DATASETS.items():
        path = full.ROOT / "results/Q15-EXTERNAL/manifests" / (dataset + ".json")
        source._assert_committed_unchanged(path)
        recorded_manifest = read_json(path)
        local_manifest = Path(args.epoch_dir) / dataset / "epoch_manifest.json"
        if local_manifest.is_symlink() or sha(local_manifest) != sha(path):
            raise ContinuationError("restored_local_epoch_manifest_changed")
        subjects = recorded_manifest.get("subjects", [])
        if (len(subjects) != count
                or [row.get("subject") for row in subjects] != list(range(1, count + 1))):
            raise ContinuationError("restored_epoch_person_inventory_changed")
        for row in subjects:
            for field, extension in (("npz_path", ".npz"), ("metadata_path", ".csv")):
                artifact = Path(row.get(field, ""))
                expected_path = Path(args.epoch_dir) / dataset / (f"s{row['subject']:02d}" + extension)
                if artifact != expected_path or artifact.resolve() != artifact or not artifact.is_file():
                    raise ContinuationError("restored_epoch_canonical_artifact_missing")
        if preprocess.validate_epoch_manifest(path) != recorded_manifest:
            raise ContinuationError("restored_epoch_manifest_not_reproduced")
        manifests[dataset] = path
    return manifests


def verified_receipt(publisher, receipt, branch):
    return (isinstance(receipt, dict) and receipt.get("readback_verified") is True
            and receipt.get("branch") == branch
            and COMMIT_RE.fullmatch(str(receipt.get("commit", ""))) is not None
            and bool(publisher.receipts) and publisher.receipts[-1] == receipt)


def public_publication_evidence(receipt, root, paths, job_id, purpose):
    """Describe the preceding verified commit, never this evidence's own commit."""
    if purpose not in ("scientific_results", "failure_status"):
        raise ContinuationError("publication_evidence_purpose_invalid")
    value = {"schema_version": 1, "kind": "q15_github_publication_evidence",
             "job_id": job_id, "branch": receipt["branch"],
             "publication_purpose": purpose, "verified_commit": receipt["commit"],
             "readback_verified": True, "original_source_fits": 15,
             "new_source_fits": 0, "target_fits": 0,
             "physical_shutdown_confirmed": False}
    # The frozen Publisher's only artifact identity field is artifact_sha256.
    # Omit every other private receipt field, including URL and API metadata.
    if "artifact_sha256" in receipt:
        hashes = receipt["artifact_sha256"]
        names = {Path(path).relative_to(root).as_posix() for path in paths}
        if (not isinstance(hashes, dict) or set(hashes) != names
                or any(not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)
                       for digest in hashes.values())):
            raise ContinuationError("publication_evidence_artifact_identity_invalid")
        value["artifact_sha256"] = dict(hashes)
    return value


def run(args, full, publisher, job, restore):
    # Outside the publication/failure/stop handlers, including remote readback
    # for resumed commits. An invalid starting HEAD cannot be published over.
    verify_continuation_head(args, full, publisher)
    branch = "q15/run-" + args.job_id
    public_dir = full.ROOT / "research_runs/Q15-MIGRATION-20261004/jobs" / args.job_id
    public_status = public_dir / "job_status.json"
    private_status = job / "job_status.json"
    state = {"schema_version": 1, "job_id": args.job_id, "branch": branch,
             "origin_job_id": ORIGIN_JOB_ID, "origin_pod_id": ORIGIN_POD_ID,
             "original_source_fits": 15, "new_source_fits": 0, "target_fits": 0,
             "fits_started": 15, "source_fit_execution_started": False,
             "original_source_fits_verified": False, "source_only_reuse": True,
             "scientific_validation_passed": False, "predictions_computed": False,
             "github_results_backup_verified": False,
             "status": "restore_preflight_running", "supervisor_pid": os.getpid()}
    pod_verified = False
    backup_verified = False
    backup_evidence_receipt = None

    def stage(name, **fields):
        state.update({"status": name, "updated_at_utc": full.now(), **fields})
        full.atomic_json(private_status, state)
        if not args.check_only:
            full.atomic_json(public_status, state)
        print(json.dumps({"stage": name, "original_source_fits": 15, "new_source_fits": 0,
                          "target_fits": 0}), flush=True)

    def commit(paths, message):
        receipt = publisher.commit(paths, message + ": " + args.job_id)
        if not verified_receipt(publisher, receipt, branch):
            raise ContinuationError("continuation_publication_readback_unverified")
        return receipt

    def publish_backup_evidence(receipt, paths, purpose):
        if not verified_receipt(publisher, receipt, branch):
            raise ContinuationError("publication_evidence_requires_verified_preceding_commit")
        evidence = public_dir / "publication_evidence.json"
        full.atomic_json(evidence, public_publication_evidence(
            receipt, full.ROOT, paths, args.job_id, purpose))
        return commit([evidence, public_status], "Publish Q15 " + purpose + " readback evidence")

    def evidence_failed(exc):
        stage("failed_backup_manual_attention_required", backup_error_code=safe_code(exc),
              shutdown_status="not_requested_publication_evidence_unverified")
        # Publishing this diagnostic cannot substitute for the missing evidence
        # readback and never authorizes Stop. An uncertain remote HEAD remains
        # protected by the frozen Publisher's concurrent-change checks.
        try:
            commit([public_status], "Record Q15 publication evidence failure requiring manual attention")
        except Exception as diagnostic_exc:  # noqa: BLE001 — retain only safe diagnostic codes.
            stage("failed_backup_manual_attention_required",
                  diagnostic_backup_error_code=safe_code(diagnostic_exc))
        return 1

    try:
        stage("restore_preflight_running")
        cloud = restored_module(full, "q15_cloud.q15_cloud_job")
        current = cloud.current_pod_id()
        if current == ORIGIN_POD_ID:
            raise ContinuationError("original_pod_identity_forbidden")
        result = full.preflight(args, publisher)
        if result.get("pod_id") != current or result.get("pod_id") == ORIGIN_POD_ID:
            raise ContinuationError("new_pod_preflight_identity_mismatch")
        pod_verified = True
        stage("new_pod_preflight_passed", pod_id=current, startup_verified=True)
        stage("original_source_and_epochs_revalidation_running")
        manifests = verify_reused_science(args, full)
        stage("original_source_and_epochs_revalidated", original_source_fits_verified=True,
              deep_fit_count=14, shallow_fit_count=1, epoch_person_count=106,
              source_runtime_provenance_preserved=True)
        if args.check_only:
            stage("continuation_ready_no_new_fits_or_predictions")
            return 0
        provenance = public_dir / "restored_migration_provenance.json"
        # Deliberate public allowlist: never copy transport endpoints, buckets,
        # credentials, old private receipts, or arbitrary restore fields.
        provenance_keys = ["manifest_sha256", "code_base_commit", "scientific_revision",
                           "origin_job_id", "origin_pod_id"]
        if restore["kind"] == ARCHIVE_RESTORE_KIND:
            provenance_keys.append("archive_sha256")
        else:
            provenance_keys.append("restore_method")
        full.atomic_json(provenance, {"schema_version": 1,
            "kind": "q15_validated_source_and_epochs_continuation",
            **{key: restore[key] for key in provenance_keys},
            "job_id": args.job_id, "branch": branch, "original_source_fits": 15,
            "new_source_fits": 0, "target_fits": 0, "source_only_reuse": True,
            "raw_originals_verified": 160, "epoch_person_count": 106,
            "restore_receipt_sha256": sha(args.restore_receipt)})
        commit([provenance, public_status], "Record verified Q15 migration provenance")
        external = restored_module(full, "q15_external")
        stage("inference_freeze_preparing_no_predictions")
        freeze = external.prepare_freeze(manifests)
        commit([freeze, public_status], "Freeze continued Q15 external inference before predictions")
        external.verify_freeze(manifests)
        stage("external_inference_running", inference_contract_frozen=True)
        external.run_external(manifests, "cuda")
        stage("independent_external_validation_running", predictions_computed=True)
        independent = restored_module(full, "q15_validate_external")
        validation = independent.validate_external(manifests, device_name="cuda", write_report=True)
        required = {"passed": True, "scientific_validation_passed": True,
                    "status": "completed_with_calibration_limitations", "target_fits": 0,
                    "new_model_fits": 0, "model_state_unchanged": True,
                    "source_deep_fit_count": 14, "source_shallow_fit_count": 1,
                    "raw_auditor_replayed": True, "raw_to_epoch_replayed": True,
                    "frozen_checkpoint_prediction_replayed": True,
                    "statistics_independently_reconstructed": True, "calibration_verified": False}
        if (any(type(validation.get(key)) is not type(value) or validation.get(key) != value
                for key, value in required.items())
                or validation.get("calibration_limitations") != CALIBRATION_LIMITATIONS):
            raise ContinuationError("independent_external_validation_not_passed")
        stage("completed_with_calibration_limitations", scientific_validation_passed=True,
              calibration_limitations=CALIBRATION_LIMITATIONS,
              shutdown_status="pending_verified_publication_then_stop")
        result_paths = [*full.external_artifacts(validation), public_status]
        result_receipt = commit(result_paths,
            "Complete continued Q15 with independent replay and calibration limitations")
        stage("completed_with_calibration_limitations", github_results_backup_verified=True,
              results_commit=result_receipt["commit"],
              shutdown_status="pending_verified_publication_evidence_then_stop")
        try:
            backup_evidence_receipt = publish_backup_evidence(
                result_receipt, result_paths, "scientific_results")
        except Exception as evidence_exc:  # noqa: BLE001 — no Stop without evidence readback.
            return evidence_failed(evidence_exc)
        backup_verified = True
    except Exception as exc:  # noqa: BLE001 — redact all failures before public status.
        failed_stage = state["status"]
        if args.check_only:
            stage("continuation_check_failed", error_code=safe_code(exc), failed_stage=failed_stage,
                  scientific_validation_passed=False, shutdown_status="not_requested_check_only")
            return 1
        stage("failed_or_blocked", error_code=safe_code(exc), failed_stage=failed_stage,
              scientific_validation_passed=False,
              shutdown_status="pending_verified_failure_publication_then_stop")
        try:
            failure_receipt = commit([public_status],
                                    "Record Q15 continuation failure without false completion")
            stage("failed_or_blocked", github_failure_backup_verified=True,
                  failure_commit=failure_receipt["commit"],
                  shutdown_status="pending_verified_failure_evidence_then_stop")
            backup_evidence_receipt = publish_backup_evidence(
                failure_receipt, [public_status], "failure_status")
            backup_verified = True
        except Exception as backup_exc:  # noqa: BLE001 — preserve unknown backup failures safely.
            stage("failed_backup_manual_attention_required", backup_error_code=safe_code(backup_exc),
                  shutdown_status="not_requested_backup_unverified")
            return 1
    if not pod_verified:
        stage("manual_attention_required", shutdown_status="not_requested_pod_identity_unverified")
        return 1
    try:
        current = cloud.current_pod_id()
        if current == ORIGIN_POD_ID or current != state.get("pod_id"):
            raise ContinuationError("new_pod_identity_changed_before_stop")
        if not backup_verified or not verified_receipt(publisher, backup_evidence_receipt, branch):
            raise ContinuationError("verified_backup_required_before_stop")
        inspected = cloud.runpod_request(os.environ["RUNPOD_API_KEY"], current)
        if inspected.get("pod_id") != current:
            raise ContinuationError("new_pod_reinspection_identity_mismatch")
        stopped = cloud.runpod_request(os.environ["RUNPOD_API_KEY"], current, "POST", "/stop")
        full.atomic_json(job / "stop_api_receipt.json", {"pod_id": current,
            "http_status": stopped.get("http_status"), "action": "stop",
            "physical_shutdown_confirmed": False})
        print(json.dumps({"stage": "new_pod_stop_api_accepted",
                          "physical_shutdown_confirmed": False}), flush=True)
    except Exception as exc:  # noqa: BLE001 — report unconfirmed stop without private exception text.
        stage("manual_stop_required", stop_error_code=safe_code(exc), shutdown_status="stop_unconfirmed")
        try:
            commit([public_status], "Record unconfirmed new Q15 Pod stop")
        except Exception as backup_exc:  # noqa: BLE001 — no false public backup claim.
            stage("manual_stop_required", backup_error_code=safe_code(backup_exc),
                  stop_status_backup_verified=False)
        return 1
    return 0 if state["scientific_validation_passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--workspace", default="/workspace")
    parser.add_argument("--revision", default=SCIENTIFIC_REVISION)
    parser.add_argument("--restore-receipt")
    parser.add_argument("--check-only", action="store_true")
    args = canonical_arguments(parser.parse_args(argv))
    restore = validate_restore_receipt(args)
    full = load_restored_full(args)
    cloud = restored_module(full, "q15_cloud.q15_cloud_job")
    if Path(args.control_dir).resolve() != Path(args.control_dir):
        raise ContinuationError("canonical_workspace_lock_directory_symlinked")
    # Outside every publication/failure/stop handler: a duplicate worker cannot
    # publish over or stop the worker that already owns the workspace lock.
    with cloud.acquire_job_lock(Path(args.control_dir) / "active.lock"):
        job = Path(args.workspace) / "q15-execution/jobs" / args.job_id
        if job.resolve() != job:
            raise ContinuationError("continuation_job_directory_symlinked")
        job.mkdir(parents=True, exist_ok=True)
        publication_state = job / "github_publication_receipt.json"
        if publication_state.is_symlink():
            raise ContinuationError("continuation_publication_receipt_symlinked")
        publisher = full.Publisher(os.environ.get("GH_TOKEN", ""), "q15/run-" + args.job_id,
                                   publication_state)
        return run(args, full, publisher, job, restore)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — fail closed without printing private exception text.
        print(json.dumps({"status": "continuation_startup_blocked", "error_code": safe_code(exc),
                          "origin_job_id": ORIGIN_JOB_ID, "original_source_fits": 15,
                          "original_source_fits_verified": False, "new_source_fits": 0,
                          "target_fits": 0, "scientific_validation_passed": False}), flush=True)
        raise SystemExit(1) from None
