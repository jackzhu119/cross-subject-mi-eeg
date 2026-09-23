from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path("/workspace/Q5_EEGNet_Cloud_Ready/research_runs/Q8-A001")
INPUT = ROOT / "inputs"
OUT = ROOT / "analysis"
FIG = ROOT / "figures"

OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)


# ============================================================
# Utilities
# ============================================================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_corr(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(x) < 3:
        return {
            "pearson_r": np.nan,
            "pearson_p": np.nan,
            "spearman_rho": np.nan,
            "spearman_p": np.nan,
        }

    if np.std(x) == 0 or np.std(y) == 0:
        return {
            "pearson_r": np.nan,
            "pearson_p": np.nan,
            "spearman_rho": np.nan,
            "spearman_p": np.nan,
        }

    pr, pp = pearsonr(x, y)
    sr, sp = spearmanr(x, y)

    return {
        "pearson_r": float(pr),
        "pearson_p": float(pp),
        "spearman_rho": float(sr),
        "spearman_p": float(sp),
    }


# ============================================================
# 1. Load frozen data
# ============================================================

datasets = {}

for exp in ["Q5", "Q6"]:
    datasets[exp] = {
        "learning": pd.read_csv(INPUT / f"{exp}_learning_curves.csv"),
        "selection": pd.read_csv(INPUT / f"{exp}_selection.csv"),
        "metrics": pd.read_csv(INPUT / f"{exp}_per_subject_metrics.csv"),
    }

q7 = pd.read_csv(INPUT / "Q7_four_cell_summary.csv")


# ============================================================
# 2. Structural validation
# ============================================================

required_curve_cols = {
    "fold",
    "stage",
    "inner_fold",
    "seed",
    "epoch",
    "train_ce",
    "val_ce",
}

for exp, obj in datasets.items():

    lc = obj["learning"]

    missing = required_curve_cols - set(lc.columns)

    if missing:
        raise AssertionError(
            f"{exp} learning_curves missing columns: {missing}"
        )

    inner = lc[lc["stage"] == "inner"].copy()

    # 9 folds × 4 inner folds × 40 epochs
    if len(inner) != 9 * 4 * 40:
        raise AssertionError(
            f"{exp}: expected 1440 inner rows, got {len(inner)}"
        )

    for subject in range(1, 10):

        fold = f"loso_s{subject}"

        g = inner[inner["fold"] == fold]

        if len(g) != 160:
            raise AssertionError(
                f"{exp} {fold}: expected 160 rows, got {len(g)}"
            )

        inner_ids = sorted(
            int(x) for x in g["inner_fold"].dropna().unique()
        )

        if inner_ids != [1, 2, 3, 4]:
            raise AssertionError(
                f"{exp} {fold}: inner folds are {inner_ids}"
            )

        for inner_fold in [1, 2, 3, 4]:

            epochs = (
                g[g["inner_fold"] == inner_fold]["epoch"]
                .astype(int)
                .tolist()
            )

            if epochs != list(range(1, 41)):
                raise AssertionError(
                    f"{exp} {fold} inner {inner_fold}: "
                    "epochs are not exactly 1..40"
                )

print("Structural validation of Q5/Q6 learning curves: PASSED")


# ============================================================
# 3. Full per-subject selection audit
# ============================================================

audit_rows = []
curve_rows = []
fold_optimum_rows = []
checkpoint_rows = []

TOLERANCES = [0.001, 0.0025, 0.005, 0.01]
CHECKPOINT_EPOCHS = [1, 2, 4, 8, 12, 16, 20, 24, 32, 40]

