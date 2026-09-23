from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

Q5 = Path("/workspace/Q5_EEGNet_Cloud_Ready")
A002 = Q5 / "research_runs/Q8-A002"
A003 = Q5 / "research_runs/Q8-A003"

O2 = A002 / "analysis"
O3 = A003 / "analysis"

F2 = A002 / "figures"
F3 = A003 / "figures"

O2.mkdir(parents=True, exist_ok=True)
O3.mkdir(parents=True, exist_ok=True)
F2.mkdir(parents=True, exist_ok=True)
F3.mkdir(parents=True, exist_ok=True)


# ============================================================
# UTILITIES
# ============================================================

ALL_SUBJECTS = list(range(1, 10))


def load_experiment(exp: str):
    root = (
        Q5 / "results/Q5-E001"
        if exp == "Q5"
        else Path(
            "/workspace/Q6_EEGNet_SourceNorm/results/Q6-E001"
        )
    )

    lc = pd.read_csv(
        root / "learning_curves.csv"
    )

    sel = pd.read_csv(
        root / "selection.csv"
    )

    lc = lc[
        lc["stage"] == "inner"
    ].copy()

    return lc, sel


def validation_pairs(target: int):
    source = [
        s for s in ALL_SUBJECTS
        if s != target
    ]

    assert len(source) == 8

    return {
        1: source[0:2],
        2: source[2:4],
        3: source[4:6],
        4: source[6:8],
    }


def earliest_argmin(series: pd.Series):
    minimum = series.min()

    candidates = (
        series[
            np.isclose(
                series,
                minimum,
                atol=1e-12,
                rtol=0,
            )
        ]
        .index
        .astype(int)
        .tolist()
    )

    return min(candidates)


def trimmed_mean(values):
    arr = np.sort(
        np.asarray(
            values,
            dtype=float,
        )
    )

    if len(arr) <= 2:
        return float(
            np.mean(arr)
        )

    return float(
        np.mean(
            arr[1:-1]
        )
    )


def aggregate_rule(
    matrix: pd.DataFrame,
    rule: str,
):
    """
    matrix:
      index = epoch
      columns = validation folds
      values = validation CE
    """

    if rule == "mean_ce":

        score = matrix.mean(axis=1)

    elif rule == "median_ce":

        score = matrix.median(axis=1)

    elif rule == "trimmed_mean_ce":

        score = matrix.apply(
            trimmed_mean,
            axis=1,
        )

    elif rule == "worst_fold_ce":

        score = matrix.max(axis=1)

    elif rule == "mean_rank":

        ranks = matrix.rank(
            axis=0,
            method="average",
            ascending=True,
        )

        score = ranks.mean(axis=1)

    elif rule == "median_rank":

        ranks = matrix.rank(
            axis=0,
            method="average",
            ascending=True,
        )

        score = ranks.median(axis=1)

    else:
        raise ValueError(
            f"Unknown rule: {rule}"
        )

    selected = earliest_argmin(
        score
    )

    return selected, score


RULES = [
    "mean_ce",
    "median_ce",
    "trimmed_mean_ce",
    "worst_fold_ce",
    "mean_rank",
    "median_rank",
]


# ============================================================
# STRUCTURAL CHECKS
# ============================================================

DATA = {}

for exp in ["Q5", "Q6"]:

    lc, sel = load_experiment(
        exp
    )

    DATA[exp] = {
        "lc": lc,
        "selection": sel,
    }

    for subject in ALL_SUBJECTS:

        fold = f"loso_s{subject}"

        g = lc[
            lc.fold == fold
        ]

        if len(g) != 160:
            raise AssertionError(
                f"{exp} S{subject}: "
                f"expected 160 inner rows, got {len(g)}"
            )

        for inner in [1, 2, 3, 4]:

            z = g[
                g.inner_fold == inner
            ]

            if z.epoch.astype(int).tolist() != list(
                range(1, 41)
            ):
                raise AssertionError(
                    f"{exp} S{subject} inner {inner}: "
                    "epochs != 1..40"
                )

