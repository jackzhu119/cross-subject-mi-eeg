"""Q15 V001/V002 metadata-only, local-file audit (no downloads or model calls).

The only implemented raw metadata extractor is an explicitly opted-in tiny
synthetic JSON fixture for tests. Real Lee/Cho MAT files are SHA-256 checked
but then fail closed until a separately reviewed raw-provider adapter and an
independently authenticated provider inventory exist. The resulting receipt
is never permission to score an external cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTRACT_PATH = ROOT / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json"
STRUCTURAL_VALIDATOR_PATH = CONTRACT_PATH.with_name("q15_validate_contract.py")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _structural_validator():
    spec = importlib.util.spec_from_file_location("q15_validate_contract", STRUCTURAL_VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_metadata(path: Path) -> dict:
    # Only explicit tiny test fixtures are decoded. Never deserialize MAT/EEG
    # bytes through an unreviewed adapter just to make a gate appear green.
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Synthetic metadata fixture exceeds 1 MiB")
    return _read_json(path)


def _event_metadata_ok(item: dict, required_window: list[float]) -> bool:
    """Inspect cue/sample coverage and label definitions, never predictions."""
    events = item.get("events")
    rate = item.get("sampling_rate_hz")
    n_samples = item.get("signal_n_samples")
    duration = item.get("task_duration_s")
    if (
        not isinstance(events, list) or not events
        or not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate <= 60
        or not isinstance(n_samples, int) or isinstance(n_samples, bool) or n_samples <= 0
        or not isinstance(duration, (int, float)) or isinstance(duration, bool)
        or duration < required_window[1]
    ):
        return False
    onsets: set[int] = set()
    labels: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            return False
        onset = event.get("onset_sample")
        label = event.get("label")
        if (
            not isinstance(onset, int) or isinstance(onset, bool) or onset < 0
            or onset in onsets or label not in {"left_hand", "right_hand"}
        ):
            return False
        onsets.add(onset)
        labels.add(label)
        # Half-open [0.5, 2.5) source window must exist after every MI cue.
        if onset + round(required_window[1] * rate) > n_samples:
            return False
    return labels == {"left_hand", "right_hand"}


def audit_manifest(manifest_path: Path, *, synthetic_fixture: bool = False) -> dict:
    """Hash listed local files and inspect only supported metadata adapters.

    The manifest is an expected-inventory claim, not proof of a provider's
    original inventory. Consequently ``provider_inventory_verified`` remains
    false until a future independent provider-manifest adapter is reviewed.
    """
    manifest_path = manifest_path.resolve()
    # Real files use the separately reviewed prospective operational adapter.
    # Its receipt preserves unverified physical calibration explicitly; fixture
    # receipts remain distinct and can never be substituted for a real cohort.
    try:
        claim = _read_json(manifest_path)
    except (OSError, ValueError, TypeError):
        claim = {}
    claim_files = claim.get("files") if isinstance(claim.get("files"), list) else []
    if not synthetic_fixture and any(
        row.get("adapter") == "real_mat_operational_v1"
        for row in claim_files if isinstance(row, dict)
    ):
        from scripts.q15_real_metadata import audit_inventory
        return audit_inventory(manifest_path)
    plan = _read_json(CONTRACT_PATH)
    try:
        manifest_hash = _sha256(manifest_path)
    except OSError:
        manifest_hash = None
    result: dict = {
        "schema_version": 1,
        "status": "blocked_invalid_manifest",
        "dataset": None,
        "metadata_only": True,
        "predictions_computed": False,
        "model_predictions_computed": False,
        "performance_metrics_computed": False,
        "target_fits": 0,
        "external_prediction_authorized": False,
        "source_training_authorized": False,
        "synthetic_fixture": synthetic_fixture,
        "raw_hashes_verified": False,
        "provider_inventory_verified": False,
        "auditor_sha256": _sha256(Path(__file__)),
        "provider_manifest_path": str(manifest_path),
        "provider_manifest_sha256": manifest_hash,
        "provider_manifest_authenticated": False,
        "expected_file_ids": [],
        "files": [],
        "failed_files": [],
        "blocking_reasons": [],
    }
    try:
        manifest = _read_json(manifest_path)
        if manifest.get("schema_version") != 1:
            raise ValueError("Unknown inventory manifest schema")
        dataset = manifest.get("dataset")
        specs = {entry["dataset"]: entry for entry in plan["metadata_audits"]}
        if dataset not in specs:
            raise ValueError("Dataset is not a frozen Q15 external cohort")
        result["dataset"] = dataset
        for field in ("provider_version", "loader_version", "license", "provider_inventory_source"):
            value = manifest.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Missing {field}")
            result[field] = value
        expected_ids = manifest.get("expected_file_ids")
        records = manifest.get("files")
        if (
            not isinstance(expected_ids, list) or not expected_ids
            or len(expected_ids) != len(set(expected_ids))
            or not isinstance(records, list) or not records
            or len(records) != len(expected_ids)
            or {record.get("file_id") for record in records} != set(expected_ids)
        ):
            raise ValueError("Expected and observed file inventories differ")
        result["expected_file_ids"] = expected_ids
        result["all_expected_files_hashed"] = False
        required_channels = plan["new_source_arm"]["channels"]
        required_window = plan["new_source_arm"]["cue_window_s_half_open"]
        unsupported = False
        incompatible = False
        for record in records:
            raw_path = Path(record["path"])
            if not raw_path.is_absolute():
                raw_path = manifest_path.parent / raw_path
            raw_path = raw_path.resolve()
            expected_hash = record.get("sha256")
            file_id = record["file_id"]
            if SHA256.fullmatch(str(expected_hash)) is None:
                result["failed_files"].append(file_id)
                result["blocking_reasons"].append(f"invalid_expected_sha256:{file_id}")
                continue
            if not raw_path.is_file():
                result["failed_files"].append(file_id)
                result["blocking_reasons"].append(f"raw_file_missing:{file_id}")
                continue
            actual_hash = _sha256(raw_path)
            if actual_hash != expected_hash:
                result["failed_files"].append(file_id)
                result["blocking_reasons"].append(f"raw_hash_mismatch:{file_id}")
                continue
            base = {"file_id": file_id, "path": str(raw_path), "sha256": actual_hash}
            adapter = record.get("adapter")
            if adapter != "synthetic_json_v1" or not synthetic_fixture:
                unsupported = True
                result["files"].append(base)
                result["blocking_reasons"].append(f"raw_adapter_unverified:{file_id}")
                continue
            try:
                metadata = _fixture_metadata(raw_path)
                for key in ("file_id", "subject", "session", "run"):
                    if metadata.get(key) != record.get(key):
                        raise ValueError(f"Manifest and raw metadata disagree on {key}")
                if metadata.get("file_id") != file_id:
                    raise ValueError("Raw file ID mismatch")
                if not _event_metadata_ok(metadata, required_window):
                    raise ValueError("Cue-relative event labels/window unavailable")
                if dataset == "Lee2019_MI" and metadata.get("run_role") != "offline_train":
                    raise ValueError("Lee online/unlabeled MI runs are excluded")
                if dataset == "Cho2017" and metadata.get("run_role") != "offline_labeled":
                    raise ValueError("Cho run role is not audited labeled MI")
                metadata.pop("events", None)  # avoid unnecessary trial-level data in receipt
                result["files"].append(metadata | base)
            except (AttributeError, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
                incompatible = True
                result["files"].append(base)
                result["blocking_reasons"].append(f"metadata_incompatible:{file_id}:{exc}")
        result["raw_hashes_verified"] = not result["failed_files"]
        result["all_expected_files_hashed"] = result["raw_hashes_verified"]
        result["n_files"] = len(records)
        if result["failed_files"]:
            result["status"] = "blocked_raw_integrity"
        elif unsupported:
            result["status"] = "blocked_raw_adapter_unverified"
        elif incompatible:
            result["status"] = "blocked_incompatible_metadata"
        else:
            try:
                structural = _structural_validator().validate_metadata_receipt(
                    result, specs[dataset], required_channels
                )
            except AssertionError as exc:
                result["status"] = "blocked_incompatible_metadata"
                result["blocking_reasons"].append(f"cohort_contract_incompatible:{exc}")
            else:
                result["n_subjects"] = structural["subjects"]
                result["status"] = "metadata_passed_non_authorizing_synthetic_fixture"
    except (AssertionError, AttributeError, KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        result["status"] = "blocked_invalid_manifest_or_metadata"
        result["blocking_reasons"].append(f"audit_failed:{exc}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Local expected-file inventory; no downloads")
    parser.add_argument("--output", type=Path, required=True, help="Versioned non-authorizing receipt path")
    parser.add_argument("--synthetic-fixture", action="store_true", help="Test-only JSON metadata extractor; never scientific release")
    args = parser.parse_args()
    receipt = audit_manifest(args.manifest, synthetic_fixture=args.synthetic_fixture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(json.dumps({key: receipt[key] for key in ("status", "dataset", "raw_hashes_verified", "provider_inventory_verified", "external_prediction_authorized", "blocking_reasons")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
