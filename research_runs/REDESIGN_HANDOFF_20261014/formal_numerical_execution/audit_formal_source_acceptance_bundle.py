"""Audit the exact first formal source receipt archive; never execute payloads.

This checks the recorded evidence and immutable Git blobs. It neither rebuilds
EEG inputs nor authorizes training, budget migration, target access, or Pod stop.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

EXPECTED_BYTES = 12299
EXPECTED_SHA256 = "a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d"
REVISION = "97f1f42a712c4feb1a0be7eca25ac04b06c9c946"
FORMAL = "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/"
CLOUD = "research_runs/REDESIGN_CLOUD_20261013/"
PARALLEL = "parallel-p1-source-fit6-run01/"
OUTPUT = "paper1-readonly-probe/formal-source-numerics-acceptance-run01"
SOURCE_COPY = "paper1-formal-numerics-review-97f1f42a/" + FORMAL + "accept_source_numerics.py"
REPORT = OUTPUT + "/formal_source_acceptance.json"
EXPECTED_NAMES = {
    PARALLEL + name for name in (
        "completion.json", "dispatch.log", "execution-claim.json", "overlap-samples.jsonl",
        "paper2-launcher.log", "paper2.exit-code", "plan-only.json",
        "preparation-parse-correction.log", "preparation.log", "prepare.py", "run_once.py", "starts.json",
    )
} | {REPORT, OUTPUT + ".worker.log", OUTPUT + ".exit-code", SOURCE_COPY, "manifest.json"}
EXPECTED_IDENTITIES = {
    CLOUD + "config/experiment.json": "8ba78d4ead0e41fc5a5fc6f9890b750f0bdfdaba74a57efab5422b43d57feff0",
    CLOUD + "config/numerical_execution_v1.json": "04f562ddddc4e5019e56240b980d6d9c2d78645860857a5ab0d9746e788ae476",
    CLOUD + "scripts/formal_core_inputs.py": "bcd89d6747f00fb03bf1793df3753c53f67cfbf2f95275d40b042b682db61577",
    CLOUD + "scripts/prepare_data.py": "426252640951bdbcfd1cafebc5b103b2846bac2f363d1bbbc6cb8586afe8e3db",
    CLOUD + "scripts/train_exploratory.py": "4c8e66ce75b7f4133ea648be1bb9b58320b1df2d30e9bba19f4176b0ac665a3d",
    CLOUD + "scripts/validate_source.py": "d7b1d801790293c5ad88db46a4f33e6275be37ad1cd3c8bc6bf69faa4fe96661",
    CLOUD + "scripts/infer_exploratory.py": "0ff2547f9f3f4c4c56064ce5cb94d78c47d3f67053df049bf141a34f195f3538",
    CLOUD + "scripts/numerical_review_gate.py": "8e6e6b74926cb5df14223aeab802c79dca07bc14a4282779628505f2158d5243",
    FORMAL + "accept_source_numerics.py": "001eb38f2189ad8f2fe19d27600a5e0e16ac95d6c9eb1b52d115ba41a507dba9",
    FORMAL + "audit_full_diagnostic_bundle.py": "467bed0bb5669ebc760b9d804b85a5fa6bbed0f94ea089065163ff20b5c52a27",
}
EXPECTED_ARRAYS = {
    "broad": "420cd1635c3748e4706c3635e795384f7f859961736bbe7400eae9eb4db7dcd0",
    "mu": "704635466155eb4965a732d389ffcb71a1a7a862ffc41e0d615dc3c68b7d17dc",
    "beta": "8e2a88db18e4db719a4b1e396a7871bc102123f99358751f332e0dbd678c6462",
}
EXPECTED_COMMAND = [
    "timeout", "--signal=TERM", "--kill-after=10s", "300s",
    "/workspace/paper1-diagnostic-runtime/bin/python",
    "/workspace/paper1-formal-numerics-review-97f1f42a/" + FORMAL + "accept_source_numerics.py",
    "--code-revision", REVISION, "--data-dir", "/workspace/paper1-readonly-probe/data",
    "--output-dir", "/workspace/" + OUTPUT, "--old-work-root", "/workspace/mi-eeg-cloud",
    "--runtime-role", "diagnostic",
]


class AuditError(ValueError):
    """The named immutable evidence did not satisfy a required condition."""


def require(value, message):
    if not value:
        raise AuditError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_json(data):
    def unique(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate_json_key")
            out[key] = value
        return out
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(AuditError("nonfinite_json")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("invalid_json") from exc


def read_members(data):
    """Read bounded regular UTF-8 members in memory; do not extract."""
    require(len(data) <= 128 * 1024, "archive_size_limit")
    members = {}
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for item in archive:
                name = item.name
                require(isinstance(name, str) and "\\" not in name and "\0" not in name,
                        "unsafe_member_name")
                require(not name.startswith("/") and not re.match(r"^[A-Za-z]:", name), "absolute_member_name")
                require(all(part not in ("", ".", "..") for part in name.split("/")), "unsafe_member_path")
                require(str(PurePosixPath(name)) == name, "member_path_alias")
                require(item.isfile(), "nonregular_member")
                require(name not in members, "duplicate_member")
                require(len(members) < 32 and 0 <= item.size <= 128 * 1024, "member_size_limit")
                total += item.size
                require(total <= 256 * 1024, "expanded_size_limit")
                value = archive.extractfile(item).read(128 * 1024 + 1)
                require(len(value) == item.size and b"\0" not in value, "member_size_or_binary")
                value.decode("utf-8")
                members[name] = value
    except (tarfile.TarError, UnicodeError) as exc:
        raise AuditError("invalid_archive_or_encoding") from exc
    require(set(members) == EXPECTED_NAMES, "unexpected_payload_set")
    return members


def verify_manifest(members):
    manifest = parse_json(members["manifest.json"])
    records = manifest.get("files")
    require(isinstance(records, list) and len(records) == 16, "manifest_payload_count")
    found = set()
    for record in records:
        require(isinstance(record, dict) and set(record) == {"path", "bytes", "sha256"}, "manifest_schema")
        name = record["path"]
        require(name in members and name != "manifest.json" and name not in found, "manifest_members")
        require(type(record["bytes"]) is int and record["bytes"] == len(members[name]), "manifest_bytes")
        require(record["sha256"] == sha(members[name]), "manifest_sha256")
        found.add(name)
    require(found == EXPECTED_NAMES - {"manifest.json"}, "manifest_coverage")


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise AuditError("invalid_timestamp") from exc
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, "timestamp_not_UTC")
    return result


def audit_members(members, git_blob):
    """Validate semantics independently of the outer immutable archive pin."""
    verify_manifest(members)
    report = parse_json(members[REPORT])
    require(members[REPORT] == members[OUTPUT + ".worker.log"], "report_worker_log_disagree")
    require(report["status"] == "SOURCE_NUMERICS_MATCH_PRIVATE_PACKAGE_OR_TRAINING_RUNTIME_PENDING", "report_status")
    require(report["code_revision"] == REVISION, "code_revision")
    require(report["source_complete_exact_hash_gate_passed"] is True, "source_hash_gate")
    require(report["source_array_hashes"] == EXPECTED_ARRAYS, "source_array_hashes")
    for name, expected in (("source_files", 18), ("source_runs", 108), ("source_trials", 2592), ("new_fits", 0)):
        require(type(report[name]) is int and report[name] == expected, "report_count:" + name)
    for name in ("training_consumer_imports_verified", "private_full_package_independently_verified",
                 "target_complete_restoration_verified", "target_frozen_input_mapping_verified",
                 "runtime_GPU_preflight_verified", "old_machine_identity_proven", "budget_resume_authorized",
                 "checkpoint_and_verified_backup_gates_passed", "training_authorization", "target_EEG_read",
                 "target_predictions_computed", "source_arrays_serialized_or_replaced",
                 "historical_generation_BLAS_identity_established"):
        require(report[name] is False, "pending_gate_or_scope_changed:" + name)
    require(report["private_full_package_sha256"] is None, "private_archive_unexpectedly_bound")
    require(report["private_package_audit"] == {"status": "PRIVATE_FULL_PACKAGE_NOT_ACCESSIBLE_NOT_AUDITED"}, "private_package_status")
    require(report["old_accounting_observation"] == {"observed": False, "reason": "old_registration_not_accessible"}, "old_accounting_observation")
    require(report["old_accounting_records_unchanged"] is True, "old_accounting_change")
    require(report["consumer_static_bindings"] == {
        "train_exploratory.py": True, "validate_source.py": True, "prepare_data.py": True}, "static_consumer_bindings")
    require(report["execution_file_identities"] == EXPECTED_IDENTITIES, "execution_file_inventory")
    for name, expected in EXPECTED_IDENTITIES.items():
        require(sha(git_blob(name)) == expected, "fixed_revision_file_mismatch:" + name)
    require(members[SOURCE_COPY] == git_blob(FORMAL + "accept_source_numerics.py"), "archived_source_mismatch")
    numeric = report["numerical_execution"]
    require(numeric == {
        "policy_id": "explicit_sos_initial_state_v1_20261014",
        "policy_sha256": EXPECTED_IDENTITIES[CLOUD + "config/numerical_execution_v1.json"],
        "execution_module_sha256": EXPECTED_IDENTITIES[CLOUD + "scripts/formal_core_inputs.py"],
        "historical_loader_sha256": "03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5",
        "historical_generation_BLAS_identity_established": False,
        "state_application": "every_band_every_trial_source_and_target",
    }, "numerical_policy_scope")
    starts = parse_json(members[PARALLEL + "starts.json"])
    completion = parse_json(members[PARALLEL + "completion.json"])
    p1, p2 = completion["processes"]["paper1"], completion["processes"]["paper2"]
    for label in ("paper1", "paper2"):
        require(starts[label] == {key: completion["processes"][label][key] for key in starts[label]}, "start_completion_mismatch")
    require(p1["command"] == EXPECTED_COMMAND, "acceptance_command")
    require(type(p1["exit_code"]) is int and p1["exit_code"] == 3 and members[OUTPUT + ".exit-code"] == b"3\n", "intentional_exit_three")
    require(p1["pid"] == 29459 and p2["pid"] == 29460, "dispatcher_pids")
    require(p2["exit_code"] == 75 and members[PARALLEL + "paper2.exit-code"] == b"75\n", "paper2_backup_pending_exit")
    require(completion["automatic_next_fit"] is False, "automatic_next_fit")
    require(completion["free_bytes"] == 20443377664, "recorded_free_disk")
    require(timestamp(p1["start_utc"]) <= timestamp(report["checked_at_utc"]) < timestamp(p1["exit_observed_utc"]), "acceptance_timeline")
    require(timestamp(p1["start_utc"]) <= timestamp(p2["start_utc"]) < timestamp(p2["exit_observed_utc"]) < timestamp(p1["exit_observed_utc"]), "overlap_timeline")
    claim = parse_json(members[PARALLEL + "execution-claim.json"])
    require(claim["single_p1_acceptance"] is True and claim["single_p2_fit"] is True and claim["automatic_retry"] is False, "dispatch_single_run_claim")
    preparation = members[PARALLEL + "preparation.log"].decode()
    correction = members[PARALLEL + "preparation-parse-correction.log"].decode()
    require("json.decoder.JSONDecodeError: Extra data: line 2 column 1" in preparation, "original_parse_error_missing")
    require("wrapper JSON multi-line parsing correction only; no fit or data acceptance was run." in correction, "correction_scope_missing")
    require(preparation.count('"fetch"') == 2 and preparation.count('"worktree", "add"') == 1, "preparation_fetch_worktree_record")
    plan = parse_json(members[PARALLEL + "plan-only.json"])
    require(plan["status"] == "plan_only" and plan["fit_executed"] is False, "preflight_not_execution")
    require(plan["next_job"] == parse_json(correction.splitlines()[-1].encode()), "correction_plan_disagrees")
    paper2 = members[PARALLEL + "paper2-launcher.log"].decode()
    receipts = [parse_json(line.encode()) for line in paper2.splitlines() if line.startswith("{")]
    local_fit = [item for item in receipts if item.get("status") == "fit_saved_private_backup_pending"]
    require(len(local_fit) == 1 and local_fit[0]["R2_backup_verified"] is False and local_fit[0]["stop_Pod"] is False, "paper2_backup_observation")
    require(local_fit[0]["job_id"] == plan["next_job"]["job_id"] and local_fit[0]["subject"] == "sub-4" and local_fit[0]["seed"] == 20261014, "paper2_plan_receipt_identity")
    samples = [parse_json(line) for line in members[PARALLEL + "overlap-samples.jsonl"].splitlines() if line]
    require(len(samples) == 10, "overlap_sample_count")
    gpu_samples, live_gpu_samples, zombie_gpu_samples = 0, 0, 0
    last_time = timestamp(p1["start_utc"])
    for sample in samples:
        current = timestamp(sample["utc"])
        require(last_time < current < timestamp(p2["exit_observed_utc"]), "sample_time_scope")
        last_time = current
        require(sample["both_child_processes_live"] is True, "sample_dispatcher_claim")
        processes = {}
        for line in sample["sanitized_processes"].splitlines()[1:]:
            fields = line.split()
            require(len(fields) == 6, "process_sample_schema")
            processes[int(fields[0])] = {"ppid": int(fields[1]), "stat": fields[2], "command": fields[5]}
        require(processes[29461]["ppid"] == 29459 and not processes[29461]["stat"].startswith("Z"), "paper1_cpu_child")
        require(processes[29459]["ppid"] == claim["supervisor_pid"] and processes[29460]["ppid"] == claim["supervisor_pid"], "sample_parent_identity")
        if sample["gpu_compute"]:
            gpu_samples += 1
            lines = sample["gpu_compute"].strip().splitlines()
            require(len(lines) == 1 and re.fullmatch(r"29471, \d+", lines[0]), "GPU_process_sample")
            require(processes[29471]["ppid"] == 29470 and processes[29470]["ppid"] == 29467 and processes[29467]["ppid"] == 29460, "GPU_paper2_parent_chain")
            if processes[29471]["stat"].startswith("Z"):
                zombie_gpu_samples += 1
            else:
                live_gpu_samples += 1
    require((gpu_samples, live_gpu_samples, zombie_gpu_samples) == (6, 5, 1), "GPU_overlap_scope")
    return {
        "status": "FORMAL_SOURCE_DIAGNOSTIC_RECEIPT_AUDIT_PASSED_TRAINING_BLOCKED",
        "archive_bytes": EXPECTED_BYTES, "archive_sha256": EXPECTED_SHA256,
        "manifest_payloads_verified": 16, "physical_members_verified": 17,
        "code_revision": REVISION, "archived_acceptor_matches_fixed_git_blob": True,
        "execution_git_blob_hashes_checked": len(EXPECTED_IDENTITIES),
        "recorded_source_counts": {"files": 18, "runs": 108, "trials": 2592},
        "recorded_frozen_array_hashes": EXPECTED_ARRAYS,
        "recorded_source_strict_hash_gate_passed": True,
        "EEG_arrays_independently_recomputed_by_this_audit": False,
        "acceptance_role": "diagnostic", "expected_acceptance_exit": 3,
        "start_utc": p1["start_utc"], "report_utc": report["checked_at_utc"],
        "exit_observed_utc": p1["exit_observed_utc"],
        "original_preflight_JSON_error_preserved": True,
        "correction_plan_matches_existing_output": True,
        "recorded_overlap_samples": 10, "samples_with_GPU_PID": gpu_samples,
        "samples_with_non_zombie_paper2_GPU_child": live_gpu_samples,
        "samples_with_GPU_PID_already_zombie": zombie_gpu_samples,
        "paper2_receipt_scope": "local_fit_saved_private_backup_pending_not_independently_audited",
        "recorded_disk_free_bytes": completion["free_bytes"],
        "old_accounting_observed": False, "historical_machine_identity_proven": False,
        "training_consumer_imports_verified": False,
        "private_full_package_bound_in_this_remote_acceptance": False,
        "training_authorization": False, "budget_transition_authorized": False,
        "target_mapping_or_restoration_verified": False,
        "new_fits_started_by_this_audit": 0, "target_EEG_read_by_this_audit": False,
        "archive_scripts_executed": False, "Pod_queried_or_stopped": False,
        "observation_limits": [
            "Integrity and internal consistency of recorded evidence do not establish live Pod state.",
            "No diagnostic, acceptance, training, prediction, or target processing was rerun.",
            "Static bindings and diagnostic source equality do not verify actual GPU training imports.",
            "Unavailable old registration prevents old budget/checkpoint/identity verification.",
            "Six GPU records include one zombie snapshot; only five show a non-zombie concurrent GPU child.",
            "Paper2 archive contents and private backup were not provided or independently audited here.",
        ],
    }


def audit_bundle(archive_path, checkout):
    path = Path(archive_path)
    require(path.is_file() and not path.is_symlink(), "regular_archive_required")
    require(path.stat().st_size == EXPECTED_BYTES, "exact_archive_bytes")
    data = path.read_bytes()
    require(len(data) == EXPECTED_BYTES and sha(data) == EXPECTED_SHA256, "exact_archive_sha256")
    cache = {}
    def git_blob(name):
        require(name in EXPECTED_IDENTITIES, "unbound_git_path")
        if name not in cache:
            try:
                cache[name] = subprocess.check_output([
                    "git", "--no-replace-objects", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
                    "-C", str(Path(checkout)), "cat-file", "blob", REVISION + ":" + name,
                ], stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as exc:
                raise AuditError("fixed_git_blob_unavailable:" + name) from exc
        return cache[name]
    return audit_members(read_members(data), git_blob)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit_bundle(args.archive, args.checkout)
    except (AuditError, KeyError, TypeError) as exc:
        result = {"status": "FORMAL_SOURCE_RECEIPT_AUDIT_BLOCKED", "error_code": str(exc), "training_authorization": False}
        print(json.dumps(result, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
