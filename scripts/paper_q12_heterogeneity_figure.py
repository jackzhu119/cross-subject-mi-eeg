"""Render the fixed-order Q12 subject-paired contrast heatmap for paper review.

This is a descriptive figure, not a new endpoint or significance test. Each
cell is the three-seed-averaged held-out-subject BA difference already saved
by the independent Q12 analysis. GroupDRO uses balanced ERM as its control;
all other rows use frozen Q8 broad EEGNet. No target score selects a row.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/Q12-BATCH/paired_subject_contrasts.json"
DESTINATION = (ROOT / "research_runs/PAPER_RELEASE_20260927/figures"
               / "q12_subject_delta_heatmap.png")

ROWS = (
    ("SOURCE_POOLED_WHITEN-Q8-E001", "Whitening − Q8"),
    ("SOURCE_BALANCED_ERM-Q8-E001", "Balanced ERM − Q8"),
    ("SOURCE_GROUP_DRO-SOURCE_BALANCED_ERM", "GroupDRO − balanced ERM"),
    ("GAIN_PERTURB-Q8-E001", "Gain perturb. − Q8"),
    ("CHANNEL_DROPOUT-Q8-E001", "Channel dropout − Q8"),
    ("CHANNEL_AND_GAIN-Q8-E001", "Channel + gain − Q8"),
)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    values = np.array([
        [float(source[key]["per_subject_delta"][str(subject)]) * 100
         for subject in range(1, 10)]
        for key, _ in ROWS
    ])
    if values.shape != (6, 9) or not np.isfinite(values).all():
        raise AssertionError("Q12 subject contrast grid is incomplete")

    fig, ax = plt.subplots(figsize=(11, 4.5), layout="constrained")
    im = ax.imshow(values, cmap="RdBu", vmin=-20, vmax=20, aspect="auto")
    ax.set_xticks(range(9), [f"S{i}" for i in range(1, 10)])
    ax.set_yticks(range(len(ROWS)), [label for _, label in ROWS])
    ax.set_xlabel("Held-out BNCI2014_001 subject")
    ax.set_title("Q12 source-only changes: paired balanced-accuracy difference")
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            color = "white" if abs(value) >= 10 else "black"
            ax.text(column, row, f"{value:+.1f}", ha="center", va="center",
                    color=color, fontsize=9)
    fig.colorbar(im, ax=ax, label="Δ balanced accuracy (percentage points)")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(DESTINATION, dpi=180)
    plt.close(fig)
    print(DESTINATION)


if __name__ == "__main__":
    main()