for exp, obj in datasets.items():

    lc = obj["learning"]
    sel = obj["selection"]

    inner = lc[
        lc["stage"] == "inner"
    ].copy()

    for subject in range(1, 10):

        fold = f"loso_s{subject}"

        g = inner[
            inner["fold"] == fold
        ].copy()

        val_pivot = g.pivot(
            index="epoch",
            columns="inner_fold",
            values="val_ce",
        ).sort_index()

        train_pivot = g.pivot(
            index="epoch",
            columns="inner_fold",
            values="train_ce",
        ).sort_index()

        val_pivot.columns = [
            int(x) for x in val_pivot.columns
        ]

        train_pivot.columns = [
            int(x) for x in train_pivot.columns
        ]

        val_mean = val_pivot.mean(axis=1)
        val_sd = val_pivot.std(axis=1, ddof=1)
        val_sem = val_sd / np.sqrt(4)

        train_mean = train_pivot.mean(axis=1)

        selected = int(
            sel.loc[
                sel["fold"] == fold,
                "selected_epochs",
            ].iloc[0]
        )

        saved_validation_ce = float(
            sel.loc[
                sel["fold"] == fold,
                "validation_ce",
            ].iloc[0]
        )

        computed_selected = int(
            val_mean.idxmin()
        )

        if computed_selected != selected:
            raise AssertionError(
                f"{exp} {fold}: computed selection "
                f"{computed_selected} != saved {selected}"
            )

        selected_ce = float(
            val_mean.loc[selected]
        )

        if not np.isclose(
            selected_ce,
            saved_validation_ce,
            atol=1e-10,
            rtol=0,
        ):
            raise AssertionError(
                f"{exp} {fold}: saved validation CE mismatch"
            )

        sorted_mean = val_mean.sort_values()

        best_ce = float(
            sorted_mean.iloc[0]
        )

        second_best_ce = float(
            sorted_mean.iloc[1]
        )

        second_best_margin = (
            second_best_ce - best_ce
        )

        fold_min_epochs = (
            val_pivot.idxmin(axis=0)
            .astype(int)
            .to_numpy()
        )

        fold_min_ces = (
            val_pivot.min(axis=0)
            .to_numpy(dtype=float)
        )

        selected_fold_values = (
            val_pivot.loc[selected]
            .to_numpy(dtype=float)
        )

        fold_regret = (
            selected_fold_values
            - fold_min_ces
        )

        row = {
            "experiment": exp,
            "subject": subject,
            "fold": fold,
            "selected_epoch": selected,
            "selected_mean_val_ce": selected_ce,
            "selected_fold_sd": float(
                val_sd.loc[selected]
            ),
            "selected_fold_sem": float(
                val_sem.loc[selected]
            ),
            "selected_mean_train_ce": float(
                train_mean.loc[selected]
            ),
            "second_best_mean_val_ce": second_best_ce,
            "margin_to_second_best": float(
                second_best_margin
            ),
            "early_selection_le_2": bool(
                selected <= 2
            ),
            "early_selection_le_5": bool(
                selected <= 5
            ),
            "boundary_epoch_40": bool(
                selected == 40
            ),
            "inner_optimum_epoch_1": int(
                fold_min_epochs[0]
            ),
            "inner_optimum_epoch_2": int(
                fold_min_epochs[1]
            ),
            "inner_optimum_epoch_3": int(
                fold_min_epochs[2]
            ),
            "inner_optimum_epoch_4": int(
                fold_min_epochs[3]
            ),
            "inner_optimum_epoch_mean": float(
                np.mean(fold_min_epochs)
            ),
            "inner_optimum_epoch_median": float(
                np.median(fold_min_epochs)
            ),
            "inner_optimum_epoch_std": float(
                np.std(
                    fold_min_epochs,
                    ddof=1,
                )
            ),
            "inner_optimum_epoch_min": int(
                np.min(fold_min_epochs)
            ),
            "inner_optimum_epoch_max": int(
                np.max(fold_min_epochs)
            ),
            "inner_optimum_epoch_range": int(
                np.max(fold_min_epochs)
                - np.min(fold_min_epochs)
            ),
            "inner_optimum_epoch_iqr": float(
                np.percentile(
                    fold_min_epochs,
                    75,
                )
                - np.percentile(
                    fold_min_epochs,
                    25,
                )
            ),
            "inner_optima_within_selected_pm2": int(
                np.sum(
                    np.abs(
                        fold_min_epochs
                        - selected
                    )
                    <= 2
                )
            ),
            "inner_optima_within_selected_pm5": int(
                np.sum(
                    np.abs(
                        fold_min_epochs
                        - selected
                    )
                    <= 5
                )
            ),
            "selected_fold_regret_mean": float(
                np.mean(fold_regret)
            ),
            "selected_fold_regret_max": float(
                np.max(fold_regret)
            ),
        }

        for tol in TOLERANCES:

            suffix = str(tol).replace(
                "0.",
                "",
            )

            near = val_mean[
                val_mean <= best_ce + tol
            ]

            near_epochs = (
                near.index.astype(int)
                .to_numpy()
            )

            row[
                f"near_min_{suffix}_count"
            ] = int(len(near_epochs))

            row[
                f"near_min_{suffix}_earliest"
            ] = int(np.min(near_epochs))

            row[
                f"near_min_{suffix}_latest"
            ] = int(np.max(near_epochs))

            row[
                f"near_min_{suffix}_span"
            ] = int(
                np.max(near_epochs)
                - np.min(near_epochs)
            )

        for epoch in CHECKPOINT_EPOCHS:

            row[
                f"mean_val_ce_epoch_{epoch}"
            ] = float(
                val_mean.loc[epoch]
            )

            row[
                f"delta_ce_epoch_{epoch}_minus_selected"
            ] = float(
                val_mean.loc[epoch]
                - selected_ce
            )

        audit_rows.append(row)

        for epoch in range(1, 41):

            curve_rows.append(
                {
                    "experiment": exp,
                    "subject": subject,
                    "fold": fold,
                    "epoch": epoch,
                    "mean_val_ce": float(
                        val_mean.loc[epoch]
                    ),
                    "sd_val_ce": float(
                        val_sd.loc[epoch]
                    ),
                    "sem_val_ce": float(
                        val_sem.loc[epoch]
                    ),
                    "mean_train_ce": float(
                        train_mean.loc[epoch]
                    ),
                    "selected_epoch": selected,
                    "is_selected": bool(
                        epoch == selected
                    ),
                }
            )

        for inner_fold in [1, 2, 3, 4]:

            opt_epoch = int(
                val_pivot[
                    inner_fold
                ].idxmin()
            )

            fold_optimum_rows.append(
                {
                    "experiment": exp,
                    "subject": subject,
                    "fold": fold,
                    "inner_fold": inner_fold,
                    "optimum_epoch": opt_epoch,
                    "optimum_val_ce": float(
                        val_pivot.loc[
                            opt_epoch,
                            inner_fold,
                        ]
                    ),
                    "val_ce_at_group_selected": float(
                        val_pivot.loc[
                            selected,
                            inner_fold,
                        ]
                    ),
                    "epoch_distance_from_group_selected":
                        int(
                            opt_epoch
                            - selected
                        ),
                }
            )

        for epoch in CHECKPOINT_EPOCHS:

            checkpoint_rows.append(
                {
                    "experiment": exp,
                    "subject": subject,
                    "epoch": epoch,
                    "mean_val_ce": float(
                        val_mean.loc[epoch]
                    ),
                    "mean_train_ce": float(
                        train_mean.loc[epoch]
                    ),
                    "selected_epoch": selected,
                    "delta_ce_from_selected": float(
                        val_mean.loc[epoch]
                        - selected_ce
                    ),
                }
            )