print("Input structural checks: PASSED")


# ============================================================
# Q8-A002
# LEAVE-ONE-INNER-FOLD-OUT INFLUENCE
# ============================================================

loifo_rows = []
summary_rows = []
fold_subject_rows = []

for exp in ["Q5", "Q6"]:

    lc = DATA[exp]["lc"]
    selection = DATA[exp][
        "selection"
    ]

    for subject in ALL_SUBJECTS:

        fold = f"loso_s{subject}"

        pairs = validation_pairs(
            subject
        )

        g = lc[
            lc.fold == fold
        ].copy()

        pivot = g.pivot(
            index="epoch",
            columns="inner_fold",
            values="val_ce",
        ).sort_index()

        pivot.columns = [
            int(x)
            for x in pivot.columns
        ]

        full_mean = pivot.mean(
            axis=1
        )

        original_selected = int(
            selection.loc[
                selection.fold == fold,
                "selected_epochs",
            ].iloc[0]
        )

        recomputed = earliest_argmin(
            full_mean
        )

        if recomputed != original_selected:
            raise AssertionError(
                f"{exp} {fold}: "
                f"recomputed={recomputed}, "
                f"saved={original_selected}"
            )

        omitted_results = []

        for omitted_fold in [
            1,
            2,
            3,
            4,
        ]:

            remaining = [
                c
                for c in [1, 2, 3, 4]
                if c != omitted_fold
            ]

            reduced_mean = pivot[
                remaining
            ].mean(axis=1)

            selected = earliest_argmin(
                reduced_mean
            )

            shift = (
                selected
                - original_selected
            )

            omitted_subjects = pairs[
                omitted_fold
            ]

            row = {
                "experiment": exp,
                "target_subject": subject,
                "original_selected_epoch":
                    original_selected,
                "omitted_inner_fold":
                    omitted_fold,
                "omitted_validation_subject_1":
                    omitted_subjects[0],
                "omitted_validation_subject_2":
                    omitted_subjects[1],
                "omitted_validation_pair":
                    (
                        f"S{omitted_subjects[0]}"
                        f"+S{omitted_subjects[1]}"
                    ),
                "selected_epoch_after_omission":
                    selected,
                "epoch_shift":
                    shift,
                "absolute_epoch_shift":
                    abs(shift),
                "selected_score_after_omission":
                    float(
                        reduced_mean.loc[
                            selected
                        ]
                    ),
                "original_epoch_score_after_omission":
                    float(
                        reduced_mean.loc[
                            original_selected
                        ]
                    ),
            }

            loifo_rows.append(
                row
            )

            omitted_results.append(
                row
            )

        temp = pd.DataFrame(
            omitted_results
        )

        max_row = temp.loc[
            temp.absolute_epoch_shift.idxmax()
        ]

        unique_epochs = sorted(
            temp[
                "selected_epoch_after_omission"
            ].unique()
        )

        summary_rows.append(
            {
                "experiment": exp,
                "target_subject":
                    subject,
                "original_selected_epoch":
                    original_selected,
                "min_LOIFO_epoch":
                    int(
                        temp[
                            "selected_epoch_after_omission"
                        ].min()
                    ),
                "max_LOIFO_epoch":
                    int(
                        temp[
                            "selected_epoch_after_omission"
                        ].max()
                    ),
                "LOIFO_epoch_range":
                    int(
                        temp[
                            "selected_epoch_after_omission"
                        ].max()
                        - temp[
                            "selected_epoch_after_omission"
                        ].min()
                    ),
                "mean_absolute_shift":
                    float(
                        temp[
                            "absolute_epoch_shift"
                        ].mean()
                    ),
                "max_absolute_shift":
                    int(
                        temp[
                            "absolute_epoch_shift"
                        ].max()
                    ),
                "n_unique_LOIFO_selections":
                    int(
                        len(
                            unique_epochs
                        )
                    ),
                "LOIFO_selected_epochs":
                    ",".join(
                        map(
                            str,
                            unique_epochs,
                        )
                    ),
                "most_influential_omitted_fold":
                    int(
                        max_row[
                            "omitted_inner_fold"
                        ]
                    ),
                "most_influential_validation_pair":
                    str(
                        max_row[
                            "omitted_validation_pair"
                        ]
                    ),
                "most_influential_shift":
                    int(
                        max_row[
                            "epoch_shift"
                        ]
                    ),
            }
        )

        for inner_fold, pair in pairs.items():

            fold_subject_rows.append(
                {
                    "experiment": exp,
                    "target_subject":
                        subject,
                    "inner_fold":
                        inner_fold,
                    "validation_subject_1":
                        pair[0],
                    "validation_subject_2":
                        pair[1],
                    "validation_pair":
                        f"S{pair[0]}+S{pair[1]}",
                }
            )


