"""Render Q15 manuscript figures from independently checked participant tables.

The six panels preserve the participant as the unit of inference. This module
does not read EEG, load checkpoints, make predictions, or fit any model.
Run with the paper directory as the optional first argument.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
DATASETS = (("Cho2017", "Cho2017", 52), ("Lee2019_MI", "Lee2019 MI", 54))
MODELS = (
    ("BROAD_EEGNET", "Broad EEGNet", "#1b7c88", "o", True),
    ("MU_BETA_SHARED", "Shared mu/beta", "#c76d2d", "^", False),
    ("CSP4_LDA", "CSP4 + LDA", "#70777d", "s", False),
)


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_data(out: Path = HERE) -> tuple[dict, dict]:
    """Read checked tables, reject missing/duplicated persons and summary drift."""
    people, summaries = {}, {}
    person_rows = _rows(out / "tables/q15_external_subjects.csv")
    summary_rows = _rows(out / "tables/q15_model_summary.csv")
    assert len(person_rows) == 106 and len(summary_rows) == 6
    for dataset, _, n in DATASETS:
        cohort = [r for r in person_rows if r["dataset"] == dataset]
        cohort.sort(key=lambda r: int(r["subject"]))
        assert [int(r["subject"]) for r in cohort] == list(range(1, n + 1))
        people[dataset] = cohort
        summaries[dataset] = {}
        for model, *_ in MODELS:
            selected = [r for r in summary_rows if r["dataset"] == dataset and r["model"] == model]
            assert len(selected) == 1
            row = selected[0]
            values = np.array([float(r[model]) for r in cohort])
            assert np.isfinite(values).all() and ((0 <= values) & (values <= 1)).all()
            assert int(row["n_persons"]) == n
            assert math.isclose(values.mean(), float(row["mean_balanced_accuracy"]), abs_tol=1e-12)
            assert math.isclose(values.std(ddof=1), float(row["person_sample_sd"]), abs_tol=1e-12)
            assert int(row["n_seeds"]) == (1 if model == "CSP4_LDA" else 3)
            summaries[dataset][model] = row
        delta = np.array([float(r["primary_delta"]) for r in cohort])
        reconstructed = np.array([float(r["MU_BETA_SHARED"]) - float(r["BROAD_EEGNET"]) for r in cohort])
        assert np.allclose(delta, reconstructed, atol=1e-12, rtol=0)
        assert math.isclose(delta.mean(), float(summaries[dataset]["BROAD_EEGNET"]["primary_delta_mean"]), abs_tol=1e-12)
    return people, summaries


def swarm_offsets(values: np.ndarray, step: float = 0.015, dy: float = 0.65) -> np.ndarray:
    """Deterministically spread nearby values; jitter never encodes a measure."""
    values = np.asarray(values)
    order = np.argsort(values, kind="stable")
    offsets = np.zeros(len(values), dtype=float)
    done: list[int] = []
    candidates = [0.0] + [v for j in range(1, len(values) + 1) for v in (-j * step, j * step)]
    for i in order:
        neighbours = [j for j in done if abs(values[i] - values[j]) < dy]
        for candidate in candidates:
            if all(abs(candidate - offsets[j]) >= step * .96 for j in neighbours):
                offsets[i] = candidate
                break
        done.append(int(i))
    assert np.max(np.abs(offsets)) < .19
    return offsets


def _style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.5,
        "axes.titlesize": 9, "axes.labelsize": 8.5,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .65, "lines.linewidth": .9,
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "savefig.dpi": 300, "savefig.facecolor": "white",
    })


def _save(fig, out: Path, name: str) -> None:
    for extension in ("png", "pdf", "svg"):
        fig.savefig(out / "figures" / f"{name}.{extension}", dpi=300)
    plt.close(fig)


def _p_label(p: float) -> str:
    return "Holm p < 0.001" if p < .001 else f"Holm p = {p:.3f}"


def _main_figure(out: Path, people: dict, summaries: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.9), gridspec_kw={"width_ratios": [1.42, 1]})
    ax = axes[0]
    centers = (0.0, 1.25)
    for center, (dataset, _, _) in zip(centers, DATASETS):
        for position, (model, _, color, marker, filled) in zip((-.29, 0, .29), MODELS):
            values = np.array([float(r[model]) * 100 for r in people[dataset]])
            x = center + position + swarm_offsets(values)
            ax.scatter(x, values, s=12, marker=marker,
                       facecolors=color if filled else "none", edgecolors=color,
                       linewidths=.65, alpha=.70, zorder=3)
            row = summaries[dataset][model]
            mean = float(row["mean_balanced_accuracy"]) * 100
            sd = float(row["person_sample_sd"]) * 100
            # The horizontal black diamond and bars are descriptive mean +/- SD.
            ax.errorbar(center + position, mean, yerr=sd, fmt="D", markersize=4.1,
                        color="#202428", capsize=3.0, linewidth=1.0, zorder=4,
                        markeredgecolor="white", markeredgewidth=.45)
    ax.axhline(50, color="#666666", ls=":", lw=.8, zorder=1)
    ax.set(title="A  External participant performance", ylabel="Balanced accuracy (%)",
           xlim=(-.57, 1.82), ylim=(35, 100), xticks=centers,
           xticklabels=["Cho2017\nn = 52", "Lee2019 MI\nn = 54"])
    ax.set_yticks([40, 50, 60, 70, 80, 90, 100])
    ax.grid(axis="y", color="#e5e5e5", lw=.45)
    handles = [Line2D([], [], color=c, marker=m, markerfacecolor=c if filled else "none",
                      linestyle="none", markersize=4.5, label=label)
               for _, label, c, m, filled in MODELS]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.22), ncol=3,
              frameon=False, fontsize=6.9, handletextpad=.25, columnspacing=.9)
    ax.text(.02, -.35, "Diamonds/bars: mean ± participant SD; all participant points shown",
            transform=ax.transAxes, fontsize=6.8, ha="left", va="top")
    ax = axes[1]
    for y, (dataset, label, n) in zip((1, 0), DATASETS):
        row = summaries[dataset]["BROAD_EEGNET"]
        mean, low, high = [float(row[k]) * 100 for k in ("primary_delta_mean", "primary_ci_low", "primary_ci_high")]
        ax.errorbar(mean, y, xerr=[[mean - low], [high - mean]], fmt="o", color="#202428",
                    markersize=4.6, capsize=3.6, lw=1.25, zorder=4)
        ax.text(-2.8, y + .23, f"{mean:+.2f} pp [{low:+.2f}, {high:+.2f}]",
                fontsize=7.8, ha="left", va="center")
        ax.text(-2.8, y - .23, _p_label(float(row["primary_holm_p"])),
                fontsize=7.8, ha="left", va="center")
    ax.axvline(0, color="#666666", lw=.85, zorder=1)
    ax.set(title="B  Prespecified paired contrast", yticks=[1, 0],
           yticklabels=["Cho2017", "Lee2019 MI"], xlim=(-3.05, 1.6), ylim=(-.65, 1.65),
           xlabel="Shared mu/beta − broad EEGNet\nBalanced-accuracy difference (pp)")
    ax.set_xticks([-3, -2, -1, 0, 1])
    ax.grid(axis="x", color="#e5e5e5", lw=.45)
    ax.text(.02, -.35, "Bars: paired-person bootstrap 95% CI\nHolm correction: two prespecified cohorts",
            transform=ax.transAxes, fontsize=6.8, ha="left", va="top")
    fig.subplots_adjust(left=.075, right=.985, top=.91, bottom=.31, wspace=.50)
    _save(fig, out, "figure4_q15_external_transfer")


def _supplement(out: Path, people: dict, summaries: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 5.2), sharey="row")
    delta_values = np.concatenate([np.array([float(r["primary_delta"]) * 100 for r in people[d]]) for d, _, _ in DATASETS])
    lim = max(10, math.ceil(np.max(np.abs(delta_values)) / 5) * 5)
    seed_values = np.concatenate([np.array([float(r[m + "_seed_sd"]) * 100 for r in people[d]])
                                  for d, _, _ in DATASETS for m, *_ in MODELS[:2]])
    seed_lim = max(10, math.ceil(np.max(seed_values) / 5) * 5)
    for column, (dataset, label, n) in enumerate(DATASETS):
        persons = np.array([int(r["subject"]) for r in people[dataset]])
        values = np.array([float(r["primary_delta"]) * 100 for r in people[dataset]])
        ax = axes[0, column]
        ax.vlines(persons, 0, values, color="#9da2a5", linewidth=.55)
        ax.scatter(persons, values, s=13, marker="o", color="#303639", zorder=3)
        ax.axhline(0, color="#666666", lw=.85)
        mean = float(summaries[dataset]["BROAD_EEGNET"]["primary_delta_mean"]) * 100
        ax.axhline(mean, color="#c76d2d", lw=1.0, ls="--")
        ax.set(title=f"{'A' if column == 0 else 'B'}  {label} (n = {n})", xlim=(.1, n + .9), ylim=(-lim, lim))
        ax.text(.02, .95, f"Participant mean: {mean:+.2f} pp", transform=ax.transAxes,
                fontsize=7.6, va="top")
        ax.set_xticks([1, 10, 20, 30, 40, 50])
        ax.grid(axis="y", color="#e5e5e5", lw=.45)
        if column == 0:
            ax.set_ylabel("Shared − broad BA (pp)")
        ax = axes[1, column]
        for offset, (model, label_model, color, marker, filled) in zip((-.14, .14), MODELS[:2]):
            sd = np.array([float(r[model + "_seed_sd"]) * 100 for r in people[dataset]])
            assert np.isfinite(sd).all() and (sd >= 0).all()
            ax.scatter(persons + offset, sd, s=13, marker=marker, facecolors=color if filled else "none",
                       edgecolors=color, linewidths=.65, label=label_model, zorder=3)
        ax.set(title=f"{'C' if column == 0 else 'D'}  Within-participant seed variation", xlabel="Participant ID",
               xlim=(.1, n + .9), ylim=(0, seed_lim))
        ax.set_xticks([1, 10, 20, 30, 40, 50])
        ax.grid(axis="y", color="#e5e5e5", lw=.45)
        if column == 0:
            ax.set_ylabel("BA sample SD across three seeds (pp)")
    handles = [Line2D([], [], color=c, marker=m, markerfacecolor=c if filled else "none",
                      linestyle="none", markersize=4.5, label=label)
               for _, label, c, m, filled in MODELS[:2]]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.55, .044), ncol=2,
               frameon=False, fontsize=7.4, handletextpad=.35)
    fig.subplots_adjust(left=.11, right=.985, top=.93, bottom=.18, hspace=.44, wspace=.18)
    fig.text(.11, .014, "All 106 participants retained. Sessions are pooled within participant; seeds are not independent participants.",
             fontsize=7.0, ha="left")
    _save(fig, out, "figureS2_q15_participant_heterogeneity")


def main(out: Path = HERE) -> None:
    out = out.resolve()
    (out / "figures").mkdir(exist_ok=True)
    (out / "evidence").mkdir(exist_ok=True)
    people, summaries = load_data(out)
    _style()
    _main_figure(out, people, summaries)
    _supplement(out, people, summaries)
    inputs = ["tables/q15_external_subjects.csv", "tables/q15_model_summary.csv"]
    artifacts = [f"figures/{name}.{ext}" for name in ("figure4_q15_external_transfer", "figureS2_q15_participant_heterogeneity") for ext in ("png", "pdf", "svg")]
    record = {
        "schema_version": 1, "status": "rendered_pending_visual_inspection",
        "input_sha256": {p: hashlib.sha256((out / p).read_bytes()).hexdigest() for p in inputs},
        "artifact_sha256": {p: hashlib.sha256((out / p).read_bytes()).hexdigest() for p in artifacts},
        "participants": {d: len(people[d]) for d, _, _ in DATASETS},
        "unit_of_inference": "participant; three-seed mean after pooling declared sessions",
        "primary_contrast": "MU_BETA_SHARED_minus_BROAD_EEGNET",
        "model_point_count_main_panel": 318,
        "descriptive_error_bar": "sample SD of participant seed means, not confidence interval",
        "primary_interval": "95% paired-person percentile bootstrap from independently checked table",
        "multiplicity": "Holm over two prespecified external cohorts; no pooled estimate",
        "figureS2": {"paired_difference_points": 106, "seed_sample_sd_points": 212, "seed_count": 3,
                     "deterministic_CSP_seed_SD": "not applicable and omitted"},
        "formats": {"png_dpi": 300, "pdf": "vector with embedded TrueType fonts", "svg": "vector and editable text"},
        "inline_TeX": "tex_q15_figures.tex_inline_figure(name, out, numbers=None); no external figure files",
        "new_model_fits": 0, "new_predictions": 0,
    }
    (out / "evidence/figures_q15.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figures": 2, "participant_points": 636, "new_model_fits": 0, "new_predictions": 0}))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE)
