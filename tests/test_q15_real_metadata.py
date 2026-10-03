"""Synthetic native-MAT audit tests; fixtures never become real audit receipts."""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from scripts import q15_real_metadata as audit


@pytest.fixture(autouse=True)
def clean_decode_cache():
    audit._CACHE.clear()
    yield
    audit._CACHE.clear()


def _broadcast(shape, value=0.0):
    return np.broadcast_to(np.array(value, dtype=float), shape)


def _lee_train():
    channels = list(audit.execution_contract()["shared_transform"]["channels"])
    channels += [f"extra{number}" for number in range(62 - len(channels))]
    labels = np.array([1, 2] * 50)
    return {
        "fs": np.array([[1000]]), "x": _broadcast((6600, 62)),
        "chan": np.array([channels], dtype=object),
        "t": np.arange(2001, 2101)[None, :], "y_dec": labels[None, :],
        "class": np.array([["1", "right"], ["2", "left"]], dtype=object),
        "y_class": np.array([["right" if value == 1 else "left" for value in labels]], dtype=object),
        "y_logic": np.stack([labels == 1, labels == 2]).astype(int),
        "smt": _broadcast((4000, 100, 62)),
    }


def _cho_eeg(subject=1):
    count = 120 if subject in (7, 9, 46) else 100
    marker = np.zeros(count * 3584, dtype=np.uint8)
    marker[1023 + np.arange(count) * 3584] = 1
    return {"srate": 512, "n_imagery_trials": count,
            "imagery_left": _broadcast((68, count * 3584)),
            "imagery_right": _broadcast((68, count * 3584)),
            "imagery_event": marker, "frame": np.array([-2000, 5000])}


