"""Planning-matrix consistency tests; these do not test experiment results."""

from __future__ import annotations

import copy
import json
import unittest
from collections import Counter

from validate_matrix import MATRIX, validate_matrix


class PlannedMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    def test_frozen_plan_arithmetic(self) -> None:
        self.assertEqual(validate_matrix(self.matrix), [])

    def test_miscount_is_rejected(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["totals"]["q10_q14_conditional_new_deep_fits_if_N109"] += 1
        self.assertTrue(any("summary" in error for error in validate_matrix(changed)))

    def test_status_cannot_claim_execution(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["experiments"][0]["status"] = "complete"
        self.assertTrue(any("claims execution" in error for error in validate_matrix(changed)))

    def test_source_count_fit_formula(self) -> None:
        changed = copy.deepcopy(self.matrix)
        experiment = next(e for e in changed["experiments"] if e["id"] == "Q13-E002")
        experiment["conditions"][0]["final_fits"] -= 1
        self.assertTrue(any("source-count" in error for error in validate_matrix(changed)))

    def test_external_eligibility_remains_unobserved(self) -> None:
        changed = copy.deepcopy(self.matrix)
        experiment = next(e for e in changed["experiments"] if e["id"] == "Q14-E003")
        experiment["eligible_subjects"] = 109
        self.assertTrue(any("eligibility" in error for error in validate_matrix(changed)))

    def test_cyclic_source_subsets_have_equal_coverage(self) -> None:
        eight_source_ids = list(range(1, 9))
        for k in (2, 4, 6):
            counts = Counter(
                eight_source_ids[(start + offset) % 8]
                for start in (0, 2, 4, 6)
                for offset in range(k)
            )
            self.assertEqual(set(counts), set(eight_source_ids))
            self.assertEqual(set(counts.values()), {k // 2})

    def test_external_bnci_inner_groups_partition_all_sources(self) -> None:
        groups = self.matrix["external_contract_candidate_not_frozen"]["bnci_all_source_inner_groups_candidate"]
        self.assertEqual(len(groups), 4)
        self.assertEqual(sorted(subject for group in groups for subject in group), list(range(1, 10)))


if __name__ == "__main__":
    unittest.main()