loifo = pd.DataFrame(
    loifo_rows
)

influence_summary = pd.DataFrame(
    summary_rows
)

fold_subject_map = pd.DataFrame(
    fold_subject_rows
)

loifo.to_csv(
    O2
    / "leave_one_inner_fold_out_results.csv",
    index=False,
)

influence_summary.to_csv(
    O2
    / "inner_fold_influence_summary.csv",
    index=False,
)

fold_subject_map.to_csv(
    O2
    / "inner_fold_validation_subject_map.csv",
    index=False,
)


# ============================================================
# IDENTIFY HIGH-INFLUENCE CASES
# purely source-validation based
# ============================================================

high_influence = influence_summary[
    (
        influence_summary[
            "max_absolute_shift"
        ] >= 5
    )
    |
    (
        influence_summary[
            "LOIFO_epoch_range"
        ] >= 10
    )
].copy()

high_influence.to_csv(
    O2
    / "high_influence_cases.csv",
    index=False,
)


# ============================================================
# SPECIFIC S2/S3/S8 REPORT
# ============================================================

critical = loifo[
    loifo[
        "target_subject"
    ].isin(
        [2, 3, 8]
    )
].copy()

critical.to_csv(
    O2
    / "critical_S2_S3_S8_LOIFO.csv",
    index=False,
)


# ============================================================
# Q8-A003
# SOURCE-ONLY AGGREGATION RULE SENSITIVITY
# ============================================================

rule_rows = []
rule_loo_rows = []

for exp in ["Q5", "Q6"]:

    lc = DATA[exp]["lc"]

    for subject in ALL_SUBJECTS:

        fold = f"loso_s{subject}"

        g = lc[
            lc.fold == fold
        ].copy()

        pivot = g.pivot(
            index="epoch",
            columns="inner_fold",
            values="val_ce",
        ).sort_index()

        pivot.columns = [
            int(x)
            for x in pivot.columns
        ]

        for rule in RULES:

            selected, score = (
                aggregate_rule(
                    pivot,
                    rule,
                )
            )

            loo_selected = []

            for omitted in [
                1,
                2,
                3,
                4,
            ]:

                reduced = pivot[
                    [
                        c
                        for c in [
                            1,
                            2,
                            3,
                            4,
                        ]
                        if c != omitted
                    ]
                ]

                loo_epoch, loo_score = (
                    aggregate_rule(
                        reduced,
                        rule,
                    )
                )

                loo_selected.append(
                    loo_epoch
                )

                pair = validation_pairs(
                    subject
                )[omitted]

                rule_loo_rows.append(
                    {
                        "experiment":
                            exp,
                        "target_subject":
                            subject,
                        "rule":
                            rule,
                        "full_selected_epoch":
                            selected,
                        "omitted_inner_fold":
                            omitted,
                        "omitted_validation_pair":
                            (
                                f"S{pair[0]}"
                                f"+S{pair[1]}"
                            ),
                        "LOIFO_selected_epoch":
                            loo_epoch,
                        "epoch_shift":
                            (
                                loo_epoch
                                - selected
                            ),
                        "absolute_epoch_shift":
                            abs(
                                loo_epoch
                                - selected
                            ),
                    }
                )

            loo_selected = np.asarray(
                loo_selected,
                dtype=int,
            )

            rule_rows.append(
                {
                    "experiment":
                        exp,
                    "target_subject":
                        subject,
                    "rule":
                        rule,
                    "selected_epoch":
                        selected,
                    "selected_source_score":
                        float(
                            score.loc[
                                selected
                            ]
                        ),
                    "LOIFO_min_epoch":
                        int(
                            loo_selected.min()
                        ),
                    "LOIFO_max_epoch":
                        int(
                            loo_selected.max()
                        ),
                    "LOIFO_epoch_range":
                        int(
                            loo_selected.max()
                            - loo_selected.min()
                        ),
                    "LOIFO_mean_absolute_shift":
                        float(
                            np.mean(
                                np.abs(
                                    loo_selected
                                    - selected
                                )
                            )
                        ),
                    "LOIFO_max_absolute_shift":
                        int(
                            np.max(
                                np.abs(
                                    loo_selected
                                    - selected
                                )
                            )
                        ),
                    "LOIFO_n_unique":
                        int(
                            len(
                                np.unique(
                                    loo_selected
                                )
                            )
                        ),
                }
            )