@pytest.fixture
def lee(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-lee.mat"
    path.write_bytes(b"not-real-EEG; synthetic audit fixture")
    train = _lee_train()
    calls = []

    def load(_path, **kwargs):
        assert kwargs == {"variable_names": ["EEG_MI_train"], "mat_dtype": True}
        calls.append(str(_path))
        return {"EEG_MI_train": np.array([[train]], dtype=object)}

    monkeypatch.setattr(audit, "loadmat", load)
    return path, train, calls


@pytest.fixture
def cho(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-cho.mat"
    path.write_bytes(b"not-real-EEG; synthetic Cho audit fixture")
    eeg = _cho_eeg()
    calls = []

    def load(_path, **kwargs):
        assert kwargs == {"variable_names": ["eeg"], "simplify_cells": True}
        calls.append(str(_path))
        return {"eeg": eeg}

    monkeypatch.setattr(audit, "loadmat", load)
    return path, eeg, calls


def _audit_lee(lee):
    return audit.audit_raw_file(lee[0], "Lee2019_MI", "session1/s1/sess01_subj01_EEG_MI.mat")


def _audit_cho(cho):
    return audit.audit_raw_file(cho[0], "Cho2017", "s01.mat")


def test_lee_native_label_reversal_and_matlab_cue_are_explicit(lee):
    row = _audit_lee(lee)
    assert row["n_labeled_trials"] == 100
    assert row["provider_smt_alignment_python_t_matches"] == 100
    assert row["native_label_map"] == {"right_hand": 1, "left_hand": 2}
    assert row["events"][0] == {"sample_id": "s01_1_offline_train_t001", "onset_sample": 2000,
                                "label": "right_hand", "canonical_label": 2,
                                "native_code": 1, "trial_ordinal": 1}
    assert row["events"][1]["canonical_label"] == 1
    assert row["events"][1]["label"] == "left_hand"
    assert row["native_numeric_calibration_verified"] is False
    assert row["hardware_cue_latency_verified"] is False
    assert row["no_outcomes_inspected"] is True
    assert row["declared_analysis_unit"] == "uV"
    assert "unverified" in row["native_physical_unit"]
    assert "one sample" in row["cue_index_convention"]


@pytest.mark.parametrize("mutation,message", [
    (lambda train: train.update({"class": np.array([["1", "left"], ["2", "right"]], dtype=object)}), "class definitions"),
    (lambda train: train["y_class"].__setitem__((0, 0), "left"), "string/numeric"),
    (lambda train: train["y_logic"].__setitem__((1, 0), 1), "one-hot/numeric"),
    (lambda train: train.update({"y_logic": np.zeros((100, 2), dtype=int)}), "one-hot/numeric"),
    (lambda train: train["y_dec"].__setitem__((0, 0), 2), "class counts"),
    (lambda train: train["t"].__setitem__((0, 1), train["t"][0, 0]), "cue uniqueness"),
    (lambda train: train.update({"t": train["t"].astype(float) + .5}), "Noninteger"),
    (lambda train: train.update({"t": train["t"].astype(float) * np.nan}), "Noninteger"),
    (lambda train: train.update({"smt": _broadcast((3999, 100, 62))}), "segment shape"),
    (lambda train: train.update({"smt": _broadcast((4000, 100, 62), 1)}), "alignment drifted"),
    (lambda train: train.update({"x": _broadcast((6600, 62), np.inf)}), "Nonfinite"),
    (lambda train: train.update({"x": _broadcast((6598, 62))}), "complete shared context"),
    (lambda train: train["t"].__setitem__((0, 0), 1500), "complete shared context"),
    (lambda train: train["chan"].__setitem__((0, 1), train["chan"][0, 0]), "channel/rate"),
    (lambda train: train["chan"].__setitem__((0, 0), "missingRequiredChannel"), "source channels absent"),
    (lambda train: train.update({"fs": np.array([[512]])}), "channel/rate"),
    (lambda train: train.update({"fs": np.array([[1000.5]])}), "Noninteger"),
    (lambda train: train.update({"fs": np.array([1000, 1000])}), "scalar expected"),
    (lambda train: train.update({"t": train["t"].astype(complex)}), "Noninteger"),
    (lambda train: train.update({"t": np.full((1, 100), 2 ** 63, dtype=np.uint64)}), "exceeds sample representation"),
    (lambda train: train.update({"x": _broadcast((6600, 61))}), "channel/rate"),
])
def test_lee_label_segment_rate_channel_and_context_drift_blocks(lee, mutation, message):
    mutation(lee[1])
    with pytest.raises(ValueError, match=message):
        _audit_lee(lee)


def test_cho_class_concatenation_is_not_invented_physical_runs(cho):
    row = _audit_cho(cho)
    assert row["n_labeled_trials"] == 200
    assert row["events"][0]["onset_sample"] == 1023
    assert row["events"][99]["onset_sample"] == 1023 + 99 * 3584
    assert row["events"][100]["onset_sample"] == 1023
    assert row["events"][100]["canonical_label"] == 2
    assert row["events"][100]["sample_id"] == "s01_1_retained_2_t001"
    assert row["channel_name_field_in_mat"] is False
    assert row["physical_run_identity"] is None
    assert row["physical_run_reconstruction_verified"] is False
    assert row["original_reference_verified"] is False
    assert row["native_numeric_calibration_verified"] is False
    assert row["hardware_cue_latency_verified"] is False


@pytest.mark.parametrize("subject", [7, 9, 46])
def test_cho_three_long_subjects_keep_240_trials(cho, subject):
    cho[1].update(_cho_eeg(subject))
    row = audit.audit_raw_file(cho[0], "Cho2017", f"s{subject:02d}.mat")
    assert row["n_labeled_trials"] == 240
    assert row["trials_per_class"] == 120


@pytest.mark.parametrize("mutation,message", [
    (lambda eeg: eeg.update({"srate": 250}), "class array/count"),
    (lambda eeg: eeg.update({"srate": 512.5}), "Noninteger"),
    (lambda eeg: eeg.update({"n_imagery_trials": 99}), "class array/count"),
    (lambda eeg: eeg.update({"n_imagery_trials": 100.5}), "Noninteger"),
    (lambda eeg: eeg.update({"n_imagery_trials": [100, 100]}), "scalar expected"),
    (lambda eeg: eeg.update({"imagery_right": _broadcast((68, 3584 * 99))}), "class array/count"),
    (lambda eeg: eeg.update({"imagery_left": _broadcast((64, 3584 * 100))}), "class array/count"),
    (lambda eeg: eeg["imagery_event"].__setitem__(1023, 2), "marker/chunk"),
    (lambda eeg: eeg["imagery_event"].__setitem__(1023, 0), "marker/chunk"),
    (lambda eeg: eeg.update({"imagery_event": np.roll(eeg["imagery_event"], 1)}), "marker/chunk"),
    (lambda eeg: eeg.update({"imagery_event": eeg["imagery_event"][:-1]}), "marker/chunk"),
    (lambda eeg: eeg.update({"imagery_event": eeg["imagery_event"].astype(float) + .5}), "Noninteger"),
    (lambda eeg: eeg.update({"frame": [-2000, 4999]}), "frame contract"),
    (lambda eeg: eeg.update({"imagery_left": _broadcast((68, 358400), np.nan)}), "Nonfinite"),
    (lambda eeg: eeg.update({"imagery_right": _broadcast((68, 358400), np.inf)}), "Nonfinite"),
])
def test_cho_markers_boundaries_class_shapes_and_native_values_block(cho, mutation, message):
    mutation(cho[1])
    with pytest.raises(ValueError, match=message):
        _audit_cho(cho)


def test_cached_metadata_cannot_be_mutated_by_the_caller_and_bytes_are_rehashed(lee):
    original = _audit_lee(lee)
    original["events"][0]["canonical_label"] = 99
    original["channels"][0] = "tampered"
    repeated = _audit_lee(lee)
    assert repeated["events"][0]["canonical_label"] == 2
    assert repeated["channels"][0] != "tampered"
    assert len(lee[2]) == 1
    old_sha = repeated["sha256"]
    lee[0].write_bytes(b"different synthetic source bytes")
    changed = _audit_lee(lee)
    assert changed["sha256"] != old_sha
    assert len(lee[2]) == 2
    assert changed["sha256"] == hashlib.sha256(lee[0].read_bytes()).hexdigest()


@pytest.mark.parametrize("dataset,file_id", [
    ("Cho2017", "s00.mat"), ("Cho2017", "s53.mat"), ("Cho2017", "../s01.mat"),
    ("Lee2019_MI", "session1/s1/sess02_subj01_EEG_MI.mat"),
    ("Lee2019_MI", "session1/s2/sess01_subj01_EEG_MI.mat"),
    ("Lee2019_MI", "session2/s55/sess02_subj55_EEG_MI.mat"),
    ("unknown", "s01.mat"),
])
def test_unknown_provider_identity_fails_before_native_decode(tmp_path, monkeypatch, dataset, file_id):
    path = tmp_path / "synthetic.mat"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audit, "loadmat", lambda *_a, **_k: pytest.fail("Unknown identity decoded"))
    with pytest.raises(ValueError, match="Unknown provider file identity"):
        audit.audit_raw_file(path, dataset, file_id)


def _mock_provider(tmp_path, monkeypatch):
    raw = tmp_path / "synthetic.mat"
    raw.write_bytes(b"only a synthetic fixture, never actual EEG")
    digest = audit.digest_original(raw)
    ids = [f"s{number:02d}.mat" for number in range(1, 53)]
    provider = {"dataset": "Cho2017", "provider_version": "synthetic-test-only",
                "license": "test-only", "provider_inventory_source": "synthetic-test-only",
                "expected_file_ids": ids, "files": {file_id: digest.copy() for file_id in ids}}
    monkeypatch.setattr(audit, "authenticated_inventory", lambda dataset: copy.deepcopy(provider))

    def decode(path, dataset, file_id):
        subject = int(file_id[1:3])
        return {"subject": subject, "file_id": file_id,
                "n_labeled_trials": 240 if subject in (7, 9, 46) else 200,
                **audit.digest_original(path)}

    monkeypatch.setattr(audit, "audit_raw_file", decode)
    manifest = {"schema_version": 1, "dataset": "Cho2017", "expected_file_ids": ids.copy(),
                "files": [{"file_id": file_id, "path": str(raw), "sha256": digest["sha256"],
                           "subject": int(file_id[1:3]), "session": 1,
                           "run": "retained_labeled_MI", "adapter": "real_mat_operational_v1"}
                          for file_id in ids]}
    path = tmp_path / "synthetic-provider-claim.json"
    return path, manifest, provider, raw


def test_complete_mocked_metadata_is_still_non_authorizing(tmp_path, monkeypatch):
    path, manifest, *_ = _mock_provider(tmp_path, monkeypatch)
    path.write_text(json.dumps(manifest))
    receipt = audit.audit_inventory(path)
    assert receipt["status"] == "metadata_passed_non_authorizing"
    assert receipt["n_labeled_trials"] == 10520
    assert receipt["source_training_authorized"] is False
    assert receipt["external_prediction_authorized"] is False
    assert receipt["target_fits"] == 0
    assert receipt["predictions_computed"] is False
    assert receipt["native_numeric_calibration_verified"] is False
    assert receipt["calibration_limitations_must_be_reported"] is True


@pytest.mark.parametrize("mutation", [
    lambda manifest: manifest["files"].pop(),
    lambda manifest: manifest["files"].__setitem__(-1, manifest["files"][0]),
    lambda manifest: manifest["expected_file_ids"].reverse(),
    lambda manifest: manifest.update({"schema_version": 99}),
])
def test_caller_cannot_shrink_duplicate_or_reorder_complete_provider_inventory(tmp_path, monkeypatch, mutation):
    path, manifest, *_ = _mock_provider(tmp_path, monkeypatch)
    mutation(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match="independently authenticated complete inventory"):
        audit.audit_inventory(path)


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("subject", 2), ("session", 2),
    ("run", "invented_physical_run"), ("adapter", "synthetic_json_v1"), ("path", "relative.mat"),
])
def test_caller_identity_hash_adapter_or_path_forgery_blocks_receipt(tmp_path, monkeypatch, field, value):
    path, manifest, *_ = _mock_provider(tmp_path, monkeypatch)
    manifest["files"][0][field] = value
    path.write_text(json.dumps(manifest))
    receipt = audit.audit_inventory(path)
    assert receipt["status"] == "blocked_real_raw_metadata"
    assert receipt["failed_files"] == ["s01.mat"]
    assert receipt["raw_hashes_verified"] is False
    assert receipt["all_expected_files_hashed"] is False
    assert receipt["source_training_authorized"] is False


