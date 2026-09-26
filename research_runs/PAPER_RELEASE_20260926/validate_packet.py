"""Read-only consistency check for the paper-stage *plan*, not EEG results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = Path(__file__).resolve().parent


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def validate(packet: Path = PACKET, root: Path = ROOT) -> dict:
    plan = _read(packet / "MATRIX.json")
    q12 = _read(root / "research_runs/Q12-PREP-20260926/MATRIX.json")
    q13 = _read(root / "research_runs/Q13-PREP-20260926/MATRIX.json")
    documents = (
        "README.md", "EXTERNAL_PROTOCOL.md", "NEUROPHYSIOLOGY_PROTOCOL.md",
        "STATISTICAL_ANALYSIS_PLAN.md", "RELEASE_GATES.md",
    )
    if any(not (packet / item).is_file() for item in documents):
        raise AssertionError("Paper packet has a missing protocol or release gate")
    if plan.get("packet_status") != "prepared_not_executed":
        raise AssertionError("Planning packet is mislabelled as an executed result")
    if q12.get("status") != "prepared_not_executed" or q13.get("status") != (
        "implementation_prepared_not_executed"
    ):
        raise AssertionError("Q12/Q13 execution status is not accurately declared")
    q12_total = sum(row["inner_fits"] + row["final_fits"] for row in q12["conditions"])
    q13_total = sum(row["new_deep_fits"] for row in q13["experiments"])
    if (len(q12["conditions"]) != 6 or q12_total != 378
            or q12["totals"]["new_deep_fits"] != q12_total
            or q13_total != 837 or q13["total_new_deep_fits"] != q13_total):
        raise AssertionError("Q12/Q13 matrix fit arithmetic changed")
    experiments = plan["experiments"]
    ids = [entry["id"] for entry in experiments]
    if len(ids) != len(set(ids)):
        raise AssertionError("Paper plan has duplicate experiment IDs")
    by_id = {entry["id"]: entry for entry in experiments}
    if (by_id["Q12-E001+E002"]["new_deep_fits"] != q12_total
            or by_id["Q13-E001+E004+E005"][
                "new_deep_fits_if_q5_identity_reuse_verified"] != q13_total):
        raise AssertionError("Paper matrix disagrees with runnable Q12/Q13 matrices")
    if any(entry.get("target_fits") != 0 for entry in experiments):
        raise AssertionError("A planned arm incorrectly permits target fitting")
    totals = plan["fit_totals"]
    if (totals["q12_q13_deep_if_reuse_verified"] != q12_total + q13_total
            or totals["q12_q13_deep_if_reuse_fails"] != q12_total + q13_total + 27
            or totals["mandatory_plus_conditional_q15_deep_if_reuse_verified"]
            != q12_total + q13_total + by_id["Q15-E002"]["new_deep_fits"]
            or totals["all_listed_deep_if_reuse_verified"] != (
                q12_total + q13_total + by_id["Q15-E002"]["new_deep_fits"]
                + by_id["Q11-E002-SHALLOW-ARM"]["new_deep_fits"]
            )):
        raise AssertionError("Paper queue total differs from experimental arms")
    q14 = _read(root / "results/Q14-E002R2/external/completion_receipt.json")
    failed = _read(root / "results/Q14-R2BATCH/batch_status.json")
    if (q14.get("n_subjects") != 109 or q14.get("n_prediction_rows") != 34426
            or q14.get("external_target_fit_count") != 0
            or failed.get("status") != "failed_stopped"):
        raise AssertionError("Q14 historical completion/failure custody changed")
    report_path = root / "results/Q14-E002R2/validation_report.json"
    full_pass = False
    if report_path.is_file():
        report = _read(report_path)
        full_pass = (report.get("passed") is True and report.get("n_subjects") == 109
                     and report.get("n_prediction_rows") == 34426
                     and report.get("n_verified_official_edf_files") == 327)
    return {
        "status": "planning_packet_consistent_not_scientific_validation",
        "base_commit": plan["as_of_main_commit"],
        "q14_full_independent_validation": "passed" if full_pass else "pending_cloud_raw_edf",
        "q12_new_deep_fits_planned": q12_total,
        "q13_new_deep_fits_planned": q13_total,
        "q12_q13_new_deep_fits_planned": q12_total + q13_total,
        "new_training_started_by_this_check": False,
        "cloud_accessed_by_this_check": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(validate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
