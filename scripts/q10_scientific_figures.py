"""Reproducible descriptive figures for the frozen Q5--Q9 audit.

These are exploratory development-cohort figures.  The script consumes only
the independently recomputed Q10-V001 tables and frozen learning curves; it
does not train, select a method, or inspect new external target performance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "results/Q10-V001"
OUT = AUDIT / "figures"
CONDITIONS = [
    "Q4-E001/BroadCSP_LDA",
    "Q5-E001",
    "Q8-E001",
    "Q9-E001/MID_8_30",
    "Q9-E001/MU_BETA_SHARED",
    "Q9-E001/BETA_13_30",
]
LABELS = {
    "Q4-E001/BroadCSP_LDA": "CSP+LDA",
    "Q5-E001": "Q5 broadband",
    "Q8-E001": "Q8 broadband",
    "Q9-E001/MID_8_30": "Q9 8-30 Hz",
    "Q9-E001/MU_BETA_SHARED": "Q9 mu/beta shared",
    "Q9-E001/BETA_13_30": "Q9 beta only",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subject_performance() -> None:
    table = pd.read_csv(AUDIT / "subject_summary.csv")
    table = table[table.condition.isin(CONDITIONS)]
    fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    subjects = np.arange(1, 10)
    for condition in CONDITIONS:
        subset = table[table.condition.eq(condition)].sort_values("subject")
        if len(subset) != 9:
            raise ValueError(f"incomplete subject inventory: {condition}")
        ax.plot(subjects, subset.mean_seed_ba.to_numpy(), marker="o", lw=1.6,
                label=LABELS[condition])
    ax.axhline(0.25, color="black", ls="--", lw=0.8, alpha=0.5)
    ax.set(xlabel="Held-out BNCI subject", ylabel="Balanced accuracy",
           xticks=subjects, ylim=(0, 0.85),
           title="Development-cohort subject heterogeneity (exploratory)")
    ax.grid(alpha=0.2)
    ax.legend(ncol=2, fontsize=8)
    fig.savefig(OUT / "subject_performance.png", dpi=180)
    fig.savefig(OUT / "subject_performance.pdf")
    plt.close(fig)


def seed_variability() -> None:
    table = pd.read_csv(AUDIT / "subject_seed_metrics.csv")
    table = table[table.condition.isin(CONDITIONS)]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.8), sharex=True, sharey=True,
                             constrained_layout=True)
    for ax, condition in zip(axes.flat, CONDITIONS):
        for subject, group in table[table.condition.eq(condition)].groupby("subject"):
            values = group.balanced_accuracy.to_numpy(dtype=float)
            if condition.startswith("Q4-") and len(values) != 1:
                raise ValueError("Q4 is deterministic and should have one fit")
            if not condition.startswith("Q4-") and len(values) != 3:
                raise ValueError(f"missing seed: {condition}, S{subject}")
            ax.plot([subject] * len(values), values, "o", ms=3, alpha=0.5,
                    color="#1456a0")
            ax.hlines(values.mean(), subject - .28, subject + .28,
                      color="#d33a2c", lw=1.7)
        ax.set_title(LABELS[condition], fontsize=10)
        ax.axhline(.25, color="black", ls="--", lw=.7, alpha=.5)
        ax.grid(alpha=.15)
    for ax in axes[-1]:
        ax.set_xlabel("Held-out subject")
    for ax in axes[:, 0]:
        ax.set_ylabel("Balanced accuracy")
    axes[0, 0].set(xticks=range(1, 10), ylim=(0, .85))
    fig.suptitle("Individual seeds (blue); within-subject mean (red)", fontsize=12)
    fig.savefig(OUT / "seed_variability.png", dpi=180)
    fig.savefig(OUT / "seed_variability.pdf")
    plt.close(fig)


def confusion() -> None:
    table = pd.read_csv(AUDIT / "confusion_matrices.csv")
    shown = ["Q4-E001/BroadCSP_LDA", "Q8-E001", "Q9-E001/MU_BETA_SHARED",
             "Q9-E001/BETA_13_30"]
    fig, axes = plt.subplots(1, 4, figsize=(12.5, 3.4), constrained_layout=True)
    for ax, condition in zip(axes, shown):
        rows = table[table.condition.eq(condition)]
        matrix = np.zeros((4, 4), dtype=float)
        for row in rows.itertuples(index=False):
            matrix[int(row.true_class) - 1, int(row.predicted_class) - 1] += row.n_trials
        if matrix.sum() <= 0 or np.any(matrix.sum(axis=1) == 0):
            raise ValueError(f"invalid confusion: {condition}")
        normalized = matrix / matrix.sum(axis=1, keepdims=True)
        ax.imshow(normalized, vmin=0, vmax=1, cmap="Blues")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{normalized[i, j]:.2f}", ha="center", va="center",
                        fontsize=8, color="white" if normalized[i, j] > .52 else "black")
        ax.set(title=LABELS[condition], xlabel="Predicted class", ylabel="True class",
               xticks=range(4), yticks=range(4),
               xticklabels=["L", "R", "F", "T"], yticklabels=["L", "R", "F", "T"])
    fig.suptitle("Row-normalized confusion; all subjects/seeds (descriptive)")
    fig.savefig(OUT / "confusion.png", dpi=180)
    fig.savefig(OUT / "confusion.pdf")
    plt.close(fig)


def epoch_selection() -> None:
    q5 = pd.read_csv(ROOT / "results/Q5-E001/learning_curves.csv")
    q5 = q5[q5.stage.eq("inner")]
    q8_selection = pd.read_csv(ROOT / "research_runs/Q8-E001/results/selection.csv")
    q9_selection = pd.read_csv(ROOT / "results/Q9-E001/MU_BETA_SHARED/selection.csv")
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), sharex=True, sharey=True,
                             constrained_layout=True)
    for subject, ax in zip(range(1, 10), axes.flat):
        fold = f"loso_s{subject}"
        broad = q5[q5.fold.eq(fold)].groupby("epoch").val_ce.mean()
        narrow_curves = []
        for inner in range(1, 5):
            path = ROOT / f"results/Q9-E001/MU_BETA_SHARED/inner/{fold}/inner_{inner}/learning_curve.csv"
            frame = pd.read_csv(path)
            if len(frame) != 40:
                raise ValueError(f"incomplete inner curve: {path}")
            narrow_curves.append(frame.val_ce.to_numpy(dtype=float))
        narrow = np.mean(narrow_curves, axis=0)
        if len(broad) != 40:
            raise ValueError(f"incomplete Q5 inner curve: {fold}")
        ax.plot(np.arange(1, 41), broad.to_numpy(), color="#1456a0", lw=1.5,
                label="Q5 curves reused by Q8")
        ax.plot(np.arange(1, 41), narrow, color="#d35400", lw=1.5,
                label="Q9 shared curves")
        e8 = int(q8_selection.loc[q8_selection.subject.eq(subject), "selected_epochs"].iloc[0])
        e9 = int(q9_selection.loc[q9_selection.subject.eq(subject), "selected_epochs"].iloc[0])
        ax.axvline(e8, color="#1456a0", ls="--", lw=1)
        ax.axvline(e9, color="#d35400", ls=":", lw=1.5)
        ax.set_title(f"S{subject}: Q8 e{e8}; Q9 e{e9}", fontsize=9)
        ax.grid(alpha=.15)
    for ax in axes[-1]:
        ax.set_xlabel("Epoch")
    for ax in axes[:, 0]:
        ax.set_ylabel("Mean inner-validation CE")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(.5, 1.04))
    fig.suptitle("Source-only learning curves and frozen mean-rank epoch choices", y=1.08)
    fig.savefig(OUT / "epoch_selection.png", dpi=180, bbox_inches="tight")
    fig.savefig(OUT / "epoch_selection.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    subject_performance()
    seed_variability()
    confusion()
    epoch_selection()
    source_paths = [
        AUDIT / "subject_summary.csv", AUDIT / "subject_seed_metrics.csv",
        AUDIT / "confusion_matrices.csv", ROOT / "results/Q5-E001/learning_curves.csv",
        ROOT / "research_runs/Q8-E001/results/selection.csv",
        ROOT / "results/Q9-E001/MU_BETA_SHARED/selection.csv",
    ]
    source_paths.extend(ROOT.glob("results/Q9-E001/MU_BETA_SHARED/inner/loso_s*/inner_*/learning_curve.csv"))
    (OUT / "figure_receipt.json").write_text(json.dumps({
        "status": "descriptive_figures_generated",
        "scientific_scope": "exploratory_BNCI_development_only",
        "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p)
                         for p in sorted(source_paths)},
        "figures": ["subject_performance", "seed_variability", "confusion", "epoch_selection"],
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
