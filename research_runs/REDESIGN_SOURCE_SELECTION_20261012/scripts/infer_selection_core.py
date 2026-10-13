#!/usr/bin/env python3
"""Future, separately gated target inference; default reads no target EEG.

This is software preparation, not completed independent validation. Execution
requires a public immutable pre-inference freeze, independently validated source
models, a qualified full-cohort raw-only roster, genuine author first-use facts,
and separately authorized live GPU inference. No target fitting, normalization,
BatchNorm updating, selector revision, downloads, scoring, or publication occurs.
"""
from __future__ import annotations

import argparse
import collections
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
CONFIG = STUDY / "config/core_experiment_v1.json"
DATA_GATE = STUDY / "evidence/core_data_gate.json"
RUNTIME_LOCK = STUDY / "evidence/core_runtime_lock.json"
FREEZE = STUDY / "evidence/core_preinference_freeze.json"
AUTHORIZATION = STUDY / "evidence/target_inference_authorization.json"
REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
ARCH_MAP = {"BROAD_EEGNET": "broad", "MU_BETA_SHARED": "shared"}
SELECTOR_MAP = {"fixed20": "fixed", "mean_loss": "mean_loss", "mean_rank": "mean_rank"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 ** 2), b""):
            digest.update(block)
    return digest.hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def regular_path(name, base=ROOT, within=STUDY):
    require(isinstance(name, str) and name and not Path(name).is_absolute() and ".." not in Path(name).parts,
            "Artifact must use a non-traversing repository-relative path")
    path = base / name
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(within.resolve()),
            "Artifact absent, redirected, or outside the new study: " + name)
    for parent in path.parents:
        if parent == base:
            break
        require(not parent.is_symlink(), "Artifact ancestor is a symlink: " + name)
    return path


def read_json(path):
    require(Path(path).is_file() and not Path(path).is_symlink(), "Required regular JSON absent: " + Path(path).name)
    result = json.loads(Path(path).read_text())
    require(isinstance(result, dict), "JSON artifact must be an object")
    return result


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def artifact(gate, key):
    path = regular_path(gate.get(key + "_path"))
    expected = gate.get(key + "_sha256")
    require(isinstance(expected, str) and HASH.fullmatch(expected) and sha(path) == expected,
            "Authenticated artifact hash mismatch: " + key)
    return path


def subject_name(number):
    require(type(number) is int and 1 <= number <= 87, "Invalid global provider participant identity")
    return ("A" if number <= 60 else "B" if number <= 81 else "C") + f"{number:02d}"


def event_identity(number, run, ordinal):
    require(run in {"R1acquisition", "R2acquisition"} and type(ordinal) is int and 1 <= ordinal <= 40,
            "Unexpected acquisition run/event ordinal")
    return f"{subject_name(number)}_{run}_cue_{ordinal:02d}"


