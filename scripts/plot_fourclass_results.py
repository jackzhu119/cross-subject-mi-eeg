"""Render standalone Q4 scientific figures from independently validated results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLORS = {
    "BroadCSP_LDA": "#244E7A",
    "BroadCSP_SVM": "#5F7D9E",
    "FBCSP_LDA": "#B57924",
    "FBCSP_MI8_LDA": "#826A43",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "outputs/Q4-E001")
    args = parser.parse_args()
    output = args.output
    report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    if report["status"] != "passed":
        raise ValueError("Q4 must pass independent validation before plotting")
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    models = [model["name"] for model in config["models"]]
    values = pd.read_csv(output / "per_subject_metrics.csv").query("stratum == 'all'")
    matrix = values.pivot(index="subject", columns="model", values="balanced_accuracy")[models]
    if matrix.shape != (9, len(models)):
        raise AssertionError("Plot data lack complete nine-subject model coverage")
    matrix = matrix.mul(100)
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.4, 5.1), constrained_layout=True)
    image = ax.imshow(matrix, cmap="YlGnBu", vmin=20, vmax=75, aspect="auto")
    ax.set_xticks(np.arange(len(models)), models)
    ax.set_yticks(np.arange(9), [f"S{subject:02d}" for subject in matrix.index])
    ax.set_xlabel("Fixed traditional pipeline")
    ax.set_ylabel("Held-out subject")
    ax.set_title("Four-class LOSO balanced accuracy by held-out subject")
    for i in range(9):
        for j in range(len(models)):
            score = matrix.iloc[i, j]
            ax.text(
                j,
                i,
                f"{score:.1f}",
                ha="center",
                va="center",
                color="white" if score >= 57 else "#20272C",
                fontsize=10,
            )
    bar = fig.colorbar(image, ax=ax, shrink=0.86)
    bar.set_label("Balanced accuracy (%)")
    fig.savefig(folder / "fourclass_loso_subject_heatmap.png", dpi=220)
    plt.close(fig)

    baseline = matrix["BroadCSP_LDA"]
    fig, ax = plt.subplots(figsize=(8.4, 5.1), constrained_layout=True)
    offsets = {"BroadCSP_SVM": -0.19, "FBCSP_LDA": 0, "FBCSP_MI8_LDA": 0.19}
    for name in models[1:]:
        delta = matrix[name] - baseline
        ax.scatter(
            matrix.index.to_numpy() + offsets[name],
            delta,
            label=name,
            color=COLORS[name],
            s=58,
            marker="o" if name != "FBCSP_MI8_LDA" else "s",
        )
        ax.plot(
            [matrix.index.min() + offsets[name] - 0.1, matrix.index.max() + offsets[name] + 0.1],
            [delta.mean(), delta.mean()],
            color=COLORS[name],
            alpha=0.85,
            linewidth=1.2,
            linestyle="--",
        )
    ax.axhline(0, color="#30383D", linewidth=1)
    ax.set_xticks(matrix.index, [f"S{subject:02d}" for subject in matrix.index])
    ax.set_xlabel("Held-out subject")
    ax.set_ylabel("BA difference vs BroadCSP_LDA (percentage points)")
    ax.set_title("Paired subject differences; dashed lines show mean differences")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, loc="best")
    fig.savefig(folder / "fourclass_loso_paired_differences.png", dpi=220)
    plt.close(fig)

    pd.DataFrame(
        {"subject": matrix.index, **{name: matrix[name].to_numpy() for name in models}}
    ).to_csv(folder / "figure_data.csv", index=False)
    (folder / "figure_note.json").write_text(
        json.dumps(
            {
                "input": "per_subject_metrics.csv: stratum=all",
                "n_subjects": 9,
                "n_trials_per_subject": 576,
                "chance_balanced_accuracy_percent": 25,
                "error_bars": "none; per-subject observed scores and paired deltas, not inferential intervals",
                "source_validation": "validation_report.json: passed",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(folder)


if __name__ == "__main__":
    main()
