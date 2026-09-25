"""Synthetic Q14-R2 continuation contracts; no download, target scoring, or GPU."""

from __future__ import annotations

import json
from pathlib import Path

import mne
import numpy as np
import pytest
from scipy.signal import resample_poly

from scripts import q14_r2_external as external
from scripts import q14_r2_migration as migration
from scripts.q14_source import CONFIG, sha256

FROZEN = json.loads(CONFIG.read_text(encoding="utf-8"))
AMENDMENT = json.loads(migration.AMENDMENT.read_text(encoding="utf-8"))


def test_rate_branch_is_fixed_by_subject_metadata_only() -> None:
    assert AMENDMENT["native_128_hz_subjects"] == [88, 92, 100]
    assert [s for s in range(88, 110) if external.expected_rate(s, AMENDMENT) == 128] == [
        88, 92, 100
    ]
    assert all(
        external.expected_rate(s, AMENDMENT) == 160
        for s in range(88, 110)
        if s not in (88, 92, 100)
    )
    with pytest.raises(AssertionError, match="remaining"):
        external.expected_rate(87, AMENDMENT)
    with pytest.raises(AssertionError, match="pre-outcome"):
        external.expected_rate(88, {**AMENDMENT, "native_128_hz_subjects": [88, 92]})


class _HeaderOnlyRaw:
    def __init__(self, rate: int) -> None:
        self.info = {"sfreq": float(rate)}
        self.ch_names = FROZEN["channels"].copy()
        self.closed = False

    def get_channel_types(self, picks=None):
        return ["eeg"] * len(picks or self.ch_names)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_edfs(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "edf"
    data_dir.mkdir()
    official = {}
    for subject in range(88, 110):
        for run in FROZEN["external_runs"]:
            file = data_dir / f"S{subject:03d}R{run:02d}.edf"
            file.write_bytes(f"synthetic EDF header S{subject:03d}R{run:02d}".encode())
            official[file.name] = sha256(file)

    def load_data(*, subjects, runs, path, update_path, verbose):
        assert path == str(data_dir) and runs == [4, 8, 12]
        assert update_path is False and verbose == "ERROR"
        return [data_dir / f"S{subjects:03d}R{run:02d}.edf" for run in runs]

    rate_override = {}
    headers = []

    def read_raw_edf(file, *, preload, verbose):
        assert preload is False and verbose is False
        subject = int(Path(file).name[1:4])
        rate = rate_override.get(subject, external.expected_rate(subject, AMENDMENT))
        raw = _HeaderOnlyRaw(rate)
        headers.append(raw)
        return raw

    monkeypatch.setattr(external.eegbci, "load_data", load_data)
    monkeypatch.setattr(external.eegbci, "standardize", lambda raw: None)
    monkeypatch.setattr(external.mne.io, "read_raw_edf", read_raw_edf)
    return data_dir, official, rate_override, headers


def test_preflight_verifies_all_66_official_edfs_before_new_scoring(fake_edfs) -> None:
    data_dir, official, _, headers = fake_edfs
    records = external.preflight_remaining(data_dir, FROZEN, AMENDMENT, official)
    assert len(records) == 66 and len(headers) == 66
    assert all(raw.closed for raw in headers)
    assert {(r["subject"], r["run"]) for r in records} == {
        (s, run) for s in range(88, 110) for run in (4, 8, 12)
    }
    assert {(r["subject"], r["run"]) for r in records if r["resampled_to_160_hz"]} == {
        (s, run) for s in (88, 92, 100) for run in (4, 8, 12)
    }
    assert {r["native_rate_hz"] for r in records} == {128, 160}


def test_preflight_rejects_unknown_native_rate_and_tampered_edf(fake_edfs) -> None:
    data_dir, official, rate_override, _ = fake_edfs
    rate_override[89] = 256
    with pytest.raises(AssertionError, match="Unexpected native rate 256"):
        external.preflight_remaining(data_dir, FROZEN, AMENDMENT, official)
    rate_override.clear()
    (data_dir / "S088R04.edf").write_bytes(b"changed after official hash was frozen")
    with pytest.raises(AssertionError, match="Official PhysioNet SHA-256 mismatch: S088R04.edf"):
        external.preflight_remaining(data_dir, FROZEN, AMENDMENT, official)


def test_native_128_hz_epochs_resample_384_to_480_without_reindexing_events(
    tmp_path: Path, monkeypatch
) -> None:
    subject = 88
    data_dir = tmp_path / "edf"
    data_dir.mkdir()
    official = {}
    preflight = []
    for run in FROZEN["external_runs"]:
        file = data_dir / f"S{subject:03d}R{run:02d}.edf"
        file.write_bytes(f"synthetic EDF S{subject:03d}R{run:02d}".encode())
        digest = sha256(file)
        official[file.name] = digest
        preflight.append(
            {
                "subject": subject,
                "run": run,
                "filename": file.name,
                "bytes": file.stat().st_size,
                "sha256": digest,
                "native_rate_hz": 128,
            }
        )

    def load_data(*, subjects, runs, path, update_path, verbose):
        assert subjects == subject and path == str(data_dir)
        return [data_dir / f"S{subject:03d}R{run:02d}.edf" for run in runs]

    def read_raw_edf(file, *, preload, verbose):
        assert preload is True
        t = np.arange(1280) / 128
        signal = np.tile(1e-6 * np.sin(2 * np.pi * 10 * t), (22, 1))
        raw = mne.io.RawArray(
            signal, mne.create_info(FROZEN["channels"], 128, "eeg"), verbose=False
        )
        raw.set_annotations(
            mne.Annotations(onset=[1.0, 5.0], duration=[0, 0], description=["T1", "T2"])
        )
        return raw

    monkeypatch.setattr(external.eegbci, "load_data", load_data)
    monkeypatch.setattr(external.eegbci, "standardize", lambda raw: None)
    monkeypatch.setattr(external.mne.io, "read_raw_edf", read_raw_edf)
    arrays, metadata, files = external.load_128_subject(
        subject, data_dir, FROZEN, AMENDMENT, official, preflight
    )
    assert len(files) == 3 and len(metadata) == 6
    assert metadata["event_sample"].tolist() == [128, 640] * 3  # Native 128-Hz indices.
    assert metadata["label"].tolist() == [1, 2] * 3
    assert metadata["sample_id"].tolist()[0] == "physio_s088_r04_t001"
    for values in arrays.values():
        assert values.shape == (6, 22, 480)
        assert values.dtype == np.float32 and values.flags.c_contiguous
        assert np.isfinite(values).all()

    # This is a sample-rate conversion, not 96 samples of padding or a label rewrite.
    probe = np.arange(384, dtype=np.float32)[None, None, :]
    probe = np.broadcast_to(probe, (1, 22, 384)).copy()
    expected = resample_poly(probe, up=5, down=4, axis=2).astype(np.float32) * 1e6
    actual = external._resample_128_epoch(probe, FROZEN)
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=2)