audit = pd.DataFrame(audit_rows)

mean_curves = pd.DataFrame(curve_rows)

fold_optima = pd.DataFrame(
    fold_optimum_rows
)

checkpoints = pd.DataFrame(
    checkpoint_rows
)

audit.to_csv(
    OUT / "selection_stability_audit.csv",
    index=False,
)

mean_curves.to_csv(
    OUT / "mean_inner_validation_curves.csv",
    index=False,
)

fold_optima.to_csv(
    OUT / "inner_fold_optimum_epochs.csv",
    index=False,
)

checkpoints.to_csv(
    OUT / "validation_ce_checkpoints.csv",
    index=False,
)


# ============================================================
# 4. Q5 vs Q6 selection trajectory comparison
# ============================================================

q5a = audit[
    audit["experiment"] == "Q5"
].copy()

q6a = audit[
    audit["experiment"] == "Q6"
].copy()

compare = q5a.merge(
    q6a,
    on="subject",
    suffixes=("_Q5", "_Q6"),
)

compare["selected_epoch_delta"] = (
    compare["selected_epoch_Q6"]
    - compare["selected_epoch_Q5"]
)

compare["inner_optimum_mean_delta"] = (
    compare["inner_optimum_epoch_mean_Q6"]
    - compare["inner_optimum_epoch_mean_Q5"]
)

