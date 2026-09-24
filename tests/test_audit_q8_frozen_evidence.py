"""Regression checks for the frozen Q5/Q8 interpretation audit."""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_q8_frozen_evidence.py"
SPEC = importlib.util.spec_from_file_location("audit_q8_frozen_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrozenQ8AuditTest(unittest.TestCase):
    def test_recomputed_predictions_and_statistical_boundary(self) -> None:
        result = MODULE.audit(ROOT)
        self.assertEqual(result["source"]["paired_predictions"], 15552)
        self.assertEqual(result["source"]["q8_manifest"]["files_verified"], 34)
        aggregate = result["aggregate"]
        self.assertTrue(math.isclose(aggregate["q5_mean_balanced_accuracy"], 0.33719135802469136))
        self.assertTrue(math.isclose(aggregate["q8_mean_balanced_accuracy"], 0.42669753086419754))
        self.assertTrue(math.isclose(aggregate["mean_delta_pp"], 8.950617283950617))
        self.assertEqual(
            (aggregate["improved_subjects"], aggregate["unchanged_subjects"], aggregate["worsened_subjects"]),
            (7, 2, 0),
        )
        self.assertEqual(aggregate["conventional_two_sided_sign_test_excluding_ties_p"], 0.015625)
        self.assertTrue(math.isclose(aggregate["s3_s8_share_of_total_delta"], 0.8757183908045977))
        self.assertEqual(aggregate["q4_comparison"]["BroadCSP_LDA"]["q8_subject_wins"], 5)
        self.assertEqual(aggregate["q4_comparison"]["FBCSP_LDA"]["q8_subject_wins"], 4)
        s5 = result["subjects"][4]
        self.assertEqual(s5["Q8"]["class_recall"]["3"], 0)
        self.assertEqual(s5["Q8"]["class_recall"]["4"], 0)


if __name__ == "__main__":
    unittest.main()
