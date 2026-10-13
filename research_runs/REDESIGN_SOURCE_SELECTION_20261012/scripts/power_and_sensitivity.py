#!/usr/bin/env python3
"""Prospective paired-mean power scenarios; no EEG data or performance is read.

Exact planning uses the noncentral t distribution under independent Gaussian
participant differences. The scenarios are assumptions, not observed results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.stats import chi2, nct, norm, t


SD_PP = (5.0, 10.0, 15.0)
COHORT_N = (10, 21, 60, 85, 87)
EFFECT_PP = (2.0, 3.0, 5.0)
ALPHAS = (("primary", 0.05), ("family2_bonferroni_bound", 0.025),
          ("family3_bonferroni_bound", 0.05 / 3.0))
TARGET_POWER = 0.8


def paired_t_power(n: int, effect_pp: float, sd_pp: float, alpha: float = 0.05) -> float:
    if n < 3 or sd_pp <= 0 or not 0 < alpha < 1:
        raise ValueError("Requires n >= 3, positive paired SD and 0 < alpha < 1")
    critical = t.ppf(1 - alpha / 2, n - 1)
    noncentrality = abs(effect_pp) * math.sqrt(n) / sd_pp
    # Symmetry gives the left-tail probability as a survival probability with
    # negative noncentrality. This avoids SciPy's occasional NaN for an extreme
    # negative CDF tail; no probability is silently imputed or dropped.
    value = float(nct.sf(critical, n - 1, noncentrality)
                  + nct.sf(critical, n - 1, -noncentrality))
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ArithmeticError("Noncentral-t calculation produced an invalid probability")
    return value


def minimum_detectable_effect(n: int, sd_pp: float, alpha: float = 0.05) -> float:
    return float(brentq(lambda effect: paired_t_power(n, effect, sd_pp, alpha) - TARGET_POWER,
                        0.0, 10.0 * sd_pp, xtol=1e-12))


def required_n(effect_pp: float, sd_pp: float, alpha: float = 0.05) -> int:
    if effect_pp <= 0:
        raise ValueError("Effect must be positive")
    high = 4
    while paired_t_power(high, effect_pp, sd_pp, alpha) < TARGET_POWER:
        high *= 2
        if high > 1_000_000:
            raise RuntimeError("Unreasonably large planning sample")
    low = 3
    while low < high:
        mid = (low + high) // 2
        if paired_t_power(mid, effect_pp, sd_pp, alpha) >= TARGET_POWER:
            high = mid
        else:
            low = mid + 1
    return low


def independent_power_quadrature(n: int, effect_pp: float, sd_pp: float, alpha: float) -> float:
    """Independent normal/chi-square mixture calculation of t rejection power."""
    df = n - 1
    critical = t.ppf(1 - alpha / 2, df)
    noncentrality = abs(effect_pp) * math.sqrt(n) / sd_pp

    def integrand(v: float) -> float:
        boundary = critical * math.sqrt(v / df)
        conditional = norm.sf(boundary - noncentrality) + norm.cdf(-boundary - noncentrality)
        return float(conditional * chi2.pdf(v, df))

    value, error = quad(integrand, 0, math.inf, epsabs=1e-11, epsrel=1e-10, limit=250)
    if error > 1e-8:
        raise AssertionError("Quadrature did not meet its error tolerance")
    return float(value)


def make_rows() -> list[dict]:
    rows: list[dict] = []
    for family, alpha in ALPHAS:
        for n in COHORT_N:
            for sd in SD_PP:
                mde = minimum_detectable_effect(n, sd, alpha)
                rows.append({"record_type": "mde_for_fixed_n", "planning_family": family,
                             "two_sided_alpha": alpha, "target_power": TARGET_POWER,
                             "participants_n": n, "paired_sd_pp": sd, "effect_pp": mde,
                             "attained_power": paired_t_power(n, mde, sd, alpha),
                             "power_at_n_minus_one": "", "scenario_not_observed": True})
        for sd in SD_PP:
            for effect in EFFECT_PP:
                n = required_n(effect, sd, alpha)
                rows.append({"record_type": "n_for_fixed_effect", "planning_family": family,
                             "two_sided_alpha": alpha, "target_power": TARGET_POWER,
                             "participants_n": n, "paired_sd_pp": sd, "effect_pp": effect,
                             "attained_power": paired_t_power(n, effect, sd, alpha),
                             "power_at_n_minus_one": paired_t_power(n - 1, effect, sd, alpha),
                             "scenario_not_observed": True})
    return rows


def verify(rows: list[dict]) -> dict:
    checks = []
    for row in rows:
        power = row["attained_power"]
        if row["record_type"] == "mde_for_fixed_n":
            assert abs(power - TARGET_POWER) < 1e-9
        else:
            assert power >= TARGET_POWER
            assert row["power_at_n_minus_one"] < TARGET_POWER
        checks.append({"check": f"boundary:{row['record_type']}:{row['planning_family']}:"
                                f"{row['participants_n']}:{row['paired_sd_pp']}:{row['effect_pp']}",
                       "passed": True})
    for n, effect, sd, alpha in ((10, 5.0, 10.0, 0.05), (21, 3.0, 15.0, 0.05),
                                (60, 5.0, 10.0, 0.05 / 3), (85, 3.0, 10.0, 0.05),
                                (87, 3.0, 5.0, 0.025)):
        exact = paired_t_power(n, effect, sd, alpha)
        independent = independent_power_quadrature(n, effect, sd, alpha)
        assert abs(exact - independent) < 1e-8
        checks.append({"check": "normal_chisquare_independent_quadrature", "n": n,
                       "effect_pp": effect, "sd_pp": sd, "alpha": alpha,
                       "noncentral_t_power": exact, "quadrature_power": independent,
                       "absolute_difference": abs(exact - independent), "passed": True})
    assert abs(paired_t_power(21, 0, 10, 0.05) - 0.05) < 1e-12
    checks.append({"check": "null_rejection_probability_equals_alpha", "passed": True})
    assert paired_t_power(60, 3, 10) > paired_t_power(21, 3, 10)
    checks.append({"check": "more_independent_participants_increases_power", "passed": True})
    return {"all_passed": True, "check_count": len(checks), "checks": checks,
            "method": "noncentral t; independently verified normal/chi-square mixture integral",
            "eeg_data_read": False, "model_fits_started": 0, "target_predictions_computed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "results")
    args = parser.parse_args()
    rows = make_rows()
    verification = verify(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "power_sensitivity.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification["csv_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    (args.output_dir / "power_sensitivity_verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"planning_rows": len(rows), "validation_checks": verification["check_count"],
                      "all_passed": True, "csv_sha256": verification["csv_sha256"],
                      "model_fits_started": 0, "target_predictions_computed": False}))


if __name__ == "__main__":
    main()
