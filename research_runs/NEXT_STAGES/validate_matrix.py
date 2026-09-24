"""Validate arithmetic and non-executable status of the Q11-Q14 planning matrix.

This validates a *plan*, not experiment outputs or scientific conclusions.
It intentionally has no imports from training code and never reads target data.
"""

from __future__ import annotations

import json
from pathlib import Path


MATRIX = Path(__file__).with_name("MATRIX.json")


def validate_matrix(matrix: dict) -> list[str]:
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(matrix.get("schema_version") == 1, "unsupported schema_version")
    require(matrix.get("status") == "planned_not_executed", "matrix must remain a plan")
    require("No target labels" in matrix.get("primary_contract", {}).get("target_data_policy", ""),
            "missing explicit source-only target-data policy")

    gates = {gate.get("id") for gate in matrix.get("gates", [])}
    require(len(gates) == len(matrix.get("gates", [])), "duplicate gate ID")
    ids: set[str] = set()
    by_id: dict[str, dict] = {}
    all_condition_ids: set[str] = set()
    for experiment in matrix.get("experiments", []):
        experiment_id = experiment.get("id", "")
        require(experiment_id.startswith(("Q11-", "Q12-", "Q13-", "Q14-")),
                f"out-of-scope experiment ID: {experiment_id}")
        require(experiment_id not in ids, f"duplicate experiment ID: {experiment_id}")
        ids.add(experiment_id)
        by_id[experiment_id] = experiment
        require(experiment.get("status") in {
            "planned_unimplemented", "blocked_pending_metadata_only_audit",
            "blocked_pending_external_metadata_and_implementation",
        }, f"{experiment_id}: status claims execution")
        require(set(experiment.get("required_gates", [])) <= gates,
                f"{experiment_id}: unknown required gate")
        for condition in experiment.get("conditions", []):
            condition_id = condition.get("id", "")
            require(condition_id not in all_condition_ids,
                    f"duplicate condition ID: {condition_id}")
            all_condition_ids.add(condition_id)
            for key in ("inner_fits", "final_fits", "shallow_fits"):
                if key in condition:
                    require(isinstance(condition[key], int) and condition[key] >= 0,
                            f"{experiment_id}/{condition_id}: invalid {key}")
        if experiment_id != "Q14-E003":
            calculated_deep = sum(c.get("inner_fits", 0) + c.get("final_fits", 0)
                                  for c in experiment.get("conditions", []))
            calculated_shallow = sum(c.get("shallow_fits", 0)
                                     for c in experiment.get("conditions", []))
            require(experiment.get("planned_deep_fits") == calculated_deep,
                    f"{experiment_id}: deep fit total mismatch")
            require(experiment.get("planned_shallow_fits") == calculated_shallow,
                    f"{experiment_id}: shallow fit total mismatch")

    expected_ids = {
        "Q11-E001", "Q11-E002", "Q11-A001", "Q12-E001", "Q12-E002",
        "Q13-E001", "Q13-E002", "Q13-E003", "Q14-V001", "Q14-E001",
        "Q14-E002", "Q14-E003",
    }
    require(ids == expected_ids, "missing or unexpected experiment IDs")

    source_count = by_id.get("Q13-E002", {})
    require(source_count.get("planned_deep_fits") == 2 * 3 * 4 * 9 * 3,
            "Q13 source-count new-fit formula mismatch")
    require(source_count.get("reused_k8_final_fits") == 2 * 9 * 3,
            "Q13 frozen k=8 reuse count mismatch")
    for condition in source_count.get("conditions", []):
        require(condition.get("final_fits") == condition.get("subsets_per_target", 0)
                * condition.get("targets", 0) * condition.get("final_seeds", 0),
                f"Q13 source-count {condition.get('id')}: final-fit formula mismatch")

    external = by_id.get("Q14-E003", {})
    n = external.get("provisional_subjects_if_all_eligible")
    require(external.get("eligible_subjects") is None,
            "Q14 eligibility must remain unfilled until metadata audit")
    require(n == 109, "Q14 provisional dataset size must be traceable to official source")
    for condition in external.get("conditions", []):
        if "provisional_deep_fits_if_N109" in condition:
            expected = n * (condition.get("inner_fits_per_target", 0)
                            + condition.get("final_fits_per_target", 0))
            require(condition["provisional_deep_fits_if_N109"] == expected,
                    f"Q14/{condition.get('id')}: deep-fit formula mismatch")
        if "provisional_shallow_fits_if_N109" in condition:
            expected = n * condition.get("shallow_fits_per_target", 0)
            require(condition["provisional_shallow_fits_if_N109"] == expected,
                    f"Q14/{condition.get('id')}: shallow-fit formula mismatch")
    require(external.get("provisional_deep_fits_if_N109") == 2 * n * (4 + 3),
            "Q14-E003 deep total mismatch")
    require(external.get("provisional_shallow_fits_if_N109") == n,
            "Q14-E003 shallow total mismatch")

    totals = matrix.get("totals", {})
    q11_q13 = [e for e in matrix.get("experiments", []) if e.get("id", "").startswith(("Q11-", "Q12-", "Q13-"))]
    q14_fixed = [e for e in matrix.get("experiments", []) if e.get("id", "").startswith("Q14-") and e.get("id") != "Q14-E003"]
    d_11_13 = sum(e.get("planned_deep_fits", 0) for e in q11_q13)
    s_11_13 = sum(e.get("planned_shallow_fits", 0) for e in q11_q13)
    d_14 = sum(e.get("planned_deep_fits", 0) for e in q14_fixed) + external.get("provisional_deep_fits_if_N109", 0)
    s_14 = sum(e.get("planned_shallow_fits", 0) for e in q14_fixed) + external.get("provisional_shallow_fits_if_N109", 0)
    expected_totals = {
        "q11_q13_new_deep_fits": d_11_13,
        "q11_q13_new_shallow_fits": s_11_13,
        "q14_new_deep_fits_if_N109": d_14,
        "q14_new_shallow_fits_if_N109": s_14,
        "q11_q14_new_deep_fits_if_N109": d_11_13 + d_14,
        "q11_q14_new_shallow_fits_if_N109": s_11_13 + s_14,
        "q10_q14_conditional_new_deep_fits_if_N109": d_11_13 + d_14 + totals.get("separately_owned_q10_planning_assumption_deep_fits", 0),
        "q10_q14_conditional_new_shallow_fits_if_N109": s_11_13 + s_14 + totals.get("separately_owned_q10_planning_assumption_shallow_fits", 0),
        "reused_frozen_q13_k8_final_fits_not_new": source_count.get("reused_k8_final_fits", 0),
    }
    for key, expected in expected_totals.items():
        require(totals.get(key) == expected, f"summary {key}: expected {expected}")
    return errors


def main() -> int:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    errors = validate_matrix(matrix)
    print(json.dumps({
        "status": "passed_plan_arithmetic_only" if not errors else "failed",
        "experiment_count": len(matrix.get("experiments", [])),
        "condition_count": sum(len(e.get("conditions", [])) for e in matrix.get("experiments", [])),
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
