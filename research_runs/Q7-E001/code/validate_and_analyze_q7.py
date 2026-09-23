from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    cohen_kappa_score,
    confusion_matrix,
)

Q5 = Path("/workspace/Q5_EEGNet_Cloud_Ready")
Q6 = Path("/workspace/Q6_EEGNet_SourceNorm")
Q7 = Path("/workspace/Q7_Mechanistic_Ablation")
R = Q7 / "results/Q7-E001"
ARCHIVE = Q7 / "research_archive"

ARCHIVE.mkdir(parents=True, exist_ok=True)

SEEDS = [20260924, 20260925, 20260926]


def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def prediction_entropy(y_pred):
    counts = np.array(
        [(y_pred == c).sum() for c in [1, 2, 3, 4]],
        dtype=float,
    )
    p = counts / counts.sum()
    p = p[p > 0]
    return float(
        -np.sum(p * np.log(p)) / np.log(4)
    )


def dominant_share(y_pred):
    counts = np.array(
        [(y_pred == c).sum() for c in [1, 2, 3, 4]]
    )
    return float(counts.max() / counts.sum())


# ============================================================
# 1. Validate protocol
# ============================================================

protocol = json.loads(
    (R / "protocol.json").read_text(encoding="utf-8")
)

status = json.loads(
    (R / "status.json").read_text(encoding="utf-8")
)

if status["status"] != "complete":
    raise AssertionError("Q7 run is not complete")

if protocol["target_subject"] != 3:
    raise AssertionError("Q7 target is not S3")

if protocol["new_cells"]["B"] != {
    "normalization": True,
    "epochs": 2,
}:
    raise AssertionError("Condition B protocol changed")

if protocol["new_cells"]["C"] != {
    "normalization": False,
    "epochs": 16,
}:
    raise AssertionError("Condition C protocol changed")

receipt = json.loads(
    (R / "condition_B_source_normalizer.json")
    .read_text(encoding="utf-8")
)

if receipt["target_fitted_transform"] is not False:
    raise AssertionError("Target-derived normalization detected")

if sorted(receipt["train_subjects"]) != [
    1, 2, 4, 5, 6, 7, 8, 9
]:
    raise AssertionError(
        "Condition B source scaler subjects incorrect"
    )

if receipt["n_train_trials"] != 4608:
    raise AssertionError(
        "Condition B scaler did not fit 4608 source trials"
    )


# ============================================================
# 2. Validate Q7 predictions/metrics independently
# ============================================================

pred = pd.read_csv(R / "predictions.csv")
metrics_saved = pd.read_csv(R / "per_subject_metrics.csv")

expected_rows = 2 * 3 * 576

if len(pred) != expected_rows:
    raise AssertionError(
        f"Expected {expected_rows} predictions, got {len(pred)}"
    )

validation_rows = []

for condition in ["B", "C"]:
    for seed in SEEDS:

        z = pred[
            (pred.condition == condition)
            & (pred.seed == seed)
        ].copy()

        if len(z) != 576:
            raise AssertionError(
                f"{condition}/{seed}: expected 576 predictions"
            )

        truth = z.y_true.to_numpy()
        guess = z.y_pred.to_numpy()

        ba = balanced_accuracy_score(truth, guess)
        f1 = f1_score(
            truth,
            guess,
            labels=[1, 2, 3, 4],
            average="macro",
        )
        kappa = cohen_kappa_score(
            truth,
            guess,
            labels=[1, 2, 3, 4],
        )

        saved = metrics_saved[
            (metrics_saved.condition == condition)
            & (metrics_saved.seed == seed)
            & (metrics_saved.stratum == "all")
        ].iloc[0]

        for name, recomputed, stored in [
            ("balanced_accuracy", ba, saved.balanced_accuracy),
            ("macro_f1", f1, saved.macro_f1),
            ("cohen_kappa", kappa, saved.cohen_kappa),
        ]:
            if not np.isclose(
                recomputed,
                stored,
                atol=1e-12,
                rtol=0,
            ):
                raise AssertionError(
                    f"{condition}/{seed} {name} mismatch"
                )

        validation_rows.append(
            {
                "condition": condition,
                "seed": seed,
                "balanced_accuracy": ba,
                "macro_f1": f1,
                "cohen_kappa": kappa,
                "prediction_entropy": prediction_entropy(guess),
                "dominant_prediction_share": dominant_share(guess),
            }
        )

validation_df = pd.DataFrame(validation_rows)

validation_df.to_csv(
    ARCHIVE / "q7_new_condition_validation.csv",
    index=False,
)


# ============================================================
# 3. Load existing A and D from Q5/Q6
# ============================================================