def verify_target_gate(config):
    from acquire_dreyer_runs import author_gate, verified_manifest_and_plan
    from analyze_redesign_scores import validate_contract
    from train_source_selection_core import verify_data_gate_envelope
    gate = verify_data_gate_envelope(config, read_json(DATA_GATE))
    for field in ("author_first_use_confirmation", "all_retained_target_files_verified",
                  "complete_acquisition_run_coverage_verified", "native_event_semantics_verified",
                  "physical_header_scale_verified", "genuine_channel_order_verified",
                  "cross_version_event_conversion_verified", "raw_only_roster_frozen", "duplicate_identity_audit_passed"):
        require(gate.get(field) is True, "Full data gate requires an actual Boolean audit judgment: " + field)
    require(gate.get("target_predictions_computed") is False and type(gate.get("target_fits")) is int
            and gate["target_fits"] == 0, "No prior target fits/predictions may open this first-inference gate")
    prior_path = artifact(gate, "author_prior_use")
    prior = author_gate(prior_path)  # Real author evidence required; never self-populated.
    require(gate.get("author_declaration_sha256") == prior["declaration_sha256"], "Author declaration binding mismatch")
    roster_path = artifact(gate, "roster")
    require(artifact(gate, "adapter").resolve() == Path(__file__).resolve(), "Full data gate names a different target adapter")
    raw_audit_path = artifact(gate, "raw_audit")
    access_path = artifact(gate, "acquisition_receipt")
    raw_audit, access = read_json(raw_audit_path), read_json(access_path)
    required = {"status": "PASS_RAW_ONLY_FULL_COHORT_QC", "target_predictions_computed": False, "target_fits": 0,
                "all_174_files_examined": True, "physical_header_scale_verified": True,
                "native_event_semantics_verified": True, "duplicate_identity_audit_passed": True,
                "participant_and_event_eligibility_frozen": True, "performance_used_for_eligibility": False,
                "config_sha256": sha(CONFIG), "roster_sha256": sha(roster_path)}
    for key, value in required.items():
        require(type(raw_audit.get(key)) is type(value) and raw_audit.get(key) == value,
                "Full raw-only audit missing/failed: " + key)
    require(access.get("all_declared_files_hash_header_event_audited") is True
            and access.get("target_predictions") == 0 and access.get("target_fits") == 0,
            "Complete acquisition byte/header/event audit is absent")
    manifest_rows, plan = verified_manifest_and_plan()
    access_files = {row.get("path"): row for row in access.get("files", [])}
    require(len(access_files) == len(access.get("files", [])) == 174 and set(access_files) == {r["path"] for r in manifest_rows},
            "All 174 provider acquisition identities must have raw audit coverage")
    for row in manifest_rows:
        actual = access_files[row["path"]]
        require(actual.get("sha256") == row["checksum"] and actual.get("size_bytes") == row["size"],
                "Acquisition receipt differs from pinned provider identity")
    roster = read_json(roster_path)
    require(roster.get("synthetic_fixture") is not True, "A fixture cannot qualify a real target cohort")
    people, _ = validate_contract(roster, False)
    require(roster.get("qualification") == gate["qualification"], "Cohort provenance qualification differs")
    require(raw_audit.get("retained_participants") == people, "QC and analysis retained participant rosters differ")
    by_path = {row["path"]: row for row in manifest_rows}
    counts = collections.Counter()
    seen_events = set()
    for item in roster["events"]:
        path_name = item.get("source_file")
        require(path_name in by_path, "Locked event is not in a registered acquisition EDF")
        from acquire_dreyer_runs import PATH_PATTERN
        match = PATH_PATTERN.fullmatch(path_name)
        number, run = int(match.group(1)), match.group(2)
        require(number not in (17, 41) and item.get("subject_id") == subject_name(number),
                "Event identity/montage exclusion differs from fixed provider map")
        ordinal, cue_sample = item.get("cue_ordinal"), item.get("cue_sample")
        require(item.get("event_id") == event_identity(number, run, ordinal), "Locked native event identity is inconsistent")
        require(type(cue_sample) is int and cue_sample >= 0 and item.get("native_sampling_hz") == 512,
                "Locked cue sample/rate must refer to native EDF grid")
        code = item.get("native_event_code")
        require(code in ("769", "770") and item["ytrue"] == int(code) - 769,
                "Verified native left/right mapping differs from analysis label")
        require(item.get("source_file_sha256") == by_path[path_name]["checksum"], "Locked event source hash differs")
        hashes = item.get("input_sha256", {})
        require(set(hashes) == {"broad", "mu", "beta"} and all(isinstance(h, str) and HASH.fullmatch(h) for h in hashes.values()),
                "Every eligible event needs pre-inference fingerprints for all three fixed inputs")
        require(item.get("epoch_sha256") == object_hash(hashes), "All-input event fingerprint differs from locked inputs")
        require(item["event_id"] not in seen_events, "Duplicate physical event identity")
        seen_events.add(item["event_id"])
        counts[(item["subject_id"], run)] += 1
    require(all(1 <= counts[(person, run)] <= 40 for person in people for run in plan["eligible_run_names"]),
            "Both genuine acquisition runs must cover every retained person")
    return {"gate": gate, "roster": roster, "roster_path": roster_path, "manifest_rows": manifest_rows,
            "required_paths": [DATA_GATE, prior_path, roster_path, raw_audit_path, access_path]}