def test_authenticated_hashes_override_a_caller_matching_its_changed_local_bytes(tmp_path, monkeypatch):
    path, manifest, _provider, raw = _mock_provider(tmp_path, monkeypatch)
    raw.write_bytes(b"modified local fixture after independent provider snapshot")
    digest = audit.digest_original(raw)
    for row in manifest["files"]:
        row["sha256"] = digest["sha256"]
    path.write_text(json.dumps(manifest))
    receipt = audit.audit_inventory(path)
    assert receipt["status"] == "blocked_real_raw_metadata"
    assert len(receipt["failed_files"]) == 52
    assert receipt["raw_hashes_verified"] is False


def test_matching_claim_hash_does_not_cover_different_original_bytes(tmp_path, monkeypatch):
    path, manifest, _provider, raw = _mock_provider(tmp_path, monkeypatch)
    raw.write_bytes(b"modified fixture but original hashes retained in the claim")
    path.write_text(json.dumps(manifest))
    receipt = audit.audit_inventory(path)
    assert len(receipt["failed_files"]) == 52
    assert receipt["status"] == "blocked_real_raw_metadata"


def test_symlink_original_is_rejected_before_decode(tmp_path, monkeypatch):
    path, manifest, _provider, raw = _mock_provider(tmp_path, monkeypatch)
    link = tmp_path / "synthetic-link.mat"
    link.symlink_to(raw)
    manifest["files"][0]["path"] = str(link)
    path.write_text(json.dumps(manifest))
    assert audit.audit_inventory(path)["failed_files"] == ["s01.mat"]


