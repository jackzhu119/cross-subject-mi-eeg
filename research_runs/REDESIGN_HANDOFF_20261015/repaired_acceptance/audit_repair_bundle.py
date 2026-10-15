#!/usr/bin/env python3
"""Offline, stdlib-only review of one immutable repair evidence archive.

No payload is extracted or executed. Archived observations are not live Pod proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from urllib.parse import urlsplit

ARCHIVE_BYTES = 442155
ARCHIVE_SHA256 = "7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1"
REPAIR_REVISION = "461d079eca6e91addcfb59de944b966e51e1b30b"
BASE_REVISION = "1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac"
ENVIRONMENT = "/workspace/paper1-training-runtime-cp312-run01"
EXPECTED = {
    "environment/runtime_repair_run01.json": "0e487c7c8dcc83006681c8bdb066254da4184d49ab9f6ce96a07ad53d7cf092b",
    "environment/repair_run01.journal.jsonl": "db82e716e22ce7bcf48e6d7908f279b4b8a5ae9ececbd67714ec083d6aa89b0d",
    "environment/wheel-resolution.json": "a0ed2680c8e057a60aec9cde0d736c9869f3ea9e747f5a6216d79766d07f9b5a",
    "inputs/gpu_donor_inventory.json": "3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1",
    "fixed-repair-source/repair_preparation_once.py": "a6d6b30bdbda3594bf459cbc98031b82f3f2e7fe76fc26a29d15b687303375fc",
    "fixed-repair-source/manpage_policy.py": "701cf5e37461307776ef8f476655366cb4cb49619fc63ee7600e6ec1cb62a9b5",
    "fixed-repair-source/frozen_wheel_cache_index.json": "8a973c03b28297a5c533b8f86ea62a83da82b246197a99dd929a2d21494d51bf",
    "fixed-original-source/prepare_runtime_only.py": "7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3",
    "installed-manpages/ttx.1": "70b6e6fe938e8f50bbe93d905ef0f1cf00e3f6093e193779473b6f4ccb28b85c",
    "installed-manpages/isympy.1": "f4365d48e2102e292b0131e56e4743674e0b0508a0643504d3fa025c10ef741b",
}


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(value: object, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timestamp_without_timezone")
    return parsed


def safe_archive(path: Path, expected_bytes: int, expected_sha: str) -> tuple[dict, dict]:
    raw = path.read_bytes()
    require(len(raw) == expected_bytes and sha(raw) == expected_sha, "archive_identity")
    payloads = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            pure = PurePosixPath(name)
            require(member.isfile() and not pure.is_absolute() and ".." not in pure.parts
                    and "\\" not in name and str(pure) == name and name not in payloads,
                    "unsafe_or_duplicate_archive_member:" + name)
            require(0 <= member.size <= 8 * 1024 * 1024, "archive_member_size")
            stream = archive.extractfile(member)
            require(stream is not None, "missing_archive_stream")
            payloads[name] = stream.read()
            require(len(payloads[name]) == member.size, "short_archive_member")
    manifest = json.loads(payloads.pop("MANIFEST.json"))
    entries = manifest["payloads"]
    require(len({x["path"] for x in entries}) == len(entries), "duplicate_manifest_path")
    require(set(payloads) == {x["path"] for x in entries}, "manifest_membership")
    for entry in entries:
        body = payloads[entry["path"]]
        require(len(body) == entry["bytes"] and sha(body) == entry["sha256"],
                "manifest_payload_identity:" + entry["path"])
    return payloads, manifest


def audit(path: Path, repo: Path | None = None, failure_archive: Path | None = None) -> dict:
    payloads, manifest = safe_archive(path, ARCHIVE_BYTES, ARCHIVE_SHA256)
    require(len(payloads) == 30, "repair_payload_count")
    for name, expected in EXPECTED.items():
        require(sha(payloads[name]) == expected, "pinned_payload_identity:" + name)
    def load(name: str) -> dict:
        return json.loads(payloads[name])
    receipt = load("environment/runtime_repair_run01.json")
    review = load("dispatch/parent-review.json")
    slot = load("dispatch/runtime-preparation-slot.json")
    start, end = load("dispatch/start.json"), load("dispatch/completion.json")
    pre, post = load("dispatch/preflight.json"), load("dispatch/postflight.json")
    index = load("fixed-repair-source/frozen_wheel_cache_index.json")
    resolution = load("environment/wheel-resolution.json")
    donor = load("inputs/gpu_donor_inventory.json")
    journal = [json.loads(line) for line in payloads["environment/repair_run01.journal.jsonl"].splitlines()]
    require(start["command"] == load("dispatch/command.json"), "dispatch_command_identity")
    require(start["automatic_retry"] is False and end["automatic_retry"] is False
            and end["exit_code"] == 0, "single_attempt_exit")
    began, ended = timestamp(end["started_utc"]), timestamp(end["ended_utc"])
    require(began == timestamp(start["utc"]) and began < ended, "actual_times")
    require(timestamp(review["reviewed_at_utc"]) < timestamp(slot["issued_at_utc"]) <= began
            and ended < timestamp(slot["expires_at_utc"])
            and ended < timestamp(review["expires_at_utc"]), "fresh_review_slot_window")
    require(review["issuer"] == "dot_parent"
            and review["status"] == "DOT_PARENT_SINGLE_OFFLINE_REPAIR_APPROVED"
            and slot["issuer"] == "dot" and slot["operation"] == "runtime_preparation",
            "review_slot_role")
    require(slot["pod_id"] == "52ivinpjwv947i" and slot["container_id"] == "a7d3f0e408a4",
            "recorded_pod_container")
    for field, member in (("review_sha256", "dispatch/parent-review.json"),
                          ("slot_sha256", "dispatch/runtime-preparation-slot.json"),
                          ("repair_controller_sha256", "fixed-repair-source/repair_preparation_once.py"),
                          ("donor_report_sha256", "inputs/gpu_donor_inventory.json"),
                          ("wheel_resolution_sha256", "environment/wheel-resolution.json")):
        require(receipt[field] == sha(payloads[member]), "receipt_binding:" + field)
    for field, member in (("repair_controller_sha256", "fixed-repair-source/repair_preparation_once.py"),
                          ("manpage_policy_sha256", "fixed-repair-source/manpage_policy.py"),
                          ("wheel_cache_index_sha256", "fixed-repair-source/frozen_wheel_cache_index.json"),
                          ("donor_report_sha256", "inputs/gpu_donor_inventory.json"),
                          ("wheel_resolution_sha256", "environment/wheel-resolution.json")):
        require(review[field] == sha(payloads[member]), "parent_review_binding:" + field)
    require(load("dispatch/controller-console.stdout.log") == receipt
            and payloads["dispatch/controller-console.stderr.log"] == b"", "controller_console_receipt")
    require(receipt["repair_revision"] == REPAIR_REVISION and review["repair_revision"] == REPAIR_REVISION
            and receipt["original_base_revision"] == BASE_REVISION
            and review["base_revision"] == BASE_REVISION and receipt["environment"] == ENVIRONMENT,
            "code_environment_binding")
    require(receipt["status"] == "REPAIRED_PREPARED_IMPORT_SOURCE_REVIEW_PENDING"
            and receipt["future_acceptance_adapter_review_required"] is True, "independent_receipt_status")
    for key in ("training_authorization", "target_EEG_read", "runtime_import_acceptance_passed",
                "source_acceptance_passed", "old_accounting_reconciled", "old_cost_known", "budget_reset",
                "budget_expanded"):
        require(receipt[key] is False, "gate_not_closed:" + key)
    require(receipt["new_fits"] == 0 and post["repair_attempts"] == 1
            and post["original_runtime_preparation_receipt_exists"] is False, "no_old_receipt_or_fit")
    require(len(index["wheels"]) == 79 == len(resolution["install"]), "resolution_count")
    resolved = {canonical_name(x["metadata"]["name"]): x for x in resolution["install"]}
    require(len(resolved) == 79, "unique_resolved_names")
    installed = receipt["installed_versions_metadata_only"]
    closure = {}
    for wheel in index["wheels"]:
        name = canonical_name(wheel["name"])
        row = resolved[name]
        source = row["download_info"]
        require(source["url"] == wheel["official_url"]
                and urlsplit(source["url"]).scheme == "https"
                and urlsplit(source["url"]).netloc == "files.pythonhosted.org"
                and urlsplit(source["url"]).path.rsplit("/", 1)[-1] == wheel["file"]
                and source["archive_info"]["hashes"]["sha256"] == wheel["sha256"]
                and row["metadata"]["version"] == wheel["version"] == installed[name],
                "closure_binding:" + name)
        closure[name] = wheel["version"]
    donor_versions = {canonical_name(k): v["version"] for k, v in donor["distributions"].items()}
    require(len(donor_versions) == 17 and not set(donor_versions) & set(closure), "gpu_closure_separation")
    require(installed == {**closure, **donor_versions, "pip": "24.0"}
            and len(installed) == 97, "installed97_metadata_partition")
    require(receipt["donor_metadata_unchanged"] is True
            and receipt["no_resolver_or_download_executed"] is True
            and receipt["no_second_environment_created"] is True, "recorded_repair_only_scope")
    require([x["stage"] for x in journal] == ["REPAIR_ATTEMPT_CONSUMED_BEFORE_INSTALL",
            "OWNED_OFFLINE_CHILD_START", "OWNED_OFFLINE_CHILD_EXIT0", "OWNED_OFFLINE_CHILD_START",
            "OWNED_OFFLINE_CHILD_EXIT0", "REPAIR_PREPARATION_COMPLETE_ACCEPTANCE_STILL_BLOCKED"],
            "one_shot_journal_sequence")
    require(journal[-1]["repair_receipt_sha256"] == sha(payloads["environment/runtime_repair_run01.json"]),
            "journal_receipt_binding")
    install = journal[1]["command"]
    require(install[:10] == [ENVIRONMENT + "/bin/python", "-I", "-B", "-m", "pip", "install",
                            "--no-deps", "--no-index", "--no-cache-dir", "--disable-pip-version-check"],
            "offline_install_flags")
    require(install == journal[2]["command"] and len(install[10:]) == 79
            and {PurePosixPath(x).name for x in install[10:]} == {x["file"] for x in index["wheels"]}
            and all(PurePosixPath(x).parent == PurePosixPath(ENVIRONMENT) / "reviewed-wheels" for x in install[10:]),
            "same79_cache_install")
    require(journal[3]["command"] == journal[4]["command"]
            == [ENVIRONMENT + "/bin/python", "-I", "-B", "-m", "pip", "check"], "pip_check_command")
    log = payloads["repair/paper1-repair-run01.log"].decode()
    require(log.count("Processing ") == 79 and log.count("Successfully installed ") == 1
            and log.count("No broken requirements found.") == 1, "install_pip_check_logs")
    require(receipt["actual_total_owned_bytes"] == receipt["observed_peak_owned_bytes"] == 869490688
            and receipt["actual_total_owned_bytes"] < 3 * 1024**3
            and journal[0]["actual_total_storage_cap_bytes"] == 3 * 1024**3
            and journal[0]["actual_reserved_free_floor_bytes"] == 15 * 1024**3
            and post["free_bytes"] == 43565662208, "recorded_storage_budget")
    require(pre["GPU_compute"] == post["GPU_compute"] == "", "archived_gpu_empty_snapshots")
    require([len(payloads["installed-manpages/" + name]) for name in ("ttx.1", "isympy.1")] == [5377, 6659],
            "actual_manpage_lengths")
    manpages = load("dispatch/installed-manpage-hashes.json")
    require(len(manpages) == 2, "postflight_manpage_count")
    for row in manpages:
        name = PurePosixPath(row["path"]).name
        require(row["path"] == ENVIRONMENT + "/share/man/man1/" + name
                and row["bytes"] == len(payloads["installed-manpages/" + name])
                and row["sha256"] == sha(payloads["installed-manpages/" + name]),
                "postflight_actual_manpage_binding")
    original_logs = post["original_failure_logs"]
    old_entries = {x["path"].rsplit("/", 1)[-1]: x for x in index["evidence_payloads"]}
    require(len(original_logs) == 4 and all(x["unchanged"] is True for x in original_logs),
            "four_old_logs_unchanged_record")
    for row in original_logs:
        candidates = [x for x in old_entries.values() if x["sha256"] == row["sha256"] and x["bytes"] == row["bytes"]]
        require(candidates, "old_failure_log_historical_identity")
    old_archive_checked = False
    if failure_archive is not None:
        safe_archive(failure_archive, 423996, "7c83bcb991857dd99b7cda2b4bd8f9fe467d87217fb3a73c408b7b1474f4b3a0")
        old_archive_checked = True
    source_readback = {}
    if repo is not None:
        for filename in ("repair_preparation_once.py", "manpage_policy.py", "frozen_wheel_cache_index.json"):
            rel = "research_runs/REDESIGN_HANDOFF_20261015/repair_run01/" + filename
            fixed = subprocess.check_output(["git", "-C", str(repo), "show", REPAIR_REVISION + ":" + rel])
            require(fixed == payloads["fixed-repair-source/" + filename], "fixed_git_source:" + filename)
            source_readback[filename] = sha(fixed)
    return {
        "schema_version": 1,
        "status": "INDEPENDENT_OFFLINE_REPAIR_EVIDENCE_PASS_RUNTIME_SOURCE_STILL_UNACCEPTED",
        "archive": {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256, "payloads": 30},
        "manifest_created_at_utc": manifest["created_at_utc"],
        "all_payload_bytes_sha256_verified": True, "safe_regular_unique_members_only": True,
        "recorded_execution": {"started_utc": end["started_utc"], "ended_utc": end["ended_utc"],
            "exit_code": 0, "supervisor_pid": start["supervisor_pid"], "controller_pid": start["controller_pid"],
            "automatic_retry": False, "review_covered_dispatch": True, "fresh_slot_covered_dispatch": True},
        "repair_revision": REPAIR_REVISION, "base_revision": BASE_REVISION,
        "environment": ENVIRONMENT, "payload_pins": EXPECTED,
        "review_sha256": sha(payloads["dispatch/parent-review.json"]),
        "slot_sha256": sha(payloads["dispatch/runtime-preparation-slot.json"]),
        "fixed_git_source_readback": source_readback,
        "closure": {"wheel_count": 79, "compressed_bytes": sum(x["bytes"] for x in index["wheels"]),
            "official_resolution_identities_verified": True, "installed_metadata_distribution_count": 97,
            "partition": {"frozen_wheel_closure": 79, "gpu_donor": 17, "seed_pip": 1},
            "two_installed_manpage_payloads_verified": True, "only_offline_install_and_pip_check_recorded": True},
        "old_failure": {"original_preparation_receipt_absent_in_postflight": True,
            "four_logs_recorded_hashes_match_historical_index": True,
            "original_failure_archive_locally_verified": old_archive_checked},
        "storage": {"recorded_peak_and_final_owned_bytes": 869490688,
            "postflight_free_bytes": post["free_bytes"], "original_total_cap_bytes": 3 * 1024**3,
            "reserved_free_floor_bytes": 15 * 1024**3, "new_environment_created": False},
        "limits": ["No wheel binaries are contained in this archive; cached-wheel rehash is an authenticated controller observation, not an independent offline rehash of wheel bytes.",
            "No installed scientific files or exhaustive donor payload bytes are included; 97 installed versions are metadata observations, not runtime import acceptance.",
            "Old failure log bytes are not repeated in this archive; fresh postflight hashes agree with historical evidence, but this audit cannot reobserve Pod files.",
            "Pre/post GPU and disk snapshots do not establish continuous monitoring or present Pod state.",
            "Source MAT files are not in the archive and have not been observed as restored in the new container.",
            "This offline audit performs no network calls, installation, CUDA imports, EEG reads, source diagnostic or fit; no next Pod operation is authorized."],
        "runtime_import_acceptance_passed": False, "source_acceptance_passed": False,
        "old_accounting_reconciled": False, "old_cost_known": False,
        "target_mapping_or_backup_accepted": False, "training_authorization": False,
        "budget_reset": False, "budget_expanded": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--failure-archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.archive, args.repo, args.failure_archive)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