compare["near_min_005_span_delta"] = (
    compare["near_min_005_span_Q6"]
    - compare["near_min_005_span_Q5"]
)


# ============================================================
# 5. Add target-performance information for context
# ============================================================

def subject_ba(metrics):
    z = metrics[
        metrics["stratum"] == "all"
    ]

    return (
        z.groupby("subject")[
            "balanced_accuracy"
        ]
        .mean()
    )


q5_ba = subject_ba(
    datasets["Q5"]["metrics"]
)

q6_ba = subject_ba(
    datasets["Q6"]["metrics"]
)

compare["Q5_BA"] = compare[
    "subject"
].map(q5_ba)

compare["Q6_BA"] = compare[
    "subject"
].map(q6_ba)

compare["BA_delta"] = (
    compare["Q6_BA"]
    - compare["Q5_BA"]
)

compare["BA_delta_pp"] = (
    compare["BA_delta"]
    * 100
)


# ============================================================
# 6. Q5 vs Q6 mean-curve distance
# ============================================================

curve_compare_rows = []

for subject in range(1, 10):

    a = mean_curves[
        (mean_curves.experiment == "Q5")
        & (mean_curves.subject == subject)
    ].sort_values("epoch")

    b = mean_curves[
        (mean_curves.experiment == "Q6")
        & (mean_curves.subject == subject)
    ].sort_values("epoch")

    if not np.array_equal(
        a.epoch.to_numpy(),
        b.epoch.to_numpy(),
    ):
        raise AssertionError(
            f"S{subject}: Q5/Q6 epochs differ"
        )

    diff = (
        b.mean_val_ce.to_numpy()
        - a.mean_val_ce.to_numpy()
    )

    curve_compare_rows.append(
        {
            "subject": subject,
            "mean_Q6_minus_Q5_val_ce": float(
                np.mean(diff)
            ),
            "curve_RMSE_Q5_Q6": float(
                np.sqrt(
                    np.mean(
                        diff ** 2
                    )
                )
            ),
            "max_abs_curve_difference": float(
                np.max(
                    np.abs(diff)
                )
            ),
            "epoch_of_max_abs_curve_difference": int(
                a.epoch.to_numpy()[
                    np.argmax(
                        np.abs(diff)
                    )
                ]
            ),
        }
    )

curve_compare = pd.DataFrame(
    curve_compare_rows
)

compare = compare.merge(
    curve_compare,
    on="subject",
    how="left",
)

compare.to_csv(
    OUT
    / "q5_q6_selection_and_performance_comparison.csv",
    index=False,
)


# ============================================================
# 7. Critical-subject diagnostics: S2 / S3 / S8
# ============================================================

critical_rows = []