rule_selection = pd.DataFrame(
    rule_rows
)

rule_loifo = pd.DataFrame(
    rule_loo_rows
)

rule_selection.to_csv(
    O3
    / "candidate_rule_subject_selections.csv",
    index=False,
)

rule_loifo.to_csv(
    O3
    / "candidate_rule_LOIFO_results.csv",
    index=False,
)


# ============================================================
# GLOBAL RULE STABILITY SUMMARY
# no target performance used
# ============================================================

rule_stability = (
    rule_selection
    .groupby(
        [
            "experiment",
            "rule",
        ],
        as_index=False,
    )
    .agg(
        mean_selected_epoch=(
            "selected_epoch",
            "mean",
        ),
        median_selected_epoch=(
            "selected_epoch",
            "median",
        ),
        mean_LOIFO_epoch_range=(
            "LOIFO_epoch_range",
            "mean",
        ),
        median_LOIFO_epoch_range=(
            "LOIFO_epoch_range",
            "median",
        ),
        mean_LOIFO_absolute_shift=(
            "LOIFO_mean_absolute_shift",
            "mean",
        ),
        max_LOIFO_absolute_shift=(
            "LOIFO_max_absolute_shift",
            "max",
        ),
        mean_LOIFO_unique_selections=(
            "LOIFO_n_unique",
            "mean",
        ),
    )
)

rule_stability.to_csv(
    O3
    / "candidate_rule_stability_summary.csv",
    index=False,
)


# ============================================================
# Q5 vs Q6 RULE CONSISTENCY
# still source-only
# ============================================================

q5rules = rule_selection[
    rule_selection.experiment
    == "Q5"
][
    [
        "target_subject",
        "rule",
        "selected_epoch",
    ]
].rename(
    columns={
        "selected_epoch":
            "Q5_selected_epoch"
    }
)

q6rules = rule_selection[
    rule_selection.experiment
    == "Q6"
][
    [
        "target_subject",
        "rule",
        "selected_epoch",
    ]
].rename(
    columns={
        "selected_epoch":
            "Q6_selected_epoch"
    }
)

rule_consistency = q5rules.merge(
    q6rules,
    on=[
        "target_subject",
        "rule",
    ],
)

rule_consistency[
    "Q6_minus_Q5_epoch"
] = (
    rule_consistency[
        "Q6_selected_epoch"
    ]
    - rule_consistency[
        "Q5_selected_epoch"
    ]
)

rule_consistency[
    "absolute_Q5_Q6_epoch_difference"
] = np.abs(
    rule_consistency[
        "Q6_minus_Q5_epoch"
    ]
)

rule_consistency.to_csv(
    O3
    / "Q5_Q6_rule_consistency_by_subject.csv",
    index=False,
)

