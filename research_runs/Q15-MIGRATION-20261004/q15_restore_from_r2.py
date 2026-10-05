"""Restore the committed Q15 models and original R2 data without an old Pod.

Only the pinned preprocessor may regenerate epochs. Source fitting is never
called. The continuation independently revalidates all reused science.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

BASE = "782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc"
SCIENCE = "271af288a2f3863430ab80e3145c2dee9bd5571d"
ORIGIN_JOB = "20261004T005335Z-9b3bce30277a"
ORIGIN_POD = "hvjo2yy3m3wamh"
METHOD = "pinned_github_source_r2_raw_regenerated_epochs"
ORIGIN_URL = "https://github.com/jackzhu119/cross-subject-mi-eeg.git"
SECRET_NAMES = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "GH_TOKEN", "GITHUB_TOKEN", "RUNPOD_API_KEY")
DATASETS = {"Cho2017": 52, "Lee2019_MI": 54}


class RestorationError(RuntimeError):
    def __init__(self, code):
        self.safe_code = code
        super().__init__(code)


def safe_path(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise RestorationError("restoration_path_symlinked")
    return path


def public_git(repo, *arguments):
    environment = {key: value for key, value in os.environ.items()
                   if key not in SECRET_NAMES and not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c",
                             "credential.helper=", "-C", str(repo), *arguments],
                            env=environment, capture_output=True, check=False)
    if result.returncode:
        raise RestorationError("pinned_public_git_operation_failed")
    return result.stdout


def ensure_public_baseline(repo, allow_published_resume=False):
    """Never overwrite an occupied checkout or reset a progressing continuation."""
    repo = safe_path(repo)
    if repo.exists():
        if (not repo.is_dir() or (not allow_published_resume
                                 and public_git(repo, "rev-parse", "HEAD").decode().strip() != BASE)
                or public_git(repo, "remote", "get-url", "origin").decode().strip() != ORIGIN_URL):
            raise RestorationError("occupied_repository_is_not_pinned_baseline")
        return repo
    repo.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".q15-r2-repo-", dir=repo.parent) as staging:
        checkout = Path(staging) / "repo"
        checkout.mkdir()
        public_git(checkout, "init", "--quiet")
        public_git(checkout, "remote", "add", "origin", ORIGIN_URL)
        # Complete ancestry is needed to verify the original scientific pin.
        public_git(checkout, "fetch", "--quiet", "origin", BASE)
        public_git(checkout, "checkout", "--quiet", "--detach", BASE)
        if repo.exists():
            raise RestorationError("repository_appeared_during_restore")
        os.rename(checkout, repo)
    return repo


def verify_source_checkout(repo, bundle, continuation):
    """Bind resumed opaque model bytes to the immutable validated public ledger."""
    public_git(repo, "merge-base", "--is-ancestor", SCIENCE, BASE)
    public_git(repo, "merge-base", "--is-ancestor", BASE, "HEAD")
    bundle._verify_source_baseline(repo, BASE)
    relative = "results/Q15-E005/source_validation.json"
    path = safe_path(repo / relative)
    if path.read_bytes() != public_git(repo, "show", BASE + ":" + relative):
        raise RestorationError("public_source_validation_bytes_changed")
    report = continuation.read_json(path)
    for relative, digest in report["artifact_sha256"].items():
        if continuation.sha(safe_path(repo / relative)) != digest:
            raise RestorationError("public_source_artifact_bytes_changed")
    if (repo / "requirements-q15-runtime.txt").read_bytes() != public_git(
            repo, "show", BASE + ":requirements-q15-runtime.txt"):
        raise RestorationError("pinned_dependency_spec_changed")
    return {"verified_source_artifacts": len(report["artifact_sha256"])}


def remaining_download_bytes(records):
    # This is only quota planning. The transfer still hashes every reused file.
    total = 0
    for row in records:
        path = safe_path(row["path"])
        part = safe_path(path.with_name(path.name + ".part"))
        available = path.stat().st_size if path.is_file() else part.stat().st_size if part.is_file() else 0
        total += max(0, row["size_bytes"] - min(available, row["size_bytes"]))
    return total


def arguments(workspace, job_id, continuation):
    return continuation.canonical_arguments(SimpleNamespace(
        workspace=str(workspace), job_id=job_id, revision=SCIENCE,
        restore_receipt=None, check_only=False))


def download_originals(transport, client, bucket, records, progress, workers=4):
    """Independent bounded transfers, each with full persisted SHA256 verification."""
    verified = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(transport.download_verified, client, bucket,
                                  row["r2_object_key"], row["path"], row["sha256"],
                                  row["size_bytes"], expected_md5=row.get("md5")): row
                   for row in records}
        try:
            for future in as_completed(pending):
                row = pending[future]
                result = future.result()
                if (result.get("verified") is not True or result.get("sha256") != row["sha256"]
                        or type(result.get("size_bytes")) is not int
                        or result["size_bytes"] != row["size_bytes"]):
                    raise RestorationError("download_identity_not_verified")
                verified.append({"dataset": row["dataset"], "file_id": row["file_id"],
                                 "size_bytes": result["size_bytes"], "sha256": result["sha256"]})
                progress(len(verified), len(records), sum(item["size_bytes"] for item in verified))
        except Exception:
            for future in pending:
                future.cancel()
            raise
    return verified


def regenerate_epochs(full, continuation, epoch_root):
    source = continuation.restored_module(full, "q15_source")
    source._verify_committed_freeze()
    validator = continuation.restored_module(full, "q15_validate_source")
    recorded = continuation.read_json(full.ROOT / "results/Q15-E005/source_validation.json")
    if validator.validate_source(full.ROOT / "results/Q15-E005", write_report=False) != recorded:
        raise RestorationError("reused_source_validation_not_reproduced")
    preprocess = continuation.restored_module(full, "q15_preprocess_external")
    manifests = {}
    for dataset, expected_count in DATASETS.items():
        expected = full.git("show", BASE + ":results/Q15-EXTERNAL/manifests/" + dataset + ".json")
        directory = safe_path(Path(epoch_root) / dataset)
        directory.mkdir(parents=True, exist_ok=True)
        local = directory / "epoch_manifest.json"
        reused = False
        if local.is_file() and local.read_bytes() == expected:
            row = continuation.read_json(local)
            artifacts = [(person[field], person[digest]) for person in row.get("subjects", [])
                         for field, digest in (("npz_path", "npz_sha256"),
                                               ("metadata_path", "metadata_sha256"))]
            reused = len(artifacts) == expected_count * 2 and all(
                safe_path(path).is_relative_to(directory) and Path(path).is_file()
                and continuation.sha(path) == digest for path, digest in artifacts)
        if not reused:
            local = preprocess.prepare_dataset(dataset, directory)
        if safe_path(local) != directory / "epoch_manifest.json" or local.read_bytes() != expected:
            raise RestorationError("regenerated_epochs_differ_from_committed_baseline")
        manifests[dataset] = {"path": "epochs/" + dataset + "/epoch_manifest.json",
                              "sha256": continuation.sha(local)}
    return manifests, recorded["artifact_sha256"]


def restore_from_r2(workspace, job_id, job_directory, private_log, install_runtime):
    import q15_continue_validated as continuation
    import q15_migration_bundle as bundle
    import q15_migration_transport as transport

    workspace = safe_path(workspace)
    job_directory = safe_path(job_directory)
    args = arguments(workspace, job_id, continuation)
    custody = safe_path(workspace / "q15-migration")
    custody.mkdir(parents=True, exist_ok=True)
    canonical_receipt = custody / "restore_receipt.json"
    if canonical_receipt.exists():
        existing = continuation.read_json(canonical_receipt)
        if existing.get("kind") != "q15_committed_source_and_epochs_restore":
            raise RestorationError("existing_restore_method_conflicts_with_r2_restore")
        if existing.get("ready_for_continuation") is True:
            continuation.validate_restore_receipt(args)
            verify_source_checkout(args.repo, bundle, continuation)
            install_runtime(args.repo, private_log)
            return existing
    publication_state = safe_path(workspace / "q15-execution/jobs" / job_id / "github_publication_receipt.json")
    repo = ensure_public_baseline(args.repo, allow_published_resume=publication_state.is_file())
    proof = verify_source_checkout(repo, bundle, continuation)
    install_runtime(repo, private_log)
    full = continuation.load_restored_full(args)
    if (full.git("diff", SCIENCE, "--", *full.PINNED_PATHS)
            or full.git("ls-files", "--others", "--exclude-standard", "--", *full.PINNED_PATHS)):
        raise RestorationError("pinned_scientific_checkout_changed_before_import")
    cloud = continuation.restored_module(full, "q15_cloud.q15_cloud_job")
    # The lock is held by this preparation process; the later continuation
    # obtains it again after restoration returns.
    with cloud.acquire_job_lock(Path(args.control_dir) / "active.lock"):
        job = safe_path(workspace / "q15-execution/jobs" / job_id)
        job.mkdir(parents=True, exist_ok=True)
        publisher = full.Publisher(os.environ["GH_TOKEN"], "q15/run-" + job_id,
                                   job / "github_publication_receipt.json")
        # Check resumed receipt/ref identities outside failure publication.
        continuation.verify_continuation_head(args, full, publisher)
        state = {"schema_version": 1, "job_id": job_id, "origin_job_id": ORIGIN_JOB,
                 "origin_pod_id": ORIGIN_POD, "original_source_fits": 15, "new_source_fits": 0,
                 "fits_started": 15, "target_fits": 0, "scientific_validation_passed": False,
                 "predictions_computed": False, "original_source_fits_verified": True,
                 "source_checkpoint_custody_verified": proof["verified_source_artifacts"]}
        public_status = repo / "research_runs/Q15-MIGRATION-20261004/jobs" / job_id / "job_status.json"
        pod_verified = False

        def stage(name, publish=False, **fields):
            state.update(status=name, updated_at_utc=full.now(), **fields)
            full.atomic_json(job / "job_status.json", state)
            full.atomic_json(job_directory / "migration_status.json", state)
            full.atomic_json(public_status, state)
            print(json.dumps({"stage": name, "new_source_fits": 0, "target_fits": 0, **fields}), flush=True)
            if publish:
                receipt = publisher.commit([public_status], "Record Q15 R2 restoration: " + job_id)
                if not continuation.verified_receipt(publisher, receipt, "q15/run-" + job_id):
                    raise RestorationError("restoration_github_readback_not_verified")

        try:
            stage("r2_restore_preflight_running")
            preflight = full.preflight(args, publisher)
            pod = preflight.get("pod_id")
            if not pod or pod == ORIGIN_POD or pod != cloud.current_pod_id():
                raise RestorationError("r2_restore_requires_new_verified_pod")
            pod_verified = True
            state["pod_id"] = pod
            originals = transport.load_raw_inventory(repo, Path(args.raw_dir), revision=BASE)
            bnci = transport.load_bnci_inventory(repo, Path(args.raw_dir), revision=BASE)
            if len(originals) != 160 or len(bnci) != 18:
                raise RestorationError("complete_original_inventory_required")
            required_bytes = remaining_download_bytes(originals + bnci) + 25 * 1024**3
            free = preflight["disk_capacity_gb"] * 10**9 - full.workspace_allocated_bytes(workspace)
            if free < required_bytes:
                raise RestorationError("purchased_workspace_capacity_insufficient_for_r2_restore")
            client, bucket = transport.make_s3()
            probe = transport.probe_r2(client, bucket)
            stage("r2_original_download_running", publish=True, files_verified=0, expected_files=178)
            evidence = download_originals(transport, client, bucket, bnci + originals,
                lambda done, total, size: stage("r2_original_download_running",
                                                files_verified=done, expected_files=total,
                                                downloaded_verified_bytes=size))
            if (sum(row["dataset"] == "BNCI2014_001" for row in evidence) != 18
                    or sum(row["dataset"] in DATASETS for row in evidence) != 160):
                raise RestorationError("restored_original_proof_count_invalid")
            stage("r2_originals_verified_regenerating_epochs", publish=True,
                  bnci_originals_verified=18, raw_originals_verified=160)
            epoch_manifests, artifacts = regenerate_epochs(full, continuation, args.epoch_dir)
            manifest = {"schema_version": 1, "kind": "q15_committed_source_and_epochs",
                        "restore_method": METHOD, "code_base_commit": BASE,
                        "scientific_revision": SCIENCE, "origin_job_id": ORIGIN_JOB,
                        "origin_pod_id": ORIGIN_POD, "source_fit_count": 15,
                        "source_artifacts": artifacts, "epoch_manifests": epoch_manifests,
                        "bnci_original_count": 18, "raw_original_count": 160,
                        "epoch_person_count": 106, "created_at_utc": full.now()}
            manifest_path = custody / "migration_manifest.json"
            full.atomic_json(manifest_path, manifest)
            receipt = {"schema_version": 1, "kind": "q15_committed_source_and_epochs_restore",
                       "restore_method": METHOD, "code_base_commit": BASE,
                       "scientific_revision": SCIENCE, "origin_job_id": ORIGIN_JOB,
                       "origin_pod_id": ORIGIN_POD, "source_fit_count": 15,
                       "source_only_reuse": True, "paths_verified": True,
                       "repository_baseline_verified": True, "bnci_originals_verified": 18,
                       "raw_originals_verified": 160, "epoch_person_count": 106,
                       "ready_for_continuation": True, "manifest_sha256": continuation.sha(manifest_path),
                       "paths": {"repo": str(repo), "raw_dir": args.bnci_dir,
                                 "epoch_dir": args.epoch_dir, "manifest": str(manifest_path)},
                       "r2_probe": probe, "restored_at_utc": full.now()}
            full.atomic_json(canonical_receipt, receipt)
            continuation.validate_restore_receipt(args)
            stage("r2_restoration_verified_ready_for_continuation", publish=True,
                  bnci_originals_verified=18, raw_originals_verified=160, epoch_person_count=106)
            return receipt
        except Exception as exc:
            failed_stage = state.get("status")
            stage("r2_restore_failed_or_blocked", error_code=continuation.safe_code(exc),
                  failed_stage=failed_stage, shutdown_status="pending_verified_failure_backup")
            if not pod_verified:
                raise
            # Only this authenticated new Pod may stop, after a verified failure
            # commit. A rejected resume/ref or duplicate never reaches this block.
            try:
                stage("r2_restore_failed_or_blocked", publish=True,
                      error_code=continuation.safe_code(exc), failed_stage=failed_stage)
                current = cloud.current_pod_id()
                if current != state["pod_id"] or current == ORIGIN_POD:
                    raise RestorationError("pod_identity_changed_before_setup_stop")
                inspected = cloud.runpod_request(os.environ["RUNPOD_API_KEY"], current)
                if inspected.get("pod_id") != current:
                    raise RestorationError("pod_identity_unverified_before_setup_stop")
                stopped = cloud.runpod_request(os.environ["RUNPOD_API_KEY"], current, "POST", "/stop")
                full.atomic_json(job / "stop_api_receipt.json", {
                    "pod_id": current, "action": "stop", "http_status": stopped.get("http_status"),
                    "physical_shutdown_confirmed": False})
            except Exception as backup_error:  # noqa: BLE001 - redact all SDK/API failures
                stage("r2_restore_manual_attention_required",
                      error_code=continuation.safe_code(exc),
                      backup_or_stop_error_code=continuation.safe_code(backup_error),
                      shutdown_status="not_physically_confirmed")
            raise RestorationError("r2_restore_failed_or_blocked") from None