for subject in [2, 3, 8]:

    for exp in ["Q5", "Q6"]:

        r = audit[
            (audit.experiment == exp)
            & (audit.subject == subject)
        ].iloc[0]

        critical_rows.append(
            {
                "subject": subject,
                "experiment": exp,
                "selected_epoch":
                    int(r.selected_epoch),
                "selected_mean_val_ce":
                    float(
                        r.selected_mean_val_ce
                    ),
                "margin_to_second_best":
                    float(
                        r.margin_to_second_best
                    ),
                "inner_optimum_epochs":
                    ",".join(
                        str(
                            int(
                                r[
                                    f"inner_optimum_epoch_{i}"
                                ]
                            )
                        )
                        for i in range(1, 5)
                    ),
                "inner_optimum_epoch_range":
                    int(
                        r.inner_optimum_epoch_range
                    ),
                "inner_optimum_epoch_std":
                    float(
                        r.inner_optimum_epoch_std
                    ),
                "near_min_001_count":
                    int(
                        r.near_min_001_count
                    ),
                "near_min_005_count":
                    int(
                        r.near_min_005_count
                    ),
                "near_min_005_earliest":
                    int(
                        r.near_min_005_earliest
                    ),
                "near_min_005_latest":
                    int(
                        r.near_min_005_latest
                    ),
                "near_min_005_span":
                    int(
                        r.near_min_005_span
                    ),
                "CE_epoch_1":
                    float(
                        r.mean_val_ce_epoch_1
                    ),
                "CE_epoch_2":
                    float(
                        r.mean_val_ce_epoch_2
                    ),
                "CE_epoch_8":
                    float(
                        r.mean_val_ce_epoch_8
                    ),
                "CE_epoch_16":
                    float(
                        r.mean_val_ce_epoch_16
                    ),
                "CE_epoch_24":
                    float(
                        r.mean_val_ce_epoch_24
                    ),
                "CE_epoch_40":
                    float(
                        r.mean_val_ce_epoch_40
                    ),
                "CE16_minus_selected":
                    float(
                        r.delta_ce_epoch_16_minus_selected
                    ),
                "CE40_minus_selected":
                    float(
                        r.delta_ce_epoch_40_minus_selected
                    ),
            }
        )

critical = pd.DataFrame(
    critical_rows
)

critical.to_csv(
    OUT / "critical_subjects_S2_S3_S8.csv",
    index=False,
)


# ============================================================
# 8. Explicit exploratory associations
# ============================================================

association_rows = []

for subset_name, subset in [
    ("all_S1-S9", compare),
    (
        "excluding_S3",
        compare[
            compare.subject != 3
        ],
    ),
]:

    c = safe_corr(
        subset["selected_epoch_delta"],
        subset["BA_delta"],
    )

    association_rows.append(
        {
            "subset": subset_name,
            "x": "Q6_minus_Q5_selected_epoch",
            "y": "Q6_minus_Q5_BA",
            "n": int(len(subset)),
            **c,
        }
    )

associations = pd.DataFrame(
    association_rows
)

associations.to_csv(
    OUT
    / "selection_delta_vs_performance_associations.csv",
    index=False,
)


# ============================================================
# 9. Descriptive flags — NOT a new decision rule
# ============================================================

flags = audit[
    [
        "experiment",
        "subject",
        "selected_epoch",
        "early_selection_le_2",
        "early_selection_le_5",
        "inner_optimum_epoch_range",
        "inner_optimum_epoch_std",
        "near_min_001_count",
        "near_min_005_count",
        "near_min_005_span",
        "margin_to_second_best",
        "inner_optima_within_selected_pm2",
        "inner_optima_within_selected_pm5",
    ]
].copy()

flags["wide_inner_optimum_range_ge_10"] = (
    flags[
        "inner_optimum_epoch_range"
    ] >= 10
)

flags["flat_minimum_many_epochs_005"] = (
    flags[
        "near_min_005_count"
    ] >= 5
)

flags.to_csv(
    OUT / "descriptive_selection_flags.csv",
    index=False,
)


# ============================================================
# 10. Q7 mechanistic reference
# ============================================================

q7_out = q7.copy()

q7_out.to_csv(
    OUT / "q7_reference_four_cell_summary.csv",
    index=False,
)


# ============================================================
# 11. Generate figures (optional)
# ============================================================

plot_status = {
    "matplotlib_available": False,
    "figures_created": [],
}

