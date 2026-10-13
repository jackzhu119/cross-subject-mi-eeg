#!/usr/bin/env python3
"""Default: metadata-only dry-run. Explicit modes transport/audit only.

Never fits, infers, computes target performance or starts another worker. An
author prior-use declaration and a Git-committed access plan are mandatory for
future --download/--audit-cache. Scientific and original-GDF gates stay separate.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
MANIFEST_PATH = ROOT / "evidence/dataset_sources/dreyer_nemar_manifest.txt"
PLAN_PATH = ROOT / "DREYER_DATA_ACCESS_PLAN.json"
PINNED_SHA256 = "061a8e215093e1bb0db8f80f95b112c60266acfa640284d05f92c0c6a5ddc544"
COMMON19 = ["Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz",
            "C2", "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "Pz"]
PATH_PATTERN = re.compile(r"sourcedata/sub-(\d{2})/eeg/sub-\1_task-(R[12]acquisition)_eeg\.edf")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def verified_manifest_and_plan(manifest_path=MANIFEST_PATH, plan_path=PLAN_PATH):
    data = manifest_path.read_bytes()
    if sha_bytes(data) != PINNED_SHA256:
        raise ValueError("provider_manifest_not_pinned_version")
    manifest = json.loads(data)
    plan = json.loads(plan_path.read_text())
    required = {"dataset": "Dreyer2023", "provider_dataset_id": "nm000250", "provider_version": "v1.0.5",
                "provider_manifest_sha256": PINNED_SHA256, "declared_persons": 87,
                "declared_acquisition_files": 174, "declared_acquisition_bytes": 2515343396,
                "canonical19_order": COMMON19, "eligible_run_names": ["R1acquisition", "R2acquisition"],
                "source_edf_cue_mapping": {"769": 1, "770": 2}, "metadata_excluded_subjects_primary": [17, 41],
                "model_training_enabled": False, "model_inference_enabled": False}
    for field, expected in required.items():
        if type(plan.get(field)) is not type(expected) or plan.get(field) != expected:
            raise ValueError("access_plan_mismatch:" + field)
    rows = [row for row in manifest if PATH_PATTERN.fullmatch(row["path"])]
    names, per_person = set(), collections.defaultdict(set)
    for row in rows:
        match = PATH_PATTERN.fullmatch(row["path"])
        person, run = int(match.group(1)), match.group(2)
        expected_url = "https://data.nemar.org/nm000250/v1.0.5/" + row["path"]
        if not 1 <= person <= 87 or row["path"] in names:
            raise ValueError("duplicate_or_invalid_person_path")
        if row["bytes_url"] != expected_url or row["url"] != expected_url:
            raise ValueError("provider_file_url_not_pinned_path")
        if row["checksum_algorithm"] != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", row["checksum"]):
            raise ValueError("missing_content_sha256")
        names.add(row["path"])
        per_person[person].add(run)
    if len(rows) != 174 or set(per_person) != set(range(1, 88)):
        raise ValueError("acquisition_manifest_cohort_count_mismatch")
    if any(runs != {"R1acquisition", "R2acquisition"} for runs in per_person.values()):
        raise ValueError("missing_primary_acquisition_run")
    if sum(row["size"] for row in rows) != 2515343396:
        raise ValueError("acquisition_manifest_size_mismatch")
    return sorted(rows, key=lambda row: row["path"]), plan


def author_gate(declaration_path):
    if declaration_path is None:
        raise ValueError("author_prior_use_declaration_missing")
    declaration = json.loads(declaration_path.read_text())
    required = {"status": "AUTHOR_CONFIRMED", "dataset": "Dreyer2023", "provider_dataset_id": "nm000250",
                "provider_manifest_sha256": PINNED_SHA256,
                "prior_proposed_decoder_results_inspected_or_used": False,
                "prior_dataset_scientific_analysis_performed": False,
                "used_in_other_manuscripts_or_projects": False,
                "acknowledged_current_metadata_annotation_and_precue_transport_preflight": True}
    for field, expected in required.items():
        actual = declaration.get(field)
        # In particular, null/0/empty are not an author-confirmed Boolean False.
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError("author_prior_use_gate_unresolved_or_incompatible:" + field)
    if not declaration.get("author_name") or not declaration.get("confirmation_record"):
        raise ValueError("author_confirmation_evidence_missing")
    timestamp = declaration.get("confirmed_at_utc")
    if not isinstance(timestamp, str):
        raise ValueError("author_confirmation_timestamp_missing")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("author_confirmation_timestamp_requires_timezone")
    return {"declaration_sha256": sha_bytes(declaration_path.read_bytes()), "status": "author_reported_prior_use_confirmed",
            "independent_identity_reconciliation_established": False}


def committed_plan_gate(revision, plan_path=PLAN_PATH):
    if revision is None or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("full_registration_commit_required")
    relative = str(plan_path.resolve().relative_to(REPO.resolve()))
    result = subprocess.run(["git", "-C", str(REPO), "show", revision + ":" + relative],
                            capture_output=True, check=False)
    if result.returncode or result.stdout != plan_path.read_bytes():
        raise ValueError("access_plan_not_identical_to_committed_registration")
    return {"commit": revision, "path": relative, "sha256": sha_bytes(result.stdout),
            "scientific_preprocessing_and_inference_freeze_established": False}


def import_header_module():
    source = ROOT / "scripts/check_dreyer_metadata.py"
    specification = importlib.util.spec_from_file_location("dreyer_header_preflight", source)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def audit_one(row, path, module):
    if not path.is_file() or path.is_symlink():
        raise ValueError("missing_or_symlinked_cached_edf")
    if path.stat().st_size != row["size"] or module.sha256(path) != row["checksum"]:
        raise ValueError("cached_file_size_or_sha256_mismatch")
    header = module.parse_header(path)
    events, precue = module.annotation_and_prefix(path, header)
    names = [channel["label"] for channel in header["channels"]]
    if len(names) != len(set(names)) or any(label not in names for label in COMMON19):
        raise ValueError("duplicate_or_missing_common19_channel")
    kept = [channel for channel in header["channels"] if channel["label"] in COMMON19]
    if any(channel["sampling_frequency_hz"] != 512 or channel["unit"] not in ("uV", "µV") for channel in kept):
        raise ValueError("common19_sampling_or_units_mismatch")
    cues = [event for event in events if event["description"] in ("769", "770")]
    counts = collections.Counter(event["description"] for event in cues)
    if counts != {"769": 20, "770": 20} or min(cue["onset"] for cue in cues) <= 1:
        raise ValueError("cue_counts_or_precue_prefix_mismatch")
    person = int(PATH_PATTERN.fullmatch(row["path"]).group(1))
    return {"path": row["path"], "size_bytes": path.stat().st_size, "sha256": row["checksum"],
            "subject": person, "run": PATH_PATTERN.fullmatch(row["path"]).group(2),
            "common19": COMMON19, "header_units": "uV", "si_conversion_scale": 1e-6,
            "eeg_native_numeric_is_not_assumed_volts": True, "sampling_hz": 512,
            "duration_seconds": header["duration_seconds"], "record_shape_verified": True,
            "cue_counts": dict(counts), "first_cue_onset_seconds": min(cue["onset"] for cue in cues),
            "cue_metadata": cues, "precue_one_second_format_scalability_verified": len(precue) == 19,
            "physical_acquisition_channel_order_authentication_established": False,
            "eligible_for_primary_by_provider_montage_flag_only": person not in (17, 41),
            "signal_only_qc_complete": False, "original_gdf_equivalence_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--download", action="store_true", help="Explicit future data transfer and metadata audit; no models.")
    mode.add_argument("--audit-cache", action="store_true", help="Explicit future byte/header/event audit of existing full cohort cache.")
    parser.add_argument("--author-declaration", type=Path)
    parser.add_argument("--registration-commit")
    parser.add_argument("--cache-dir", type=Path, default=Path("/workspace/mi-eeg-redesign-data/dreyer_acquisition"))
    parser.add_argument("--receipt", type=Path, default=ROOT / "evidence/dreyer_acquisition_dry_run.json")
    args = parser.parse_args()
    receipt = {"schema_version": 1, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
               "operation": "download_and_metadata_audit" if args.download else "audit_cache" if args.audit_cache else "metadata_only_dry_run",
               "source_fits_started_by_this_operation": 0, "target_fits": 0, "target_predictions": 0,
               "target_decoder_scores": 0, "task_eeg_features_computed": False,
               "full_cohort_signal_qc_complete": False, "original_gdf_equivalence_verified": False,
               "confirmatory_model_evaluation_authorized": False, "raw_bytes_downloaded_now": 0,
               "files": [], "errors": []}
    try:
        rows, plan = verified_manifest_and_plan()
        receipt.update(provider_dataset_id="nm000250", provider_version="v1.0.5",
                       provider_manifest_sha256=PINNED_SHA256, declared_acquisition_files=len(rows),
                       declared_acquisition_bytes=sum(row["size"] for row in rows),
                       source_edf_mirror_not_original_gdf=True, common19=COMMON19,
                       primary_n_upper_bound_before_signal_qc=85, metadata_excluded_subjects_primary=[17, 41],
                       cache_directory=str(args.cache_dir), declared_file_plan=[{name: row[name] for name in ["path", "size", "checksum", "bytes_url"]} for row in rows])
        if not (args.download or args.audit_cache):
            receipt["status"] = "DRY_RUN_NO_DOWNLOAD_NO_TARGET_PERFORMANCE_AUTHOR_AND_REGISTRATION_GATES_PENDING"
        else:
            # Both author facts and a real Git-committed plan are checked before
            # touching absent signals. Provider metadata is not the author answer.
            receipt["author_prior_use"] = author_gate(args.author_declaration)
            receipt["committed_access_plan"] = committed_plan_gate(args.registration_commit)
            module = import_header_module()
            if args.download:
                args.cache_dir.mkdir(parents=True, exist_ok=True)
                needed = sum(row["size"] for row in rows if not (args.cache_dir / row["path"]).is_file())
                if shutil.disk_usage(args.cache_dir).free < needed + 256 * 1024 ** 2:
                    raise ValueError("insufficient_free_space_for_fixed_cohort_and_reserve")
            for row in rows:
                path = args.cache_dir / row["path"]
                try:
                    existed = path.is_file()
                    if args.download:
                        if existed and (path.is_symlink() or path.stat().st_size != row["size"] or module.sha256(path) != row["checksum"]):
                            raise ValueError("existing_cached_file_corrupt_do_not_silently_overwrite")
                        transfer = module.download_one(row, args.cache_dir, online=True)
                        if not existed:
                            receipt["raw_bytes_downloaded_now"] += transfer["bytes"]
                    receipt["files"].append(audit_one(row, path, module))
                except (OSError, ValueError) as error:
                    receipt["errors"].append({"path": row["path"], "error_code": str(error)})
                    # Stop at a corrupted/missing file; never convert failed
                    # technical checks into a person exclusion or score rescue.
                    break
                finally:
                    args.receipt.parent.mkdir(parents=True, exist_ok=True)
                    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            receipt["all_declared_files_hash_header_event_audited"] = len(receipt["files"]) == 174 and not receipt["errors"]
            receipt["status"] = "SOURCE_EDF_MIRROR_METADATA_AUDIT_COMPLETE_SCIENTIFIC_GATES_STILL_CLOSED" if receipt["all_declared_files_hash_header_event_audited"] else "BLOCKED_METADATA_AUDIT_NO_MODEL_STARTED"
    except (OSError, ValueError) as error:
        receipt["errors"].append({"error_code": str(error)})
        receipt["status"] = "BLOCKED_DATA_ACCESS_GATE_NO_DOWNLOAD_NO_MODEL_STARTED"
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt),
                      "declared_files": receipt.get("declared_acquisition_files", 0),
                      "raw_bytes_downloaded_now": receipt["raw_bytes_downloaded_now"],
                      "target_predictions": 0, "target_decoder_scores": 0}, ensure_ascii=False))
    if receipt["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