def load_parent(exp, root, condition, name, epochs, norm):
    m = pd.read_csv(
        root / "per_subject_metrics.csv"
    )

    m = m[
        (m.subject == 3)
        & (m.stratum == "all")
    ].copy()

    rows = []

    for seed in SEEDS:

        r = m[m.seed == seed].iloc[0]

        pred = pd.read_csv(
            root
            / "folds"
            / "loso_s3"
            / f"predictions_seed_{seed}.csv"
        )

        ypred = pred.y_pred.to_numpy()

        rows.append(
            {
                "condition": condition,
                "condition_name": name,
                "source_experiment": exp,
                "normalization": norm,
                "fixed_epochs": epochs,
                "seed": seed,
                "balanced_accuracy": float(r.balanced_accuracy),
                "macro_f1": float(r.macro_f1),
                "cohen_kappa": float(r.cohen_kappa),
                "prediction_entropy": prediction_entropy(ypred),
                "dominant_prediction_share": dominant_share(ypred),
            }
        )

    return pd.DataFrame(rows)


A = load_parent(
    "Q5-E001",
    Q5 / "results/Q5-E001",
    "A",
    "Raw_plus_2epochs",
    2,
    False,
)

D = load_parent(
    "Q6-E001",
    Q6 / "results/Q6-E001",
    "D",
    "SourceNorm_plus_16epochs",
    16,
    True,
)

new_rows = []

for condition, name, epochs, norm in [
    ("B", "SourceNorm_plus_2epochs", 2, True),
    ("C", "Raw_plus_16epochs", 16, False),
]:

    z = validation_df[
        validation_df.condition == condition
    ].copy()

    z["condition_name"] = name
    z["source_experiment"] = "Q7-E001"
    z["normalization"] = norm
    z["fixed_epochs"] = epochs

    new_rows.append(z)

B, C = new_rows

four = pd.concat(
    [A, B, C, D],
    ignore_index=True,
)

four = four[
    [
        "condition",
        "condition_name",
        "source_experiment",
        "normalization",
        "fixed_epochs",
        "seed",
        "balanced_accuracy",
        "macro_f1",
        "cohen_kappa",
        "prediction_entropy",
        "dominant_prediction_share",
    ]
]

four.to_csv(
    ARCHIVE / "q7_four_cell_seed_results.csv",
    index=False,
)


# ============================================================
# 4. Mean four-cell factorial summary
# ============================================================

summary = (
    four.groupby(
        [
            "condition",
            "condition_name",
            "source_experiment",
            "normalization",
            "fixed_epochs",
        ],
        as_index=False,
    )
    .agg(
        BA_mean=("balanced_accuracy", "mean"),
        BA_seed_std=("balanced_accuracy", "std"),
        macroF1_mean=("macro_f1", "mean"),
        kappa_mean=("cohen_kappa", "mean"),
        entropy_mean=("prediction_entropy", "mean"),
        dominant_share_mean=(
            "dominant_prediction_share",
            "mean",
        ),
    )
)

summary = summary.sort_values("condition")

summary.to_csv(
    ARCHIVE / "q7_four_cell_summary.csv",
    index=False,
)

means = summary.set_index("condition")

Aba = float(means.loc["A", "BA_mean"])
Bba = float(means.loc["B", "BA_mean"])
Cba = float(means.loc["C", "BA_mean"])
Dba = float(means.loc["D", "BA_mean"])

contrasts = {
    "A_raw_2": Aba,
    "B_norm_2": Bba,
    "C_raw_16": Cba,
    "D_norm_16": Dba,

    "normalization_effect_at_2_epochs_B_minus_A": Bba - Aba,

    "training_duration_effect_without_norm_C_minus_A": Cba - Aba,

    "training_duration_effect_with_norm_D_minus_B": Dba - Bba,

    "normalization_effect_at_16_epochs_D_minus_C": Dba - Cba,

    "factorial_interaction_D_minus_C_minus_B_plus_A":
        Dba - Cba - Bba + Aba,
}

(Path(ARCHIVE) / "q7_factorial_contrasts.json").write_text(
    json.dumps(
        contrasts,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# 5. Class recall for all four cells
# ============================================================

class_rows = []

def parent_predictions(root, seed):
    return pd.read_csv(
        root
        / "folds"
        / "loso_s3"
        / f"predictions_seed_{seed}.csv"
    )


for condition in ["A", "B", "C", "D"]:

    for seed in SEEDS:

        if condition == "A":
            p = parent_predictions(
                Q5 / "results/Q5-E001",
                seed,
            )

        elif condition == "D":
            p = parent_predictions(
                Q6 / "results/Q6-E001",
                seed,
            )

        else:
            p = pred[
                (pred.condition == condition)
                & (pred.seed == seed)
            ].copy()

        truth = p.y_true.to_numpy()
        guess = p.y_pred.to_numpy()

        cm = confusion_matrix(
            truth,
            guess,
            labels=[1, 2, 3, 4],
        )

        for i, label in enumerate([1, 2, 3, 4]):

            total = cm[i].sum()

            class_rows.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "class_id": label,
                    "correct": int(cm[i, i]),
                    "total": int(total),
                    "recall": float(
                        cm[i, i] / total
                    ),
                }
            )