cross_exp_summary = (
    rule_consistency
    .groupby(
        "rule",
        as_index=False,
    )
    .agg(
        mean_absolute_Q5_Q6_difference=(
            "absolute_Q5_Q6_epoch_difference",
            "mean",
        ),
        median_absolute_Q5_Q6_difference=(
            "absolute_Q5_Q6_epoch_difference",
            "median",
        ),
        max_absolute_Q5_Q6_difference=(
            "absolute_Q5_Q6_epoch_difference",
            "max",
        ),
        subjects_same_epoch=(
            "absolute_Q5_Q6_epoch_difference",
            lambda s:
                int(
                    np.sum(
                        s == 0
                    )
                ),
        ),
    )
)

cross_exp_summary.to_csv(
    O3
    / "candidate_rule_cross_experiment_stability.csv",
    index=False,
)


# ============================================================
# RULE DEFINITIONS
# ============================================================

definitions = {
    "analysis_id":
        "Q8-A003",
    "status":
        "analysis_only",
    "target_performance_used_to_choose_rule":
        False,
    "rules": {
        "mean_ce":
            (
                "Current Q5/Q6 rule: "
                "minimum mean validation CE "
                "across four source-validation folds."
            ),
        "median_ce":
            (
                "Minimum median validation CE "
                "across folds."
            ),
        "trimmed_mean_ce":
            (
                "At each epoch remove highest "
                "and lowest fold CE and average "
                "the middle values."
            ),
        "worst_fold_ce":
            (
                "Minimize the largest validation "
                "CE across folds (minimax)."
            ),
        "mean_rank":
            (
                "Rank epochs separately within "
                "each fold and minimize mean rank."
            ),
        "median_rank":
            (
                "Rank epochs separately within "
                "each fold and minimize median rank."
            ),
    },
    "interpretation_boundary":
        (
            "These are retrospective source-only "
            "sensitivity analyses. A future rule "
            "must be frozen before new target "
            "evaluation. Target BA must not be used "
            "to select among these rules."
        ),
}