def source_cells(source_dir):
    """Reconcile complete source trajectories, frozen selectors, aliases and weights."""
    from train_source_selection_core import ARCHITECTURES, schedule_cells, select_epochs
    source_dir = Path(source_dir).resolve()
    require(source_dir.is_relative_to((STUDY / "results").resolve()) and source_dir.is_dir(), "Source job must be inside this new study")
    completion = read_json(source_dir / "source_completion_manifest.json")
    validation = read_json(source_dir / "source_independent_validation.json")
    require(validation.get("status") == "PASS_SOURCE_ONLY_GRID_VALIDATION" and validation.get("target_predictions_computed") is False
            and validation.get("target_fits") == 0 and validation.get("source_completion_manifest_sha256") == sha(source_dir / "source_completion_manifest.json"),
            "Independent full source-grid validation is absent or unbound")
    require(completion.get("target_fits") == 0 and completion.get("target_predictions_computed") is False
            and completion.get("nominal_inner_fits") == 8 and completion.get("nominal_final_cells") == 18,
            "Source completion must cover exactly the prespecified source-only grid")
    paths = [source_dir / "source_completion_manifest.json", source_dir / "source_independent_validation.json",
             source_dir / "source19_input_audit.json", source_dir / "runtime_provenance.json", source_dir / "selected_epochs.json"]
    audit = read_json(source_dir / "source19_input_audit.json")
    require(audit.get("status") == "PASS_SOURCE19_INPUTS_ONLY" and audit.get("n_binary_trials") == 2592
            and audit.get("n_raw_files") == 18 and audit.get("target_eeg_read") is False,
            "New real 19-channel source-input audit is absent")
    selected = read_json(source_dir / "selected_epochs.json")
    config = read_json(CONFIG)
    output, real_fits, aliases = [], 8, 0
    for name in ARCHITECTURES:
        curves = []
        for fold, group in enumerate(config["source_validation_groups"], 1):
            directory = source_dir / "inner" / name / f"fold_{fold:02d}"
            curve_path, fit_path = directory / "source_curve.json", directory / "fit_receipt.json"
            curve = json.loads(curve_path.read_text())
            fit = read_json(fit_path)
            require(fit.get("status") == "completed" and fit.get("architecture") == name and fit.get("seed") == config["selection_seed"]
                    and fit.get("epochs") == 40 and fit.get("target_fit") is False
                    and fit.get("n_validation_trials") == 288 * len(group) and fit.get("n_training_trials") == 288 * (9 - len(group))
                    and fit.get("curve_sha256") == sha(curve_path), "Source validation trajectory receipt is incomplete")
            curves.append(curve)
            paths += [curve_path, fit_path, directory / "partition.json"]
        selection = select_epochs(curves, config["candidate_epochs"])
        require(selected.get(name) == selection and completion.get("selected_epochs", {}).get(name) == selection,
                "Immutable schedule does not reproduce equal-fold source selection")
        for cell in schedule_cells(name, selection, config["final_seeds"]):
            owner_dir = source_dir / "final" / cell["owner_cell"]
            checkpoint, fit_path = owner_dir / "checkpoint.pt", owner_dir / "fit_receipt.json"
            fit = read_json(fit_path)
            require(fit.get("status") == "completed" and fit.get("architecture") == name and fit.get("seed") == cell["seed"]
                    and fit.get("epochs") == cell["epochs"] and fit.get("n_training_trials") == 2592
                    and fit.get("n_validation_trials") == 0 and fit.get("target_fit") is False
                    and fit.get("configuration_sha256") == sha(CONFIG) and fit.get("checkpoint_sha256") == sha(checkpoint),
                    "Final source owner checkpoint/fit identity is incomplete")
            expected_updates = math.ceil(2592 / 64) * cell["epochs"]
            require(fit.get("optimizer_updates") == expected_updates, "All-source minibatch update count differs")
            if cell["alias"]:
                alias_path = source_dir / "final" / cell["cell"] / "alias_receipt.json"
                alias = read_json(alias_path)
                require(all(alias.get(k) == v for k, v in cell.items()) and alias.get("new_real_neural_fit") is False
                        and alias.get("owner_checkpoint_sha256") == fit["checkpoint_sha256"]
                        and alias.get("owner_model_state_sha256") == fit["model_state_sha256"], "Identical-schedule alias differs from real owner")
                aliases += 1
                paths.append(alias_path)
            else:
                real_fits += 1
            output.append({**cell, "model_arch": ARCH_MAP[name], "analysis_selector": SELECTOR_MAP[cell["selector"]],
                           "checkpoint_file": str(checkpoint.relative_to(ROOT)), "checkpoint_sha256": fit["checkpoint_sha256"],
                           "model_state_sha256": fit["model_state_sha256"], "source_only": True, "target_fit_count": 0})
            paths += [checkpoint, fit_path, owner_dir / "partition.json", owner_dir / "source_curve.json"]
    require(len(output) == 18 and completion.get("actual_new_neural_fits") == real_fits and completion.get("aliases") == aliases,
            "Source real-fit/alias accounting differs from complete nominal cells")
    require(completion.get("final_cells") == [{k: cell[k] for k in ("cell", "architecture", "selector", "seed", "epochs", "owner_cell", "alias")} for cell in output],
            "Source completion nominal cells differ from reconstructed selectors")
    return output, sorted(set(paths)), completion