try:
    import matplotlib.pyplot as plt

    plot_status[
        "matplotlib_available"
    ] = True

    # One plot per subject, Q5 vs Q6 mean source-validation CE.
    for subject in range(1, 10):

        fig, ax = plt.subplots(
            figsize=(8, 5)
        )

        for exp in ["Q5", "Q6"]:

            z = mean_curves[
                (mean_curves.experiment == exp)
                & (mean_curves.subject == subject)
            ].sort_values("epoch")

            ax.plot(
                z["epoch"],
                z["mean_val_ce"],
                label=exp,
            )

            selected = int(
                z["selected_epoch"].iloc[0]
            )

            selected_val = float(
                z.loc[
                    z.epoch == selected,
                    "mean_val_ce",
                ].iloc[0]
            )

            ax.plot(
                [selected],
                [selected_val],
                marker="o",
                linestyle="None",
            )

        ax.set_xlabel("Epoch")
        ax.set_ylabel(
            "Mean inner-fold validation cross-entropy"
        )
        ax.set_title(
            f"S{subject}: Q5 vs Q6 source-validation trajectory"
        )
        ax.legend()

        fig.tight_layout()

        path = (
            FIG
            / f"S{subject}_Q5_Q6_validation_curves.png"
        )

        fig.savefig(
            path,
            dpi=160,
        )

        plt.close(fig)

        plot_status[
            "figures_created"
        ].append(
            str(path.name)
        )

    # Inner fold details for S2, S3, S8.
    for subject in [2, 3, 8]:

        for exp in ["Q5", "Q6"]:

            lc = datasets[exp][
                "learning"
            ]

            g = lc[
                (lc.stage == "inner")
                & (
                    lc.fold
                    == f"loso_s{subject}"
                )
            ].copy()

            fig, ax = plt.subplots(
                figsize=(8, 5)
            )

            for inner_fold in [
                1,
                2,
                3,
                4,
            ]:

                z = g[
                    g.inner_fold
                    == inner_fold
                ].sort_values("epoch")

                ax.plot(
                    z["epoch"],
                    z["val_ce"],
                    label=(
                        f"inner {inner_fold}"
                    ),
                )

            ax.set_xlabel("Epoch")
            ax.set_ylabel(
                "Validation cross-entropy"
            )
            ax.set_title(
                f"{exp} S{subject}: four source-validation folds"
            )
            ax.legend()

            fig.tight_layout()

            path = (
                FIG
                / f"{exp}_S{subject}_inner_fold_curves.png"
            )

            fig.savefig(
                path,
                dpi=160,
            )

            plt.close(fig)

            plot_status[
                "figures_created"
            ].append(
                str(path.name)
            )

except Exception as exc:

    plot_status[
        "plot_error"
    ] = repr(exc)


with open(
    OUT / "plot_status.json",
    "w",
) as f:
    json.dump(
        plot_status,
        f,
        indent=2,
    )


# ============================================================
# 12. Machine-readable summary
# ============================================================

s3_q5 = audit[
    (audit.experiment == "Q5")
    & (audit.subject == 3)
].iloc[0]

s3_q6 = audit[
    (audit.experiment == "Q6")
    & (audit.subject == 3)
].iloc[0]

summary_json = {
    "analysis_id": "Q8-A001",
    "analysis_type": (
        "source-only epoch-selection stability audit; "
        "no model fitting"
    ),
    "input_experiments": [
        "Q5-E001",
        "Q6-E001",
        "Q7-E001",
    ],
    "subjects": 9,
    "inner_folds_per_subject": 4,
    "epochs_per_inner_fit": 40,
    "primary_question": (
        "How stable is the source-only earliest-minimum "
        "epoch-selection procedure, and why did S3 move "
        "from epoch 2 in Q5 to epoch 16 in Q6?"
    ),
    "s3": {
        "Q5_selected_epoch":
            int(
                s3_q5.selected_epoch
            ),
        "Q6_selected_epoch":
            int(
                s3_q6.selected_epoch
            ),
        "Q5_inner_optimum_epoch_range":
            int(
                s3_q5.inner_optimum_epoch_range
            ),
        "Q6_inner_optimum_epoch_range":
            int(
                s3_q6.inner_optimum_epoch_range
            ),
        "Q5_near_min_005_count":
            int(
                s3_q5.near_min_005_count
            ),
        "Q6_near_min_005_count":
            int(
                s3_q6.near_min_005_count
            ),
        "Q5_CE16_minus_selected":
            float(
                s3_q5.delta_ce_epoch_16_minus_selected
            ),
        "Q6_CE2_minus_selected":
            float(
                s3_q6.mean_val_ce_epoch_2
                - s3_q6.selected_mean_val_ce
            ),
    },
    "interpretation_boundary": (
        "Q8-A001 is post-hoc analysis of source-validation "
        "curves already observed after Q5-Q7. It may identify "
        "selection instability and generate hypotheses, but "
        "it must not be used to retroactively claim a "
        "confirmatory optimal epoch-selection rule."
    ),
}

