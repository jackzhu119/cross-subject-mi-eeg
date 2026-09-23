"""Plot descriptive C3/C4 Welch spectra from the fixed clean trial population."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from run_csp_baselines import load_epochs
from scipy.signal import welch

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "P3-E001" / "figures" / "welch_c3_c4_grandmean.png",
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing figure: {args.output}")
    mne.set_log_level("WARNING")
    warnings.filterwarnings("ignore", message="Montage name 'standard_1005' is deprecated.*")
    X, meta, _ = load_epochs(list(range(1, 10)), args.data_dir.resolve(), True)
    picks = {"C3": 7, "C4": 11}
    frequencies, psd = welch(
        X[:, list(picks.values()), :],
        fs=250,
        window="hann",
        nperseg=250,
        noverlap=125,
        nfft=250,
        detrend="constant",
        scaling="density",
        average="mean",
        axis=-1,
    )
    keep = (frequencies >= 8) & (frequencies <= 30)
    per_subject = {}
    for subject in range(1, 10):
        per_subject[subject] = {}
        for label in (1, 2):
            chosen = (meta["subject"].to_numpy() == subject) & (meta["label"].to_numpy() == label)
            per_subject[subject][label] = psd[chosen].mean(axis=0)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True, layout="constrained")
    for channel_index, (channel, _) in enumerate(picks.items()):
        ax = axes[channel_index]
        for label, name, color in (
            (1, "Left-hand imagery", "#2066aa"),
            (2, "Right-hand imagery", "#d96d17"),
        ):
            # Average subject-wise log power so each of the nine subjects has equal weight.
            db = np.mean(
                [
                    10 * np.log10(np.maximum(per_subject[s][label][channel_index], 1e-20))
                    for s in range(1, 10)
                ],
                axis=0,
            )
            ax.plot(frequencies[keep], db[keep], label=name, color=color, linewidth=1.8)
        ax.set(title=channel, xlabel="Frequency (Hz)", xlim=(8, 30))
        ax.axvspan(8, 12, color="#4b7bec", alpha=0.07)
        ax.axvspan(13, 30, color="#e67e22", alpha=0.04)
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Subject-equal mean PSD (dB re 1 V²/Hz)")
    axes[1].legend(fontsize=8)
    fig.suptitle("C3/C4 spectra on clean trials (descriptive, not a significance test)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)
    print(f"Saved {args.output.resolve()}")


if __name__ == "__main__":
    main()