def public_bytes(revision, name):
    from train_source_selection_core import public_source_bytes
    return public_source_bytes(revision, name)


def verify_freeze(paths, roster_path, source_manifest_path):
    freeze = read_json(FREEZE)
    revision = freeze.get("commit_sha")
    required = {"schema_version": 1, "status": "FROZEN_BEFORE_FIRST_TARGET_PREDICTION", "repository": REPOSITORY,
                "target_predictions_computed": False, "target_fits": 0,
                "roster_sha256": sha(roster_path), "source_manifest_sha256": sha(source_manifest_path)}
    for field, value in required.items():
        require(type(freeze.get(field)) is type(value) and freeze.get(field) == value, "Pre-inference freeze absent/invalid: " + field)
    require(isinstance(revision, str) and COMMIT.fullmatch(revision) and freeze.get("branch"), "An immutable full public commit is required")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"], check=True)
    frozen = freeze.get("files", {})
    required_paths = set(paths + [Path(__file__), HERE / "core_source_inputs.py", HERE / "train_source_selection_core.py",
                                  HERE / "analyze_redesign_scores.py", HERE / "acquire_dreyer_runs.py", HERE / "check_dreyer_metadata.py",
                                  CONFIG, RUNTIME_LOCK, STUDY / "PROSPECTIVE_VALIDATION_PROTOCOL.md", STUDY / "STATISTICAL_ANALYSIS_PLAN.md",
                                  STUDY / "DREYER_DATA_ACCESS_PLAN.json", STUDY / "evidence/dataset_sources/dreyer_nemar_manifest.txt"])
    for path in sorted(required_paths):
        name = path.relative_to(ROOT).as_posix()
        regular_path(name)
        expected = frozen.get(name)
        require(isinstance(expected, str) and HASH.fullmatch(expected) and sha(path) == expected, "Live artifact differs from pre-inference freeze: " + name)
        committed = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{name}"])
        require(hashlib.sha256(committed).hexdigest() == expected and hashlib.sha256(public_bytes(revision, name)).hexdigest() == expected,
                "Local/public immutable freeze differs: " + name)
    return freeze


