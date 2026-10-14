"""Synthetic receipt and tamper tests; no EEG or scientific runtime execution."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("formal_receipt_auditor", HERE / "audit_formal_source_acceptance_bundle.py")
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


def dump(obj):
    return (json.dumps(obj, indent=2) + "\n").encode()


def manifest(members):
    members["manifest.json"] = dump({"files": [
        {"path": name, "bytes": len(value), "sha256": auditor.sha(value)}
        for name, value in members.items() if name != "manifest.json"
    ]})
    return members


@pytest.fixture
def synthetic(monkeypatch):
    # Deliberately fake source bytes/hashes, only within this synthetic fixture.
    blobs = {name: (name + "\n").encode() for name in auditor.EXPECTED_IDENTITIES}
    identities = {name: auditor.sha(value) for name, value in blobs.items()}
    monkeypatch.setattr(auditor, "EXPECTED_IDENTITIES", identities)
    members = {name: b"placeholder\n" for name in auditor.EXPECTED_NAMES}
    report = {
        "status": "SOURCE_NUMERICS_MATCH_PRIVATE_PACKAGE_OR_TRAINING_RUNTIME_PENDING",
        "code_revision": auditor.REVISION, "source_complete_exact_hash_gate_passed": True,
        "source_array_hashes": dict(auditor.EXPECTED_ARRAYS), "source_files": 18,
        "source_runs": 108, "source_trials": 2592, "new_fits": 0,
        "checked_at_utc": "2026-10-14T14:24:20.566766+00:00",
        "private_full_package_sha256": None,
        "private_package_audit": {"status": "PRIVATE_FULL_PACKAGE_NOT_ACCESSIBLE_NOT_AUDITED"},
        "old_accounting_observation": {"observed": False, "reason": "old_registration_not_accessible"},
        "old_accounting_records_unchanged": True,
        "consumer_static_bindings": {"train_exploratory.py": True, "validate_source.py": True, "prepare_data.py": True},
        "execution_file_identities": identities,
        "numerical_execution": {
            "policy_id": "explicit_sos_initial_state_v1_20261014",
            "policy_sha256": identities[auditor.CLOUD + "config/numerical_execution_v1.json"],
            "execution_module_sha256": identities[auditor.CLOUD + "scripts/formal_core_inputs.py"],
            "historical_loader_sha256": "03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5",
            "historical_generation_BLAS_identity_established": False,
            "state_application": "every_band_every_trial_source_and_target",
        },
    }
    for name in (
        "training_consumer_imports_verified", "private_full_package_independently_verified",
        "target_complete_restoration_verified", "target_frozen_input_mapping_verified",
        "runtime_GPU_preflight_verified", "old_machine_identity_proven", "budget_resume_authorized",
        "checkpoint_and_verified_backup_gates_passed", "training_authorization", "target_EEG_read",
        "target_predictions_computed", "source_arrays_serialized_or_replaced", "historical_generation_BLAS_identity_established",
    ):
        report[name] = False
    members[auditor.REPORT] = members[auditor.OUTPUT + ".worker.log"] = dump(report)
    members[auditor.SOURCE_COPY] = blobs[auditor.FORMAL + "accept_source_numerics.py"]
    starts = {"paper1": {"command": list(auditor.EXPECTED_COMMAND), "pid": 29459,
                         "start_utc": "2026-10-14T14:23:46.928326+00:00"},
              "paper2": {"command": ["bash", "launcher.sh"], "pid": 29460,
                         "start_utc": "2026-10-14T14:23:46.929164+00:00"}}
    completion = {"processes": deepcopy(starts), "free_bytes": 20443377664, "automatic_next_fit": False}
    completion["processes"]["paper1"].update(exit_code=3, exit_observed_utc="2026-10-14T14:24:21.579247+00:00")
    completion["processes"]["paper2"].update(exit_code=75, exit_observed_utc="2026-10-14T14:23:57.575838+00:00")
    members[auditor.PARALLEL + "starts.json"] = dump(starts)
    members[auditor.PARALLEL + "completion.json"] = dump(completion)
    members[auditor.OUTPUT + ".exit-code"] = b"3\n"
    members[auditor.PARALLEL + "paper2.exit-code"] = b"75\n"
    members[auditor.PARALLEL + "execution-claim.json"] = dump({
        "single_p1_acceptance": True, "single_p2_fit": True, "automatic_retry": False, "supervisor_pid": 29454})
    members[auditor.PARALLEL + "preparation.log"] = (
        'COMMAND ["fetch"]\nCOMMAND ["fetch"]\nCOMMAND ["worktree", "add"]\n'
        'json.decoder.JSONDecodeError: Extra data: line 2 column 1\n').encode()
    job = {"job_id": "paper2-synthetic", "subject": "sub-4", "seed": 20261014}
    members[auditor.PARALLEL + "plan-only.json"] = dump({"status": "plan_only", "fit_executed": False, "next_job": job})
    members[auditor.PARALLEL + "preparation-parse-correction.log"] = (
        'wrapper JSON multi-line parsing correction only; no fit or data acceptance was run.\n' + json.dumps(job) + '\n').encode()
    members[auditor.PARALLEL + "paper2-launcher.log"] = (json.dumps({
        **job, "status": "fit_saved_private_backup_pending", "R2_backup_verified": False, "stop_Pod": False}) + "\n").encode()
    samples = []
    for index in range(10):
        processes = '\n'.join([
            "PID PPID STAT %CPU RSS COMMAND", "29454 1 S 0 0 python3", "29459 29454 S 0 0 timeout",
            "29460 29454 S 0 0 bash", "29461 29459 Rl 10 100 python", "29467 29460 S 0 0 bash",
            "29470 29467 S 0 0 timeout", "29471 29470 " + ("Zl" if index == 9 else "Rl") + " 10 100 python",
        ]) + '\n'
        samples.append(json.dumps({
            "utc": f"2026-10-14T14:23:{47 + index:02d}.000000+00:00", "both_child_processes_live": True,
            "sanitized_processes": processes, "gpu_compute": "29471, 214\n" if index >= 4 else ""}))
    members[auditor.PARALLEL + "overlap-samples.jsonl"] = ('\n'.join(samples) + '\n').encode()
    return manifest(members), blobs


def test_synthetic_receipt_is_diagnostic_and_blocked(synthetic):
    members, blobs = synthetic
    out = auditor.audit_members(members, blobs.__getitem__)
    assert out["training_authorization"] is False
    assert out["samples_with_non_zombie_paper2_GPU_child"] == 5
    assert out["samples_with_GPU_PID_already_zombie"] == 1
    assert out["EEG_arrays_independently_recomputed_by_this_audit"] is False


@pytest.mark.parametrize("field", [
    "training_authorization", "training_consumer_imports_verified", "private_full_package_independently_verified",
    "target_EEG_read", "target_predictions_computed", "budget_resume_authorized", "old_machine_identity_proven",
    "runtime_GPU_preflight_verified", "source_arrays_serialized_or_replaced", "target_frozen_input_mapping_verified",
])
def test_recomputed_manifest_cannot_hide_scope_change(synthetic, field):
    members, blobs = synthetic
    report = auditor.parse_json(members[auditor.REPORT]); report[field] = True
    members[auditor.REPORT] = members[auditor.OUTPUT + ".worker.log"] = dump(report)
    manifest(members)
    with pytest.raises(auditor.AuditError, match="pending_gate"):
        auditor.audit_members(members, blobs.__getitem__)


@pytest.mark.parametrize("field,value", [("source_trials", 2591), ("source_runs", 109), ("new_fits", 1), ("source_files", True)])
def test_count_types_and_exact_counts(synthetic, field, value):
    members, blobs = synthetic
    report = auditor.parse_json(members[auditor.REPORT]); report[field] = value
    members[auditor.REPORT] = members[auditor.OUTPUT + ".worker.log"] = dump(report)
    manifest(members)
    with pytest.raises(auditor.AuditError, match="report_count"):
        auditor.audit_members(members, blobs.__getitem__)


def test_worker_report_mismatch(synthetic):
    members, blobs = synthetic
    members[auditor.OUTPUT + ".worker.log"] += b"\n"
    manifest(members)
    with pytest.raises(auditor.AuditError, match="worker_log_disagree"):
        auditor.audit_members(members, blobs.__getitem__)


def test_original_parse_failure_cannot_be_erased(synthetic):
    members, blobs = synthetic
    members[auditor.PARALLEL + "preparation.log"] = b"success\n"
    manifest(members)
    with pytest.raises(auditor.AuditError, match="parse_error_missing"):
        auditor.audit_members(members, blobs.__getitem__)


def test_runtime_role_cannot_be_relabeled_as_training(synthetic):
    members, blobs = synthetic
    starts = auditor.parse_json(members[auditor.PARALLEL + "starts.json"])
    completion = auditor.parse_json(members[auditor.PARALLEL + "completion.json"])
    starts["paper1"]["command"][-1] = "training"
    completion["processes"]["paper1"]["command"][-1] = "training"
    members[auditor.PARALLEL + "starts.json"] = dump(starts)
    members[auditor.PARALLEL + "completion.json"] = dump(completion)
    manifest(members)
    with pytest.raises(auditor.AuditError, match="acceptance_command"):
        auditor.audit_members(members, blobs.__getitem__)


def test_zombie_is_not_counted_as_active_gpu_overlap(synthetic):
    members, blobs = synthetic
    members[auditor.PARALLEL + "overlap-samples.jsonl"] = members[auditor.PARALLEL + "overlap-samples.jsonl"].replace(b"29471 29470 Zl", b"29471 29470 Rl")
    manifest(members)
    with pytest.raises(auditor.AuditError, match="GPU_overlap_scope"):
        auditor.audit_members(members, blobs.__getitem__)


def test_forged_gpu_parent_chain(synthetic):
    members, blobs = synthetic
    members[auditor.PARALLEL + "overlap-samples.jsonl"] = members[auditor.PARALLEL + "overlap-samples.jsonl"].replace(b"29471 29470", b"29471 29459")
    manifest(members)
    with pytest.raises(auditor.AuditError, match="GPU_paper2_parent_chain"):
        auditor.audit_members(members, blobs.__getitem__)


def test_manifest_hash_tamper(synthetic):
    members, blobs = synthetic
    members[auditor.REPORT] += b"\n"
    with pytest.raises(auditor.AuditError, match="manifest_bytes"):
        auditor.audit_members(members, blobs.__getitem__)


def test_payload_source_must_match_fixed_blob(synthetic):
    members, blobs = synthetic
    members[auditor.SOURCE_COPY] += b"# other code\n"
    manifest(members)
    with pytest.raises(auditor.AuditError, match="archived_source_mismatch"):
        auditor.audit_members(members, blobs.__getitem__)


def test_fixed_git_blob_must_match_pinned_hash(synthetic):
    members, blobs = synthetic
    blobs[next(iter(blobs))] += b"changed"
    with pytest.raises(auditor.AuditError, match="fixed_revision_file_mismatch"):
        auditor.audit_members(members, blobs.__getitem__)


@pytest.mark.parametrize("data", [b'{"a":1,"a":2}', b'{"x":NaN}', b'not json'])
def test_strict_json(data):
    with pytest.raises(auditor.AuditError):
        auditor.parse_json(data)


def tar_data(name, kind=tarfile.REGTYPE):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        item = tarfile.TarInfo(name); item.type = kind
        if kind == tarfile.REGTYPE:
            item.size = 2; archive.addfile(item, io.BytesIO(b"{}"))
        else:
            item.linkname = "manifest.json"; archive.addfile(item)
    return stream.getvalue()


@pytest.mark.parametrize("name", ["../escape.json", "/absolute.json", "x/../escape.json", "x//a.json", "C:/a.json", "x\\a.json"])
def test_unsafe_tar_path(name):
    with pytest.raises(auditor.AuditError):
        auditor.read_members(tar_data(name))


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE])
def test_nonregular_tar_members(kind):
    with pytest.raises(auditor.AuditError, match="nonregular"):
        auditor.read_members(tar_data("manifest.json", kind))


def test_outer_pin_rejects_other_archive(tmp_path):
    path = tmp_path / "other.tar.gz"; path.write_bytes(b"x" * auditor.EXPECTED_BYTES)
    with pytest.raises(auditor.AuditError, match="exact_archive_sha256"):
        auditor.audit_bundle(path, HERE)


def test_archive_symlink_is_rejected(tmp_path):
    path = tmp_path / "real"; path.write_bytes(b"x")
    link = tmp_path / "link"; link.symlink_to(path)
    with pytest.raises(auditor.AuditError, match="regular_archive"):
        auditor.audit_bundle(link, HERE)
