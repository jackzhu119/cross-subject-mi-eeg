from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

Q5 = Path("/workspace/Q5_EEGNet_Cloud_Ready")
Q8 = Path("/workspace/Q8_MeanRank_Selection")
RUN = Q8 / "results/Q8-E001"

CURVES = Q5 / "results/Q5-E001/learning_curves.csv"
Q5_CONFIG = Q5 / "configs/q5_e001_eegnet.json"

OUT = RUN / "predeclared_selection.csv"
PROVENANCE = RUN / "selection_provenance.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def earliest_argmin(series: pd.Series) -> int:
    minimum = float(series.min())

    candidates = [
        int(epoch)
        for epoch, value in series.items()
        if np.isclose(
            float(value),
            minimum,
            atol=1e-12,
            rtol=0,
        )
    ]

    return min(candidates)


config = json.loads(
    Q5_CONFIG.read_text(encoding="utf-8")
)

lc = pd.read_csv(CURVES)

required = {
    "fold",
    "stage",
    "inner_fold",
    "seed",
    "epoch",
    "train_ce",
    "val_ce",
}

missing = required - set(lc.columns)

if missing:
    raise AssertionError(
        f"Q5 learning curves missing columns: {missing}"
    )

inner = lc[
    lc["stage"] == "inner"
].copy()

# Q5 frozen contract:
# 9 outer folds × 4 inner folds × 40 epochs
if len(inner) != 9 * 4 * 40:
    raise AssertionError(
        f"Expected 1440 Q5 inner rows, got {len(inner)}"
    )

if sorted(inner["seed"].unique().tolist()) != [
    config["training"]["selection_seed"]
]:
    raise AssertionError(
        "Unexpected Q5 inner selection seed"
    )

rows = []
detail_rows = []

for subject in config["subjects"]:

    fold = f"loso_s{subject}"

    g = inner[
        inner["fold"] == fold
    ].copy()

    if len(g) != 160:
        raise AssertionError(
            f"{fold}: expected 160 rows, got {len(g)}"
        )

    pivot = g.pivot(
        index="epoch",
        columns="inner_fold",
        values="val_ce",
    ).sort_index()

    pivot.columns = [
        int(x) for x in pivot.columns
    ]

    if list(pivot.index.astype(int)) != list(
        range(1, 41)
    ):
        raise AssertionError(
            f"{fold}: epochs are not exactly 1..40"
        )

    if list(pivot.columns) != [1, 2, 3, 4]:
        raise AssertionError(
            f"{fold}: inner folds are not 1..4"
        )

    # Rank epochs independently within each validation fold.
    # Smallest CE = best rank.
    ranks = pivot.rank(
        axis=0,
        method="average",
        ascending=True,
    )

    mean_rank = ranks.mean(axis=1)

    selected_epoch = earliest_argmin(
        mean_rank
    )

    selected_mean_rank = float(
        mean_rank.loc[selected_epoch]
    )

    rows.append(
        {
            "fold": fold,
            "subject": int(subject),
            "selected_epochs": int(selected_epoch),
            "selection_rule": "mean_rank",
            "selected_mean_rank": selected_mean_rank,
            "inner_curve_source": "Q5-E001",
            "selection_seed": int(
                config["training"]["selection_seed"]
            ),
            "max_candidate_epoch": 40,
            "target_result_used": False,
        }
    )

    for epoch in range(1, 41):
        detail_rows.append(
            {
                "fold": fold,
                "subject": int(subject),
                "epoch": epoch,
                "rank_inner_1": float(
                    ranks.loc[epoch, 1]
                ),
                "rank_inner_2": float(
                    ranks.loc[epoch, 2]
                ),
                "rank_inner_3": float(
                    ranks.loc[epoch, 3]
                ),
                "rank_inner_4": float(
                    ranks.loc[epoch, 4]
                ),
                "mean_rank": float(
                    mean_rank.loc[epoch]
                ),
                "selected": bool(
                    epoch == selected_epoch
                ),
            }
        )

selection = pd.DataFrame(rows)
details = pd.DataFrame(detail_rows)

# Important idempotence:
# if selection was already frozen, it must be identical.
if OUT.exists():
    previous = pd.read_csv(OUT)

    if not previous.equals(selection):
        raise AssertionError(
            "Existing Q8 predeclared selection differs. "
            "Refusing to overwrite a frozen selection."
        )

selection.to_csv(
    OUT,
    index=False,
)

details.to_csv(
    RUN / "mean_rank_epoch_details.csv",
    index=False,
)

selection_sha = sha256_file(OUT)

provenance = {
    "experiment_id": "Q8-E001",
    "selection_status": "frozen_before_Q8_target_evaluation",
    "selection_rule": (
        "earliest epoch minimizing mean within-fold "
        "validation-CE rank"
    ),
    "source_learning_curves": str(CURVES),
    "source_learning_curves_sha256": sha256_file(
        CURVES
    ),
    "source_q5_config": str(Q5_CONFIG),
    "source_q5_config_sha256": sha256_file(
        Q5_CONFIG
    ),
    "predeclared_selection_sha256": selection_sha,
    "target_results_read_by_freeze_script": False,
    "inner_fits_retrained": False,
    "n_subjects": 9,
    "n_inner_folds": 4,
    "candidate_epochs": [1, 40],
}

if PROVENANCE.exists():
    old = json.loads(
        PROVENANCE.read_text(encoding="utf-8")
    )

    if old != provenance:
        raise AssertionError(
            "Existing selection provenance differs."
        )

PROVENANCE.write_text(
    json.dumps(
        provenance,
        indent=2,
    ),
    encoding="utf-8",
)

print()
print("============================================================")
print(" Q8-E001 PREDECLARED SELECTION FROZEN")
print("============================================================")
print()
print(
    selection[
        [
            "subject",
            "selected_epochs",
            "selected_mean_rank",
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)
print()
print("Selection SHA256:")
print(selection_sha)
