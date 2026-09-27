"""Independent full-data/27-checkpoint validator for Q13-E006.

No model is fitted here. This only validates the versioned matched-runtime
duration comparator; the original 837-fit Q13 validator remains unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import pandas as pd
import torch

from scripts import q9_neural as q9
from scripts import q13_e006
from scripts.run_eegnet import sha256_file, verify_q4_identity, write_json
from scripts.validate_q13 import REFERENCE, _validate_fit


def validate(data_dir: Path, results_root: Path) -> dict:
    fixed, current_environment, epochs = q13_e006.preflight(data_dir)
    output = results_root / q13_e006.EXPERIMENT / q13_e006.CONDITION
    config_path = output / "run_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = q13_e006.build_config(data_dir, fixed, epochs)
    if config != expected:
        raise AssertionError("Q13-E006 config differs from the versioned amendment")
    environment = json.loads((output / "environment.json").read_text(encoding="utf-8"))
    for key in ("python", "platform", "packages", "torch_cuda_runtime", "cuda_device_name"):
        if environment.get(key) != current_environment.get(key):
            raise AssertionError(f"Q13-E006 fit runtime changed before validation: {key}")
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if (status.get("status") != "complete" or status.get("completed_final_fits") != 27
            or status.get("target_fits") != 0):
        raise AssertionError("Q13-E006 27-fit receipt incomplete")
    reference = pd.read_csv(REFERENCE)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_num_threads(4)
    mne.set_log_level("ERROR")
    device = torch.device("cuda")
    signal, _labels, loaded_meta, _numpy_signal = q9._load_data(config, data_dir,
                                                                 device, output)
    verify_q4_identity(loaded_meta, reference)
    rows = []
    for target in q13_e006.SUBJECTS:
        sources = tuple(subject for subject in q13_e006.SUBJECTS if subject != target)
        for seed in q13_e006.SEEDS:
            directory = q13_e006.q13_neural._fit_dir(output, target, "all", seed)
            rows.append(_validate_fit(
                directory, reference, target=target, seed=seed,
                condition=q13_e006.CONDITION, subset_id="all", source=sources,
                session=None, selected=epochs[str(target)],
                replay_context=(config, signal, device)))
    if len(rows) != 27:
        raise AssertionError("Q13-E006 checkpoint replay coverage differs")
    aggregate = pd.read_csv(output / "predictions.csv")
    if (len(aggregate) != 27 * 576
            or aggregate[["subject", "seed", "sample_id"]].duplicated().any()
            or set(aggregate.subject) != set(q13_e006.SUBJECTS)
            or set(aggregate.seed) != set(q13_e006.SEEDS)):
        raise AssertionError("Q13-E006 aggregate trial coverage differs")
    individual = pd.concat(
        (pd.read_csv(q13_e006.q13_neural._fit_dir(output, target, "all", seed)
                     / "predictions.csv")
         for target in q13_e006.SUBJECTS for seed in q13_e006.SEEDS),
        ignore_index=True)
    columns = ["subject", "seed", "sample_id", "y_true", "y_pred",
               "p_class_1", "p_class_2", "p_class_3", "p_class_4"]
    keys = ["subject", "seed", "sample_id"]
    merged = aggregate[columns].merge(individual[columns], on=keys,
                                       how="outer", indicator=True,
                                       suffixes=("_aggregate", "_fit"),
                                       validate="one_to_one")
    if not merged._merge.eq("both").all():
        raise AssertionError("Q13-E006 aggregate trial keys differ from fit files")
    for column in ("y_true", "y_pred"):
        if not merged[f"{column}_aggregate"].eq(merged[f"{column}_fit"]).all():
            raise AssertionError(f"Q13-E006 aggregate {column} differs")
    for column in ("p_class_1", "p_class_2", "p_class_3", "p_class_4"):
        if not (merged[f"{column}_aggregate"] -
                merged[f"{column}_fit"]).abs().le(1e-12).all():
            raise AssertionError(f"Q13-E006 aggregate {column} differs")
    report = {
        "status": "passed", "experiment_id": q13_e006.EXPERIMENT,
        "condition": q13_e006.CONDITION, "new_final_fits": 27,
        "checkpoint_replays": 27, "n_held_out_subjects": 9,
        "n_independently_checked_predictions": 27 * 576,
        "target_fit_or_selection": False,
        "matched_runtime_comparator": "Q13-E001/Q8_FIXED20",
        "selection": "historical_Q5_source_only_raw_CE_schedule_not_reselected_on_new_runtime",
        "analysis_status": "exploratory_not_independent_confirmation",
        "amendment_matrix_sha256": sha256_file(q13_e006.MATRIX),
        "run_config_sha256": sha256_file(config_path),
    }
    write_json(results_root / q13_e006.EXPERIMENT / "validation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, default=q13_e006.ROOT / "results")
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    args = parser.parse_args()
    if args.results_root.resolve() != (q13_e006.ROOT / "results").resolve():
        raise RuntimeError("Q13-E006 validator must use the repository results directory")
    print(json.dumps(validate(args.data_dir.resolve(), args.results_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
