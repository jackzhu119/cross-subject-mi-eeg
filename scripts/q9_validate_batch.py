"""Audit Q9 batch receipts without making a scientific performance claim.

The batch audit proves command completion, source-frozen selection receipts,
expected fit counts, and unchanged logs/manifest. A separate experiment-level
validator is still required before manuscript statistics are reported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate(batch_dir: Path) -> dict:
    manifest_path = batch_dir / "batch_manifest.json"
    manifest = read_json(manifest_path)
    matrix_path = Path(manifest["matrix_path"])
    errors: list[str] = []
    if digest(matrix_path) != manifest["matrix_sha256"]:
        errors.append("Experiment matrix hash changed")
    for relative, expected in manifest.get("code_sha256", {}).items():
        path = ROOT / relative
        if not path.is_file() or digest(path) != expected:
            errors.append(f"Code hash changed: {relative}")
    jobs = manifest["jobs"]
    if not jobs or len({job["job_id"] for job in jobs}) != len(jobs):
        errors.append("Job list empty or duplicate IDs")
    findings: list[dict] = []
    for job in jobs:
        job_id = job["job_id"]
        status_path = batch_dir / "jobs" / job_id / "status.json"
        log_path = batch_dir / "jobs" / job_id / "run.log"
        result = {"job_id": job_id, "phase": job["phase"], "complete": False}
        try:
            status = read_json(status_path)
            if status.get("status") != "complete" or status.get("exit_code") != 0:
                raise ValueError("job did not exit successfully")
            if status.get("argv") != job["argv"]:
                raise ValueError("job command differs from frozen manifest")
            if digest(log_path) != status.get("log_sha256"):
                raise ValueError("job log hash differs from receipt")
            completion_path = Path(job["completion_status"])
            output_root = Path(manifest["output_root"]).resolve()
            if not completion_path.resolve().is_relative_to(output_root):
                raise ValueError("completion marker outside Q9 results")
            completed = read_json(completion_path)
            if completed.get("status") != job["completion_value"]:
                raise ValueError("experiment completion marker not in expected state")
            if digest(completion_path) != status.get("completion_status_sha256"):
                raise ValueError("experiment completion marker changed after job")
            if job["phase"] == "selection":
                selection_file = completion_path.parent / "selection.csv"
                if digest(selection_file) != completed.get("selection_sha256"):
                    raise ValueError("frozen selected-epoch CSV hash mismatch")
                if int(completed.get("inner_fits", -1)) != 36:
                    raise ValueError("selection receipt does not show 36 inner fits")
            if job["phase"] == "final":
                if int(completed.get("completed_final_fits", -1)) != 27:
                    raise ValueError("final result lacks 27 final fits")
                predictions = completion_path.parent / "predictions.csv"
                counts: dict[tuple[int, int], int] = {}
                with predictions.open(newline="", encoding="utf-8") as stream:
                    for row in csv.DictReader(stream):
                        key = int(row["subject"]), int(row["seed"])
                        counts[key] = counts.get(key, 0) + 1
                if set(counts) != {(subject, seed) for subject in range(1, 10)
                                   for seed in (20260924, 20260925, 20260926)}:
                    raise ValueError("final predictions lack the nine-by-three LOSO/seed grid")
                if any(count != 576 for count in counts.values()):
                    raise ValueError("final predictions do not have 576 trials per subject/seed")
            if job["phase"] == "source_fits":
                if int(completed.get("completed_folds", -1)) != 9:
                    raise ValueError("PSD control lacks nine LOSO targets")
                if int(completed.get("completed_shallow_fits", -1)) != 18:
                    raise ValueError("PSD control lacks 18 source fits")
            result["complete"] = True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result["issue"] = str(exc)
            errors.append(f"{job_id}: {exc}")
        findings.append(result)
    return {
        "status": "passed_orchestration_only" if not errors else "failed",
        "audited_at_utc": datetime.now(UTC).isoformat(),
        "scientific_validation": "not_performed_by_this_batch_validator",
        "matrix_sha256": manifest["matrix_sha256"],
        "selected_conditions": manifest["selected_conditions"],
        "unselected_planned_conditions": manifest["unselected_planned_conditions"],
        "jobs_expected": len(jobs),
        "jobs_complete": sum(item["complete"] for item in findings),
        "findings": findings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.batch_dir.resolve())
    write_json(args.batch_dir / "validation_report.json", report)
    print(json.dumps({key: report[key] for key in
                      ("status", "scientific_validation", "jobs_expected", "jobs_complete",
                       "unselected_planned_conditions", "errors")}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed_orchestration_only" else 1


if __name__ == "__main__":
    sys.exit(main())