def _archived_provider(tmp_path, monkeypatch, dataset):
    base = tmp_path / "execution"
    evidence = base / "evidence"
    evidence.mkdir(parents=True)
    monkeypatch.setattr(audit, "BASE", base)
    monkeypatch.setattr(audit, "execution_contract", lambda: {"target_fits": 0})
    ids = ([f"s{number:02d}.mat" for number in range(1, 53)] if dataset == "Cho2017" else
           [f"session{session}/s{number}/sess0{session}_subj{number:02d}_EEG_MI.mat"
            for session in (1, 2) for number in range(1, 55)])
    md5 = hashlib.md5(b"synthetic snapshot only").hexdigest()
    rows = [{"file_id": file_id, "size_bytes": 12, "provider_md5": md5,
             "checksum_kind": "official_md5"} for file_id in ids]
    if dataset == "Cho2017":
        for row in rows:
            if row["file_id"] in {"s07.mat", "s09.mat", "s46.mat"}:
                row["provider_md5"] = None
                row["checksum_kind"] = "multipart_etag_not_md5"
    provider = {"dataset": dataset, "provider_version": "synthetic-test-only", "license": "test-only",
                "provider_inventory_source": "synthetic-test-only", "expected_file_ids": ids,
                "files": rows}
    name = "cho_transfer_manifest.json" if dataset == "Cho2017" else "lee_transfer_manifest.json"
    path = evidence / name
    path.write_text(json.dumps(provider))
    transport = tmp_path / "synthetic-transport.json"
    transport.write_text(json.dumps({"files": [{"dataset": dataset, "file_id": file_id,
                                                "size_bytes": 12, "md5": md5,
                                                "sha256": "a" * 64} for file_id in ids]}))
    monkeypatch.setattr(audit, "TRANSPORT", transport)
    (evidence / "100542.md5").write_text("\n".join(f"{md5} ./{file_id}" for file_id in ids))
    return path, provider, transport, evidence


