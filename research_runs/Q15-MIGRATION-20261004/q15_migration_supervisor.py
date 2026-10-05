"""Detached account migration: verified backup, or restore then inference only."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SECRETS = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
           "GH_TOKEN", "GITHUB_TOKEN", "RUNPOD_API_KEY")
BASE = "782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc"
ORIGIN_JOB = "20261004T005335Z-9b3bce30277a"
ORIGIN_POD = "hvjo2yy3m3wamh"


class MigrationError(RuntimeError):
    pass


def status(path, stage, **fields):
    row = {"stage": stage, "updated_at_utc": datetime.now(UTC).isoformat(),
           "new_source_fits": 0, "target_fits": 0, **fields}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(row, indent=2) + "\n")
    temporary.replace(path)
    print(json.dumps(row), flush=True)


def read_api(url, token):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                                                  "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read(2 * 1024**2))
    except urllib.error.HTTPError as exc:
        raise MigrationError("account_api_http_" + str(exc.code)) from None
    except Exception:  # noqa: BLE001 - response and network diagnostics may contain credentials
        raise MigrationError("account_api_unreachable") from None


def check_destination_identity():
    """Fail before a 75 GB restore if the destination account credentials are wrong."""
    pod = os.environ.get("RUNPOD_POD_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pod) or pod == ORIGIN_POD:
        raise MigrationError("new_destination_pod_required")
    for name in ("GH_TOKEN", "RUNPOD_API_KEY"):
        if not os.environ.get(name):
            raise MigrationError("required_credential_missing:" + name)
    result = read_api("https://rest.runpod.io/v1/pods/" + pod,
                      os.environ["RUNPOD_API_KEY"])
    if result.get("id") != pod:
        raise MigrationError("destination_account_pod_identity_unverified")
    repo = read_api("https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg",
                    os.environ["GH_TOKEN"])
    if (repo.get("full_name") != "jackzhu119/cross-subject-mi-eeg"
            or repo.get("permissions", {}).get("push") is not True):
        raise MigrationError("github_publication_access_unverified")
    return pod


def check_cuda_template():
    """Reject an incompatible image before downloading the real raw data."""
    import importlib.metadata

    import torch
    if (sys.version_info[:2] != (3, 12) or torch.__version__ != "2.8.0+cu128"
            or torch.version.cuda != "12.8" or not torch.cuda.is_available()
            or importlib.metadata.version("torchaudio") != "2.8.0+cu128"):
        raise MigrationError("pinned_pytorch_cuda_template_required")
    if torch.ones(1, device="cuda").item() != 1:
        raise MigrationError("cuda_zero_eeg_template_probe_failed")
    torch.cuda.empty_cache()


def existing_ready_restore(archive_sha256, object_key):
    """Resume a validated restoration without overwriting its progressed Git HEAD."""
    path = Path("/workspace/q15-migration/restore_receipt.json")
    if not path.exists():
        return False
    # Reuse the continuation's strict receipt/provenance/path checks. Scientific
    # model, epoch and raw checks remain mandatory inside its frozen runner.
    import q15_continue_validated as continuation
    receipt = continuation.read_json(path)
    if receipt.get("ready_for_continuation") is not True:
        return False
    if receipt.get("archive_sha256") != archive_sha256 or receipt.get("object_key") != object_key:
        raise MigrationError("existing_restore_backup_identity_mismatch")
    from types import SimpleNamespace
    arguments = continuation.canonical_arguments(SimpleNamespace(
        workspace="/workspace", restore_receipt=None, job_id="migration-receipt-preflight",
        revision=continuation.SCIENTIFIC_REVISION))
    continuation.validate_restore_receipt(arguments)
    return True


def continuation_descriptor_options():
    # A detached child must retain the migration lock even if this supervisor
    # exits unexpectedly. Plain subprocess.run would close FD9 in the child.
    try:
        os.fstat(9)
    except OSError:
        return {}
    return {"pass_fds": (9,)}


def install_scientific_runtime(repo, private_log):
    # Keep CUDA wheels from the user's chosen template. Install only frozen non-CUDA pins.
    environment = {k: v for k, v in os.environ.items() if k not in SECRETS}
    with private_log.open("wb") as stream:
        result = subprocess.run([sys.executable, "-m", "pip", "install",
                                 "--disable-pip-version-check", "-r",
                                 str(repo / "requirements-q15-runtime.txt")],
                                stdout=stream, stderr=subprocess.STDOUT, env=environment,
                                check=False)
    if result.returncode:
        raise MigrationError("scientific_dependency_install_failed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("backup", "restore", "from-r2"))
    parser.add_argument("--job-directory", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--private-log", required=True, type=Path)
    parser.add_argument("--object-key")
    parser.add_argument("--archive-sha256")
    args = parser.parse_args(argv)
    job = args.job_directory
    job.mkdir(parents=True, exist_ok=True)
    progress = job / "migration_status.json"
    repo = Path("/workspace/q15-execution/repo")
    try:
        import q15_migration_transport as transport
        if args.mode == "backup":
            status(progress, "exporting_verified_source_and_epochs", origin_job_id=ORIGIN_JOB)
            result = transport.main([
                "backup", "--repo", str(repo), "--epoch-dir", "/workspace/q15-data/epochs",
                "--bnci-dir", "/workspace/q15-data/raw/BNCI2014_001", "--archive",
                str(job / "validated-source-and-epochs.tar"), "--receipt",
                str(job / "r2_backup_receipt.json"), "--base-commit", BASE,
                "--origin-job", ORIGIN_JOB, "--origin-pod", ORIGIN_POD])
            if result not in (None, 0):
                raise MigrationError("backup_transport_failed")
            receipt = json.loads((job / "r2_backup_receipt.json").read_text())
            if receipt.get("readback_verified") is not True:
                raise MigrationError("backup_readback_not_verified")
            status(progress, "backup_verified_old_pod_can_be_stopped_manually",
                   object_key=receipt["object_key"], archive_sha256=receipt["archive_sha256"],
                   backup_readback_verified=True, origin_source_fits=15)
            return 0
        status(progress, "destination_account_preflight")
        pod = check_destination_identity()
        check_cuda_template()
        if args.mode == "from-r2":
            import q15_restore_from_r2
            receipt = q15_restore_from_r2.restore_from_r2(
                Path("/workspace"), args.job_id, job, args.private_log, install_scientific_runtime)
            if receipt.get("ready_for_continuation") is not True:
                raise MigrationError("r2_restoration_not_ready")
        else:
            if not args.object_key or not re.fullmatch(r"[a-f0-9]{64}", args.archive_sha256 or ""):
                raise MigrationError("verified_backup_locator_required")
            status(progress, "restoring_archive_and_raw_originals", pod_id=pod)
            if existing_ready_restore(args.archive_sha256, args.object_key):
                status(progress, "verified_restoration_reused_scientific_revalidation_still_required", pod_id=pod)
            else:
                result = transport.main([
                    "restore", "--workspace", "/workspace", "--archive", str(job / "backup.tar"),
                    "--object-key", args.object_key, "--archive-sha256", args.archive_sha256,
                    "--receipt", "/workspace/q15-migration/restore_receipt.json"])
                if result not in (None, 0):
                    raise MigrationError("restore_transport_failed")
            receipt = json.loads(Path("/workspace/q15-migration/restore_receipt.json").read_text())
            if receipt.get("ready_for_continuation") is not True:
                raise MigrationError("restored_originals_not_verified")
            status(progress, "installing_frozen_inference_runtime", pod_id=pod)
            install_scientific_runtime(repo, args.private_log)
        status(progress, "validated_source_continuation_starting", pod_id=pod,
               origin_source_fits=15)
        result = subprocess.run([
            sys.executable, str(Path(__file__).with_name("q15_continue_validated.py")),
            "--job-id", args.job_id, "--workspace", "/workspace"], check=False,
            **continuation_descriptor_options())
        if result.returncode:
            raise MigrationError("continuation_failed_or_blocked")
        status(progress, "continuation_process_returned", pod_id=pod,
               scientific_completion_requires_job_report=True)
        return 0
    except Exception as exc:  # noqa: BLE001 - redact all SDK/API failures
        # SDK/network tracebacks can embed endpoint or credential material; never emit them.
        code = str(exc) if isinstance(exc, MigrationError) else getattr(exc, "safe_code", type(exc).__name__)
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_: .-]{1,160}", code):
            code = "unexpected_migration_failure"
        for name in SECRETS:
            value = os.environ.get(name, "")
            if value and value in code:
                code = "redacted_failure"
        status(progress, "failed_or_blocked", error_code=code,
               automatic_pod_stop_requested_by_migration_supervisor=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
