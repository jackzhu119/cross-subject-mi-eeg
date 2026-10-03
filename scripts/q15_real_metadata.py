"""Deterministic real-MAT audit for the declared Q15 operational revision.

Metadata only: no filtering, processed EEG writes, models, fits or outcomes.
Native exported voltage calibration remains explicitly unverified. Passing this
audit verifies originals and the operational input contract, never calibration.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research_runs/Q15-EXECUTION-20261003"
EXECUTION = BASE / "EXECUTION_CONTRACT.json"
TRANSPORT = ROOT / "research_runs/Q15-PREPARATION/transport_inventory.json"
CHO_CHANNELS = json.loads((BASE / "evidence/cho_channel_map.json").read_text())["channel_names"]
_CACHE: dict[tuple, dict] = {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def digest_original(path: Path) -> dict:
    sha, md5 = hashlib.sha256(), hashlib.md5()
    size = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            sha.update(block); md5.update(block); size += len(block)
    return {"sha256": sha.hexdigest(), "md5": md5.hexdigest(), "size_bytes": size}


def execution_contract() -> dict:
    value = json.loads(EXECUTION.read_text())
    if value.get("schema_version") != 1 or value.get("target_fits") != 0:
        raise AssertionError("Q15 operational contract identity changed")
    transform = value["shared_transform"]
    if transform.get("analysis_input_unit_convention") != "native_numeric_as_microvolts" or transform.get("native_export_units_verified") is not False:
        raise AssertionError("Unknown calibration cannot be declared verified")
    for name, expected in value["evidence_sha256"].items():
        if Path(name).name != name or sha256(BASE / "evidence" / name) != expected:
            raise AssertionError("Primary/secondary provider evidence changed")
    return value


def _identity(dataset: str, file_id: str) -> tuple[int, int, str]:
    if dataset == "Cho2017":
        match = re.fullmatch(r"s(\d{2})\.mat", file_id)
        if match and 1 <= int(match[1]) <= 52:
            return int(match[1]), 1, "retained_labeled_MI"
    elif dataset == "Lee2019_MI":
        match = re.fullmatch(r"session([12])/s([1-9]\d?)/sess0([12])_subj(\d{2})_EEG_MI\.mat", file_id)
        if match and match[1] == match[3] and int(match[2]) == int(match[4]) and 1 <= int(match[2]) <= 54:
            return int(match[2]), int(match[1]), "offline_train"
    raise ValueError("Unknown provider file identity")


def _integers(values, name):
    values = np.asarray(values).reshape(-1)
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values) or not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError("Noninteger native " + name)
    if np.any(values < -(2 ** 63)) or np.any(values >= 2 ** 63):
        raise ValueError("Native integer exceeds sample representation: " + name)
    return values.astype(np.int64)


def _integer_scalar(value, name):
    values = _integers(value, name)
    if len(values) != 1:
        raise ValueError("Native scalar expected: " + name)
    return int(values[0])


def _strings(values):
    return [str(np.asarray(item).squeeze().item()) for item in np.asarray(values).ravel()]


def _finite(array, sample_axis):
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError("Nonnumeric native EEG")
    for start in range(0, array.shape[sample_axis], 65536):
        region = [slice(None)] * array.ndim
        region[sample_axis] = slice(start, start + 65536)
        if not np.isfinite(array[tuple(region)]).all():
            raise ValueError("Nonfinite native EEG sample")


def audit_raw_file(path: Path, dataset: str, file_id: str) -> dict:
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Original MAT unavailable")
    subject, session, run = _identity(dataset, file_id)
    protocol = execution_contract()
    actual = digest_original(path)  # Rehash bytes even when decoded metadata is cached.
    cache_key = (str(path), dataset, file_id, actual["sha256"], sha256(Path(__file__)), sha256(EXECUTION))
    if cache_key in _CACHE:
        return copy.deepcopy(_CACHE[cache_key])
    common = {
        "file_id": file_id, "path": str(path), **actual,
        "subject": subject, "session": session, "run": run,
        "physical_run_identity": None if dataset == "Cho2017" else "EEG_MI_train",
        "native_physical_unit": "provider MAT numeric unit unverified; prospective native-uV analysis convention",
        "native_numeric_calibration_verified": False,
        "declared_analysis_unit": "uV", "loader_output_unit": "V",
        "unit_conversion": "declared numeric uV convention * 1e-6 to V; uniform processor returns uV; not export calibration evidence",
        "cue_origin": "MI_cue_onset", "hardware_cue_latency_verified": False,
        "task": "left_right_motor_imagery", "labeled": True,
        "label_map": {"left_hand": 1, "right_hand": 2},
        "available_cue_window_s": [-1.5, 4.5],
        "context_bounds_verified": True,
        "execution_contract_sha256": sha256(EXECUTION),
        "no_outcomes_inspected": True,
    }
    events = []
    required_channels = protocol["shared_transform"]["channels"]
    if dataset == "Lee2019_MI":
        mat = loadmat(path, variable_names=["EEG_MI_train"], mat_dtype=True)
        train = mat["EEG_MI_train"][0, 0]
        rate = _integer_scalar(train["fs"], "fs")
        x = train["x"]
        channels = _strings(train["chan"])
        times, labels = _integers(train["t"], "t"), _integers(train["y_dec"], "y_dec")
        classes = {int(_strings(row[:1])[0]): _strings(row[1:])[0].lower() for row in train["class"]}
        if rate != 1000 or x.ndim != 2 or x.shape[1] != 62 or len(channels) != 62 or len(set(channels)) != 62:
            raise ValueError("Lee native signal/channel/rate contract failed")
        if classes != {1: "right", 2: "left"} or len(times) != 100 or len(labels) != 100:
            raise ValueError("Lee class definitions/cue inventory failed")
        if np.any(np.diff(times) <= 0) or {int(c): int(n) for c, n in zip(*np.unique(labels, return_counts=True))} != {1: 50, 2: 50}:
            raise ValueError("Lee cue uniqueness/class counts failed")
        if _strings(train["y_class"]) != [classes[int(label)] for label in labels]:
            raise ValueError("Lee string/numeric label disagreement")
        logic = np.asarray(train["y_logic"])
        if logic.shape != (2, 100) or not np.isin(logic, (0, 1)).all() or not np.all(logic.sum(axis=0) == 1) or not np.array_equal(logic.argmax(axis=0) + 1, labels):
            raise ValueError("Lee one-hot/numeric label disagreement")
        _finite(x, 0)
        segmented = train["smt"]
        if segmented.shape != (4000, 100, 62):
            raise ValueError("Lee provider segment shape differs")
        matches = 0
        for ordinal, (stored, native_label) in enumerate(zip(times, labels), 1):
            cue = int(stored) - 1  # Explicit primary MATLAB index convention.
            start, stop = cue - 1500, cue + 4500
            if start < 0 or stop > x.shape[0]:
                raise ValueError("Lee complete shared context unavailable")
            matches += int(np.array_equal(segmented[:, ordinal - 1, :], x[int(stored):int(stored) + 4000]))
            canonical = 2 if int(native_label) == 1 else 1
            events.append({"sample_id": f"s{subject:02d}_{session}_offline_train_t{ordinal:03d}",
                           "onset_sample": cue, "label": "left_hand" if canonical == 1 else "right_hand",
                           "canonical_label": canonical, "native_code": int(native_label), "trial_ordinal": ordinal})
        if matches != 100:
            raise ValueError("Lee x/smt exporter alignment drifted")
        common.update({"run_role": "offline_train", "sampling_rate_hz": rate, "channels": channels,
                       "channel_origin": "actual EEG_MI_train.chan bytes", "signal_shape": list(x.shape),
                       "signal_n_samples": int(x.shape[0]), "task_duration_s": 4,
                       "reference": "paper acquisition nasion; fixed prospective common_average_21",
                       "native_label_map": {"right_hand": 1, "left_hand": 2},
                       "cue_index_convention": "MATLAB t minus one; supplied smt begins at Python t and differs by one sample",
                       "provider_smt_alignment_python_t_matches": matches})
    else:
        eeg = loadmat(path, variable_names=["eeg"], simplify_cells=True)["eeg"]
        rate = _integer_scalar(eeg["srate"], "srate")
        n_trials = _integer_scalar(eeg["n_imagery_trials"], "n_imagery_trials")
        expected_trials = 120 if subject in (7, 9, 46) else 100
        left, right = eeg["imagery_left"], eeg["imagery_right"]
        marker = _integers(eeg["imagery_event"], "imagery_event")
        onsets = np.flatnonzero(marker)
        if rate != 512 or n_trials != expected_trials or left.shape != right.shape or left.shape != (68, 3584 * n_trials):
            raise ValueError("Cho native class array/count contract failed")
        if len(marker) != left.shape[1] or not np.isin(marker, (0, 1)).all() or not np.array_equal(onsets, 1023 + np.arange(n_trials) * 3584):
            raise ValueError("Cho retained marker/chunk contract failed")
        if np.asarray(eeg["frame"]).ravel().tolist() != [-2000, 5000]:
            raise ValueError("Cho retained frame contract failed")
        _finite(left, 1); _finite(right, 1)
        for canonical in (1, 2):
            for ordinal, cue in enumerate(onsets, 1):
                chunk_start = (ordinal - 1) * 3584
                if int(cue) - 768 < chunk_start or int(cue) + 2304 > chunk_start + 3584:
                    raise ValueError("Cho shared context crosses an artificial trial boundary")
                events.append({"sample_id": f"s{subject:02d}_1_retained_{canonical}_t{ordinal:03d}",
                               "onset_sample": int(cue), "label": "left_hand" if canonical == 1 else "right_hand",
                               "canonical_label": canonical, "native_code": canonical,
                               "trial_ordinal": ordinal, "class_ordinal": ordinal})
        common.update({"run_role": "offline_labeled", "sampling_rate_hz": rate, "channels": list(CHO_CHANNELS),
                       "channel_origin": "official paper Figure1 numbered montage, reviewed prospective row-map assumption",
                       "channel_name_field_in_mat": False, "signal_shape": list(left.shape),
                       "signal_n_samples": int(left.shape[1]), "task_duration_s": 3,
                       "reference": "original MAT reference unverified; fixed prospective common_average_21",
                       "original_reference_verified": False, "physical_run_reconstruction_verified": False,
                       "native_label_map": {"left_hand": 1, "right_hand": 2},
                       "cue_index_convention": "zero-based imagery_event nonzero marker; retained local index1023",
                       "retained_trial_samples": 3584, "trials_per_class": n_trials})
    if not set(required_channels).issubset(common["channels"]):
        raise ValueError("Required ordered source channels absent")
    common["events"] = events
    common["n_labeled_trials"] = len(events)
    _CACHE[cache_key] = copy.deepcopy(common)
    return common


def authenticated_inventory(dataset: str) -> dict:
    """Reconcile pinned official records, complete IDs and transport hashes."""
    execution_contract()  # Verifies exact archived official evidence bytes.
    name = "cho_transfer_manifest.json" if dataset == "Cho2017" else "lee_transfer_manifest.json"
    provider = json.loads((BASE / "evidence" / name).read_text())
    if provider.get("dataset") != dataset:
        raise AssertionError("Provider dataset mismatch")
    expected = [f"s{s:02d}.mat" for s in range(1, 53)] if dataset == "Cho2017" else [
        f"session{session}/s{s}/sess0{session}_subj{s:02d}_EEG_MI.mat" for session in (1, 2) for s in range(1, 55)]
    files = provider["files"]
    if len(files) != len(expected) or set(provider["expected_file_ids"]) != set(expected) or {f["file_id"] for f in files} != set(expected):
        raise AssertionError("Official complete cohort inventory failed")
    transport = {f["file_id"]: f for f in json.loads(TRANSPORT.read_text())["files"] if f["dataset"] == dataset}
    if set(transport) != set(expected):
        raise AssertionError("Transport cohort differs from official inventory")
    official_md5 = {}
    if dataset == "Lee2019_MI":
        for line in (BASE / "evidence/100542.md5").read_text().splitlines():
            match = re.fullmatch(r"([0-9a-fA-F]{32})\s+\*?\.?/?(.*)", line.strip())
            if match:
                official_md5[match[2]] = match[1].lower()
    result = {}
    for row in files:
        file_id = row["file_id"]
        actual = transport[file_id]
        _identity(dataset, file_id)
        if row["size_bytes"] != actual["size_bytes"]:
            raise AssertionError("Official/transport original size mismatch")
        md5 = row.get("provider_md5")
        if dataset == "Lee2019_MI" and official_md5.get(file_id) != md5:
            raise AssertionError("Official Lee checksum record mismatch")
        if md5 and md5 != actual["md5"]:
            raise AssertionError("Official original MD5 mismatch")
        if dataset == "Cho2017" and not md5 and file_id not in {"s07.mat", "s09.mat", "s46.mat"}:
            raise AssertionError("Unexpected missing provider checksum")
        result[file_id] = {**actual, "provider_checksum_kind": row.get("checksum_kind", "official_md5"),
                           "provider_content_md5_available": bool(md5)}
    return {"dataset": dataset, "provider_version": provider["provider_version"], "license": provider["license"],
            "provider_inventory_source": provider.get("provider_inventory_source") or provider["source_refs"]["official_file_api"],
            "expected_file_ids": expected, "files": result}


def build_manifests(raw_dir: Path, output_dir: Path) -> dict[str, Path]:
    raw_dir, output_dir = Path(raw_dir).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for dataset in ("Cho2017", "Lee2019_MI"):
        provider = authenticated_inventory(dataset)
        files = []
        for file_id in provider["expected_file_ids"]:
            subject, session, run = _identity(dataset, file_id)
            expected = provider["files"][file_id]
            files.append({"file_id": file_id, "path": str(raw_dir / dataset / file_id),
                          "sha256": expected["sha256"], "subject": subject, "session": session,
                          "run": run, "adapter": "real_mat_operational_v1"})
        payload = {"schema_version": 1, "dataset": dataset,
                   "provider_version": provider["provider_version"], "license": provider["license"],
                   "loader_version": "Q15-native-MAT-operational-v1", "provider_inventory_source": provider["provider_inventory_source"],
                   "expected_file_ids": provider["expected_file_ids"], "files": files}
        target = output_dir / (dataset + "_provider_inventory.json")
        target.write_text(json.dumps(payload, indent=2) + "\n")
        manifests[dataset] = target
    return manifests


def audit_inventory(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    dataset = manifest["dataset"]
    provider = authenticated_inventory(dataset)
    rows = manifest["files"]
    if manifest.get("schema_version") != 1 or manifest.get("expected_file_ids") != provider["expected_file_ids"] or len(rows) != len(provider["files"]) or {r["file_id"] for r in rows} != set(provider["files"]):
        raise AssertionError("Caller manifest differs from independently authenticated complete inventory")
    result = {"schema_version": 1, "dataset": dataset, "status": "blocked_real_raw_metadata",
              "metadata_only": True, "predictions_computed": False, "model_predictions_computed": False,
              "performance_metrics_computed": False, "target_fits": 0,
              "external_prediction_authorized": False, "source_training_authorized": False,
              "synthetic_fixture": False, "raw_hashes_verified": False,
              "provider_inventory_verified": True, "provider_manifest_authenticated": True,
              "all_expected_files_hashed": False, "native_numeric_calibration_verified": False,
              "declared_analysis_convention": "native numeric microvolts; physical export calibration not verified",
              "auditor_sha256": sha256(ROOT / "scripts/q15_metadata_audit.py"),
              "raw_adapter_sha256": sha256(Path(__file__)), "execution_contract_sha256": sha256(EXECUTION),
              "provider_manifest_path": str(manifest_path), "provider_manifest_sha256": sha256(manifest_path),
              "expected_file_ids": provider["expected_file_ids"], "files": [], "failed_files": [], "blocking_reasons": [],
              "provider_version": provider["provider_version"], "loader_version": "Q15-native-MAT-operational-v1",
              "license": provider["license"], "provider_inventory_source": provider["provider_inventory_source"]}
    for row in rows:
        file_id = row["file_id"]
        try:
            subject, session, run = _identity(dataset, file_id)
            expected = provider["files"][file_id]
            if row.get("adapter") != "real_mat_operational_v1" or row.get("sha256") != expected["sha256"] or (row.get("subject"), row.get("session"), row.get("run")) != (subject, session, run):
                raise AssertionError("Manifest file hash or identity changed")
            path = Path(row["path"])
            if not path.is_absolute() or path.is_symlink():
                raise AssertionError("Original path is not declared absolute regular file")
            metadata = audit_raw_file(path, dataset, file_id)
            if any(metadata[key] != expected[key] for key in ("sha256", "md5", "size_bytes")):
                raise AssertionError("Actual original bytes differ from authenticated transport snapshot")
            result["files"].append(metadata)
        except (OSError, ValueError, TypeError, KeyError, AssertionError) as exc:
            result["failed_files"].append(file_id)
            result["blocking_reasons"].append("real_raw_audit_failed:" + file_id + ":" + type(exc).__name__)
    result["n_files"] = len(rows)
    result["n_subjects"] = len({row["subject"] for row in result["files"]})
    if not result["failed_files"]:
        expected_trials = 10520 if dataset == "Cho2017" else 10800
        if sum(row["n_labeled_trials"] for row in result["files"]) != expected_trials:
            raise AssertionError("Complete labeled trial inventory changed")
        result.update({"status": "metadata_passed_non_authorizing", "raw_hashes_verified": True,
                       "all_expected_files_hashed": True, "n_labeled_trials": expected_trials,
                       "calibration_limitations_must_be_reported": True})
    return result