def verify_authorization(receipt, runtime, current=None):
    current = current or datetime.now(timezone.utc)
    required = {"schema_version": 1, "status": "AUTHORIZED", "scope": "core_target_inference_v1",
                "authorization_kind": "explicit_author_approval", "config_sha256": sha(CONFIG),
                "preinference_freeze_sha256": sha(FREEZE), "machine_hostname": runtime["machine_hostname"], "gpu_uuid": runtime["gpu_uuid"],
                "target_fits_authorized": False, "target_predictions_authorized": True, "selector_changes_authorized": False}
    for field, value in required.items():
        require(type(receipt.get(field)) is type(value) and receipt.get(field) == value, "Separate target inference authorization missing: " + field)
    limits = {"remaining_maximum_gpu_hours": 8, "maximum_total_usd": 10, "approved_hourly_rate_usd": .75,
              "non_gpu_reserved_usd": 2, "total_previously_spent_usd": 10}
    for field, upper in limits.items():
        value = receipt.get(field)
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= upper, "Target budget field missing/exceeds proposal: " + field)
    require(receipt["remaining_maximum_gpu_hours"] > 0 and receipt["approved_hourly_rate_usd"] > 0
            and receipt.get("author_approval_record"), "Actual quote and explicit author record required")
    require(receipt["total_previously_spent_usd"] + receipt["remaining_maximum_gpu_hours"] * receipt["approved_hourly_rate_usd"]
            + receipt["non_gpu_reserved_usd"] <= receipt["maximum_total_usd"], "Source + inference total exceeds authorized experiment cap")
    for field in ("authorized_at_utc", "expires_at_utc"):
        stamp = datetime.fromisoformat(receipt.get(field, "").replace("Z", "+00:00"))
        require(stamp.tzinfo is not None and (stamp <= current if field == "authorized_at_utc" else stamp > current),
                "Target inference authorization timestamp invalid/expired")
    return receipt


def load_physical_edf(path, manifest_row):
    """Decode verified EDF records in declared physical µV, not MNE SI guesses."""
    import numpy as np
    from core_source_inputs import CHANNELS19
    from check_dreyer_metadata import parse_header, annotation_and_prefix
    require(Path(path).is_file() and not Path(path).is_symlink() and Path(path).suffix.lower() == ".edf", "Only regular registered source EDF accepted")
    require(Path(path).stat().st_size == manifest_row["size"] and sha(path) == manifest_row["checksum"], "EDF bytes differ from provider manifest")
    with Path(path).open("rb") as stream:
        fixed = stream.read(256)
    require(fixed[:8].strip() == b"0" and b"EDF+C" in fixed[192:236], "Only continuous EDF+C native sample timing implemented")
    header = parse_header(Path(path))
    channels = header["channels"]
    names = [channel["label"] for channel in channels]
    require(len(names) == len(set(names)) and set(CHANNELS19).issubset(names), "Required genuine channel names missing/duplicate")
    indices = [names.index(name) for name in CHANNELS19]
    selected = [channels[i] for i in indices]
    require(header["record_shape_verified"] and header["records"] > 0 and header["sample_bytes"] == 2, "Invalid continuous EDF record shape")
    require(all(c["sampling_frequency_hz"] == 512 and c["unit"] in ("uV", "µV") for c in selected), "Native required channels lack fixed rate/physical µV headers")
    for channel in selected:
        values = [channel[k] for k in ("physical_min", "physical_max", "digital_min", "digital_max")]
        require(np.isfinite(values).all() and values[0] < values[1] and values[2] < values[3], "Invalid EDF physical calibration range")
    offsets = np.r_[0, np.cumsum([c["samples_per_record"] * 2 for c in channels])]
    n = selected[0]["samples_per_record"]
    signal = np.empty((19, header["records"] * n), dtype=np.float64)
    with Path(path).open("rb") as stream:
        stream.seek(header["header_bytes"])
        for record in range(header["records"]):
            block = stream.read(int(offsets[-1]))
            require(len(block) == offsets[-1], "Truncated EDF native record")
            for output, index in enumerate(indices):
                c = channels[index]
                digital = np.frombuffer(block[int(offsets[index]):int(offsets[index + 1])], dtype="<i2").astype(np.float64)
                scale = (c["physical_max"] - c["physical_min"]) / (c["digital_max"] - c["digital_min"])
                signal[output, record * n:(record + 1) * n] = (digital - c["digital_min"]) * scale + c["physical_min"]
    require(np.isfinite(signal).all() and (np.ptp(signal, axis=1) > 0).all(), "Nonfinite/flatline required native channel blocks run")
    events, _ = annotation_and_prefix(Path(path), header)
    cues = [event for event in events if event["description"] in ("769", "770")]
    require(len(cues) == 40 and collections.Counter(e["description"] for e in cues) == {"769": 20, "770": 20}, "Native event counts differ from acquisition task")
    require(all(cues[i]["onset"] < cues[i + 1]["onset"] for i in range(39)), "Duplicate/nonordered physical cue onsets")
    require(sha(path) == manifest_row["checksum"], "EDF bytes changed during native signal read")
    return signal, header, cues