class_df = pd.DataFrame(class_rows)

class_df.to_csv(
    ARCHIVE / "q7_four_cell_class_recall.csv",
    index=False,
)


# ============================================================
# 6. Checkpoint hashes
# ============================================================

checkpoints = pd.read_csv(
    R / "checkpoint_hashes.csv"
)

for _, row in checkpoints.iterrows():

    path = Path(row.checkpoint)

    if not path.exists():
        raise AssertionError(
            f"Missing checkpoint: {path}"
        )

    if sha256_file(path) != row.sha256:
        raise AssertionError(
            f"Checkpoint SHA mismatch: {path}"
        )


# ============================================================
# 7. Write independent validation report
# ============================================================

validation_report = {
    "status": "passed",
    "experiment_id": "Q7-E001",
    "target_subject": 3,
    "new_conditions": ["B", "C"],
    "reused_conditions": ["A", "D"],
    "n_new_final_fits": 6,
    "n_new_predictions": int(len(pred)),
    "seeds": SEEDS,
    "condition_B_epochs": 2,
    "condition_B_normalization": True,
    "condition_C_epochs": 16,
    "condition_C_normalization": False,
    "condition_B_target_fitted_transform": False,
    "condition_B_source_subjects": receipt["train_subjects"],
    "condition_B_scaler_train_trials": receipt["n_train_trials"],
    "metrics_recomputed_from_predictions": True,
    "checkpoint_hashes_verified": True,
    "interpretation_boundary": (
        "Q7-E001 is a mechanistic S3 ablation. "
        "S3 is one held-out person; seed fits are not independent subjects. "
        "This experiment tests mechanism and does not establish "
        "population-level generalization."
    ),
}

(ARCHIVE / "validation_report.json").write_text(
    json.dumps(
        validation_report,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# 8. Markdown report
# ============================================================

lines = []

lines.append("# Q7-E001 Mechanistic Ablation Report")
lines.append("")
lines.append("## Four-cell design")
lines.append("")
lines.append("| Cell | Normalization | Epochs | Source |")
lines.append("|---|---|---:|---|")
lines.append("| A | OFF | 2 | Q5-E001 |")
lines.append("| B | ON | 2 | Q7-E001 |")
lines.append("| C | OFF | 16 | Q7-E001 |")
lines.append("| D | ON | 16 | Q6-E001 |")
lines.append("")

lines.append("## Mean results over three seeds")
lines.append("")
lines.append(
    "| Cell | BA | Macro-F1 | Kappa | Entropy | Dominant share |"
)
lines.append(
    "|---|---:|---:|---:|---:|---:|"
)

for _, r in summary.iterrows():

    lines.append(
        f"| {r.condition} | "
        f"{r.BA_mean:.4f} | "
        f"{r.macroF1_mean:.4f} | "
        f"{r.kappa_mean:.4f} | "
        f"{r.entropy_mean:.4f} | "
        f"{r.dominant_share_mean:.4f} |"
    )

lines.append("")
lines.append("## Mechanistic contrasts")
lines.append("")

for k, v in contrasts.items():
    lines.append(
        f"- {k}: **{v:+.4f}**"
        if "minus" in k or "interaction" in k
        else f"- {k}: **{v:.4f}**"
    )

lines.append("")
lines.append("## Interpretation boundary")
lines.append("")
lines.append(
    "This is a mechanistic experiment centered on S3. "
    "It is not evidence that the same mechanism generalizes "
    "to the population of unseen subjects."
)
lines.append("")
lines.append(
    "The four-cell pattern should be interpreted before "
    "designing Q8. No additional Q7 variants should be added "
    "after inspecting these results."
)

(ARCHIVE / "Q7_MECHANISTIC_REPORT.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)


# ============================================================
# 9. Terminal summary
# ============================================================

print()
print("============================================================")
print(" Q7-E001 FINAL FOUR-CELL RESULTS")
print("============================================================")
print()

print(
    summary[
        [
            "condition",
            "normalization",
            "fixed_epochs",
            "BA_mean",
            "BA_seed_std",
            "macroF1_mean",
            "kappa_mean",
            "entropy_mean",
            "dominant_share_mean",
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)

print()
print("===== FACTORIAL CONTRASTS =====")

for k, v in contrasts.items():
    print(f"{k}: {v:+.6f}")

print()
print("===== VALIDATION =====")
print(json.dumps(validation_report, indent=2))

print()
print("Q7 VALIDATION PASSED")