(
    O3
    / "candidate_rule_definitions.json"
).write_text(
    json.dumps(
        definitions,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# FIGURES
# ============================================================

plot_status = {
    "status": "not_attempted",
    "files": [],
}

try:

    import matplotlib.pyplot as plt

    plot_status["status"] = "ok"

    # ----------------------------------------
    # A002: critical subject omission effects
    # ----------------------------------------

    for exp in ["Q5", "Q6"]:

        for subject in [
            2,
            3,
            8,
        ]:

            z = loifo[
                (
                    loifo.experiment
                    == exp
                )
                &
                (
                    loifo.target_subject
                    == subject
                )
            ].sort_values(
                "omitted_inner_fold"
            )

            fig, ax = plt.subplots(
                figsize=(8, 5)
            )

            labels = z[
                "omitted_validation_pair"
            ].tolist()

            values = z[
                "selected_epoch_after_omission"
            ].to_numpy()

            x = np.arange(
                len(values)
            )

            ax.bar(
                x,
                values,
            )

            original = int(
                z[
                    "original_selected_epoch"
                ].iloc[0]
            )

            ax.axhline(
                original,
                linestyle="--",
                label=(
                    f"full 4-fold = "
                    f"{original}"
                ),
            )

            ax.set_xticks(
                x
            )

            ax.set_xticklabels(
                labels,
                rotation=30,
            )

            ax.set_ylabel(
                "Selected epoch"
            )

            ax.set_title(
                f"{exp} S{subject}: "
                "leave-one-validation-pair-out"
            )

            ax.legend()

            fig.tight_layout()

            path = (
                F2
                / (
                    f"{exp}_S{subject}"
                    "_LOIFO_selected_epoch.png"
                )
            )

            fig.savefig(
                path,
                dpi=160,
            )

            plt.close(fig)

            plot_status[
                "files"
            ].append(
                str(path)
            )

    # ----------------------------------------
    # A003: rule selections across subjects
    # ----------------------------------------

    for exp in ["Q5", "Q6"]:

        fig, ax = plt.subplots(
            figsize=(10, 6)
        )

        z = rule_selection[
            rule_selection.experiment
            == exp
        ]

        for rule in RULES:

            r = z[
                z.rule == rule
            ].sort_values(
                "target_subject"
            )

            ax.plot(
                r.target_subject,
                r.selected_epoch,
                marker="o",
                label=rule,
            )

        ax.set_xlabel(
            "Held-out subject"
        )

        ax.set_ylabel(
            "Selected epoch"
        )

        ax.set_xticks(
            ALL_SUBJECTS
        )

        ax.set_title(
            f"{exp}: source-only "
            "candidate selection rules"
        )

        ax.legend()

        fig.tight_layout()

        path = (
            F3
            / (
                f"{exp}_candidate_"
                "rule_selected_epochs.png"
            )
        )

        fig.savefig(
            path,
            dpi=160,
        )

        plt.close(fig)

        plot_status[
            "files"
        ].append(
            str(path)
        )

except Exception as exc:

    plot_status[
        "status"
    ] = "failed"

    plot_status[
        "error"
    ] = repr(exc)


(
    O3
    / "plot_status.json"
).write_text(
    json.dumps(
        plot_status,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# A002 REPORT
# ============================================================

lines = []

lines.append(
    "# Q8-A002 — Inner-Fold Influence Audit"
)

lines.append("")

lines.append(
    "**Analysis only. No model training.**"
)

lines.append("")

lines.append(
    "## Purpose"
)

lines.append("")

lines.append(
    "Determine whether a particular pair of "
    "source-validation subjects dominates the "
    "source-only selected training duration."
)

lines.append("")

lines.append(
    "For each Q5/Q6 LOSO fold, the analysis "
    "removes one of the four validation pairs "
    "at a time and recomputes the earliest epoch "
    "minimizing mean validation cross-entropy "
    "across the remaining three folds."
)

lines.append("")

lines.append(
    "## Validation-pair mapping"
)

lines.append("")

lines.append(
    "For each held-out target, the remaining "
    "eight source subjects are sorted and divided "
    "into four consecutive pairs, matching the "
    "Q5/Q6 protocol."
)

lines.append("")

lines.append(
    "## Per-subject influence summary"
)

lines.append("")

lines.append(
    "| Exp | Target | Original | "
    "LOIFO range | Mean abs shift | "
    "Max abs shift | Most influential pair | Shift |"
)

lines.append(
    "|---|---:|---:|---:|---:|---:|---|---:|"
)

for _, r in influence_summary.iterrows():

    lines.append(
        f"| {r.experiment} | "
        f"S{int(r.target_subject)} | "
        f"{int(r.original_selected_epoch)} | "
        f"{int(r.LOIFO_epoch_range)} | "
        f"{r.mean_absolute_shift:.2f} | "
        f"{int(r.max_absolute_shift)} | "
        f"{r.most_influential_validation_pair} | "
        f"{int(r.most_influential_shift):+d} |"
    )

lines.append("")

lines.append(
    "## Critical S2/S3/S8 leave-one-pair results"
)

lines.append("")

lines.append(
    "| Exp | Target | Omitted pair | "
    "Original | New epoch | Shift |"
)

lines.append(
    "|---|---:|---|---:|---:|---:|"
)

for _, r in critical.iterrows():

    lines.append(
        f"| {r.experiment} | "
        f"S{int(r.target_subject)} | "
        f"{r.omitted_validation_pair} | "
        f"{int(r.original_selected_epoch)} | "
        f"{int(r.selected_epoch_after_omission)} | "
        f"{int(r.epoch_shift):+d} |"
    )

lines.append("")

lines.append(
    "## Interpretation boundary"
)

lines.append("")

lines.append(
    "This analysis uses only source-validation "
    "losses. It diagnoses sensitivity of the "
    "existing model-selection procedure."
)

lines.append("")

lines.append(
    "Target balanced accuracy must not be used "
    "to decide which source-validation pair "
    "should be ignored."
)

(
    O2
    / "Q8_A002_INNER_FOLD_INFLUENCE_REPORT.md"
).write_text(
    "\n".join(
        lines
    )
    + "\n",
    encoding="utf-8",
)


# ============================================================
# A003 REPORT
# ============================================================

lines = []

lines.append(
    "# Q8-A003 — Source-only Selection Rule Sensitivity"
)

lines.append("")

lines.append(
    "**Analysis only. No model training.**"
)

lines.append("")

lines.append(
    "## Purpose"
)

lines.append("")

lines.append(
    "Compare several source-only aggregation "
    "rules for stability to source-validation "
    "fold composition."
)

lines.append("")

lines.append(
    "No rule is selected using held-out target "
    "performance."
)

lines.append("")

lines.append(
    "## Rules"
)

lines.append("")

for rule in RULES:

    lines.append(
        f"- `{rule}`"
    )

lines.append("")

lines.append(
    "## Leave-one-inner-fold-out stability"
)

lines.append("")

lines.append(
    "| Exp | Rule | Mean epoch range | "
    "Mean abs shift | Max abs shift |"
)

lines.append(
    "|---|---|---:|---:|---:|"
)

for _, r in rule_stability.iterrows():

    lines.append(
        f"| {r.experiment} | "
        f"{r.rule} | "
        f"{r.mean_LOIFO_epoch_range:.2f} | "
        f"{r.mean_LOIFO_absolute_shift:.2f} | "
        f"{int(r.max_LOIFO_absolute_shift)} |"
    )

lines.append("")

lines.append(
    "## Q5 versus Q6 consistency"
)

lines.append("")

lines.append(
    "| Rule | Mean abs epoch difference | "
    "Median | Max | Same epoch subjects |"
)

lines.append(
    "|---|---:|---:|---:|---:|"
)

for _, r in cross_exp_summary.iterrows():

    lines.append(
        f"| {r.rule} | "
        f"{r.mean_absolute_Q5_Q6_difference:.2f} | "
        f"{r.median_absolute_Q5_Q6_difference:.2f} | "
        f"{int(r.max_absolute_Q5_Q6_difference)} | "
        f"{int(r.subjects_same_epoch)}/9 |"
    )

lines.append("")

lines.append(
    "## Methodological boundary"
)

lines.append("")

lines.append(
    "These comparisons are retrospective "
    "sensitivity analyses. They may identify "
    "candidate families for a future frozen "
    "source-only selection rule."
)

lines.append("")

lines.append(
    "They do not justify choosing whichever rule "
    "would have produced the best already-known "
    "target performance."
)

(
    O3
    / "Q8_A003_RULE_SENSITIVITY_REPORT.md"
).write_text(
    "\n".join(
        lines
    )
    + "\n",
    encoding="utf-8",
)


# ============================================================
# CONSOLE SUMMARY
# ============================================================

print()
print(
    "============================================================"
)
print(
    " Q8-A002 FINAL INNER-FOLD INFLUENCE"
)
print(
    "============================================================"
)
print()

print(
    influence_summary[
        [
            "experiment",
            "target_subject",
            "original_selected_epoch",
            "LOIFO_epoch_range",
            "mean_absolute_shift",
            "max_absolute_shift",
            "most_influential_validation_pair",
            "most_influential_shift",
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.2f}",
    )
)

print()
print(
    "===== CRITICAL S2 / S3 / S8 ====="
)
print()

print(
    critical[
        [
            "experiment",
            "target_subject",
            "omitted_validation_pair",
            "original_selected_epoch",
            "selected_epoch_after_omission",
            "epoch_shift",
        ]
    ].to_string(
        index=False,
    )
)

print()
print(
    "============================================================"
)
print(
    " Q8-A003 SOURCE-ONLY RULE STABILITY"
)
print(
    "============================================================"
)
print()

print(
    rule_stability.to_string(
        index=False,
        float_format=lambda x: f"{x:.2f}",
    )
)

print()
print(
    "===== Q5 vs Q6 RULE CONSISTENCY ====="
)
print()

print(
    cross_exp_summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.2f}",
    )
)

print()
print(
    "NO MODEL TRAINING WAS PERFORMED."
)