def prepare_target_inputs(cache_dir, target, config, guard=None):
    """Called only after every real execution gate; replay locked raw-only inputs."""
    import numpy as np
    from core_source_inputs import array_hash, transform_context19
    roster = target["roster"]
    rows = roster["events"]
    manifest = {row["path"]: row for row in target["manifest_rows"]}
    by_file = collections.defaultdict(list)
    for row in rows:
        by_file[row["source_file"]].append(row)
    output = {name: {} for name in ("broad", "mu", "beta")}
    raw_paths = []
    for name in sorted(by_file):
        if guard:
            guard()
        path = Path(cache_dir) / name
        require(path.resolve().is_relative_to(Path(cache_dir).resolve()), "Raw cache path redirects outside designated data directory")
        signal, header, cues = load_physical_edf(path, manifest[name])
        raw_paths.append({"path": name, "sha256": manifest[name]["checksum"], "units": "physical_header_microvolts", "rate_hz": 512})
        for row in by_file[name]:
            if guard:
                guard()
            cue = cues[row["cue_ordinal"] - 1]
            sample_float = float(cue["onset"]) * 512
            native_sample = int(round(sample_float))
            require(abs(sample_float - native_sample) <= .5 and native_sample == row["cue_sample"]
                    and cue["description"] == row["native_event_code"], "Frozen cue sample/event code differs from actual EDF")
            arrays = transform_context19(signal, 512, native_sample, config, bounds=(0, signal.shape[1]))
            hashes = {band: array_hash(value) for band, value in arrays.items()}
            require(hashes == row["input_sha256"] and object_hash(hashes) == row["epoch_sha256"], "Actual target input differs from pre-inference raw-only fingerprint")
            for band, value in arrays.items():
                output[band][row["event_id"]] = value
    for band in output:
        output[band] = np.stack([output[band][row["event_id"]] for row in rows])
    return output, {"status": "LOCKED_TARGET_INPUTS_REPLAYED_NO_SCORES", "files": raw_paths, "n_events": len(rows),
                    "input_hashes": {band: array_hash(value) for band, value in output.items()}, "labels_used_for_fitting": False,
                    "fitted_target_transforms": False, "target_fits": 0}


def predict_batches(model, values, device, batch_size=64, guard=None):
    """Pure eval-only helper; CPU use exists solely for explicit software fixtures."""
    import numpy as np
    import torch
    from train_source_selection_core import state_hash
    require(batch_size == 64 and len(values) > 0 and np.isfinite(values).all(), "Fixed nonempty finite inference inputs required")
    model.eval()
    before = state_hash(model)
    batches = []
    with torch.inference_mode():
        for start in range(0, len(values), batch_size):
            if guard:
                guard()
            x = torch.as_tensor(values[start:start + batch_size], dtype=torch.float32, device=device)
            logits = model(x)
            require(tuple(logits.shape) == (len(x), 2) and bool(torch.isfinite(logits).all()), "Invalid fixed model logits")
            batches.append(torch.softmax(logits, dim=1).cpu().numpy())
    after = state_hash(model)
    require(before == after and all(not module.training for module in model.modules()), "Target inference changed weights/buffers or remained in training mode")
    probabilities = np.concatenate(batches)
    require(np.isfinite(probabilities).all() and np.max(np.abs(probabilities.sum(1) - 1)) < 1e-6, "Invalid binary probabilities")
    return probabilities, {"state_before_sha256": before, "state_after_sha256": after,
                           "parameters_and_buffers_unchanged": True, "mode": "eval_inference_mode", "target_fits": 0}


