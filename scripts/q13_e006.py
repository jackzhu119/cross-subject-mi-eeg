"""Q13-E006: matched-runtime broadband raw-CE duration sensitivity.

New, versioned 27-fit amendment. Frozen Q13/Q5 sources are read-only. No
training occurs unless --execute is supplied and all predecessor/runtime/data
gates pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import numpy as np
import pandas as pd
import torch

from scripts import q9_neural as q9
from scripts import q13_neural
from scripts.run_eegnet import sha256_file, source_files, write_json

MATRIX = ROOT / "research_runs/Q13-E006/MATRIX.json"
AMENDMENT = ROOT / "research_runs/Q13-E006/AMENDMENT.md"
Q5_CURVES = ROOT / "results/Q5-E001/learning_curves.csv"
Q5_SELECTION = ROOT / "results/Q5-E001/selection.csv"
FIXED = ROOT / "results/Q13-E001/Q8_FIXED20"
VALIDATION = ROOT / "results/Q13-BATCH/validation_report.json"
BATCH_STATUS = ROOT / "results/Q13-BATCH/batch_status.json"
EXPERIMENT = "Q13-E006"
CONDITION = "Q8_RAW_CE_MATCHED"
SUBJECTS = tuple(range(1, 10))
SEEDS = (20260924, 20260925, 20260926)
TRAINING_CODE_PATHS = (
    "scripts/q13_neural.py",
    "scripts/q9_neural.py",
    "scripts/run_eegnet.py",
    "src/mi_eeg/data/bnci_epochs.py",
    "src/mi_eeg/evaluation/splits.py",
    "src/mi_eeg/models/eegnet_training.py",
    "src/mi_eeg/provenance.py",
)
HISTORICAL_Q5_SELECTION_PATHS = (
    "results/Q5-E001/config.json",
    "results/Q5-E001/learning_curves.csv",
    "results/Q5-E001/selection.csv",
    "results/Q5-E001/validation_report.json",
)


def selected_epochs_from_q5() -> dict[str, int]:
    """Reconstruct all selections from the original 36 source-only inner fits."""
    q13_neural._check_q5_reuse()
    curves = pd.read_csv(Q5_CURVES)
    selection = pd.read_csv(Q5_SELECTION)
    inner = curves[curves.stage.eq("inner")].copy()
    if (len(inner) != 9 * 4 * 40 or len(selection) != 9
            or inner[["fold", "inner_fold", "epoch"]].duplicated().any()
            or selection.fold.duplicated().any()):
        raise AssertionError("Q5 source-only inner population changed")
    if not inner.seed.eq(20260923).all() or not np.isfinite(inner.val_ce.to_numpy(float)).all():
        raise AssertionError("Q5 inner seed or validation CE changed")
    by_fold = selection.set_index("fold")
    if set(by_fold.index) != {f"loso_s{s}" for s in SUBJECTS}:
        raise AssertionError("Q5 selection folds differ")
    chosen = {}
    for target in SUBJECTS:
        fold = f"loso_s{target}"
        part = inner[inner.fold.eq(fold)]
        if (len(part) != 160 or set(part.inner_fold.astype(int)) != {1, 2, 3, 4}
                or set(part.epoch.astype(int)) != set(range(1, 41))):
            raise AssertionError(f"Q5 inner curves incomplete: {fold}")
        losses = []
        for inner_fold in (1, 2, 3, 4):
            one = part[part.inner_fold.eq(inner_fold)].sort_values("epoch")
            if one.epoch.astype(int).tolist() != list(range(1, 41)):
                raise AssertionError(f"Q5 inner epoch grid differs: {fold}")
            losses.append(one.val_ce.to_numpy(float))
        means = np.stack(losses).mean(axis=0)
        epoch = int(np.argmin(means) + 1)
        if (int(by_fold.loc[fold, "selected_epochs"]) != epoch
                or not np.isclose(float(by_fold.loc[fold, "validation_ce"]),
                                  means[epoch - 1], rtol=0, atol=1e-12)):
            raise AssertionError(f"Q5 source-only selection disagrees: {fold}")
        chosen[str(target)] = epoch
    return chosen


def file_identity(records: list[dict]) -> dict[str, tuple[int, str]]:
    if len(records) != 18:
        raise AssertionError("Exactly 18 BNCI MAT files required")
    identity = {Path(item["path"]).name: (int(item["bytes"]), item["sha256"])
                for item in records}
    expected = {f"A{s:02d}{part}.mat" for s in SUBJECTS for part in ("T", "E")}
    if len(identity) != 18 or set(identity) != expected:
        raise AssertionError("BNCI cache has duplicated or missing MAT files")
    return identity


def assert_committed_amendment() -> str:
    q13_neural.assert_pretarget_git_freeze()
    files = ("scripts/q13_e006.py", "scripts/validate_q13_e006.py",
             "research_runs/Q13-E006/MATRIX.json",
             "research_runs/Q13-E006/AMENDMENT.md", "tests/test_q13_e006.py",
             "results/Q5-E001/learning_curves.csv", "results/Q5-E001/selection.csv",
             "results/Q5-E001/validation_report.json")
    for args in (("ls-files", "--error-unmatch", "--", *files),
                 ("diff", "--quiet", "--", *files),
                 ("diff", "--cached", "--quiet", "--", *files)):
        result = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("Q13-E006 amendment/code not committed unchanged")
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT,
                                   text=True).strip()


def assert_historical_training_sources(previous_environment: dict) -> dict[str, str]:
    """Require historical training code and Q5 selection artifacts byte-identical."""
    historical_head = previous_environment.get("git_head")
    if not isinstance(historical_head, str) or re.fullmatch(r"[0-9a-f]{40,64}", historical_head) is None:
        raise RuntimeError("Q13 fixed-20 environment lacks a valid historical Git HEAD")
    digests = {}
    for relative in (*TRAINING_CODE_PATHS, *HISTORICAL_Q5_SELECTION_PATHS):
        original = subprocess.run(
            ("git", "show", f"{historical_head}:{relative}"), cwd=ROOT,
            capture_output=True, check=False,
        )
        path = ROOT / relative
        if original.returncode or not path.is_file():
            raise RuntimeError(f"Cannot reconstruct Q13 fixed-20 training source: {relative}")
        original_digest = hashlib.sha256(original.stdout).hexdigest()
        if sha256_file(path) != original_digest:
            raise RuntimeError(f"Q13-E006 source/archive differs from fixed-20: {relative}")
        digests[relative] = original_digest
    return digests


def preflight(data_dir: Path) -> tuple[dict, dict, dict[str, int]]:
    """Check all scientific and runtime gates before paid computation."""
    if not torch.cuda.is_available():
        raise RuntimeError("Q13-E006 requires working CUDA; no CPU fallback")
    assert_committed_amendment()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    if (matrix.get("experiment_id") != EXPERIMENT or matrix.get("new_final_fits") != 27
            or matrix.get("final_seeds") != list(SEEDS) or matrix.get("target_fits") != 0):
        raise AssertionError("Q13-E006 matrix changed")
    scientific = json.loads(VALIDATION.read_text(encoding="utf-8"))
    batch = json.loads(BATCH_STATUS.read_text(encoding="utf-8"))
    if (scientific.get("status") != "passed" or scientific.get("checkpoint_replays") != 837
            or batch.get("status") != "complete_validated"):
        raise RuntimeError("Full Q13 scientific validation is required first")
    fixed = json.loads((FIXED / "run_config.json").read_text(encoding="utf-8"))
    status = json.loads((FIXED / "status.json").read_text(encoding="utf-8"))
    if (fixed.get("experiment_id") != "Q13-E001" or fixed.get("condition") != "Q8_FIXED20"
            or fixed.get("method") != "Q8_BROAD" or fixed.get("shared_mean_logits") is not False
            or set(fixed.get("selected_epochs_by_target", {}).values()) != {20}
            or fixed.get("runner_sha256") != sha256_file(Path(q13_neural.__file__))
            or status.get("status") != "complete" or status.get("completed_final_fits") != 27):
        raise AssertionError("Q13 fixed-20 comparator differs from frozen contract")
    source_provenance = fixed.get("source_only_selection_provenance", {})
    for field, path in (
        ("q5_config_sha256", ROOT / "results/Q5-E001/config.json"),
        ("q5_selection_sha256", Q5_SELECTION),
        ("q5_validation_sha256", ROOT / "results/Q5-E001/validation_report.json"),
    ):
        if source_provenance.get(field) != sha256_file(path):
            raise RuntimeError(f"Q13 fixed-20 Q5 provenance differs: {field}")
    current = q9._versions()
    previous = json.loads((FIXED / "environment.json").read_text(encoding="utf-8"))
    for key in ("python", "platform", "packages", "torch_cuda_runtime", "cuda_device_name"):
        if current.get(key) != previous.get(key):
            raise RuntimeError(f"Runtime mismatch against Q13 fixed-20: {key}")
    assert_historical_training_sources(previous)
    prior_files = json.loads((FIXED / "source_files.json").read_text(encoding="utf-8"))["files"]
    if file_identity(prior_files) != file_identity(source_files(data_dir, list(SUBJECTS))):
        raise RuntimeError("BNCI MAT files differ from Q13 fixed-20 comparator")
    return fixed, current, selected_epochs_from_q5()


def build_config(data_dir: Path, fixed: dict, epochs: dict[str, int]) -> dict:
    """Copy the fixed-20 settings, changing only identity and duration."""
    config = json.loads(json.dumps(fixed))
    config["experiment_id"] = EXPERIMENT
    config["condition"] = CONDITION
    config["selected_epochs_by_target"] = epochs
    config["source_only_selection_provenance"] = {
        **fixed["source_only_selection_provenance"],
        "q5_learning_curves_sha256": sha256_file(Q5_CURVES),
        "q5_selection_sha256": sha256_file(Q5_SELECTION),
        "selection_rule": "earliest_minimum_equal_inner_fold_mean_raw_CE",
    }
    config["data_dir"] = str(data_dir.resolve())
    config["runner_sha256"] = sha256_file(Path(__file__))
    config["amendment_matrix_sha256"] = sha256_file(MATRIX)
    config["amendment_sha256"] = sha256_file(AMENDMENT)
    config["fixed20_config_sha256"] = sha256_file(FIXED / "run_config.json")
    return config


def locked_config(output: Path, data_dir: Path, fixed: dict,
                  epochs: dict[str, int]) -> dict:
    config = build_config(data_dir, fixed, epochs)
    path = output / "run_config.json"
    if path.is_file():
        if json.loads(path.read_text(encoding="utf-8")) != config:
            raise AssertionError("Q13-E006 config changed during resume")
    else:
        write_json(path, config)
    return config


def aggregate(output: Path) -> dict:
    complete = []
    for target in SUBJECTS:
        for seed in SEEDS:
            directory = q13_neural._fit_dir(output, target, "all", seed)
            if q9._fit_complete(directory, q13_neural.FIT_FILES):
                complete.append(directory)
    state = {"experiment_id": EXPERIMENT, "condition": CONDITION,
             "status": "complete" if len(complete) == 27 else "running",
             "completed_final_fits": len(complete), "expected_final_fits": 27,
             "completed_inner_fits": 0, "target_fits": 0, "updated_at_utc": q9.now_utc()}
    if complete:
        for source, destination in (("predictions.csv", "predictions.csv"),
                                    ("metrics.csv", "per_subject_metrics.csv"),
                                    ("confusion.csv", "confusion_matrices.csv"),
                                    ("fit_manifest.csv", "fit_manifest.csv")):
            q9.atomic_csv(output / destination, pd.concat(
                (pd.read_csv(directory / source) for directory in complete), ignore_index=True))
    write_json(output / "status.json", state)
    return state


def execute(data_dir: Path, output_root: Path) -> dict:
    fixed, environment, epochs = preflight(data_dir)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    mne.set_log_level("ERROR")
    device = torch.device("cuda")
    output = output_root / EXPERIMENT / CONDITION
    output.mkdir(parents=True, exist_ok=True)
    config = locked_config(output, data_dir, fixed, epochs)
    environment_path = output / "environment.json"
    if environment_path.is_file():
        previous = json.loads(environment_path.read_text(encoding="utf-8"))
        for key in ("python", "platform", "packages", "torch_cuda_runtime", "cuda_device_name"):
            if previous.get(key) != environment.get(key):
                raise RuntimeError(f"Q13-E006 resumed under different runtime: {key}")
    else:
        write_json(environment_path, environment)
    x, y, metadata, _ = q9._load_data(config, data_dir, device, output)
    try:
        for target in SUBJECTS:
            sources = tuple(subject for subject in SUBJECTS if subject != target)
            for seed in SEEDS:
                q13_neural._run_fit(output, config, metadata, x, y, target, "all",
                                    sources, None, seed, device)
            aggregate(output)
    except Exception:
        write_json(output / "last_failure.json", {"time_utc": q9.now_utc(),
                                                  "traceback": traceback.format_exc()})
        aggregate(output)
        raise
    return aggregate(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually train; default is plan only")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "plan_only_no_training", "experiment_id": EXPERIMENT,
                          "new_final_fits": 27, "new_inner_fits": 0,
                          "q5_selected_epochs": selected_epochs_from_q5()}, indent=2))
        return 0
    if args.output_root.resolve() != (ROOT / "results").resolve():
        raise RuntimeError("Q13-E006 output must remain in the repository results directory")
    state = execute(args.data_dir.resolve(), args.output_root.resolve())
    print(json.dumps(state, indent=2))
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