def test_copy_subject_keeps_bytes_and_rejects_existing_tampering(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "r1"
    destination = tmp_path / "r2"
    source_subject = source / "subject_001"
    source_subject.mkdir(parents=True)
    destination.mkdir()
    receipt = b'{"status":"complete","subject":1}\n'
    predictions = b"opaque,original,predictions\n"
    (source_subject / "receipt.json").write_bytes(receipt)
    (source_subject / "predictions.csv").write_bytes(predictions)
    record = {
        "receipt_sha256": sha256(source_subject / "receipt.json"),
        "predictions_sha256": sha256(source_subject / "predictions.csv"),
    }
    monkeypatch.setattr(migration, "R1", source)
    monkeypatch.setattr(migration, "RESULT", destination)
    migration.copy_subject(1, record)
    migration.copy_subject(1, record)  # Resumption verifies existing bytes.
    target = destination / "subject_001"
    assert (target / "receipt.json").read_bytes() == receipt
    assert (target / "predictions.csv").read_bytes() == predictions
    (target / "predictions.csv").write_bytes(b"tampered target result")
    with pytest.raises(AssertionError, match="existing copy predictions"):
        migration.copy_subject(1, record)


def test_copy_subject_rejects_source_tampering_before_promoting(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "r1"
    destination = tmp_path / "r2"
    source_subject = source / "subject_002"
    source_subject.mkdir(parents=True)
    destination.mkdir()
    (source_subject / "receipt.json").write_bytes(b"original receipt")
    (source_subject / "predictions.csv").write_bytes(b"original predictions")
    record = {
        "receipt_sha256": sha256(source_subject / "receipt.json"),
        "predictions_sha256": sha256(source_subject / "predictions.csv"),
    }
    (source_subject / "receipt.json").write_bytes(b"changed source receipt")
    monkeypatch.setattr(migration, "R1", source)
    monkeypatch.setattr(migration, "RESULT", destination)
    with pytest.raises(AssertionError, match="staged receipt"):
        migration.copy_subject(2, record)
    assert not (destination / "subject_002").exists()
