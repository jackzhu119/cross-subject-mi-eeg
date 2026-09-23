"""Configuration-driven BNCI2014_001 epochs with auditable trial identity.

Filtering is a fixed, run-local transform. This module neither estimates a
cross-subject normalization nor fits a predictive or artifact-removal model.
"""

from __future__ import annotations

import json
import os
import warnings
from collections import Counter
from pathlib import Path

import mne
import numpy as np
import pandas as pd
from moabb.datasets import BNCI2014_001


def load_configured_epochs(
    subjects: list[int],
    data_dir: Path,
    preprocessing: dict,
    class_ids: dict[str, int],
) -> tuple[dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """Load the same selected trials in every configured frequency band.

    Returns band arrays shaped ``(trials, 22, samples)``, one aligned metadata
    row per trial, and one audit row per subject/session/run. Event positions
    are MAT trial starts; cue onset is two seconds later. ``trial_stop`` is
    exclusive. Include-all arrays are allocated once rather than duplicated
    by concatenation, which matters for full four-class filter banks.
    """

    if not subjects or len(set(subjects)) != len(subjects):
        raise ValueError("Provide a nonempty list of unique subjects")
    if any(subject not in range(1, 10) for subject in subjects):
        raise ValueError("BNCI2014_001 subjects must be integers from 1 through 9")
    valid_classes = {"left_hand": 1, "right_hand": 2, "feet": 3, "tongue": 4}
    if not class_ids or any(valid_classes.get(name) != code for name, code in class_ids.items()):
        raise ValueError("Class names and IDs must match the BNCI2014_001 event mapping")

    sfreq = float(preprocessing["sampling_rate_hz"])
    if sfreq != 250.0:
        raise ValueError("This loader preserves the dataset's native 250 Hz sample rate")
    bands = preprocessing["bands"]
    if not bands:
        raise ValueError("At least one frequency band is required")
    for name, limits in bands.items():
        if len(limits) != 2 or not 0 < limits[0] < limits[1] < sfreq / 2:
            raise ValueError(f"Invalid band {name}: {limits}")
    filter_config = preprocessing["filter"]
    if int(filter_config["order"]) != filter_config["order"] or filter_config["order"] < 1:
        raise ValueError("Filter order must be a positive integer")
    policy = preprocessing["artifact_policy"]
    if policy not in {"include_all", "exclude_flagged"}:
        raise ValueError(f"Unknown artifact policy: {policy}")
    reject_artifacts = policy == "exclude_flagged"
    trial_start = float(preprocessing["trial_start_s"])
    trial_stop = float(preprocessing["trial_stop_exclusive_s"])
    sample_start, sample_stop = trial_start * sfreq, trial_stop * sfreq
    if not all(
        np.isclose(value, round(value), atol=1e-9, rtol=0) for value in (sample_start, sample_stop)
    ):
        raise ValueError("Epoch boundaries must lie on the native sampling grid")
    if trial_stop <= trial_start:
        raise ValueError("Epoch stop must follow start")
    n_times = round(sample_stop - sample_start)
    baseline = preprocessing.get("baseline")
    if baseline is not None:
        baseline = tuple(baseline)

    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MNE_DATASETS_BNCI_PATH"] = str(data_dir)
    dataset = BNCI2014_001(artifact_handling="annotate_bad")
    selected_codes = set(class_ids.values())
    expected_per_run = 12 * len(class_ids)
    expected_total = len(subjects) * 2 * 6 * expected_per_run
    allocated = (
        {name: np.empty((expected_total, 22, n_times), dtype=np.float32) for name in bands}
        if not reject_artifacts
        else {}
    )
    chunks: dict[str, list[np.ndarray]] = {name: [] for name in bands}
    metadata_rows: list[dict] = []
    audit_rows: list[dict] = []
    channel_reference: tuple[str, ...] | None = None
    offset = 0

    for subject in subjects:
        print(f"Loading configured epochs for subject {subject} ...", flush=True)
        sessions = dataset.get_data(subjects=[subject])[subject]
        if set(sessions) != {"0train", "1test"}:
            raise AssertionError(f"Unexpected sessions for subject {subject}: {list(sessions)}")
        for session, runs in sorted(sessions.items()):
            if len(runs) != 6:
                raise AssertionError(f"Expected 6 runs: subject={subject}, session={session}")
            for run_name, raw in sorted(runs.items(), key=lambda item: int(item[0])):
                run = int(run_name)
                if raw.info["sfreq"] != sfreq:
                    raise AssertionError(
                        "Raw sampling rate differs from the configured native rate"
                    )
                channels = tuple(
                    name
                    for name, kind in zip(raw.ch_names, raw.get_channel_types())
                    if kind == "eeg"
                )
                if len(channels) != 22:
                    raise AssertionError(f"Expected 22 EEG channels, found {len(channels)}")
                if channel_reference is None:
                    channel_reference = channels
                elif channels != channel_reference:
                    raise AssertionError("EEG channel order changed across runs")

                events = mne.find_events(raw, stim_channel="STI", shortest_event=1, verbose=False)
                event_counts = Counter(events[:, 2].tolist())
                if event_counts != Counter({1: 12, 2: 12, 3: 12, 4: 12}):
                    raise AssertionError(
                        f"Unexpected events: subject={subject}, session={session}, run={run}: "
                        f"{event_counts}"
                    )
                sample_to_trial = {
                    int(sample): trial for trial, sample in enumerate(events[:, 0], 1)
                }
                flagged_trial_ids = {
                    int(extra["trial"])
                    for description, extra in zip(
                        raw.annotations.description, raw.annotations.extras
                    )
                    if description == "BAD_artifact" and extra is not None
                }
                candidates = events[np.isin(events[:, 2], list(selected_codes))]
                candidate_counts = Counter(int(label) for label in candidates[:, 2])
                flagged_counts = Counter(
                    int(label)
                    for sample, _, label in candidates
                    if sample_to_trial[int(sample)] in flagged_trial_ids
                )
                if len(candidates) != expected_per_run:
                    raise AssertionError("Candidate trial count differs from selected classes")
                n_flagged = sum(flagged_counts.values())
                expected_rejected = n_flagged if reject_artifacts else 0
                reference_events: np.ndarray | None = None

                for band_name, (low, high) in bands.items():
                    eeg_raw = raw.copy().pick("eeg")
                    if tuple(eeg_raw.ch_names) != channel_reference:
                        raise AssertionError("Selected EEG channel order changed")
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message=".*filter_length.*")
                        eeg_raw.filter(
                            l_freq=float(low),
                            h_freq=float(high),
                            method="iir",
                            iir_params={
                                "order": int(filter_config["order"]),
                                "ftype": filter_config["ftype"],
                            },
                            phase=filter_config["phase"],
                            verbose=False,
                        )
                    epochs = mne.Epochs(
                        eeg_raw,
                        events,
                        event_id=class_ids,
                        tmin=trial_start,
                        tmax=trial_stop - 1.0 / sfreq,
                        baseline=baseline,
                        reject_by_annotation=reject_artifacts,
                        preload=True,
                        verbose=False,
                    )
                    if expected_per_run - len(epochs) != expected_rejected:
                        raise AssertionError(
                            "Epoch rejection differs from selected source artifact flags: "
                            f"subject={subject}, session={session}, run={run}, band={band_name}"
                        )
                    if reference_events is None:
                        reference_events = epochs.events.copy()
                    elif not np.array_equal(reference_events, epochs.events):
                        raise AssertionError("Frequency bands selected different events or order")
                    values = epochs.get_data(copy=True).astype(np.float32)
                    if values.shape != (len(epochs), 22, n_times):
                        raise AssertionError(f"Unexpected epoch shape: {values.shape}")
                    if not np.isfinite(values).all():
                        raise AssertionError("Nonfinite EEG samples after filtering and epoching")
                    if reject_artifacts:
                        chunks[band_name].append(values)
                    else:
                        allocated[band_name][offset : offset + len(values)] = values
                    del values, epochs, eeg_raw

                if reference_events is None:
                    raise AssertionError("No frequency band was processed")
                kept_counts = Counter(int(label) for label in reference_events[:, 2])
                for sample, _, label in reference_events:
                    trial = sample_to_trial[int(sample)]
                    metadata_rows.append(
                        {
                            "sample_id": f"s{subject:02d}_{session}_r{run}_t{trial:02d}",
                            "subject": subject,
                            "session": session,
                            "run": run,
                            "trial": trial,
                            "label": int(label),
                            "event_sample": int(sample),
                            "artifact_flagged": trial in flagged_trial_ids,
                        }
                    )
                audit = {
                    "subject": subject,
                    "session": session,
                    "run": run,
                    "n_all_four_class_trials": len(events),
                    "n_candidate_trials": len(candidates),
                    "n_source_artifact_flags_all_classes": len(flagged_trial_ids),
                    "n_flagged_trials": n_flagged,
                    "n_rejected_trials": expected_rejected,
                    "n_kept_trials": len(reference_events),
                    "n_times_per_epoch": n_times,
                    "n_eeg_channels": len(channels),
                    "sampling_rate_hz": sfreq,
                    "artifact_policy": policy,
                    "class_counts_candidate": json.dumps(dict(sorted(candidate_counts.items()))),
                    "class_counts_flagged": json.dumps(
                        {code: flagged_counts[code] for code in sorted(selected_codes)}
                    ),
                    "class_counts_kept": json.dumps(
                        {code: kept_counts[code] for code in sorted(selected_codes)}
                    ),
                    "eeg_channel_names": json.dumps(channels),
                }
                for code in sorted(selected_codes):
                    audit[f"n_class_{code}_candidate"] = candidate_counts[code]
                    audit[f"n_class_{code}_flagged"] = flagged_counts[code]
                    audit[f"n_class_{code}_kept"] = kept_counts[code]
                audit_rows.append(audit)
                offset += len(reference_events)
        del sessions

    meta = pd.DataFrame(metadata_rows)
    audit = pd.DataFrame(audit_rows)
    if meta.empty or meta["sample_id"].duplicated().any():
        raise AssertionError("No selected trials or duplicate trial identifiers")
    if not reject_artifacts and offset != expected_total:
        raise AssertionError("Include-all trial count differs from preallocated capacity")
    arrays = (
        {name: np.concatenate(parts, axis=0) for name, parts in chunks.items()}
        if reject_artifacts
        else allocated
    )
    if any(values.shape != (len(meta), 22, n_times) for values in arrays.values()):
        raise AssertionError("Band arrays and metadata are not aligned")
    if len(meta) != int(audit["n_kept_trials"].sum()):
        raise AssertionError("Audit totals differ from selected metadata")
    if set(meta["subject"]) != set(subjects):
        raise AssertionError("A requested subject has no selected epochs")
    return arrays, meta, audit