@pytest.mark.parametrize("dataset,expected", [("Cho2017", 52), ("Lee2019_MI", 108)])
def test_archived_provider_and_transport_require_complete_cohorts(tmp_path, monkeypatch, dataset, expected):
    _archived_provider(tmp_path, monkeypatch, dataset)
    value = audit.authenticated_inventory(dataset)
    assert len(value["files"]) == expected
    if dataset == "Cho2017":
        missing = [name for name, row in value["files"].items() if not row["provider_content_md5_available"]]
        assert missing == ["s07.mat", "s09.mat", "s46.mat"]
        assert value["files"]["s07.mat"]["provider_checksum_kind"] == "multipart_etag_not_md5"


@pytest.mark.parametrize("mutation,message", [
    (lambda provider: provider["files"].pop(), "complete cohort inventory"),
    (lambda provider: provider["files"].__setitem__(-1, provider["files"][0]), "complete cohort inventory"),
    (lambda provider: provider["files"][0].update({"size_bytes": 999}), "size mismatch"),
    (lambda provider: provider["files"][0].update({"provider_md5": "b" * 32}), "MD5 mismatch"),
    (lambda provider: provider["files"][0].update({"provider_md5": None}), "missing provider checksum"),
])
def test_official_cho_records_and_transfer_snapshot_must_agree(tmp_path, monkeypatch, mutation, message):
    path, provider, *_ = _archived_provider(tmp_path, monkeypatch, "Cho2017")
    mutation(provider)
    path.write_text(json.dumps(provider))
    with pytest.raises(AssertionError, match=message):
        audit.authenticated_inventory("Cho2017")


def test_official_lee_md5_must_match_both_archived_records(tmp_path, monkeypatch):
    _path, _provider, _transport, evidence = _archived_provider(tmp_path, monkeypatch, "Lee2019_MI")
    (evidence / "100542.md5").write_text("0" * 32 + " ./session1/s1/sess01_subj01_EEG_MI.mat\n")
    with pytest.raises(AssertionError, match="Official Lee checksum record mismatch"):
        audit.authenticated_inventory("Lee2019_MI")


def test_incomplete_authenticated_transport_cohort_blocks(tmp_path, monkeypatch):
    _path, _provider, transport, _evidence = _archived_provider(tmp_path, monkeypatch, "Cho2017")
    value = json.loads(transport.read_text())
    value["files"].pop()
    transport.write_text(json.dumps(value))
    with pytest.raises(AssertionError, match="Transport cohort differs"):
        audit.authenticated_inventory("Cho2017")


def test_actual_execution_evidence_bytes_are_verified_without_any_eeg_decode(monkeypatch):
    monkeypatch.setattr(audit, "loadmat", lambda *_a, **_k: pytest.fail("EEG decoded during evidence check"))
    value = audit.execution_contract()
    assert value["target_fits"] == 0
    assert value["shared_transform"]["native_export_units_verified"] is False
    assert len(value["evidence_sha256"]) >= 8
