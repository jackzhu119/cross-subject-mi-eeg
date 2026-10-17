"""Exercise real reporting/export code using deterministic synthetic logits only.

No EEG files, source fitting, target preprocessing, or model inference are used.
Run with unittest, or use --preserve PATH to retain a visibly labelled preview.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image

BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))
from p1_common import atomic_bytes, atomic_json, read_json, sha256_file
from p1_report import render_report
from p1_runner import export_results, write_csv
from p1_select import DEFAULT_CONDITIONS, SELECTORS, paired_statistics, prediction_metrics


def _prediction_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, gzip.compress(stream.getvalue().encode("utf-8"), mtime=0))


def make_synthetic_run(run, *, seeds=(101, 202, 303), n_subjects=8, n_trials=20):
    """Create paired report inputs; all numbers are fabricated software fixtures."""
    run = Path(run)
    results = run / "results"
    config = read_json(BUNDLE / "config/study.json")
    config.update({"protocol_id": "SYNTHETIC_REPORT_EXPORT_CHECK_NOT_EEG_RESULTS",
                   "evidence_scope": "synthetic_only", "final_seeds": list(seeds),
                   "bootstrap_replicates": 200, "bootstrap_seed": 808,
                   "limitations": ["合成软件测试：所有数值均为虚构，不能用于科研结论。",
                                   "No real EEG was read, no model was fitted, and no real participant was scored."]})
    config["target"].update({"dataset": "SYNTHETIC_ONLY", "subjects": n_subjects,
                             "trials_per_subject": n_trials})
    config["traditional_baseline"]["enabled"] = True
    config["traditional_baseline"]["nominal_fits"] = 3 * len(seeds)
    config["nominal_external_prediction_rows"] = len(DEFAULT_CONDITIONS) * len(seeds) * n_subjects * n_trials
    config["traditional_baseline"]["nominal_prediction_rows"] = 3 * len(seeds) * n_subjects * n_trials
    rng = np.random.default_rng(20261017)
    # Shared trial noise creates paired synthetic conditions; neither the inputs
    # nor the deliberately mixed person effects describe actual EEG performance.
    noise = rng.normal(size=(n_subjects, len(seeds), n_trials))
    effects = np.resize(np.array([.55, -.6, .3, -.4, .7, -.35, .2, -.1]), n_subjects)
    labels = np.arange(n_trials) % 2
    neural, conventional = [], []
    csp_conditions = [(level, "CSP_LDA", "fixed") for level in config["source_levels"]]
    for level, pipeline, selector in (*DEFAULT_CONDITIONS, *csp_conditions):
        level_index = list(config["source_levels"]).index(level)
        selector_offset = 0 if selector == "fixed" else .015 * SELECTORS.index(selector)
        pipeline_offset = {"BROAD": 0., "MU_BETA_SHARED": .04, "CSP_LDA": -.1}[pipeline]
        for person in range(n_subjects):
            for seed_index, seed in enumerate(seeds):
                margin = .6 + noise[person, seed_index] + level_index * effects[person]
                margin += selector_offset + pipeline_offset
                for trial, label in enumerate(labels):
                    signed_margin = float(margin[trial]) * (1 if label else -1)
                    row = {"source_level": level, "pipeline": pipeline, "selector": selector,
                           "seed": seed, "dataset": "SYNTHETIC_ONLY", "subject": f"synthetic-person-{person:02d}",
                           "trial_id": f"synthetic-trial-{trial:03d}", "y_true": int(label)}
                    if pipeline == "CSP_LDA":
                        row["p_right"] = float(1 / (1 + np.exp(-signed_margin)))
                        conventional.append(row)
                    else:
                        row.update({"logit_left": -signed_margin / 2, "logit_right": signed_margin / 2})
                        neural.append(row)
    for rows, prediction_name, metrics_name, report_name, conditions, comparisons in [
        (neural, "external_predictions.csv.gz", "external_subject_seed_metrics.csv", "report.json",
         DEFAULT_CONDITIONS, None),
        (conventional, "csp_external_predictions.csv.gz", "csp_subject_seed_metrics.csv", "csp_report.json",
         csp_conditions, []),
    ]:
        prediction_path = results / prediction_name
        _prediction_csv(prediction_path, rows)
        metrics = prediction_metrics(rows)
        write_csv(results / metrics_name, metrics)
        kwargs = {} if comparisons is None else {"comparisons": comparisons}
        report = paired_statistics(metrics, expected_subjects=n_subjects, expected_seeds=seeds,
                                   expected_conditions=conditions, n_bootstrap=config["bootstrap_replicates"],
                                   bootstrap_seed=config["bootstrap_seed"], **kwargs)
        report.update({"protocol_id": config["protocol_id"], "evidence_scope": "synthetic_only",
                       "prediction_rows": len(rows), "prediction_sha256": sha256_file(prediction_path),
                       "limitations": config["limitations"], "real_model_fits": 0,
                       "real_participants_scored": 0})
        if comparisons == []:
            report["role"] = "separate_descriptive_conventional_baseline"
            report["diagnostics"].update({"primary": "none; synthetic conventional summary only",
                                           "secondary": "none; no conventional hypothesis tests",
                                           "n_hypothesis_tests": 0})
        atomic_json(results / report_name, report)
    atomic_json(run / "provenance/synthetic_config.json", config)
    atomic_json(run / "provenance/SYNTHETIC_ONLY.json",
                {"scope": "synthetic_only", "raw_eeg_read": False, "models_fitted": 0,
                 "real_participants_scored": 0, "generator": "tests/test_p1_report.py"})
    # Export must include only results/provenance and skip unfinished files.
    atomic_bytes(run / "raw/NOT_REAL_EEG.txt", b"synthetic exclusion sentinel\n")
    atomic_bytes(run / "checkpoints/NOT_A_MODEL.txt", b"synthetic exclusion sentinel\n")
    atomic_bytes(results / "unfinished.tmp", b"synthetic unfinished file\n")
    return config


def check_outputs(run, config):
    """Assert output contracts and return a reviewable artifact inventory."""
    run = Path(run)
    results = run / "results"
    people = config["target"]["subjects"]
    expected_csv_counts = {
        "condition_summaries.csv": 48 * 3, "comparisons.csv": 4,
        "per_subject_metrics.csv": 48 * people, "paired_subject_differences.csv": 4 * people,
        "csp_condition_summaries.csv": 3 * 3, "csp_per_subject_metrics.csv": 3 * people,
    }
    for name, count in expected_csv_counts.items():
        with (results / name).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == count, (name, len(rows), count)
    for name, expected in [("external_predictions.csv.gz", config["nominal_external_prediction_rows"]),
                           ("csp_external_predictions.csv.gz", config["traditional_baseline"]["nominal_prediction_rows"])]:
        with gzip.open(results / name, "rt", encoding="utf-8", newline="") as stream:
            assert sum(1 for _ in csv.DictReader(stream)) == expected
    markdown = (results / "REPORT_zh.md").read_text(encoding="utf-8")
    for token in ["合成软件测试", "非科研结果", "## 传统基线", "CSP", "S9", "S29", "S60", "Holm"]:
        assert token in markdown, token
    assert "不存在真实源训练曲线" in markdown
    assert f"跨 {len(config['final_seeds'])} 个种子" in markdown
    for stem in ["source_expansion", "paired_subject_changes"]:
        png, pdf = results / (stem + ".png"), results / (stem + ".pdf")
        with Image.open(png) as picture:
            picture.verify()
        with Image.open(png) as picture:
            assert picture.width >= 2000 and picture.height >= 1000
        assert pdf.read_bytes().startswith(b"%PDF-"), str(pdf)
        assert pdf.stat().st_size > 5000
    receipt = read_json(run / "export_receipt.json")
    archive = Path(receipt["path"])
    assert receipt["sha256"] == sha256_file(archive)
    assert receipt["raw_eeg_included"] is False
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        required = {"results/REPORT_zh.md", "results/csp_report.json", "results/report.json",
                    "provenance/SYNTHETIC_ONLY.json", "provenance/synthetic_config.json"}
        required |= {"results/" + name for name in expected_csv_counts}
        required |= {f"results/{stem}.{ext}" for stem in ["source_expansion", "paired_subject_changes"]
                     for ext in ["png", "pdf"]}
        assert required <= names, sorted(required - names)
        assert all(name.startswith(("results/", "provenance/")) and not name.endswith(".tmp") for name in names)
        assert all(z.read(name) == (run / name).read_bytes() for name in names)
    return {"scope": "synthetic_only", "status": "PASS", "real_model_fits": 0,
            "real_participants_scored": 0, "neural_conditions": 48, "csp_conditions": 3,
            "synthetic_people": people, "seeds": config["final_seeds"],
            "neural_prediction_rows": config["nominal_external_prediction_rows"],
            "csp_prediction_rows": config["traditional_baseline"]["nominal_prediction_rows"],
            "csv_row_counts": expected_csv_counts, "archive_sha256": receipt["sha256"],
            "archive_members": sorted(names),
            "artifacts": [{"path": str(path.relative_to(run)), "bytes": path.stat().st_size,
                           "sha256": sha256_file(path)} for path in sorted(results.glob("*")) if path.is_file()
                          and not path.name.endswith(".tmp")]}


def preserve_synthetic_preview(path):
    path = Path(path)
    config = make_synthetic_run(path)
    render_report(path / "results", config)
    export_results(path, config)
    validation = check_outputs(path, config)
    atomic_json(path / "synthetic_validation.json", validation)
    return validation


class ReportExportTests(unittest.TestCase):
    def test_synthetic_neural_and_csp_report_export_closure(self):
        with tempfile.TemporaryDirectory(prefix="paper1-report-synthetic-") as tmp:
            config = make_synthetic_run(tmp, seeds=(101, 202))
            render_report(Path(tmp) / "results", config)
            export_results(tmp, config)
            checked = check_outputs(tmp, config)
            self.assertEqual(checked["csp_conditions"], 3)
            self.assertEqual(checked["neural_conditions"], 48)

    def test_incomplete_report_never_produces_export(self):
        with tempfile.TemporaryDirectory(prefix="paper1-report-incomplete-") as tmp:
            config = make_synthetic_run(tmp)
            path = Path(tmp) / "results/report.json"
            report = read_json(path)
            report["diagnostics"]["complete_paired_grid"] = False
            atomic_json(path, report)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                export_results(tmp, config)
            self.assertFalse((Path(tmp) / "paper1_expansion_results.zip").exists())

    def test_enabled_baseline_is_required_for_export(self):
        with tempfile.TemporaryDirectory(prefix="paper1-report-missing-csp-") as tmp:
            config = make_synthetic_run(tmp)
            (Path(tmp) / "results/csp_report.json").unlink()
            with self.assertRaises(FileNotFoundError):
                export_results(tmp, config)
            self.assertFalse((Path(tmp) / "paper1_expansion_results.zip").exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preserve", type=Path)
    args, remaining = parser.parse_known_args()
    if args.preserve:
        preview = preserve_synthetic_preview(args.preserve)
        print(json.dumps({key: preview[key] for key in ["status", "scope", "neural_conditions", "csp_conditions"]}))
    else:
        unittest.main(argv=[sys.argv[0], *remaining])
