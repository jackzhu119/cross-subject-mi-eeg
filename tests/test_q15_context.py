"""Synthetic-only prospective context, native MAT adapters and write-gate checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io import savemat
from scipy.signal import butter, resample_poly, sosfiltfilt

from mi_eeg.data import q15_context as context
from scripts import q15_preprocess_external as external


def _native_signal(rate, seconds=8, channels=21):
    time = np.arange(rate * seconds) / rate
    weights = np.arange(1, channels + 1)[:, None]
    return (weights * np.sin(2 * np.pi * 10 * time)
            + weights[::-1] * np.sin(2 * np.pi * 20 * time)
            + 300 * np.sin(2 * np.pi * 5 * time))


@pytest.mark.parametrize("rate,ratio", [(250, (16, 25)), (512, (5, 16)), (1000, (4, 25))])
def test_native_context_matches_independent_numerical_replay(rate, ratio):
    values = _native_signal(rate)
    cue = 2 * rate
    actual = context.transform_context(values, rate, cue)
    native = values[:, rate // 2:13 * rate // 2].copy()
    native -= np.mean(native, axis=0, keepdims=True)
    for band, limits in context.BANDS.items():
        filtered = sosfiltfilt(butter(4, limits, btype="bandpass", fs=rate, output="sos"),
                              native, axis=-1, padtype="odd", padlen=27)
        replay = resample_poly(filtered, *ratio, axis=-1, window=("kaiser", 5.0),
                               padtype="constant", cval=0.0)[:, 320:640].astype(np.float32)
        assert actual[band].dtype == np.float32
        assert actual[band].shape == (21, 320)
        np.testing.assert_array_equal(actual[band], replay)
        np.testing.assert_allclose(actual[band].mean(axis=0), 0, atol=3e-6)


def test_channel_selection_before_car_excludes_fcz_and_eog():
    base = _native_signal(250)
    full = np.zeros((25, base.shape[1]))
    names = list(context.BNCI_CHANNELS) + ["EOG1", "EOG2", "EOG3"]
    for row, name in enumerate(context.CHANNELS):
        full[names.index(name)] = base[row]
    full[names.index("FCz")] = 1e10
    full[22:] = -1e10
    selected = context.select_channels(full, names)
    np.testing.assert_array_equal(selected, base)
    actual = context.transform_context(selected, 250, 500)
    expected = context.transform_context(base, 250, 500)
    for band in context.BANDS:
        np.testing.assert_array_equal(actual[band], expected[band])
    with pytest.raises(ValueError, match="Missing or duplicate"):
        context.select_channels(full, names[:-1] + ["C3"])


def test_cho_context_isolated_inside_retained_chunk_and_half_open_boundary():
    first = _native_signal(512, seconds=7)
    joined = np.concatenate((first, np.full_like(first, 1e15)), axis=1)
    actual = context.transform_context(joined, 512, 1023, (0, 3584))
    joined[:, :255] = np.nan
    joined[:, 3327:] = np.inf
    unchanged = context.transform_context(joined, 512, 1023, (0, 3584))
    for band in context.BANDS:
        np.testing.assert_array_equal(actual[band], unchanged[band])
    with pytest.raises(ValueError, match="complete frozen context"):
        context.transform_context(first, 512, 1023, (256, 3584))
    with pytest.raises(ValueError, match="complete frozen context"):
        context.transform_context(first, 512, 1023, (0, 3326))
    joined[0, 255] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        context.transform_context(joined, 512, 1023, (0, 3584))


@pytest.mark.parametrize("mutation,message", [
    (lambda values: (values[:20], 250, 500, None), "21 channels"),
    (lambda values: (values.astype(complex) + 1j, 250, 500, None), "nonnumeric"),
    (lambda values: (values, 50, 100, None), "sampling rate"),
    (lambda values: (values, 250, 500.0, None), "integer"),
    (lambda values: (values, 250, True, None), "integer"),
    (lambda values: (values, 250, 0, None), "complete frozen context"),
    (lambda values: (values, 250, 500, (-1, 2000)), "boundaries"),
    (lambda values: (values, 251, 502, None), "sampling grid"),
])
def test_context_input_and_native_boundaries_fail_closed(mutation, message):
    with pytest.raises(ValueError, match=message):
        context.transform_context(*mutation(_native_signal(250)))


def _record(path, dataset, channels, events, *, session=1, rate=None):
    return {"path": str(path), "sha256": context.sha256_file(path), "dataset": dataset,
            "file_id": f"s01_session{session}_offline_MI" if dataset == "Lee2019_MI" else "s01.mat",
            "subject": 1, "session": session,
            "run": "offline_train" if dataset == "Lee2019_MI" else "retained_labeled_MI",
            "channels": list(channels), "sampling_rate_hz": rate or (1000 if dataset == "Lee2019_MI" else 512),
            "events": events}


@pytest.fixture
def cho_fixture(tmp_path, monkeypatch):
    # Real MATLAB struct layout, one synthetic retained trial for each class.
    names = list(context.CHANNELS) + [f"other{index}" for index in range(43)]
    left = np.vstack((_native_signal(512, seconds=7), np.zeros((47, 3584))))
    right = left * 1.7
    marker = np.zeros(3584, dtype=np.uint8)
    marker[1023] = 1
    path = tmp_path / "s01.mat"
    savemat(path, {"eeg": {"srate": 512, "n_imagery_trials": 1,
                           "imagery_left": left, "imagery_right": right,
                           "imagery_event": marker}})
    events = [{"sample_id": f"s01_1_retained_{label}_t001", "onset_sample": 1023,
               "label": name, "trial_ordinal": 1}
              for label, name in ((1, "left_hand"), (2, "right_hand"))]
    record = _record(path, "Cho2017", names, events)
    monkeypatch.setattr(external, "_real_auditor", lambda: SimpleNamespace(
        audit_raw_file=lambda *_: copy.deepcopy(record), CHO_CHANNELS=names))
    return record, left, right


def test_tiny_cho_real_mat_format_preserves_marker_class_and_identity(cho_fixture):
    record, left, right = cho_fixture
    arrays, metadata = external._decode_file(record, "Cho2017")
    assert metadata["sample_id"].tolist() == ["s01_1_retained_1_t001", "s01_1_retained_2_t001"]
    assert metadata["label"].tolist() == [1, 2]
    assert metadata["cue_sample_native"].tolist() == [1023, 1023]
    assert metadata["run"].tolist() == ["retained_labeled_MI"] * 2
    for index, values in enumerate((left, right)):
        expected = context.transform_context(values[:21], 512, 1023, (0, 3584))
        for band in context.BANDS:
            np.testing.assert_array_equal(arrays[band][index], expected[band])


@pytest.fixture
def lee_fixture(tmp_path, monkeypatch):
    # Native Lee MATLAB cell-string channels and nested training struct.
    names = list(context.CHANNELS) + [f"extra{index}" for index in range(41)]
    channels = np.empty((1, len(names)), dtype=object)
    channels[0] = names
    signal = _native_signal(1000, seconds=15, channels=62).T
    stored_t = np.array([[2001, 9001]])
    path = tmp_path / "s01_sess1.mat"
    savemat(path, {"EEG_MI_train": {"x": signal, "chan": channels, "t": stored_t,
                                   "fs": 1000, "y_dec": np.array([[1, 2]])},
                  "EEG_MI_test": {"x": np.full((1, 1), np.nan)}})
    events = [{"sample_id": f"s01_1_offline_train_t{index:03d}", "onset_sample": cue,
               "label": label, "trial_ordinal": index}
              for index, (cue, label) in enumerate(((2000, "right_hand"), (9000, "left_hand")), 1)]
    record = _record(path, "Lee2019_MI", names, events)
    monkeypatch.setattr(external, "_real_auditor", lambda: SimpleNamespace(
        audit_raw_file=lambda *_: copy.deepcopy(record)))
    return record, signal


def test_tiny_lee_real_mat_format_uses_t_minus_one_and_remaps_native_labels(lee_fixture):
    record, signal = lee_fixture
    arrays, metadata = external._decode_file(record, "Lee2019_MI")
    assert metadata["label"].tolist() == [2, 1]
    assert metadata["cue_sample_native"].tolist() == [2000, 9000]
    assert metadata["trial"].tolist() == [1, 2]
    for index, cue in enumerate((2000, 9000)):
        expected = context.transform_context(signal.T[:21], 1000, cue)
        for band in context.BANDS:
            np.testing.assert_array_equal(arrays[band][index], expected[band])


@pytest.mark.parametrize("field,value", [("onset_sample", 1024), ("label", "right_hand"),
                                        ("trial_ordinal", 2), ("sample_id", "made_up")])
def test_independent_decoder_rejects_fabricated_audit_events(cho_fixture, field, value):
    record, *_ = cho_fixture
    record["events"][0][field] = value
    with pytest.raises(AssertionError, match="Independent|identity"):
        external._decode_file(record, "Cho2017")


def test_raw_hash_change_precedes_mat_decode(cho_fixture, monkeypatch):
    record, *_ = cho_fixture
    Path(record["path"]).write_bytes(b"changed")
    monkeypatch.setattr(external, "loadmat", lambda *_args, **_kwargs: pytest.fail("MAT opened after hash mismatch"))
    with pytest.raises(AssertionError, match="changed before preprocessing"):
        external._decode_file(record, "Cho2017")


@pytest.mark.parametrize("entrypoint", ["subject", "dataset", "manifest", "alias", "both"])
def test_all_public_epoch_writers_require_committed_freeze_before_any_write(tmp_path, monkeypatch, entrypoint):
    output = tmp_path / "epochs"
    receipts = {dataset: tmp_path / f"{dataset}.json" for dataset in external.DATASETS}
    monkeypatch.setattr(external.q15_source, "AUDIT_RECEIPTS", receipts)
    monkeypatch.setattr(external.q15_source, "_verify_committed_freeze", lambda: (_ for _ in ()).throw(
        AssertionError("uncommitted or modified")))
    monkeypatch.setattr(external, "_decode_subject", lambda *_: pytest.fail("raw EEG decoded before freeze"))
    with pytest.raises(AssertionError, match="uncommitted or modified"):
        if entrypoint == "subject":
            external.preprocess_subject("Cho2017", 1, output)
        elif entrypoint == "dataset":
            external.prepare_dataset("Cho2017", output)
        elif entrypoint in ("manifest", "alias"):
            method = external.prepare_manifest if entrypoint == "manifest" else external.prepare_epoch_manifest
            method("Cho2017", receipts["Cho2017"], output)
        else:
            external.prepare_epochs(receipts, output)
    assert not output.exists()


def test_alternate_audit_receipt_cannot_release_write_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(external.q15_source, "AUDIT_RECEIPTS", {"Cho2017": tmp_path / "real.json"})
    monkeypatch.setattr(external, "prepare_dataset", lambda *_: pytest.fail("alternate receipt accepted"))
    with pytest.raises(AssertionError, match="committed source-runner"):
        external.prepare_manifest("Cho2017", tmp_path / "fabricated.json", tmp_path / "epochs")


def test_changed_committed_freeze_bytes_block_before_epoch_decode(tmp_path, monkeypatch):
    freeze = tmp_path / "pre_fit_freeze.json"
    committed = b'{"frozen_sha256":"' + b"a" * 64 + b'"}\n'
    freeze.write_bytes(committed.replace(b"a" * 64, b"b" * 64))
    # Exercise the production committed-byte comparison without mutating Git.
    monkeypatch.setattr(external.q15_source, "_git_bytes", lambda _path: committed)
    monkeypatch.setattr(external.q15_source, "_verify_committed_freeze", lambda:
                        external.q15_source._assert_committed_unchanged(freeze))
    monkeypatch.setattr(external, "_decode_subject", lambda *_: pytest.fail("changed freeze allowed native decode"))
    with pytest.raises(AssertionError, match="uncommitted or modified"):
        external.preprocess_subject("Cho2017", 1, tmp_path / "epochs")
    assert not (tmp_path / "epochs").exists()


def test_contract_mismatch_stops_before_processed_write(tmp_path, monkeypatch):
    monkeypatch.setattr(external.q15_source, "_verify_committed_freeze", dict)
    monkeypatch.setattr(external, "preprocessing_contract", lambda: (_ for _ in ()).throw(
        AssertionError("transform changed")))
    monkeypatch.setattr(external, "_write_subject", lambda *_: pytest.fail("epoch written after contract mismatch"))
    with pytest.raises(AssertionError, match="transform changed"):
        external.prepare_dataset("Cho2017", tmp_path / "epochs")
    assert not (tmp_path / "epochs").exists()


def test_synthetic_epoch_write_readback_and_raw_array_replay(cho_fixture, tmp_path, monkeypatch):
    record, *_ = cho_fixture
    monkeypatch.setattr(external, "DATASETS", {"Cho2017": (1, [1])})
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"files": [record]}))
    freeze = tmp_path / "freeze.json"
    freeze.write_text("{}")
    monkeypatch.setattr(external.q15_source, "AUDIT_RECEIPTS", {"Cho2017": audit})
    monkeypatch.setattr(external.q15_source, "FREEZE", freeze)
    monkeypatch.setattr(external, "_execution_gate", lambda: {"Cho2017": {"files": [record]}})
    monkeypatch.setattr(external, "preprocessing_contract", lambda: {"synthetic_test": True})
    manifest_path = external.prepare_dataset("Cho2017", tmp_path / "epochs")
    manifest = external.validate_epoch_manifest(manifest_path)
    assert manifest["subjects"][0]["physical_run_identity"] is None
    row = manifest["subjects"][0]
    with np.load(row["npz_path"], allow_pickle=False) as archive:
        arrays = {band: archive[band].copy() for band in context.BANDS}
    arrays["broad"][0, 0, 0] += 1
    np.savez(row["npz_path"], **arrays)
    # Even a caller updating the hash cannot make altered numerical values valid.
    row["npz_sha256"] = context.sha256_file(Path(row["npz_path"]))
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match="cannot be reproduced"):
        external.validate_epoch_manifest(manifest_path)


def _bnci_run():
    return {"X": np.zeros((1700, 25), dtype=np.float32), "fs": 250,
            "trial": np.arange(1, 49), "y": np.tile([1, 2, 3, 4], 12),
            "artifacts": np.tile([0, 1], 24)}


def _write_bnci(path, mutation=None):
    runs = [_bnci_run() for _ in range(6)]
    if mutation is not None:
        mutation(runs[0])
    savemat(path, {"data": runs}, do_compression=True)


@pytest.mark.parametrize("mutation,message", [
    (lambda run: run["trial"].__setitem__(47, 1600), "complete six-second context"),
    (lambda run: run["trial"].__setitem__(47, np.iinfo(np.int64).max), "positive increasing"),
    (lambda run: run["trial"].__setitem__(0, 0), "positive increasing"),
    (lambda run: run["y"].__setitem__(47, 1), "class counts"),
    (lambda run: run["artifacts"].__setitem__(47, 2), "binary indicators"),
    (lambda run: run["X"].__setitem__((0, 0), np.nan), "nonfinite"),
    (lambda run: run.__setitem__("trial", run["trial"].astype(float) + 0.5), "native integers"),
])
def test_bnci_real_mat_audit_checks_excluded_classes_and_all_context_bounds(tmp_path, mutation, message):
    path = tmp_path / "A01T.mat"
    _write_bnci(path, mutation)
    with pytest.raises(ValueError, match=message):
        context._validated_bnci_runs(path)


def test_full_synthetic_bnci_audit_hashes_18_originals_without_transforming(tmp_path, monkeypatch):
    originals, provenance = tmp_path / "raw", tmp_path / "provenance.json"
    originals.mkdir()
    records = []
    for subject in range(1, 10):
        for session in "TE":
            path = originals / f"A{subject:02d}{session}.mat"
            _write_bnci(path)
            records.append({"path": str(path), "bytes": path.stat().st_size,
                            "sha256": context.sha256_file(path)})
    provenance.write_text(json.dumps(records))
    monkeypatch.setattr(context, "transform_context", lambda *_: pytest.fail("metadata audit transformed EEG"))
    receipt = context.audit_bnci_source(originals, provenance)
    assert receipt["metadata_only"] is True
    assert receipt["n_files"] == 18 and receipt["n_runs"] == 108
    assert receipt["n_all_four_class_trials"] == 5184 and receipt["n_binary_trials"] == 2592
    assert receipt["fits_started"] == receipt["target_fits"] == 0
    assert receipt["files"][0]["runs"][0]["context_start_samples_zero_based"][0] == 125
    calls = []

    def fixed_transform(signal, rate, cue):
        calls.append((signal.shape, rate, cue))
        return {band: np.zeros((21, 320), dtype=np.float32) for band in context.BANDS}

    monkeypatch.setattr(context, "transform_context", fixed_transform)
    arrays, metadata, audit = context.load_bnci_source(originals, [1], provenance)
    assert len(calls) == len(metadata) == 288
    assert all(shape == (21, 1700) and rate == 250 for shape, rate, _cue in calls)
    assert metadata["sample_id"].tolist()[:3] == [
        "s01_0train_r0_t01", "s01_0train_r0_t02", "s01_0train_r0_t05"]
    assert metadata["artifact_flagged"].sum() == 144
    assert all(values.shape == (288, 21, 320) for values in arrays.values())
    assert audit["n_times_per_epoch"].unique().tolist() == [500]
    assert audit["n_eeg_channels"].unique().tolist() == [22]
    assert audit["sampling_rate_hz"].unique().tolist() == [250]
    assert json.loads(audit.iloc[0]["eeg_channel_names"]) == list(context.BNCI_CHANNELS)
    assert audit["output_n_times"].unique().tolist() == [320]
    assert audit["output_n_channels"].unique().tolist() == [21]
    assert audit["common_rate"].unique().tolist() == [160]
    assert audit["n_rejected_trials"].sum() == 0
    (originals / "A09E.mat").write_bytes(b"changed source")
    with pytest.raises(ValueError, match="differs from frozen Q8"):
        context.audit_bnci_source(originals, provenance)


def test_preprocessing_contract_records_unverified_external_calibration(tmp_path):
    arm = {"channels": list(context.CHANNELS), "frequency_bands_hz": {
        name: list(limits) for name, limits in context.BANDS.items()}}
    transform = {"context_relative_s": [-1.5, 4.5], "cue_window_s": [0.5, 2.5],
                 "common_rate_hz": 160, "channels": list(context.CHANNELS),
                 "reference": "common_average_21", "bands": arm["frequency_bands_hz"],
                 "filter": {"order": 4, "ftype": "butter", "phase": "zero",
                            "scope": "each_real_retained_trial_context", "padlen": 27},
                 "output_unit": "uV", "analysis_input_unit_convention": "native_numeric_as_microvolts",
                 "native_export_units_verified": False, "dtype": "float32",
                 "artifact_policy": "include_all", "target_fitted_normalization": False,
                 "baseline_correction": False}
    execution, protocol = tmp_path / "execution.json", tmp_path / "protocol.json"
    execution.write_text(json.dumps({"schema_version": 1, "target_fits": 0, "shared_transform": transform}))
    protocol.write_text(json.dumps({"new_source_arm": arm}))
    result = context.preprocessing_contract(execution, protocol)
    assert result["native_export_units_verified"] is result["calibration_verified"] is False
    assert result["target_fits"] == 0 and result["target_normalization"] is False
    assert result["numerical_implementation"]["resampling"]["crop_half_open"] == [320, 640]
    transform["native_export_units_verified"] = True
    execution.write_text(json.dumps({"schema_version": 1, "target_fits": 0, "shared_transform": transform}))
    with pytest.raises(AssertionError, match="unverified"):
        context.preprocessing_contract(execution, protocol)