def execution_gates(source_dir):
    from train_source_selection_core import validate_config, gpu_identity, verify_runtime_lock
    config = validate_config(read_json(CONFIG))
    target = verify_target_gate(config)
    cells, paths, completion = source_cells(source_dir)
    freeze = verify_freeze(paths + target["required_paths"], target["roster_path"], Path(source_dir) / "source_completion_manifest.json")
    runtime = gpu_identity()
    verify_runtime_lock(runtime, read_json(RUNTIME_LOCK))
    authorization = verify_authorization(read_json(AUTHORIZATION), runtime)
    return config, target, cells, completion, freeze, runtime, authorization


def execute(source_dir, cache_dir, output_dir=None):
    # Critical order: no target raw path/file is opened before ALL gates pass.
    config, target, cells, completion, freeze, runtime, authorization = execution_gates(source_dir)
    import numpy as np
    import torch
    from train_source_selection_core import build_model, state_hash
    started = time.monotonic()
    def guard():
        elapsed = (time.monotonic() - started) / 3600
        require(elapsed <= authorization["remaining_maximum_gpu_hours"] and datetime.now(timezone.utc) < datetime.fromisoformat(authorization["expires_at_utc"].replace("Z", "+00:00")),
                "Target inference authorization/time envelope exhausted; worker does not stop cloud billing")
    run = "target-core-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(output_dir).resolve() if output_dir else STUDY / "results" / run
    require(output.is_relative_to((STUDY / "results").resolve()) and not output.exists(), "Inference requires a fresh new-study result directory")
    output.mkdir(parents=True)
    status = {"status": "qualified_target_input_replay", "run_id": run, "target_fits": 0, "new_source_fits": 0,
              "predictions_computed": False, "prediction_rows": 0, "nominal_cells_completed": 0,
              "independent_prediction_validation_passed": False, "statistical_scores_computed": False,
              "external_experiment_complete": False, "public_preinference_commit": freeze["commit_sha"]}
    write_json(output / "target_status.json", status)
    try:
        guard()
        arrays, audit = prepare_target_inputs(cache_dir, target, config, guard=guard)
        write_json(output / "target_input_replay_receipt.json", audit)
        rows = target["roster"]["events"]
        all_predictions, receipts = [], []
        for cell in cells:
            guard()
            checkpoint_path = regular_path(cell["checkpoint_file"])
            require(sha(checkpoint_path) == cell["checkpoint_sha256"], "Frozen source checkpoint changed before inference")
            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
            require(checkpoint.get("model") == cell["architecture"] and checkpoint.get("architecture") == config["architecture"]
                    and checkpoint.get("seed") == cell["seed"] and checkpoint.get("epochs") == cell["epochs"]
                    and checkpoint.get("config_sha256") == sha(CONFIG), "Checkpoint internal identity differs from frozen source owner")
            model = build_model(cell["architecture"], config["architecture"], torch.device("cuda:0"))
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            require(state_hash(model) == cell["model_state_sha256"], "Deserialized model state differs from independently frozen source fit")
            x = arrays["broad"] if cell["architecture"] == "BROAD_EEGNET" else np.stack([arrays["mu"], arrays["beta"]], axis=1)
            status.update(status="target_model_output_attempt_in_progress", predictions_computation_attempted=True)
            write_json(output / "target_status.json", status)
            probabilities, state_receipt = predict_batches(model, x, "cuda:0", guard=guard)
            receipts.append({**cell, **state_receipt, "checkpoint_bytes_rechecked": True})
            for row, probability in zip(rows, probabilities):
                all_predictions.append({"subject_id": row["subject_id"], "event_id": row["event_id"],
                                        "model_arch": cell["model_arch"], "selector": cell["analysis_selector"], "seed": cell["seed"],
                                        "ytrue": row["ytrue"], "ypred": int(probability.argmax()), "p_left": float(probability[0]), "p_right": float(probability[1]),
                                        "epoch_sha256": row["epoch_sha256"], "checkpoint_sha256": cell["checkpoint_sha256"],
                                        "native_event_code": row["native_event_code"], "canonical_ytrue": row["ytrue"] + 1,
                                        "canonical_ypred": int(probability.argmax()) + 1, "owner_cell": cell["owner_cell"]})
            status.update(status="target_predictions_pending_independent_validation", predictions_computed=True,
                          prediction_rows=len(all_predictions), nominal_cells_completed=len(receipts))
            write_json(output / "target_status.json", status)
            write_json(output / "model_state_receipts.json", receipts)
            # Persist each completed condition, including adverse/null outputs,
            # before another model is attempted; a later failure never erases it.
            with (output / "predictions.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(all_predictions[0]))
                writer.writeheader(); writer.writerows(all_predictions)
            del model, checkpoint, x
        from analyze_redesign_scores import validate_contract, validate_prediction_rows
        people, events = validate_contract(target["roster"], False)
        checkpoint_identities = [{"model_arch": c["model_arch"], "selector": c["analysis_selector"], "seed": c["seed"],
                                  "checkpoint_sha256": c["checkpoint_sha256"]} for c in cells]
        validate_prediction_rows(all_predictions, people, events, checkpoint_identities)
        prediction_path = output / "predictions.csv"
        with prediction_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(all_predictions[0]))
            writer.writeheader(); writer.writerows(all_predictions)
        write_json(output / "prediction_completion_receipt.json", {**status, "status": "PREDICTIONS_COMPLETE_PENDING_INDEPENDENT_VALIDATION_NO_SCORES",
                   "predictions_sha256": sha(prediction_path), "locked_contract_sha256": sha(target["roster_path"]),
                   "source_manifest_sha256": sha(Path(source_dir) / "source_completion_manifest.json"), "runtime": runtime,
                   "state_receipts_sha256": sha(output / "model_state_receipts.json"), "inference_authorization_sha256": sha(AUTHORIZATION),
                   "checkpoints": [{"model_arch": c["model_arch"], "selector": c["analysis_selector"], "seed": c["seed"],
                                    "checkpoint_file": c["checkpoint_file"], "checkpoint_sha256": c["checkpoint_sha256"],
                                    "source_only": True, "target_fit_count": 0} for c in cells],
                   "qualification": target["gate"]["qualification"], "independent_confirmation_ready": False,
                   "limits": ["No independent prediction validation or paired statistical analysis has been performed by this worker",
                              "No publication, cloud shutdown, target fitting, target normalization or selector revision was performed"]})
        status["status"] = "predictions_complete_pending_independent_validation_no_scores"
        write_json(output / "target_status.json", status)
        return output
    except Exception as error:
        status.update(status="FAILED_OR_BLOCKED_NO_AUTOMATIC_RETRY", error_type=type(error).__name__, error_message=str(error))
        write_json(output / "target_status.json", status)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-run-dir", type=Path)
    parser.add_argument("--target-cache-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN_NO_TARGET_EEG_READ_NO_MODEL_OUTPUT", "new_source_fits": 0, "target_fits": 0,
                          "target_predictions_computed": False, "scientific_experiment_completed": False,
                          "required_gates": [str(p.relative_to(ROOT)) for p in (DATA_GATE, FREEZE, RUNTIME_LOCK, AUTHORIZATION)],
                          "additional_required_artifacts": ["real author prior-use declaration", "full174-acquisition byte/header/event audit",
                            "full signal QC + duplicate identity audit + pre-inference eligible event/all-input fingerprint roster",
                            "independent source26-nominal-grid/checkpoint/schedule validation", "live authorized GPU/runtime"],
                          "implementation_status": "software_candidate_real_target_execution_unvalidated"}, indent=2))
        return
    if args.source_run_dir is None or args.target_cache_dir is None:
        parser.error("--execute needs a new-study independently validated --source-run-dir and registered --target-cache-dir")
    output = execute(args.source_run_dir, args.target_cache_dir, args.output_dir)
    print(json.dumps({"status": "target_worker_returned_predictions_need_independent_validation_and_scoring", "output": str(output.relative_to(ROOT)), "target_fits": 0}))


if __name__ == "__main__":
    main()
