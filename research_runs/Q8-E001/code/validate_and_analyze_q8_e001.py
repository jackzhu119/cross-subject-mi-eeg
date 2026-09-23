from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scipy.stats import (
    binomtest,
    ttest_rel,
    wilcoxon,
)

from sklearn.metrics import (
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
)

Q5 = Path(
    "/workspace/Q5_EEGNet_Cloud_Ready"
)

Q8 = Path(
    "/workspace/Q8_MeanRank_Selection"
)

R = Q8 / "results/Q8-E001"
OUT = Q8 / "analysis"

OUT.mkdir(
    parents=True,
    exist_ok=True,
)

SEEDS = [
    20260924,
    20260925,
    20260926,
]


def sha256_file(path: Path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            x = f.read(
                1024 * 1024
            )

            if not x:
                break

            h.update(x)

    return h.hexdigest()


def pred_entropy(y):
    counts = np.array(
        [
            np.sum(y == label)
            for label in [
                1,
                2,
                3,
                4,
            ]
        ],
        dtype=float,
    )

    p = counts / counts.sum()

    p = p[
        p > 0
    ]

    return float(
        -np.sum(
            p
            * np.log(p)
        )
        / np.log(4)
    )


def dominant_share(y):
    counts = np.array(
        [
            np.sum(y == label)
            for label in [
                1,
                2,
                3,
                4,
            ]
        ]
    )

    return float(
        counts.max()
        / counts.sum()
    )


# ============================================================
# 1. Validate completion / frozen selection
# ============================================================

status = json.loads(
    (
        R
        / "status.json"
    ).read_text(
        encoding="utf-8"
    )
)

if (
    status.get("status")
    != "complete"
    or status.get(
        "q8_complete"
    )
    is not True
):
    raise AssertionError(
        "Q8 run is incomplete"
    )

if status[
    "completed_final_fits"
] != 27:
    raise AssertionError(
        "Expected 27 final fits"
    )

if status[
    "completed_inner_fits"
] != 0:
    raise AssertionError(
        "Q8 must not retrain Q5 inner fits"
    )

selection = pd.read_csv(
    R
    / "predeclared_selection.csv"
)

provenance = json.loads(
    (
        R
        / "selection_provenance.json"
    ).read_text(
        encoding="utf-8"
    )
)

if (
    sha256_file(
        R
        / "predeclared_selection.csv"
    )
    != provenance[
        "predeclared_selection_sha256"
    ]
):
    raise AssertionError(
        "Selection SHA mismatch"
    )

if (
    selection[
        "target_result_used"
    ].astype(bool).any()
):
    raise AssertionError(
        "Frozen selection declares target use"
    )

if len(selection) != 9:
    raise AssertionError(
        "Expected nine frozen selections"
    )


# ============================================================
# 2. Independently reconstruct mean-rank selections
# ============================================================

q5_lc = pd.read_csv(
    Q5
    / "results/Q5-E001/learning_curves.csv"
)

inner = q5_lc[
    q5_lc.stage == "inner"
].copy()

reconstructed = []

for subject in range(1, 10):

    fold = f"loso_s{subject}"

    g = inner[
        inner.fold == fold
    ]

    pivot = g.pivot(
        index="epoch",
        columns="inner_fold",
        values="val_ce",
    ).sort_index()

    ranks = pivot.rank(
        axis=0,
        method="average",
        ascending=True,
    )

    score = ranks.mean(
        axis=1
    )

    minimum = score.min()

    candidates = [
        int(epoch)
        for epoch, value
        in score.items()
        if np.isclose(
            value,
            minimum,
            atol=1e-12,
            rtol=0,
        )
    ]

    selected = min(
        candidates
    )

    reconstructed.append(
        {
            "fold": fold,
            "subject": subject,
            "selected_epochs":
                selected,
        }
    )

reconstructed = pd.DataFrame(
    reconstructed
)

test = selection[
    [
        "fold",
        "subject",
        "selected_epochs",
    ]
].merge(
    reconstructed,
    on=[
        "fold",
        "subject",
    ],
    suffixes=(
        "_saved",
        "_recomputed",
    ),
)

if not np.array_equal(
    test[
        "selected_epochs_saved"
    ].to_numpy(),
    test[
        "selected_epochs_recomputed"
    ].to_numpy(),
):
    raise AssertionError(
        "Independent mean-rank reconstruction failed"
    )


# ============================================================
# 3. Validate trial identity
# ============================================================

q8_meta = pd.read_csv(
    R / "trial_metadata.csv"
)

q5_meta = pd.read_csv(
    Q5
    / "results/Q5-E001/trial_metadata.csv"
)

if len(q8_meta) != 5184:
    raise AssertionError(
        "Q8 metadata count incorrect"
    )

if len(q5_meta) != len(q8_meta):
    raise AssertionError(
        "Q5/Q8 metadata length differs"
    )

for col in [
    "sample_id",
    "subject",
    "label",
    "artifact_flagged",
]:

    if not np.array_equal(
        q8_meta[
            col
        ].astype(str).to_numpy(),
        q5_meta[
            col
        ].astype(str).to_numpy(),
    ):
        raise AssertionError(
            f"Q5/Q8 metadata mismatch: {col}"
        )


# ============================================================
# 4. Validate predictions and metrics independently
# ============================================================

pred = pd.read_csv(
    R / "predictions.csv"
)

metrics = pd.read_csv(
    R
    / "per_subject_metrics.csv"
)

confusions_saved = pd.read_csv(
    R
    / "confusion_matrices.csv"
)

if len(pred) != (
    9
    * 3
    * 576
):
    raise AssertionError(
        f"Unexpected prediction count: {len(pred)}"
    )

metric_checks = []
collapse_rows = []
class_rows = []

for subject in range(1, 10):

    for seed in SEEDS:

        p = pred[
            (
                pred.subject
                == subject
            )
            &
            (
                pred.seed
                == seed
            )
        ].copy()

        if len(p) != 576:
            raise AssertionError(
                f"S{subject}/{seed}: "
                f"{len(p)} predictions"
            )

        true = p[
            "y_true"
        ].to_numpy()

        guess = p[
            "y_pred"
        ].to_numpy()

        ba = balanced_accuracy_score(
            true,
            guess,
        )

        f1 = f1_score(
            true,
            guess,
            labels=[
                1,
                2,
                3,
                4,
            ],
            average="macro",
        )

        kappa = cohen_kappa_score(
            true,
            guess,
            labels=[
                1,
                2,
                3,
                4,
            ],
        )

        saved = metrics[
            (
                metrics.subject
                == subject
            )
            &
            (
                metrics.seed
                == seed
            )
            &
            (
                metrics.stratum
                == "all"
            )
        ]

        if len(saved) != 1:
            raise AssertionError(
                "Missing metric row"
            )

        saved = saved.iloc[0]

        for name, a, b in [
            (
                "balanced_accuracy",
                ba,
                saved.balanced_accuracy,
            ),
            (
                "macro_f1",
                f1,
                saved.macro_f1,
            ),
            (
                "cohen_kappa",
                kappa,
                saved.cohen_kappa,
            ),
        ]:

            if not np.isclose(
                a,
                b,
                atol=1e-12,
                rtol=0,
            ):
                raise AssertionError(
                    f"S{subject}/{seed}: "
                    f"{name} mismatch"
                )

            metric_checks.append(
                {
                    "subject":
                        subject,
                    "seed":
                        seed,
                    "metric":
                        name,
                    "recomputed":
                        float(a),
                    "saved":
                        float(b),
                }
            )

        cm = confusion_matrix(
            true,
            guess,
            labels=[
                1,
                2,
                3,
                4,
            ],
        )

        z = confusions_saved[
            (
                confusions_saved.subject
                == subject
            )
            &
            (
                confusions_saved.seed
                == seed
            )
            &
            (
                confusions_saved.stratum
                == "all"
            )
        ]

        for i, true_label in enumerate(
            [1, 2, 3, 4]
        ):

            for j, pred_label in enumerate(
                [1, 2, 3, 4]
            ):

                saved_count = int(
                    z.loc[
                        (
                            z.true_label
                            == true_label
                        )
                        &
                        (
                            z.predicted_label
                            == pred_label
                        ),
                        "count",
                    ].iloc[0]
                )

                if (
                    saved_count
                    != int(
                        cm[i, j]
                    )
                ):
                    raise AssertionError(
                        "Confusion cell mismatch"
                    )

        collapse_rows.append(
            {
                "subject":
                    subject,
                "seed":
                    seed,
                "prediction_entropy":
                    pred_entropy(
                        guess
                    ),
                "dominant_prediction_share":
                    dominant_share(
                        guess
                    ),
                "active_predicted_classes":
                    int(
                        len(
                            np.unique(
                                guess
                            )
                        )
                    ),
            }
        )

        for i, label in enumerate(
            [1, 2, 3, 4]
        ):

            total = int(
                cm[i, :].sum()
            )

            class_rows.append(
                {
                    "subject":
                        subject,
                    "seed":
                        seed,
                    "class_id":
                        label,
                    "correct":
                        int(
                            cm[i, i]
                        ),
                    "total":
                        total,
                    "recall":
                        float(
                            cm[i, i]
                            / total
                        ),
                }
            )

pd.DataFrame(
    metric_checks
).to_csv(
    OUT
    / "independent_metric_checks.csv",
    index=False,
)

collapse = pd.DataFrame(
    collapse_rows
)

collapse.to_csv(
    OUT
    / "q8_prediction_collapse.csv",
    index=False,
)

class_df = pd.DataFrame(
    class_rows
)

class_df.to_csv(
    OUT
    / "q8_class_recall.csv",
    index=False,
)


# ============================================================
# 5. Verify fit manifests contain no target training
# ============================================================

manifest = pd.read_csv(
    R / "fit_manifest.csv"
)

if len(manifest) != (
    27
    * 9
):
    raise AssertionError(
        f"Unexpected manifest rows: {len(manifest)}"
    )

for (
    fold,
    seed
), g in manifest.groupby(
    [
        "fold",
        "seed",
    ]
):

    target = int(
        fold.replace(
            "loso_s",
            "",
        )
    )

    target_rows = g[
        g.subject == target
    ]

    if len(target_rows) != 1:
        raise AssertionError(
            "Target manifest row missing"
        )

    if (
        target_rows.iloc[0].role
        != "test"
    ):
        raise AssertionError(
            "Target entered training"
        )

    source = g[
        g.subject != target
    ]

    if not (
        source.role
        == "train"
    ).all():
        raise AssertionError(
            "Unexpected source role"
        )


# ============================================================
# 6. Verify checkpoint hashes
# ============================================================

checkpoint_table = pd.read_csv(
    R / "checkpoint_hashes.csv"
)

if len(
    checkpoint_table
) != 27:
    raise AssertionError(
        "Expected 27 checkpoints"
    )

for _, row in checkpoint_table.iterrows():

    path = Path(
        row.checkpoint
    )

    if not path.exists():
        raise AssertionError(
            f"Missing checkpoint: {path}"
        )

    if (
        sha256_file(
            path
        )
        != row.sha256
    ):
        raise AssertionError(
            f"Checkpoint hash mismatch: {path}"
        )


# ============================================================
# 7. Q5 vs Q8 subject-level comparison
# ============================================================

q5m = pd.read_csv(
    Q5
    / "results/Q5-E001/per_subject_metrics.csv"
)

q8m = metrics

q5all = q5m[
    q5m.stratum == "all"
]

q8all = q8m[
    q8m.stratum == "all"
]

q5_subject = (
    q5all.groupby(
        "subject"
    )
    .agg(
        Q5_BA=(
            "balanced_accuracy",
            "mean",
        ),
        Q5_BA_seed_std=(
            "balanced_accuracy",
            "std",
        ),
        Q5_F1=(
            "macro_f1",
            "mean",
        ),
        Q5_kappa=(
            "cohen_kappa",
            "mean",
        ),
    )
)

q8_subject = (
    q8all.groupby(
        "subject"
    )
    .agg(
        Q8_BA=(
            "balanced_accuracy",
            "mean",
        ),
        Q8_BA_seed_std=(
            "balanced_accuracy",
            "std",
        ),
        Q8_F1=(
            "macro_f1",
            "mean",
        ),
        Q8_kappa=(
            "cohen_kappa",
            "mean",
        ),
    )
)

comparison = q5_subject.join(
    q8_subject
)

comparison[
    "delta_BA"
] = (
    comparison.Q8_BA
    - comparison.Q5_BA
)

comparison[
    "delta_BA_pp"
] = (
    comparison.delta_BA
    * 100
)

comparison[
    "delta_F1"
] = (
    comparison.Q8_F1
    - comparison.Q5_F1
)

comparison[
    "delta_kappa"
] = (
    comparison.Q8_kappa
    - comparison.Q5_kappa
)

frozen = selection.set_index(
    "subject"
)

q5_selection = pd.read_csv(
    Q5
    / "results/Q5-E001/selection.csv"
)

q5_selection[
    "subject"
] = (
    q5_selection.fold
    .str.replace(
        "loso_s",
        "",
        regex=False,
    )
    .astype(int)
)

q5_selection = (
    q5_selection
    .set_index(
        "subject"
    )
)

comparison[
    "Q5_meanCE_epoch"
] = (
    q5_selection[
        "selected_epochs"
    ]
)

comparison[
    "Q8_meanRank_epoch"
] = (
    frozen[
        "selected_epochs"
    ]
)

comparison[
    "epoch_delta"
] = (
    comparison[
        "Q8_meanRank_epoch"
    ]
    - comparison[
        "Q5_meanCE_epoch"
    ]
)

comparison.to_csv(
    OUT
    / "Q5_vs_Q8_subject_comparison.csv"
)


# ============================================================
# 8. Paired inference
# ============================================================

q5v = comparison[
    "Q5_BA"
].to_numpy()

q8v = comparison[
    "Q8_BA"
].to_numpy()

delta = (
    q8v
    - q5v
)

wil = wilcoxon(
    q8v,
    q5v,
    alternative="two-sided",
)

tt = ttest_rel(
    q8v,
    q5v,
)

sign = binomtest(
    int(
        np.sum(
            delta > 0
        )
    ),
    n=len(
        delta
    ),
    p=0.5,
    alternative="two-sided",
)

sd = float(
    np.std(
        delta,
        ddof=1,
    )
)

dz = (
    float(
        np.mean(
            delta
        )
        / sd
    )
    if sd > 0
    else float("nan")
)

rng = np.random.default_rng(
    20260923
)

boot = np.empty(
    20000
)

for i in range(
    len(boot)
):

    boot[i] = np.mean(
        rng.choice(
            delta,
            size=9,
            replace=True,
        )
    )

ci = np.percentile(
    boot,
    [
        2.5,
        97.5,
    ],
)

stats = {
    "n_subjects": 9,
    "Q5_mean_BA":
        float(
            q5v.mean()
        ),
    "Q8_mean_BA":
        float(
            q8v.mean()
        ),
    "mean_delta_pp":
        float(
            delta.mean()
            * 100
        ),
    "median_delta_pp":
        float(
            np.median(
                delta
            )
            * 100
        ),
    "subjects_improved":
        int(
            np.sum(
                delta > 0
            )
        ),
    "subjects_worsened":
        int(
            np.sum(
                delta < 0
            )
        ),
    "wilcoxon_statistic":
        float(
            wil.statistic
        ),
    "wilcoxon_p":
        float(
            wil.pvalue
        ),
    "paired_t_statistic":
        float(
            tt.statistic
        ),
    "paired_t_p":
        float(
            tt.pvalue
        ),
    "sign_test_p":
        float(
            sign.pvalue
        ),
    "paired_cohen_dz":
        dz,
    "bootstrap_mean_delta_95CI_pp":
        [
            float(
                ci[0]
                * 100
            ),
            float(
                ci[1]
                * 100
            ),
        ],
}

(
    OUT
    / "Q5_vs_Q8_paired_statistics.json"
).write_text(
    json.dumps(
        stats,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# 9. Compare prediction collapse against Q5
# ============================================================

q5pred = pd.read_csv(
    Q5
    / "results/Q5-E001/predictions.csv"
)

collapse_compare_rows = []

for exp, frame in [
    (
        "Q5",
        q5pred,
    ),
    (
        "Q8",
        pred,
    ),
]:

    for subject in range(
        1,
        10,
    ):

        for seed in SEEDS:

            z = frame[
                (
                    frame.subject
                    == subject
                )
                &
                (
                    frame.seed
                    == seed
                )
            ]

            guess = z[
                "y_pred"
            ].to_numpy()

            collapse_compare_rows.append(
                {
                    "experiment":
                        exp,
                    "subject":
                        subject,
                    "seed":
                        seed,
                    "entropy":
                        pred_entropy(
                            guess
                        ),
                    "dominant_share":
                        dominant_share(
                            guess
                        ),
                    "active_classes":
                        int(
                            len(
                                np.unique(
                                    guess
                                )
                            )
                        ),
                }
            )

collapse_compare = pd.DataFrame(
    collapse_compare_rows
)

collapse_compare.to_csv(
    OUT
    / "Q5_Q8_prediction_collapse_comparison.csv",
    index=False,
)

collapse_subject = (
    collapse_compare
    .groupby(
        [
            "experiment",
            "subject",
        ],
        as_index=False,
    )
    .agg(
        entropy_mean=(
            "entropy",
            "mean",
        ),
        dominant_share_mean=(
            "dominant_share",
            "mean",
        ),
        active_classes_mean=(
            "active_classes",
            "mean",
        ),
    )
)

collapse_subject.to_csv(
    OUT
    / "Q5_Q8_prediction_collapse_subject_means.csv",
    index=False,
)


# ============================================================
# 10. Independent validation report
# ============================================================

validation_report = {
    "status": "passed",
    "experiment_id": "Q8-E001",
    "parent_experiment": "Q5-E001",
    "selection_rule": "mean_rank",
    "selection_recomputed_independently": True,
    "selection_file_sha_verified": True,
    "inner_fits_retrained": False,
    "reused_inner_curve_experiment": "Q5-E001",
    "n_subjects": 9,
    "n_final_fits": 27,
    "n_predictions": int(
        len(
            pred
        )
    ),
    "n_metric_scalar_checks": int(
        len(
            metric_checks
        )
    ),
    "n_checkpoint_hashes_verified": int(
        len(
            checkpoint_table
        )
    ),
    "q5_trial_identity_match": True,
    "target_training_leakage_detected": False,
    "target_derived_normalization": False,
    "interpretation_boundary": (
        "Q8-E001 freezes mean-rank selection before its new final-model "
        "evaluation, but the rule itself was motivated after exploratory "
        "analyses on BNCI2014_001. Nine subjects, not 27 seed fits, are "
        "the units for subject-level inference. This is not independent "
        "external confirmation."
    ),
}

(
    OUT
    / "validation_report.json"
).write_text(
    json.dumps(
        validation_report,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# 11. Research report
# ============================================================

lines = []

lines.append(
    "# Q8-E001 — Mean-Rank Source-Only Model Selection"
)

lines.append("")

lines.append(
    "## Experiment"
)

lines.append("")

lines.append(
    "Q8-E001 is a single-factor follow-up to Q5-E001."
)

lines.append("")

lines.append(
    "All Q5 data, preprocessing, EEGNet architecture, optimization, "
    "LOSO folds, source subjects and final seeds were preserved."
)

lines.append("")

lines.append(
    "The only methodological change was the source-only epoch-selection rule."
)

lines.append("")

lines.append(
    "- Q5: earliest epoch minimizing mean validation CE."
)

lines.append(
    "- Q8-E001: rank epochs independently inside each of four "
    "source-validation folds, average the four ranks, then choose "
    "the earliest epoch with minimum mean rank."
)

lines.append("")

lines.append(
    "The 36 Q5 inner fits were not retrained. Their frozen 40-epoch "
    "validation trajectories were reused."
)

lines.append("")

lines.append(
    "## Frozen selections"
)

lines.append("")

lines.append(
    "| Subject | Q5 mean-CE epoch | Q8 mean-rank epoch | Delta |"
)

lines.append(
    "|---:|---:|---:|---:|"
)

for subject, row in comparison.iterrows():

    lines.append(
        f"| S{subject} | "
        f"{int(row.Q5_meanCE_epoch)} | "
        f"{int(row.Q8_meanRank_epoch)} | "
        f"{int(row.epoch_delta):+d} |"
    )

lines.append("")

lines.append(
    "## Subject-level performance"
)

lines.append("")

lines.append(
    "| Subject | Q5 BA | Q8 BA | Delta pp |"
)

lines.append(
    "|---:|---:|---:|---:|"
)

for subject, row in comparison.iterrows():

    lines.append(
        f"| S{subject} | "
        f"{row.Q5_BA:.4f} | "
        f"{row.Q8_BA:.4f} | "
        f"{row.delta_BA_pp:+.2f} |"
    )

lines.append("")

lines.append(
    "## Aggregate paired results"
)

lines.append("")

lines.append(
    f"- Q5 mean BA: **{stats['Q5_mean_BA']:.4f}**"
)

lines.append(
    f"- Q8 mean BA: **{stats['Q8_mean_BA']:.4f}**"
)

lines.append(
    f"- Mean difference: **{stats['mean_delta_pp']:+.2f} pp**"
)

lines.append(
    f"- Median difference: **{stats['median_delta_pp']:+.2f} pp**"
)

lines.append(
    f"- Improved subjects: **{stats['subjects_improved']}/9**"
)

lines.append(
    f"- Worsened subjects: **{stats['subjects_worsened']}/9**"
)

lines.append(
    f"- Wilcoxon p: **{stats['wilcoxon_p']:.6f}**"
)

lines.append(
    f"- Paired t-test p: **{stats['paired_t_p']:.6f}**"
)

lines.append(
    f"- Sign-test p: **{stats['sign_test_p']:.6f}**"
)

lines.append(
    f"- Paired Cohen dz: **{stats['paired_cohen_dz']:.4f}**"
)

lines.append(
    "- Bootstrap 95% CI for mean difference: "
    f"**[{stats['bootstrap_mean_delta_95CI_pp'][0]:+.2f}, "
    f"{stats['bootstrap_mean_delta_95CI_pp'][1]:+.2f}] pp**"
)

lines.append("")

lines.append(
    "## Interpretation boundary"
)

lines.append("")

lines.append(
    "Q8-E001 must not be described as independent confirmation. "
    "The mean-rank candidate was motivated by prior exploratory "
    "analysis of the same BNCI2014_001 research program."
)

lines.append("")

lines.append(
    "However, the Q8-E001 final models were trained only after the "
    "mean-rank selections had been frozen from source-validation "
    "curves, with no target-derived fitting or epoch adjustment."
)

lines.append("")

lines.append(
    "Nine held-out subjects are the subject-level inference units. "
    "The 27 final seed fits are repeated fits, not 27 independent subjects."
)

(
    OUT
    / "Q8_E001_FINAL_REPORT.md"
).write_text(
    "\n".join(
        lines
    )
    + "\n",
    encoding="utf-8",
)


# ============================================================
# 12. Terminal summary
# ============================================================

print()
print("============================================================")
print(" Q8-E001 FINAL RESULTS")
print("============================================================")
print()

print(
    comparison[
        [
            "Q5_meanCE_epoch",
            "Q8_meanRank_epoch",
            "epoch_delta",
            "Q5_BA",
            "Q8_BA",
            "delta_BA_pp",
        ]
    ].to_string(
        float_format=lambda x: f"{x:.4f}",
    )
)

print()
print("===== PAIRED SUBJECT STATISTICS =====")
print()

print(
    json.dumps(
        stats,
        indent=2,
    )
)

print()
print("===== VALIDATION =====")
print()

print(
    json.dumps(
        validation_report,
        indent=2,
    )
)

print()
print("Q8-E001 VALIDATION PASSED")