with open(
    OUT / "analysis_summary.json",
    "w",
) as f:
    json.dump(
        summary_json,
        f,
        indent=2,
    )


# ============================================================
# 13. Generate research report
# ============================================================

lines = []

lines.append(
    "# Q8-A001 — Source-only Epoch-Selection Stability Audit"
)

lines.append("")

lines.append(
    "## Status"
)

lines.append("")

lines.append(
    "**Analysis only. No EEGNet model was trained or refit.**"
)

lines.append("")

lines.append(
    "This audit analyzes the frozen Q5-E001 and Q6-E001 "
    "40-epoch inner source-validation trajectories after "
    "Q7-E001 demonstrated that S3 recovery was primarily "
    "associated with training duration."
)

lines.append("")

lines.append(
    "## Scientific question"
)

lines.append("")

lines.append(
    "How stable is the source-only rule `earliest epoch "
    "minimizing equal-inner-fold mean validation CE`, "
    "particularly for S2, S3 and S8?"
)

lines.append("")

lines.append(
    "## Q5/Q6 selection summary"
)

lines.append("")

lines.append(
    "| Subject | Q5 epoch | Q6 epoch | Delta | Q5 BA | Q6 BA | BA delta pp |"
)

lines.append(
    "|---:|---:|---:|---:|---:|---:|---:|"
)

for _, r in compare.sort_values(
    "subject"
).iterrows():

    lines.append(
        f"| S{int(r.subject)} | "
        f"{int(r.selected_epoch_Q5)} | "
        f"{int(r.selected_epoch_Q6)} | "
        f"{int(r.selected_epoch_delta):+d} | "
        f"{r.Q5_BA:.4f} | "
        f"{r.Q6_BA:.4f} | "
        f"{r.BA_delta_pp:+.2f} |"
    )

lines.append("")

lines.append(
    "## Selection-stability diagnostics"
)

lines.append("")

lines.append(
    "The following quantities are descriptive diagnostics, "
    "not a newly validated model-selection rule."
)

lines.append("")

lines.append(
    "- `inner_optimum_epoch_range`: spread between the earliest "
    "and latest optimum among the four source-validation folds."
)

lines.append(
    "- `near_min_005_count`: number of epochs whose mean "
    "validation CE lies within 0.005 of the global minimum."
)

lines.append(
    "- `margin_to_second_best`: difference between the best "
    "and second-best mean-validation CE."
)

lines.append(
    "- Very early selection, wide fold disagreement, and a "
    "large near-minimum region can indicate a fragile "
    "earliest-minimum decision."
)

lines.append("")

lines.append(
    "## Critical subjects"
)

lines.append("")

lines.append(
    "| Subject | Exp | Selected | Fold optima | Fold range | Near-min ±0.005 count | Near-min latest | CE(16)-selected |"
)

lines.append(
    "|---:|---|---:|---|---:|---:|---:|---:|"
)

for _, r in critical.iterrows():

    lines.append(
        f"| S{int(r.subject)} | "
        f"{r.experiment} | "
        f"{int(r.selected_epoch)} | "
        f"{r.inner_optimum_epochs} | "
        f"{int(r.inner_optimum_epoch_range)} | "
        f"{int(r.near_min_005_count)} | "
        f"{int(r.near_min_005_latest)} | "
        f"{r.CE16_minus_selected:+.6f} |"
    )

lines.append("")

lines.append(
    "## Q7 mechanistic anchor"
)

lines.append("")

lines.append(
    "Q7-E001 reconstructed S3 as:"
)

