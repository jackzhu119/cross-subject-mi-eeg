"""Bounded source-only diagnostics; immutable scientific code and hashes."""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

REPORT_SHA = "a481ee98d6a1184dd6a696754b8c47a9a3bcfc6b92941393a90e7dcecbbd0a2b"
SELECTED = ("s02_1test_r2_t36", "s03_1test_r0_t06", "s07_0train_r0_t06")
MODES = {"native": None, "no_fma3": "FMA3", "no_avx2_fma3": "AVX2,FMA3"}


def candidate_rounding(crop, expected, array_hash):
    # Diagnostic copies only. Never returns replacement arrays to processing.
    import numpy as np
    base = np.ascontiguousarray(crop, dtype=np.float32)
    if array_hash(base) == expected:
        return {"already_matches": True, "candidates_checked": 0, "exact_reference_matches": []}
    flat = base.ravel()
    lo = np.nextafter(flat, np.float32(-np.inf))
    hi = np.nextafter(flat, np.float32(np.inf))
    lower = (lo.astype(np.float64) + flat.astype(np.float64)) / 2
    upper = (hi.astype(np.float64) + flat.astype(np.float64)) / 2
    distance = np.minimum(abs(crop.ravel() - lower), abs(crop.ravel() - upper))
    spacing = np.maximum(hi.astype(np.float64)-flat, flat.astype(np.float64)-lo)
    indices = np.argsort(distance / spacing, kind="stable")[:32]
    matches = []
    for rank, idx in enumerate(indices):
        for direction, value in (("down", lo[idx]), ("up", hi[idx])):
            alternative = base.copy()
            alternative.ravel()[idx] = value
            if array_hash(alternative) == expected:
                matches.append({"channel_index": int(idx // base.shape[1]), "time_index": int(idx % base.shape[1]),
                                "direction": direction, "candidate_rank": rank,
                                "distance_to_midpoint_in_float32_ULP": float(distance[idx] / spacing[idx]),
                                "changed_elements": 1, "adjacent_float32_steps": 1})
    return {"already_matches": False, "candidates_checked": len(indices)*2, "exact_reference_matches": matches,
            "interpretation": "Exact candidate hash can identify an output-byte delta, not its numerical root cause; no match is inconclusive"}


def trace(signal, cue, config, core):
    import numpy as np
    from scipy.signal import sosfilt_zi
    context = np.array(signal[:, cue-375:cue+1125], dtype=np.float64, copy=True)
    stages = {"native_context": core.array_hash(context)}
    context -= context.mean(axis=0, keepdims=True)
    stages["CAR19"] = core.array_hash(context)
    outputs, crops = {}, {}
    for band, limits in core.BANDS.items():
        sos = core.butter(4, limits, btype="bandpass", fs=250, output="sos")
        zi = sosfilt_zi(sos)
        filtered = core.sosfiltfilt(sos, context, axis=-1, padtype="odd", padlen=27)
        common = core.resample_poly(filtered, 16, 25, axis=-1, window=("kaiser", 5.0), padtype="constant", cval=0.0)
        crop = common[:, 320:640]
        output = np.ascontiguousarray(crop, dtype=np.float32)
        stages[band] = {"sos": core.array_hash(sos), "zi": core.array_hash(zi), "filtered_float64": core.array_hash(filtered),
                        "resampled_float64": core.array_hash(common), "crop_float64": core.array_hash(crop),
                        "final_float32": core.array_hash(output), "shape": list(output.shape), "dtype": output.dtype.str,
                        "strides": list(output.strides)}
        outputs[band], crops[band] = output, crop
    # Trace must match production exactly; diagnostic implementation never becomes scientific loader.
    production = core.transform_context19(signal, 250, cue, config, bounds=(0, signal.shape[1]))
    for band in outputs:
        if core.array_hash(outputs[band]) != core.array_hash(production[band]):
            raise ValueError("instrumented_trace_differs_from_unmodified_production")
    return stages, outputs, crops


def worker(a):
    import numpy as np
    import scipy
    import pandas
    if (np.__version__, scipy.__version__, pandas.__version__) != ("2.3.5", "1.17.0", "2.2.3"):
        raise ValueError("exact_runtime_required")
    sys.path.insert(0, str(a.checkout / "research_runs/REDESIGN_CLOUD_20261013/scripts"))
    from reconstruct_source_readonly import verify_science
    identities = verify_science()
    sys.path.insert(0, str(a.checkout / "research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts"))
    import core_source_inputs as c
    sys.path.insert(0, str(a.checkout / "src"))
    from mi_eeg.data.q15_context import _validated_bnci_runs, BNCI_CHANNELS
    receipt = json.loads((a.checkout / "research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json").read_text())
    csvpath = a.checkout / "research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints.csv"
    if c.file_hash(csvpath) != receipt["reference_sha256"]:
        raise ValueError("frozen_CSV_digest_changed")
    with csvpath.open() as f:
        rows = list(csv.DictReader(f))
    fingerprints = {r["source_sample_id"]: r for r in rows}
    if len(rows) != 2592 or len(fingerprints) != 2592:
        raise ValueError("frozen_ID_inventory_changed")
    config = json.loads((a.checkout / "research_runs/REDESIGN_CLOUD_20261013/config/experiment.json").read_text())
    raw = {r["filename"]: r for r in receipt["source_file_provenance"]["raw_files_verified"]}
    results = []
    for sample in SELECTED:
        subject, session, runpart, trialpart = sample.split("_")
        filename = "A" + subject[1:] + ("E" if session == "1test" else "T") + ".mat"
        path = a.data_dir / "bnci" / filename
        if path.is_symlink() or path.stat().st_size != raw[filename]["bytes"] or c.file_hash(path) != raw[filename]["sha256"]:
            raise ValueError("selected_original_bytes_changed")
        run_index, trial_index = int(runpart[1:]), int(trialpart[1:])-1
        run = _validated_bnci_runs(path)[run_index]
        signal = c.ordered_channels19(run["X"][:, :22].T, BNCI_CHANNELS)
        # One nearest preceding eligible trial is a matched control, chosen without outcome search.
        control = max(i for i in range(trial_index) if int(run["y"][i]) in (1, 2))
        for index, role in ((trial_index, "mismatch"), (control, "preceding_binary_control")):
            sid = f"{subject}_{session}_r{run_index}_t{index+1:02d}"
            if int(run["y"][index]) not in (1, 2) or sid not in fingerprints:
                raise ValueError("selected_trial_identity_changed")
            cue = int(run["trial"][index])-1+500
            stages, outputs, crops = trace(signal, cue, config, c)
            repeat = c.transform_context19(signal, 250, cue, config, bounds=(0, signal.shape[1]))
            checks, serialization = {}, {}
            for band, output in outputs.items():
                expected = fingerprints[sid][band + "_sha256"]
                checks[band] = {"expected": expected, "actual": c.array_hash(output), "matches": c.array_hash(output)==expected,
                                "repeat_identical": c.array_hash(output)==c.array_hash(repeat[band])}
                stream = io.BytesIO(); np.save(stream, output, allow_pickle=False); stream.seek(0)
                serialization[band] = c.array_hash(np.load(stream, allow_pickle=False))==c.array_hash(output)
            if not all(v["repeat_identical"] for v in checks.values()) or not all(serialization.values()):
                raise ValueError("repeat_or_serialization_not_identical")
            if a.worker == "native":
                if not checks["broad"]["matches"] or not checks["beta"]["matches"] or checks["mu"]["matches"] != (role != "mismatch"):
                    raise ValueError("native_selected_trials_do_not_reproduce_prior_report")
            results.append({"sample_id": sid, "role": role, "raw_sha256": raw[filename]["sha256"], "stages": stages,
                            "checks": checks, "npy_roundtrip_identical": serialization,
                            "mu_rounding_hypothesis": candidate_rounding(crops["mu"], fingerprints[sid]["mu_sha256"], c.array_hash)})
    build = io.StringIO()
    with contextlib.redirect_stdout(build):
        np.show_config()
        scipy.show_config()
    return {"python": sys.version, "build_config": build.getvalue(),
            "numerical_environment": {k: os.environ.get(k) for k in ("OPENBLAS_CORETYPE", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "SCIPY_ARRAY_API")},
            "status": "DIAGNOSTIC_ONLY_TRAINING_BLOCKED", "mode": a.worker, "frozen_file_identities": identities,
            "enabled_cpu_features": sorted(k for k,v in np._core._multiarray_umath.__cpu_features__.items() if v),
            "NPY_DISABLE_CPU_FEATURES": os.environ.get("NPY_DISABLE_CPU_FEATURES"), "results": results,
            "raw_files_read": 3, "trials_per_mode": 6, "new_fits": 0, "target_EEG_read": False,
            "frozen_arrays_modified": False, "training_authorization": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkout", required=True, type=Path)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--prior-report", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--worker", choices=MODES)
    a = p.parse_args()
    if hashlib.sha256(a.prior_report.read_bytes()).hexdigest() != REPORT_SHA:
        raise ValueError("exact_prior_mismatch_report_required")
    if a.output_dir.resolve().is_relative_to(a.checkout.resolve()) or a.output_dir.resolve().is_relative_to(a.data_dir.resolve()):
        raise ValueError("diagnostics_must_be_outside_science_and_raw_cache")
    if a.worker:
        report = worker(a)
        with (a.output_dir / (a.worker + ".json")).open("x") as f:
            json.dump(report, f, indent=2); f.write("\n")
        return
    if os.environ.get("NPY_DISABLE_CPU_FEATURES"):
        raise ValueError("existing_CPU_override_requires_review")
    a.output_dir.mkdir(parents=False, exist_ok=False)
    statuses = []
    for mode, disabled in MODES.items():
        env = os.environ.copy()
        if disabled is not None:
            env["NPY_DISABLE_CPU_FEATURES"] = disabled
        cmd = [sys.executable, str(Path(__file__).resolve()), "--checkout", str(a.checkout), "--data-dir", str(a.data_dir),
               "--prior-report", str(a.prior_report), "--output-dir", str(a.output_dir), "--worker", mode]
        with (a.output_dir / (mode + ".log")).open("x") as log:
            try:
                result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                status = {"mode": mode, "exit_code": result.returncode, "timeout": False}
            except subprocess.TimeoutExpired:
                status = {"mode": mode, "exit_code": None, "timeout": True}
        statuses.append(status)
        with (a.output_dir / (mode + "-supervision.json")).open("x") as f:
            json.dump(status, f, indent=2)
        if status["exit_code"] != 0:
            raise SystemExit(2)
    baseline = json.loads((a.output_dir / "native.json").read_text())
    comparisons = {}
    for mode in ("no_fma3", "no_avx2_fma3"):
        other = json.loads((a.output_dir / (mode + ".json")).read_text())
        if any(feature in other["enabled_cpu_features"] for feature in MODES[mode].split(",")):
            raise ValueError("CPU_intervention_not_effective")
        comparisons[mode] = []
        for before, after in zip(baseline["results"], other["results"]):
            if before["sample_id"] != after["sample_id"]:
                raise ValueError("comparison_sample_identity_changed")
            order = [("native_context", before["stages"]["native_context"], after["stages"]["native_context"]),
                     ("CAR19", before["stages"]["CAR19"], after["stages"]["CAR19"])]
            order += [("mu." + k, before["stages"]["mu"][k], after["stages"]["mu"][k]) for k in
                      ("sos", "zi", "filtered_float64", "resampled_float64", "crop_float64", "final_float32")]
            comparisons[mode].append({"sample_id": before["sample_id"],
                "first_changed_mu_stage": next((name for name,x,y in order if x != y), None),
                "mu_reference_match": after["checks"]["mu"]["matches"]})
    with (a.output_dir / "comparison.json").open("x") as f:
        json.dump(comparisons, f, indent=2)
    with (a.output_dir / "completion.json").open("x") as f:
        json.dump({"status": "DIAGNOSTIC_COMPLETE_NOT_TRAINING_PERMISSION", "workers": statuses, "new_fits": 0}, f, indent=2)


if __name__ == "__main__":
    main()
