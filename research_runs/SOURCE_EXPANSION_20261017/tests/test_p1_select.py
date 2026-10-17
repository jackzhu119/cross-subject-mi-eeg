"""Meaningful scientific-contract checks; no real EEG is used."""

import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import t, ttest_1samp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from p1_select import (DEFAULT_COMPARISONS, DEFAULT_CONDITIONS, SELECTORS,
                       holm_adjust, paired_statistics, prediction_metrics,
                       select_epochs, weighted_tail)


def source_rows(spec, seeds=(17, 43, 91)):
    """spec maps (dataset, subject) to epoch -> (CE, BA, min_recall)."""
    rows = []
    for (dataset, subject), by_epoch in spec.items():
        for epoch, values in by_epoch.items():
            for seed in seeds:
                rows.append(dict(dataset=dataset, subject=subject, epoch=epoch, seed=seed,
                                 ce=values[0], ba=values[1], min_recall=values[2],
                                 source_level="S9", pipeline="BROAD"))
    return rows


def two_condition_metrics():
    rows = []
    for pi in range(4):
        for level in ("S9", "S60"):
            for seed in (17, 43):
                minimum = 0.2 if level == "S9" else 0.3 + 0.1 * pi
                rows.append(dict(source_level=level, pipeline="BROAD", selector="tail_min_recall",
                                 dataset="Dreyer2023", subject=f"P{pi}", seed=seed, ce=1.0,
                                 min_recall=minimum, ba=(1 + minimum) / 2,
                                 trial_manifest_sha256=f"{pi:064x}"))
    return rows


class SourceSelectionTests(unittest.TestCase):
    def test_weighted_tail_uses_exact_fractional_mass(self):
        values, weights = [0, 10, 20], [0.2, 0.5, 0.3]
        self.assertAlmostEqual(weighted_tail(values, weights, lower=True), 4.0)
        self.assertAlmostEqual(weighted_tail(values, weights, lower=False), 19.0)
        self.assertAlmostEqual(weighted_tail([7, 7, 7], weights, lower=True), 7.0)

    def test_all_eight_definitions_and_tail_direction(self):
        spec = {
            ("BNCI", "A"): {1: (.2, .95, .9), 2: (.9, .75, .6), 20: (2, .6, .2)},
            ("BNCI", "B"): {1: (.2, .95, .9), 2: (.9, .75, .6), 20: (2, .6, .2)},
            ("BNCI", "C"): {1: (2, .5, 0), 2: (.9, .75, .6), 20: (2, .6, .2)},
        }
        result = select_epochs(source_rows(spec), expected_epochs=[1, 2, 20], expected_subjects=3)
        self.assertEqual(result["epochs"], {
            "fixed20": 20, "mean_ce": 1, "mean_ba": 1, "mean_rank": 1,
            "tail_ce": 2, "tail_ba": 2, "mean_min_recall": 1, "tail_min_recall": 2,
        })
        self.assertEqual(len(SELECTORS), 8)
        self.assertFalse(result["diagnostics"]["folds_are_replicates"])

    def test_cohorts_are_equal_weight_not_trials_or_person_pooled(self):
        spec = {("BNCI", "A"): {1: (0, .6, .4), 2: (4, .6, .4), 20: (10, .6, .4)}}
        for person in ("B", "C", "D"):
            spec[("Yang2025", person)] = {1: (5, .6, .4), 2: (2, .6, .4), 20: (10, .6, .4)}
        result = select_epochs(source_rows(spec), expected_epochs=[1, 2, 20],
                               expected_subjects={"BNCI": 1, "Yang2025": 3})
        self.assertEqual(result["epochs"]["mean_ce"], 1)
        self.assertAlmostEqual(result["curve_scores"][0]["mean_ce"], 2.5)
        self.assertAlmostEqual(result["curve_scores"][1]["mean_ce"], 3.0)

    def test_rank_tie_earliest_while_other_ties_use_mean_ba(self):
        spec = {
            ("BNCI", "A"): {1: (1, .55, .4), 2: (2, .7, .5), 20: (3, .5, .3)},
            ("BNCI", "B"): {1: (2, .55, .4), 2: (1, .7, .5), 20: (3, .5, .3)},
        }
        result = select_epochs(source_rows(spec), expected_epochs=[1, 2, 20])
        self.assertEqual(result["epochs"]["mean_rank"], 1)
        self.assertEqual(result["epochs"]["mean_ce"], 2)

    def test_seeds_are_averaged_before_computing_tail(self):
        rows = source_rows({
            ("BNCI", "A"): {1: (5, .6, .4), 2: (6, .6, .4), 20: (20, .6, .4)},
            ("BNCI", "B"): {1: (5, .6, .4), 2: (6, .6, .4), 20: (20, .6, .4)},
        })
        for row in rows:
            if row["epoch"] == 1:
                sequence = [0, 10, 5] if row["subject"] == "A" else [10, 0, 5]
                row["ce"] = sequence[[17, 43, 91].index(row["seed"])]
        result = select_epochs(rows, expected_epochs=[1, 2, 20])
        self.assertAlmostEqual(result["curve_scores"][0]["tail_ce"], 5.0)
        self.assertEqual(result["epochs"]["tail_ce"], 1)

    def test_complete_grid_target_rejection_and_duplicate_rejection(self):
        rows = source_rows({("BNCI", "A"): {1: (1, .6, .4), 20: (2, .5, .3)}})
        with self.assertRaisesRegex(ValueError, "incomplete source grid"):
            select_epochs(rows[:-1], expected_epochs=[1, 20])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            select_epochs(rows + [rows[0]], expected_epochs=[1, 20])
        leaked = copy.deepcopy(rows)
        leaked[0]["dataset"] = "Dreyer2023"
        with self.assertRaisesRegex(ValueError, "target data"):
            select_epochs(leaked, expected_epochs=[1, 20])
        invalid = copy.deepcopy(rows)
        invalid[0]["ce"] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            select_epochs(invalid, expected_epochs=[1, 20])

    def test_person_has_one_fold_and_hash_is_input_order_invariant(self):
        rows = source_rows({("BNCI", "A"): {1: (1, .6, .4), 20: (2, .5, .3)}})
        for row in rows:
            row["fold"] = 0
        first = select_epochs(rows, expected_epochs=[1, 20], expected_folds=1)
        reverse = select_epochs(reversed(rows), expected_epochs=[1, 20], expected_folds=1)
        self.assertEqual(first, reverse)
        rows[0]["fold"] = 1
        with self.assertRaisesRegex(ValueError, "multiple validation folds"):
            select_epochs(rows, expected_epochs=[1, 20])

    def test_short_synthetic_fixed_epoch_override_is_explicit(self):
        rows = source_rows({("BNCI", "A"): {1: (1, .6, .4), 2: (2, .5, .3)}}, seeds=(0, 1))
        result = select_epochs(rows, expected_epochs=2, fixed_epoch=1, expected_seeds=2)
        self.assertEqual(result["epochs"]["fixed20"], 1)
        self.assertTrue(result["diagnostics"]["synthetic_fixed_epoch_override"])

    def test_expected_registry_person_ids_are_checked_not_only_counted(self):
        rows = source_rows({("BNCI", "A"): {1: (1, .6, .4), 20: (2, .5, .3)}})
        select_epochs(rows, expected_epochs=[1, 20], expected_subjects=["A"])
        with self.assertRaisesRegex(ValueError, "person identities differ"):
            select_epochs(rows, expected_epochs=[1, 20], expected_subjects=["different-person"])


