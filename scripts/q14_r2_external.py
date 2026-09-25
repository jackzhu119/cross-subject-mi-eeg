"""Metadata-gated external EDF harmonization for Q14-E002R2 only.

The frozen Q14-E002 loader remains untouched. Only the nine predeclared
128-Hz runs use a native-rate epoch followed by 5/4 polyphase resampling.
No target label or prediction is used to select a preprocessing branch.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import mne
import numpy as np
import pandas as pd
from mne.datasets import eegbci
from scipy.signal import resample_poly

from scripts import q14_external
from scripts.q14_source import sha256


def expected_rate(subject: int, amendment: dict) -> int:
    if subject not in range(88, 110):
        raise AssertionError("R2 may fetch only the remaining S088--S109 subjects")
    anomalies = amendment["native_128_hz_subjects"]
    if anomalies != [88, 92, 100]:
        raise AssertionError("The pre-outcome native-rate cohort changed")
    return 128 if subject in anomalies else 160


def _files_by_run(subject: int, data_dir: Path, runs: list[int]) -> dict[int, Path]:
    files = None
    for attempt in range(1, 5):
        try:
            files = eegbci.load_data(
                subjects=subject,
                runs=runs,
                path=str(data_dir),
                update_path=False,
                verbose="ERROR",
            )
            break
        except (OSError, TimeoutError, ConnectionError) as exc:
            if attempt == 4:
                raise
            print(
                f"S{subject:03d}: download attempt {attempt} failed ({type(exc).__name__}); retry",
                flush=True,
            )
            time.sleep(10 * attempt)
    assert files is not None
    by_run: dict[int, Path] = {}
    for file in map(Path, files):
        match = re.fullmatch(rf"S{subject:03d}R(\d{{2}})\.edf", file.name, re.IGNORECASE)
        if match is None or int(match.group(1)) not in runs:
            raise AssertionError(f"Unexpected external EDF path: {file}")
        run = int(match.group(1))
        if run in by_run:
            raise AssertionError(f"Duplicate external EDF run S{subject:03d}R{run:02d}")
        by_run[run] = file
    if set(by_run) != set(runs):
        raise AssertionError(f"Missing external EDF run for S{subject:03d}")
    return by_run


def preflight_remaining(
    data_dir: Path, config: dict, amendment: dict, official: dict[str, str]
) -> list[dict]:
    """Download/hash/header-check 66 EDFs before scoring any new subject."""
    if config["external_runs"] != amendment["external_runs"] or config["common_rate_hz"] != 160:
        raise AssertionError("Frozen external run/rate contract differs from R2 amendment")
    if amendment["copied_subjects_inclusive"] != [1, 87] or amendment["new_subjects_inclusive"] != [
        88,
        109,
    ]:
        raise AssertionError("R2 custody boundary differs")
    records = []
    for subject in range(88, 110):
        by_run = _files_by_run(subject, data_dir, config["external_runs"])
        for run in config["external_runs"]:
            file = by_run[run]
            digest = sha256(file)
            if digest != official.get(file.name):
                raise AssertionError(f"Official PhysioNet SHA-256 mismatch: {file.name}")
            raw = mne.io.read_raw_edf(file, preload=False, verbose=False)
            try:
                eegbci.standardize(raw)
                rate = float(raw.info["sfreq"])
                if rate != expected_rate(subject, amendment):
                    raise AssertionError(f"Unexpected native rate {rate} Hz: {file.name}")
                if not set(config["channels"]).issubset(raw.ch_names):
                    raise AssertionError(f"Missing frozen channel(s): {file.name}")
                if set(raw.get_channel_types(picks=config["channels"])) != {"eeg"}:
                    raise AssertionError(f"Non-EEG frozen channel: {file.name}")
                records.append(
                    {
                        "subject": subject,
                        "run": run,
                        "filename": file.name,
                        "bytes": file.stat().st_size,
                        "sha256": digest,
                        "native_rate_hz": int(rate),
                        "resampled_to_160_hz": rate == 128.0,
                    }
                )
            finally:
                raw.close()
        print(f"S{subject:03d}: 3 official EDF headers/checksums verified", flush=True)
    if len(records) != 66 or sum(r["resampled_to_160_hz"] for r in records) != 9:
        raise AssertionError("R2 metadata preflight did not cover the frozen 66/9 EDFs")
    return records


def _resample_128_epoch(values: np.ndarray, config: dict) -> np.ndarray:
    if values.ndim != 3 or values.shape[1:] != (len(config["channels"]), 384):
        raise AssertionError(f"128-Hz native epoch shape differs: {values.shape}")
    out = resample_poly(values, up=5, down=4, axis=2).astype(np.float32)
    if out.shape != (len(values), len(config["channels"]), config["n_times"]):
        raise AssertionError(f"R2 resampled epoch shape differs: {out.shape}")
    out *= config["volts_to_microvolts"]
    if not np.isfinite(out).all():
        raise AssertionError("Nonfinite R2 resampled EEG")
    return np.ascontiguousarray(out)


def load_128_subject(
    subject: int,
    data_dir: Path,
    config: dict,
    amendment: dict,
    official: dict[str, str],
    preflight: list[dict],
) -> tuple[dict[str, np.ndarray], pd.DataFrame, list[dict]]:
    """Load only a predeclared 128-Hz subject, preserving native event samples."""
    if expected_rate(subject, amendment) != 128:
        raise AssertionError("The 128-Hz adapter was requested for a 160-Hz subject")
    record_by_run = {record["run"]: record for record in preflight if record["subject"] == subject}
    if set(record_by_run) != set(config["external_runs"]):
        raise AssertionError(f"Missing metadata preflight for S{subject:03d}")
    by_run = _files_by_run(subject, data_dir, config["external_runs"])
    chunks = {band: [] for band in config["bands_hz"]}
    metadata = []
    file_records = []
    native_config = {**config, "common_rate_hz": 128, "n_times": 384, "volts_to_microvolts": 1.0}
    for run in config["external_runs"]:
        file = by_run[run]
        prior = record_by_run[run]
        if (
            sha256(file) != official.get(file.name)
            or prior["sha256"] != official[file.name]
            or file.stat().st_size != prior["bytes"]
            or prior["native_rate_hz"] != 128
        ):
            raise AssertionError(f"128-Hz EDF differs from preflight/official: {file.name}")
        file_records.append(
            {key: prior[key] for key in ("subject", "run", "filename", "bytes", "sha256")}
        )
        raw = mne.io.read_raw_edf(file, preload=True, verbose=False)
        try:
            eegbci.standardize(raw)
            if raw.info["sfreq"] != 128 or not set(config["channels"]).issubset(raw.ch_names):
                raise AssertionError(f"128-Hz EDF header drift: {file.name}")
            raw.pick_channels(config["channels"], ordered=True, verbose=False)
            if raw.ch_names != config["channels"] or set(raw.get_channel_types()) != {"eeg"}:
                raise AssertionError(f"128-Hz EDF frozen channel contract drift: {file.name}")
            events, _ = mne.events_from_annotations(
                raw, event_id=config["external_event_map"], verbose=False
            )
            if len(events) < 2 or set(events[:, 2]) != {1, 2}:
                raise AssertionError(f"128-Hz EDF event contract drift: {file.name}")
            reference_labels = None
            for band in config["bands_hz"]:
                values, labels = q14_external._event_epochs(raw, native_config, band, events)
                if reference_labels is None:
                    reference_labels = labels
                elif not np.array_equal(labels, reference_labels):
                    raise AssertionError("R2 bands produced different event order")
                chunks[band].append(_resample_128_epoch(values, config))
            for trial, (event, label) in enumerate(zip(events, reference_labels), 1):
                metadata.append(
                    {
                        "sample_id": f"physio_s{subject:03d}_r{run:02d}_t{trial:03d}",
                        "subject": subject,
                        "run": run,
                        "trial": trial,
                        "label": int(label),
                        "event_sample": int(event[0]),
                    }
                )
        finally:
            raw.close()
    frame = pd.DataFrame(metadata)
    if frame.empty or frame["sample_id"].duplicated().any():
        raise AssertionError("Empty/duplicate R2 128-Hz trial metadata")
    arrays = {band: np.concatenate(parts, axis=0) for band, parts in chunks.items()}
    if any(
        values.shape != (len(frame), len(config["channels"]), config["n_times"])
        for values in arrays.values()
    ):
        raise AssertionError("R2 arrays and trial metadata differ")
    return arrays, frame, file_records