lines.append("")

lines.append(
    "| Cell | Normalization | Epochs | Mean BA | Entropy | Dominant prediction share |"
)

lines.append(
    "|---|---:|---:|---:|---:|---:|"
)

for _, r in q7.sort_values(
    "condition"
).iterrows():

    lines.append(
        f"| {r.condition} | "
        f"{bool(r.normalization)} | "
        f"{int(r.fixed_epochs)} | "
        f"{r.BA_mean:.4f} | "
        f"{r.entropy_mean:.4f} | "
        f"{r.dominant_share_mean:.4f} |"
    )

lines.append("")

lines.append(
    "Q7 showed that Raw + 16 epochs recovered S3 while "
    "SourceNorm + 2 epochs did not. Therefore the present "
    "audit focuses on the stability of source-only "
    "training-duration selection."
)

lines.append("")

lines.append(
    "## Interpretation boundary"
)

lines.append("")

lines.append(
    "This analysis is post-hoc. Q5, Q6 and Q7 target outcomes "
    "have already been observed. Any new robust selection rule "
    "suggested by these curves must be treated as hypothesis "
    "generation unless it is subsequently frozen and tested on "
    "independent subjects/data."
)

lines.append("")

lines.append(
    "S2 and S8 may be identified as candidates for additional "
    "mechanistic duration experiments if their source-validation "
    "selection is fragile, but their target outcomes must not "
    "be used to tune the duration itself."
)

lines.append("")

lines.append(
    "## Recommended decision process after this audit"
)

lines.append("")

lines.append(
    "1. Determine whether epoch-1/2 selections show fold "
    "disagreement or broad near-minimum plateaus."
)

lines.append(
    "2. Do not immediately invent a new selection rule from "
    "target BA."
)

lines.append(
    "3. If instability is evident, define a source-only robust "
    "selection principle using only source-validation behavior."
)

lines.append(
    "4. Treat any additional S2/S8 duration ablation as "
    "exploratory mechanism testing because their target "
    "performance is already known."
)

lines.append(
    "5. Require later independent/external confirmation before "
    "claiming that a new selection rule generalizes."
)

lines.append(
    "6. Resolve training/model-selection robustness before "
    "using a new spatial-spectral representation, otherwise "
    "training-duration changes could confound Q9."
)

(OUT / "Q8_SELECTION_AUDIT_REPORT.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)


# ============================================================
# 14. Input provenance
# ============================================================

input_hash_rows = []

for path in sorted(
    INPUT.glob("*")
):

    if path.is_file():

        input_hash_rows.append(
            {
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(
                    path
                ),
            }
        )

pd.DataFrame(
    input_hash_rows
).to_csv(
    OUT / "input_file_hashes.csv",
    index=False,
)


# ============================================================
# 15. Console summary
# ============================================================

print()
print("============================================================")
print(" Q8-A001 FINAL SELECTION AUDIT")
print("============================================================")
print()

short_cols = [
    "subject",
    "selected_epoch_Q5",
    "selected_epoch_Q6",
    "selected_epoch_delta",
    "inner_optimum_epoch_range_Q5",
    "inner_optimum_epoch_range_Q6",
    "near_min_005_count_Q5",
    "near_min_005_count_Q6",
    "Q5_BA",
    "Q6_BA",
    "BA_delta_pp",
]

print(
    compare[
        short_cols
    ]
    .sort_values("subject")
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)

print()
print("===== CRITICAL SUBJECTS S2 / S3 / S8 =====")
print()

print(
    critical.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}",
    )
)

print()
print("===== SELECTION DELTA vs PERFORMANCE =====")
print()

print(
    associations.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)

print()
print("===== Q7 MECHANISTIC REFERENCE =====")
print()

print(
    q7[
        [
            "condition",
            "normalization",
            "fixed_epochs",
            "BA_mean",
            "entropy_mean",
            "dominant_share_mean",
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)

print()
print("Analysis completed. NO MODEL TRAINING was performed.")
print()
print("Report:")
print(OUT / "Q8_SELECTION_AUDIT_REPORT.md")