class PredictionMetricTests(unittest.TestCase):
    def rows(self):
        rows = []
        for seed in (17, 43):
            for trial, y, p in (("a", 0, .1), ("b", 0, .9), ("c", 1, .8), ("d", 1, .2)):
                rows.append(dict(source_level="S9", pipeline="BROAD", selector="fixed20",
                                 dataset="Dreyer2023", subject="P1", seed=seed,
                                 trial_id=trial, y_true=y, p_right=p))
        return rows

    def test_correct_balanced_metrics_and_logit_equivalence(self):
        rows = self.rows()
        first = prediction_metrics(rows)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0]["ba"], .5)
        self.assertEqual(first[0]["min_recall"], .5)
        self.assertAlmostEqual(first[0]["ce"], -np.log([.9, .1, .8, .2]).mean())
        for row in rows:
            row["logit_left"] = math.log(1 - row["p_right"])
            row["logit_right"] = math.log(row["p_right"])
        second = prediction_metrics(rows)
        self.assertAlmostEqual(second[0]["ce"], first[0]["ce"])
        self.assertEqual(second[0]["trial_manifest_sha256"], first[0]["trial_manifest_sha256"])

    def test_equal_probabilities_predict_left(self):
        rows = self.rows()
        for row in rows:
            row["p_right"] = .5
        metrics = prediction_metrics(rows)
        self.assertEqual(metrics[0]["recall_left"], 1)
        self.assertEqual(metrics[0]["recall_right"], 0)
        self.assertEqual(metrics[0]["min_recall"], 0)

    def test_cross_entropy_is_invariant_to_large_common_logit_offset(self):
        rows = self.rows()
        for row in rows:
            row["p_right"] = .5
            row["logit_left"] = 1e20
            row["logit_right"] = 1e20
        metrics = prediction_metrics(rows)
        self.assertAlmostEqual(metrics[0]["ce"], math.log(2))

    def test_saved_probability_must_agree_with_saved_logits(self):
        rows = self.rows()
        rows[0]["logit_left"] = 0
        rows[0]["logit_right"] = 0
        with self.assertRaisesRegex(ValueError, "probability disagrees"):
            prediction_metrics(rows)

    def test_duplicate_changed_label_and_trial_dropout_fail(self):
        rows = self.rows()
        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            prediction_metrics(rows + [rows[0]])
        changed = copy.deepcopy(rows)
        changed[-1]["y_true"] = 0
        with self.assertRaisesRegex(ValueError, "labels differ"):
            prediction_metrics(changed)
        with self.assertRaisesRegex(ValueError, "trial coverage differs"):
            prediction_metrics(rows[:-1])


