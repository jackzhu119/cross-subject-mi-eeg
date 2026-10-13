"""Software checks using invented labels/probabilities only, never EEG/results."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("redesign_statistics", ROOT / "scripts/analyze_redesign_scores.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fixture(primary_gain=True):
    # Deliberately unequal class/participant trial counts verify weighting. All
    # values are invented software inputs, not cohort observations.
    people = [f"fixture_{i:02d}" for i in range(12)]
    events = []
    rows = []
    for i, person in enumerate(people):
        for cls in (0, 1):
            count = 20 + 2 * i + 6 * cls
            for index in range(count):
                event = f"class{cls}_trial{index}"
                fingerprint = sha(f"invented_epoch:{person}:{event}")
                events.append(dict(subject_id=person, event_id=event, ytrue=cls, epoch_sha256=fingerprint))
                for arch in MOD.ARCHITECTURES:
                    for selector in MOD.SELECTORS:
                        for s, seed in enumerate(MOD.SEEDS):
                            correct = count // 2 + s
                            if selector == "fixed":
                                correct += 6
                            if selector == "mean_rank" and primary_gain:
                                correct += 2 + i % 4
                            if arch == "shared":
                                correct += 2
                            prediction = cls if index < correct else 1 - cls
                            rows.append(dict(subject_id=person, event_id=event, model_arch=arch,
                                             selector=selector, seed=seed, ytrue=cls, ypred=prediction,
                                             p_left=0.8 if prediction == 0 else 0.2,
                                             p_right=0.2 if prediction == 0 else 0.8,
                                             epoch_sha256=fingerprint,
                                             checkpoint_sha256=sha(f"invented_checkpoint:{arch}:{selector}:{seed}")))
    contract = dict(synthetic_fixture=True, cohort_id="invented_12_person_fixture",
                    participants=people, seeds=list(MOD.SEEDS), architectures=list(MOD.ARCHITECTURES),
                    selectors=list(MOD.SELECTORS), label_map={"0": "left_hand_MI", "1": "right_hand_MI"},
                    events=events)
    return rows, contract


def manifest_fixture(folder):
    contract_hash, predictions_hash = sha("invented_contract_bytes"), sha("invented_prediction_bytes")
    manifest = dict(locked_contract_sha256=contract_hash, predictions_sha256=predictions_hash,
                    gates={}, checkpoints=[])
    for name in MOD.REQUIRED_GATES:
        path = folder / f"{name}.json"
        receipt = dict(gate_name=name, passed=True, locked_contract_sha256=contract_hash)
        if name == "independent_prediction_validation":
            receipt["predictions_sha256"] = predictions_hash
        path.write_text(json.dumps(receipt))
        manifest["gates"][name] = dict(passed=True, evidence_file=path.name, sha256=MOD.digest(path))
    for arch in MOD.ARCHITECTURES:
        for rule in MOD.SELECTORS:
            for seed in MOD.SEEDS:
                path = folder / f"{arch}_{rule}_{seed}.synthetic-bytes"
                path.write_text(f"invented checkpoint bytes, no executable model: {arch}/{rule}/{seed}")
                manifest["checkpoints"].append(dict(model_arch=arch, selector=rule, seed=seed,
                                                    source_only=True, target_fit_count=0,
                                                    checkpoint_file=path.name, checkpoint_sha256=MOD.digest(path)))
    return manifest, contract_hash, predictions_hash


class StatisticalSoftwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.contract = fixture()
        cls.result = MOD.analyze_records(cls.rows, cls.contract, allow_synthetic=True)

    def reject_mutated(self, change, code, contract_change=False):
        rows, contract = copy.deepcopy(self.rows), copy.deepcopy(self.contract)
        change(contract if contract_change else rows)
        with self.assertRaisesRegex(MOD.ValidationError, code):
            MOD.analyze_records(rows, contract, allow_synthetic=True)

    def test_full_12_people_3_seeds_6_cells(self):
        self.assertEqual(self.result["participants_n"], 12)
        self.assertEqual(len(self.result["participant_scores"]), 72)
        self.assertEqual(len(self.result["condition_descriptives"]), 6)
        self.assertTrue(all(len(r["seed_ba_pp"]) == 3 for r in self.result["participant_scores"]))

    def test_ba_class_and_seed_and_person_weighting(self):
        by_person = {}
        for score in self.result["participant_scores"]:
            person, arch, selector = score["subject_id"], score["model_arch"], score["selector"]
            seed_scores = []
            for seed in MOD.SEEDS:
                selected = [r for r in self.rows if (r["subject_id"], r["model_arch"], r["selector"], r["seed"]) == (person, arch, selector, seed)]
                recalls = [sum(r["ypred"] == c for r in selected if r["ytrue"] == c) /
                           sum(r["ytrue"] == c for r in selected) for c in (0, 1)]
                seed_scores.append(50 * sum(recalls))
            self.assertAlmostEqual(score["balanced_accuracy_pp"], sum(seed_scores) / 3, places=12)
            by_person[(person, arch, selector)] = sum(seed_scores) / 3
        differences = [by_person[(p, "broad", "mean_rank")] - by_person[(p, "broad", "mean_loss")] for p in self.contract["participants"]]
        self.assertAlmostEqual(self.result["primary"]["mean_difference_pp"], sum(differences) / 12, places=12)

    def test_dominance_is_mean_seed_flag_not_pooled_seed_vote(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if (row["subject_id"], row["model_arch"], row["selector"]) == ("fixture_00", "broad", "fixed"):
                prediction = 1 if row["seed"] == MOD.SEEDS[1] else 0
                row.update(ypred=prediction, p_left=0.8 if prediction == 0 else 0.2,
                           p_right=0.2 if prediction == 0 else 0.8)
        result = MOD.analyze_records(rows, self.contract, allow_synthetic=True)
        person = next(r for r in result["participant_scores"]
                      if (r["subject_id"], r["model_arch"], r["selector"]) == ("fixture_00", "broad", "fixed"))
        self.assertEqual(person["seed_prediction_dominance"], [1.0, 1.0, 1.0])
        self.assertEqual(person["seed_dominant_class"], [0, 1, 0])
        self.assertTrue(person["class_dominance_flag"])
        self.assertEqual(person["balanced_accuracy_pp"], 50.0)

    def test_primary_matches_independent_scipy_ttest(self):
        vector = self.result["primary"]["participant_differences_pp"]
        independent = stats.ttest_1samp(vector, 0)
        self.assertAlmostEqual(self.result["primary"]["p_two_sided"], float(independent.pvalue), places=14)
        self.assertAlmostEqual(self.result["primary"]["t_statistic"], float(independent.statistic), places=12)
        ci = independent.confidence_interval()
        np.testing.assert_allclose(self.result["primary"]["t_interval_pp"], [ci.low, ci.high], rtol=1e-12)

    def test_synthetic_significance_never_confirmation(self):
        self.assertTrue(self.result["primary"]["statistical_threshold_passed"])
        self.assertFalse(self.result["primary"]["confirmatory_rejected"])
        self.assertFalse(self.result["secondary_confirmation_gate_open"])
        self.assertTrue(all(not r["confirmatory_rejected"] for r in self.result["secondary_family"]))
        self.assertEqual(self.result["results_role"], "synthetic_planning_only")
        self.assertFalse(self.result["equivalence_or_noninferiority_established"])
        self.assertEqual(self.result["model_fits_started_by_analysis"], 0)
        self.assertFalse(self.result["target_predictions_computed_by_analysis"])

    def test_synthetic_fabricated_ready_dictionary_still_no_confirmation(self):
        ready = dict(receipt_manifest_checked=True, independent_confirmation_ready=True, failures=[],
                     checkpoint_identities=[dict(model_arch=a, selector=r, seed=s,
                                                 checkpoint_sha256=sha(f"invented_checkpoint:{a}:{r}:{s}"))
                                            for a in MOD.ARCHITECTURES for r in MOD.SELECTORS for s in MOD.SEEDS])
        result = MOD.analyze_records(self.rows, self.contract, readiness=ready, allow_synthetic=True)
        self.assertFalse(result["primary"]["confirmatory_rejected"])
        self.assertFalse(result["secondary_confirmation_gate_open"])

    def test_zero_primary_cannot_open_secondary_gate(self):
        rows, contract = fixture(primary_gain=False)
        result = MOD.analyze_records(rows, contract, allow_synthetic=True)
        self.assertEqual(result["primary"]["test_status"], "degenerate_zero_variance")
        self.assertIsNone(result["primary"]["p_two_sided"])
        self.assertTrue(any(r["nominal_threshold_passed"] for r in result["secondary_family"]))
        self.assertFalse(any(r["confirmatory_rejected"] for r in result["secondary_family"]))

    def test_three_prespecified_secondary_contrasts(self):
        self.assertEqual([r["contrast"] for r in self.result["secondary_family"]],
                         ["broad_fixed_minus_mean_loss", "broad_fixed_minus_mean_rank", "shared_fixed_minus_broad_fixed"])
        self.assertTrue(all(not r["ordinary_95_interval_multiplicity_adjusted"] for r in self.result["secondary_family"]))
        for row in self.result["secondary_family"]:
            ordinary, simultaneous = row["t_interval_pp"], row["bonferroni_simultaneous_interval_pp"]
            if ordinary is not None:
                self.assertLessEqual(simultaneous[0], ordinary[0])
                self.assertGreaterEqual(simultaneous[1], ordinary[1])

    def test_holm_known_vector_and_unsorted_order(self):
        self.assertEqual(MOD.holm_adjust([0.04, 0.001, 0.02]), [0.04, 0.003, 0.04])
        self.assertEqual(MOD.holm_adjust([0.02, None, 0.01]), [0.04, None, 0.03])

    def test_bootstrap_determinism_and_leave_one_out(self):
        second = MOD.analyze_records(self.rows, self.contract, allow_synthetic=True)
        self.assertEqual(self.result["primary"], second["primary"])
        d = np.asarray(self.result["primary"]["participant_differences_pp"])
        np.testing.assert_allclose(self.result["primary"]["leave_one_participant_out_mean_pp"], [(d.sum() - value) / 11 for value in d])

    def test_nonzero_degenerate_not_infinite_t_or_p_zero(self):
        for identical_value in (2.0, 0.1):
            # np.std of identical 0.1 can be a nonzero rounding residue.
            result = MOD.paired_stats(np.full(12, identical_value), np.zeros((10, 12), dtype=int))
            self.assertEqual(result["test_status"], "degenerate_zero_variance")
            self.assertIsNone(result["p_two_sided"])
            self.assertIsNone(result["t_statistic"])
            self.assertTrue(result["bootstrap_interval_degenerate"])

    def test_duplicate_prediction_rejected(self):
        self.reject_mutated(lambda r: r.append(copy.deepcopy(r[0])), "duplicate_prediction_cell")

    def test_missing_prediction_rejected(self):
        self.reject_mutated(lambda r: r.pop(), "incomplete_prediction_coverage")

    def test_unexpected_participant_rejected(self):
        self.reject_mutated(lambda r: r[0].update(subject_id="unknown"), "unexpected_participant")

    def test_wrong_ground_truth_rejected(self):
        self.reject_mutated(lambda r: r[0].update(ytrue=1-r[0]["ytrue"]), "ground_truth_mismatch")

    def test_wrong_epoch_fingerprint_rejected(self):
        self.reject_mutated(lambda r: r[0].update(epoch_sha256=sha("wrongwindow")), "eeg_window_fingerprint_mismatch")

    def test_probability_argmax_guard(self):
        self.reject_mutated(lambda r: r[0].update(ypred=1-r[0]["ypred"]), "prediction_not_probability_argmax")

    def test_probability_finite_guard(self):
        self.reject_mutated(lambda r: r[0].update(p_left="nan"), "nonfinite_probability")

    def test_probability_range_guard(self):
        self.reject_mutated(lambda r: r[0].update(p_left=1.2, p_right=-0.2), "probability_out_of_range")

    def test_probability_normalization_guard(self):
        self.reject_mutated(lambda r: r[0].update(p_left=0.4, p_right=0.4), "probabilities_not_normalized")

    def test_integer_seed_guard(self):
        self.reject_mutated(lambda r: r[0].update(seed=True), "invalid_integer:seed")

    def test_prediction_checkpoint_identity_guard(self):
        self.reject_mutated(lambda r: r[0].update(checkpoint_sha256=""), "prediction_checkpoint_identity_missing")

    def test_condition_seed_checkpoint_consistency(self):
        self.reject_mutated(lambda r: r[0].update(checkpoint_sha256=sha("other-model")), "multiple_checkpoints_for_same_condition_seed")

    def test_duplicate_locked_event_guard(self):
        self.reject_mutated(lambda c: c["events"].append(copy.deepcopy(c["events"][0])), "duplicate_expected_event", True)

    def test_duplicate_eeg_window_guard(self):
        self.reject_mutated(lambda c: c["events"][1].update(epoch_sha256=c["events"][0]["epoch_sha256"]), "duplicate_expected_eeg_window", True)

    def test_both_classes_required(self):
        self.reject_mutated(lambda c: c.update(events=[e for e in c["events"] if e["subject_id"] != c["participants"][0] or e["ytrue"] == 0]), "both_classes_required_for_ba", True)

    def test_synthetic_requires_explicit_flag(self):
        with self.assertRaisesRegex(MOD.ValidationError, "synthetic_fixture_requires_explicit_flag"):
            MOD.analyze_records(self.rows, self.contract)

    def test_real_contract_no_gate_scoring_blocked(self):
        contract = copy.deepcopy(self.contract)
        contract.update(synthetic_fixture=False, cohort_id="Dreyer2023", technical_exclusions=["A17", "A41"])
        for readiness in (None, dict(independent_confirmation_ready=True)):
            with self.assertRaisesRegex(MOD.ValidationError, "audit_gates_not_passed_no_real_data_scoring"):
                MOD.analyze_records(self.rows, contract, readiness=readiness)

    def test_85_ceiling_and_electrode_order_metadata_guard(self):
        contract = copy.deepcopy(self.contract)
        contract.update(synthetic_fixture=False, cohort_id="Dreyer2023", technical_exclusions=["A17", "A41"])
        contract["participants"] = [f"mock_roster_{i}" for i in range(86)]
        with self.assertRaisesRegex(MOD.ValidationError, "eligibility_ceiling_exceeded"):
            MOD.validate_contract(contract, False)
        contract["participants"] = self.contract["participants"] + ["A17"]
        with self.assertRaisesRegex(MOD.ValidationError, "known_electrode_order_exclusion_in_roster"):
            MOD.validate_contract(contract, False)

    def test_real_inventory_minimum_twenty_trials_per_class(self):
        contract = copy.deepcopy(self.contract)
        contract.update(synthetic_fixture=False, cohort_id="Dreyer2023", technical_exclusions=["A17", "A41"])
        MOD.validate_contract(contract, False)
        contract["events"] = [e for e in contract["events"]
                              if not (e["subject_id"] == "fixture_00" and e["event_id"] == "class0_trial19")]
        with self.assertRaisesRegex(MOD.ValidationError, "fewer_than_twenty_locked_trials_per_class"):
            MOD.validate_contract(contract, False)

    def test_receipt_validity_bytes_and_declared_judgment(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ch, ph = manifest_fixture(Path(temp))
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertTrue(ready["independent_confirmation_ready"])
            gate = "author_prior_exposure_attestation"
            path = Path(temp) / manifest["gates"][gate]["evidence_file"]
            content = json.loads(path.read_text())
            content["passed"] = False
            path.write_text(json.dumps(content))
            # Even a self-consistent hash cannot override failed actual receipt.
            manifest["gates"][gate]["sha256"] = MOD.digest(path)
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertFalse(ready["independent_confirmation_ready"])
            self.assertIn(f"gate_receipt_judgment_or_identity_mismatch:{gate}", ready["failures"])

    def test_gate_receipt_hash_or_missing_gate_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ch, ph = manifest_fixture(Path(temp))
            manifest["gates"][MOD.REQUIRED_GATES[0]]["sha256"] = sha("wrong")
            manifest["gates"].pop(MOD.REQUIRED_GATES[1])
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertFalse(ready["independent_confirmation_ready"])
            self.assertEqual(len(ready["failures"]), 2)

    def test_independent_prediction_receipt_bound_to_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ch, ph = manifest_fixture(Path(temp))
            gate = "independent_prediction_validation"
            path = Path(temp) / manifest["gates"][gate]["evidence_file"]
            content = json.loads(path.read_text()); content["predictions_sha256"] = sha("different-output")
            path.write_text(json.dumps(content)); manifest["gates"][gate]["sha256"] = MOD.digest(path)
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertIn("independent_prediction_receipt_artifact_mismatch", ready["failures"])

    def test_checkpoint_artifact_identity_required(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ch, ph = manifest_fixture(Path(temp))
            manifest["checkpoints"][0]["checkpoint_sha256"] = sha("different-bytes")
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertIn("checkpoint_file_hash_mismatch", ready["failures"])

    def test_target_fits_or_missing_condition_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, ch, ph = manifest_fixture(Path(temp))
            manifest["checkpoints"][0]["target_fit_count"] = 1
            manifest["checkpoints"].pop()
            ready = MOD.verify_gate_manifest(manifest, Path(temp), ch, ph)
            self.assertIn("checkpoint_source_only_policy_unverified", ready["failures"])
            self.assertIn("checkpoint_condition_seed_coverage_mismatch", ready["failures"])

    def test_malformed_contract_and_bootstrap_guard(self):
        with self.assertRaisesRegex(MOD.ValidationError, "contract_object_required"):
            MOD.validate_contract([], True)
        with self.assertRaisesRegex(MOD.ValidationError, "invalid_paired_participant_bootstrap_indices"):
            MOD.paired_stats(np.arange(12), np.full((3, 12), 12))

    def test_cli_synthetic_serialization_and_missing_gate_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            prediction = temp / "invented_predictions.csv"
            with prediction.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(self.rows[0])); writer.writeheader(); writer.writerows(self.rows)
            contract = temp / "invented_contract.json"; contract.write_text(json.dumps(self.contract))
            output = temp / "synthetic_analysis.json"
            command = [sys.executable, str(ROOT / "scripts/analyze_redesign_scores.py"), "--predictions", str(prediction), "--contract", str(contract), "--output", str(output)]
            passed = subprocess.run(command + ["--allow-synthetic-fixture"], text=True, capture_output=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(json.loads(output.read_text())["results_role"], "synthetic_planning_only")
            output.unlink()
            blocked = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(blocked.returncode, 2)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(blocked.stdout)["status"], "blocked_no_validated_analysis")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StatisticalSoftwareTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if "--write-evidence" in sys.argv:
        evidence = dict(schema_version=1, scope="invented_12_participant_3_seed_6_condition_software_fixtures_only",
                        test_count=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                        skipped=len(result.skipped), all_passed=result.wasSuccessful(),
                        test_names=[name for name in dir(StatisticalSoftwareTests) if name.startswith("test_")],
                        analysis_script_sha256=MOD.digest(ROOT / "scripts/analyze_redesign_scores.py"),
                        tests_sha256=MOD.digest(Path(__file__)), python_version=sys.version,
                        eeg_data_read=False, observed_target_performance_read=False,
                        model_fits_started=0, target_predictions_computed=False,
                        actual_independent_cohort_audit_passed=False,
                        actual_author_prior_exposure_attestation_confirmed=False,
                        confirmation_gate_open=False,
                        limitation="Software fixture tests do not establish actual data audit passage, participant independence or scientific efficacy.")
        (ROOT / "evidence/statistical_software_validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
