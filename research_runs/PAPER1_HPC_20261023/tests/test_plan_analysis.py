"""Focused synthetic planning/statistics checks. No EEG, models, or network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from hpcmi import analysis, plan
from hpcmi.common import atomic_json, read_json


class FakeRegistry:
    def __init__(self, path):
        self.entries = [{"id": f"{dataset}__{i:02d}", "dataset": dataset, "role": "source"}
                        for dataset, n in (("bnci", 9), ("yang", 51)) for i in range(n)]
        self.entries += [{"id": f"dreyer__{i:02d}", "dataset": "dreyer", "role": "external"} for i in range(5)]
        self.by_id = {p["id"]: p for p in self.entries}
        self.source_ids = [p["id"] for p in self.entries if p["role"] == "source"]
        self.external_ids = [p["id"] for p in self.entries if p["role"] == "external"]
        self.fingerprint = "synthetic-metadata-only"

    def ensure_source(self, ids):
        if any(self.by_id[p]["role"] != "source" for p in ids):
            raise ValueError("Target leaked into training")


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.study = {"epochs": 40, "source_folds": 5, "split_seed": 20261023,
                      "methods": list(plan.METHODS), "validation_seeds": [20261031, 20261032, 20261033],
                      "final_seeds": [20261101, 20261102, 20261103],
                      "expected_source_counts": {"bnci": 9, "yang": 51},
                      "bootstrap_replicates": 101, "permutation_replicates": 103,
                      "heartbeat_seconds": 30}
        atomic_json(self.project / "config" / "study.json", self.study)
        self.registry_patch = patch.object(plan, "Registry", FakeRegistry)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def source_completions(self, evaluations=False):
        tasks = read_json(self.project / "tasks.json")
        for task in tasks:
            if task["phase"] != "development":
                continue
            # Exactly three repeats per fold; median epoch is 10+fold(2)=12.
            result = {key: task[key] for key in ("id", "phase", "method", "seed", "fold")}
            result.update({"task_id": task["id"], "status": "complete", "best_epoch": 10 + task["fold"],
                           "evaluations": {"outer_best": "evaluation/outer_best.json"}})
            run = self.project / "outputs" / "runs" / task["id"]
            if evaluations:
                self.write_evaluation(task, "outer_best")
            atomic_json(run / "complete.json", result)

    def write_evaluation(self, task, variant):
        offsets = {"erm": 0, "groupdro": .01, "tail": -.01, "consistency": 0, "tail_consistency": .02}
        people = []
        for person in task["test_ids"]:
            dataset = person.split("__")[0]
            left, right = .6 + offsets[task["method"]], .7 + offsets[task["method"]]
            people.append({"person_id": person, "dataset": dataset, "seed": task["seed"], "variant": variant,
                           "recall_left": left, "recall_right": right, "ba": (left + right) / 2,
                           "min_recall": min(left, right), "ce": .6, "n": 100, "n_left": 50, "n_right": 50})
        atomic_json(self.project / "outputs" / "runs" / task["id"] / "evaluation" / f"{variant}.json",
                    {"variant": variant, "people": people, "model_sha256": "synthetic-no-model"})


class PlanTests(ProjectCase):
    def test_source_splits_shared_and_leak_free(self):
        frozen = plan.create_plan(self.project)
        tasks = read_json(self.project / "tasks.json")
        self.assertEqual(len(tasks), 75)
        self.assertEqual(frozen["source_counts"], {"bnci": 9, "yang": 51})
        all_source = set(frozen["source_ids"])
        all_test = []
        for split in frozen["partitions"]:
            a, b, c = [set(split[k]) for k in ("train_ids", "validation_ids", "test_ids")]
            self.assertFalse(a & b or a & c or b & c)
            self.assertEqual(a | b | c, all_source)
            all_test += split["test_ids"]
            for task in [t for t in tasks if t["fold"] == split["fold"]]:
                self.assertEqual(task["train_ids"], split["train_ids"])
                self.assertEqual(task["validation_ids"], split["validation_ids"])
                self.assertEqual(task["test_ids"], split["test_ids"])
        self.assertEqual(sorted(all_test), sorted(all_source))

    def test_resume_allows_operational_change_but_preserves_science(self):
        original = plan.create_plan(self.project)
        before = (self.project / "tasks.json").read_bytes()
        self.study["heartbeat_seconds"] = 60
        atomic_json(self.project / "config" / "study.json", self.study)
        reused = plan.create_plan(self.project)
        self.assertTrue(reused["reused"])
        self.assertEqual(original["fingerprint"], reused["fingerprint"])
        self.study["epochs"] = 41
        atomic_json(self.project / "config" / "study.json", self.study)
        with self.assertRaisesRegex(ValueError, "Scientific plan/data changed"):
            plan.create_plan(self.project)
        self.assertEqual(before, (self.project / "tasks.json").read_bytes())

    def test_final_waits_then_appends_only_once_and_does_not_read_target_scores(self):
        plan.create_plan(self.project)
        with self.assertRaises(plan.PlanNotReady):
            plan.append_final_tasks(self.project)
        self.assertEqual(len(read_json(self.project / "tasks.json")), 75)
        self.source_completions()
        final = plan.append_final_tasks(self.project)
        self.assertEqual(len(final), 15)
        self.assertTrue(all(t["selected_epoch"] == 12 and t["validation_ids"] == [] for t in final))
        self.assertTrue(all(len(t["train_ids"]) == 60 for t in final))
        self.assertEqual({t["seed"] for t in final}, {20261101, 20261102, 20261103})
        self.assertFalse(read_json(self.project / "state" / "selection.json")["target_outcomes_read"])
        self.assertEqual(plan.append_final_tasks(self.project), [])
        self.assertEqual(len(read_json(self.project / "tasks.json")), 90)

    def test_corrupt_completion_does_not_become_source_selection(self):
        plan.create_plan(self.project)
        self.source_completions()
        task = read_json(self.project / "tasks.json")[0]
        path = self.project / "outputs" / "runs" / task["id"] / "complete.json"
        bad = read_json(path)
        bad["seed"] += 1
        atomic_json(path, bad)
        with self.assertRaisesRegex(ValueError, "Completion seed differs"):
            plan.append_final_tasks(self.project)

    def test_initial_two_file_interruption_retains_identical_tasks(self):
        plan.create_plan(self.project)
        before = (self.project / "tasks.json").read_bytes()
        (self.project / "state" / "plan.json").unlink()
        plan.create_plan(self.project)
        self.assertEqual(before, (self.project / "tasks.json").read_bytes())
        (self.project / "state" / "plan.json").unlink()
        changed = read_json(self.project / "tasks.json")
        changed[0]["seed"] = 999
        atomic_json(self.project / "tasks.json", changed)
        with self.assertRaisesRegex(ValueError, "differs from deterministic preparation"):
            plan.create_plan(self.project)


class StatisticsTests(unittest.TestCase):
    def test_holm_fixed_four_family(self):
        np.testing.assert_allclose(analysis.holm_adjust([.01, .04, .03, .002]), [.03, .06, .06, .008])

    def test_exact_sign_flip_and_constant_interval(self):
        stat = analysis.paired_statistics([.1] * 4, ["d"] * 4, equal_cohort=False,
                                          seed=1, bootstrap_replicates=100, permutation_replicates=100)
        self.assertEqual(stat["p_raw"], .125)
        self.assertAlmostEqual(stat["ci95_low_pp"], 10)
        self.assertAlmostEqual(stat["ci95_high_pp"], 10)
        self.assertEqual(stat["improved"], 4)
        stat = analysis.paired_statistics([0] * 4, ["d"] * 4, equal_cohort=False,
                                          seed=1, bootstrap_replicates=100, permutation_replicates=100)
        self.assertEqual(stat["p_raw"], 1)
        self.assertEqual(stat["numerically_unchanged"], 4)

    def test_equal_cohort_estimand_and_negative_results(self):
        args = dict(equal_cohort=True, seed=2, bootstrap_replicates=100, permutation_replicates=100)
        stat = analysis.paired_statistics([-.1] * 2 + [-.3] * 4, ["a"] * 2 + ["b"] * 4, **args)
        self.assertAlmostEqual(stat["effect"], -.2)
        self.assertEqual(stat["declined"], 6)
        self.assertEqual(stat, analysis.paired_statistics([-.1] * 2 + [-.3] * 4, ["a"] * 2 + ["b"] * 4, **args))

    def test_within_seed_weaker_class_before_seed_averaging(self):
        rows = [{"method": "erm", "person_id": "a", "dataset": "d", "seed": seed,
                 "n": 20, "n_left": 10, "n_right": 10, "recall_left": left, "recall_right": right,
                 "ba": .5, "min_recall": .2}
                for seed, left, right in ((1, .2, .8), (2, .8, .2))]
        person = analysis._aggregate_people(rows, ["erm"], [1, 2])[0]
        self.assertAlmostEqual(person["min_recall"], .2)
        self.assertAlmostEqual(person["recall_left"], .5)
        with self.assertRaisesRegex(ValueError, "Missing or duplicate seed"):
            analysis._aggregate_people(rows[:1], ["erm"], [1, 2])


class AnalysisIntegrationTests(ProjectCase):
    def test_missing_scores_wait_then_source_domain_is_reused(self):
        plan.create_plan(self.project)
        pending = analysis.analyze(self.project)
        self.assertEqual(pending["status"], "waiting_for_complete_saved_evaluations")
        self.source_completions(evaluations=True)
        result = analysis.analyze(self.project)
        nested = result["domains"]["nested_outer"]
        self.assertEqual(nested["n_participants"], 60)
        self.assertEqual(len(nested["method_means"]), 20)
        self.assertEqual(len(nested["comparisons"]), 5)
        self.assertAlmostEqual(nested["comparisons"][0]["effect_pp"], 2)
        self.assertEqual(nested["comparisons"][0]["family"], "primary")
        self.assertTrue(all("p_holm" in t for t in nested["comparisons"][1:]))
        path = self.project / "outputs" / "analysis" / "nested_outer.json"
        before, mtime = path.read_bytes(), path.stat().st_mtime_ns
        again = analysis.analyze(self.project)
        self.assertEqual(again["domains"]["nested_outer"], nested)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_final_complete_evaluations_retain_both_variants(self):
        plan.create_plan(self.project)
        self.source_completions(evaluations=True)
        final = plan.append_final_tasks(self.project)
        for task in final:
            complete = {k: task[k] for k in ("id", "phase", "method", "seed", "fold", "selected_epoch")}
            complete.update({"task_id": task["id"], "status": "complete", "best_epoch": None,
                             "evaluations": {v: f"evaluation/{v}.json" for v in ("fixed40", "source_selected")}})
            for variant in complete["evaluations"]:
                self.write_evaluation(task, variant)
            atomic_json(self.project / "outputs" / "runs" / task["id"] / "complete.json", complete)
        result = analysis.analyze(self.project)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(set(result["domains"]), {"nested_outer", "external_fixed40", "external_source_selected"})
        for domain in ("external_fixed40", "external_source_selected"):
            self.assertEqual(result["domains"][domain]["n_participants"], 5)
            self.assertFalse(result["domains"][domain]["independent_external_confirmation"])
            self.assertEqual(result["domains"][domain]["comparisons"][0]["family"], "exploratory_registered")


if __name__ == "__main__":
    unittest.main()