class PairedStatisticsTests(unittest.TestCase):
    def run_pair(self, rows, **kwargs):
        return paired_statistics(rows, expected_subjects=4, expected_seeds=2,
                                 expected_conditions=[("S9", "BROAD", "tail_min_recall"),
                                                      ("S60", "BROAD", "tail_min_recall")],
                                 comparisons=[DEFAULT_COMPARISONS[0]], n_bootstrap=1000,
                                 **kwargs)

    def test_paired_t_and_subject_bootstrap_match_known_difference(self):
        result = self.run_pair(two_condition_metrics())
        contrast = result["comparisons"][0]
        delta = np.array([.1, .2, .3, .4])
        self.assertEqual(contrast["n_subjects"], 4)
        self.assertEqual(contrast["degrees_of_freedom"], 3)
        self.assertAlmostEqual(contrast["mean"], .25)
        self.assertAlmostEqual(contrast["p_two_sided"], ttest_1samp(delta, 0).pvalue)
        half = t.ppf(.975, 3) * delta.std(ddof=1) / 2
        self.assertAlmostEqual(contrast["t_ci95_low"], .25 - half)
        self.assertLessEqual(contrast["bootstrap_ci95_low"], .25)
        self.assertGreaterEqual(contrast["bootstrap_ci95_high"], .25)
        self.assertEqual(result["study_status"], "exploratory_external")
        self.assertEqual(result, self.run_pair(reversed(two_condition_metrics())))

    def test_minimum_is_computed_per_seed_before_averaging(self):
        rows = two_condition_metrics()
        for row in rows:
            row["ba"] = .5
            row["min_recall"] = 0
            row["recall_left"] = 1 if row["seed"] == 17 else 0
            row["recall_right"] = 0 if row["seed"] == 17 else 1
        result = self.run_pair(rows)
        self.assertTrue(all(row["min_recall"] == 0 for row in result["per_subject_metrics"]))
        self.assertEqual(result["comparisons"][0]["p_two_sided"], 1)

    def test_missing_conditions_seeds_and_changed_manifest_fail(self):
        rows = two_condition_metrics()
        with self.assertRaisesRegex(ValueError, "conditions incomplete"):
            paired_statistics(rows, expected_subjects=4, expected_seeds=2, n_bootstrap=1000)
        with self.assertRaisesRegex(ValueError, "missing paired target cell"):
            self.run_pair(rows[:-1])
        changed = copy.deepcopy(rows)
        changed[-1]["trial_manifest_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "trials differ"):
            self.run_pair(changed)

    def test_holm_preserves_input_order_and_monotonicity(self):
        np.testing.assert_allclose(holm_adjust([.03, .01, .04]), [.06, .03, .06])
        self.assertEqual(holm_adjust([]), [])

    def test_full_48_condition_contract_and_three_secondary_family(self):
        rows = []
        for level, pipeline, selector in DEFAULT_CONDITIONS:
            for pi in range(4):
                for seed in (17, 43):
                    minimum = {"S9": .2, "S29": .3, "S60": .4}[level] + pi * .02
                    if selector == "tail_min_recall":
                        minimum += .03
                    rows.append(dict(source_level=level, pipeline=pipeline, selector=selector,
                                     dataset="Dreyer2023", subject=f"P{pi}", seed=seed, ce=1.,
                                     min_recall=minimum, ba=(1 + minimum) / 2,
                                     trial_manifest_sha256=f"{pi:064x}"))
        result = paired_statistics(rows, expected_subjects=4, expected_seeds=2, n_bootstrap=100)
        self.assertEqual(result["diagnostics"]["n_conditions"], 48)
        self.assertEqual(len(result["per_subject_metrics"]), 48 * 4)
        self.assertEqual(len(result["condition_summaries"]), 48 * 3)
        self.assertEqual(len(result["comparisons"]), 4)
        self.assertIsNone(result["comparisons"][0]["p_holm"])
        self.assertTrue(all(row["p_holm"] is not None for row in result["comparisons"][1:]))
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
