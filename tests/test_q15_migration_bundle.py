"""Synthetic Git and byte fixtures only: no EEG, fitting, API, or credentials."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

MODULE_PATH = (Path(__file__).resolve().parents[1] / "research_runs"
               / "Q15-MIGRATION-20261004/q15_migration_bundle.py")
SPEC = importlib.util.spec_from_file_location("q15_migration_bundle_test", MODULE_PATH)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bundle._json_bytes(value) if isinstance(value, (dict, list)) else value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    repo, epochs, bnci = (tmp_path / name for name in ("origin", "epochs", "bnci"))
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "Synthetic Fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _write(repo / "README.md", b"synthetic initial scientific revision\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "Synthetic science")
    science = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(bundle, "SCIENTIFIC_REVISION", science)
    monkeypatch.setattr(bundle, "ORIGIN_URL", repo.as_uri())
    _git(repo, "remote", "add", "origin", repo.as_uri())

    originals, source_originals = [], []
    for subject in range(1, 10):
        for session in ("E", "T"):
            name = f"A{subject:02d}{session}.mat"
            data = f"opaque synthetic original {name}".encode()
            _write(bnci / name, data)
            record = {"bytes": len(data), "sha256": _sha(data)}
            originals.append({"path": f"/frozen/Q8/{name}", **record})
            source_originals.append({"filename": name, **record})
    _write(repo / "research_runs/Q8-E001/results/source_files.json", originals)

    root = repo / bundle.SOURCE_ROOT
    _write(root / "pre_fit_freeze.json", {"synthetic_test_fixture": True})
    source = root / "source"
    for name in ("run_config.json", "source_metadata.csv", "source_audit.csv"):
        _write(source / name, f"opaque synthetic {name}".encode())
    _write(source / "source_files.json", {"files": source_originals})
    _write(source / "source_stage_complete.json", {
        "status": "fits_complete_pending_independent_source_validation", "deep_fit_count": 14,
        "shallow_fit_count": 1, "external_predictions_computed": False,
        "external_prediction_authorized": False,
    })
    for model in bundle.MODELS:
        base = source / model / "all_source"
        _write(base / "selection.json", {"synthetic_test_fixture": True})
        fits = [f"inner_{fold:02d}" for fold in range(1, 5)]
        fits += [f"final_seed_{seed}" for seed in bundle.SEEDS]
        for name in fits:
            job = base / name
            checkpoint, curve = f"opaque {model}/{name}".encode(), b"opaque synthetic curve"
            _write(job / "checkpoint.pt", checkpoint)
            _write(job / "curve.json", curve)
            _write(job / "manifest.json", {"status": "complete",
                   "checkpoint_sha256": _sha(checkpoint), "curve_sha256": _sha(curve)})
    csp = source / "CSP4_LDA/all_source"
    _write(csp / "model.joblib", b"opaque synthetic shallow model")
    _write(csp / "manifest.json", {"status": "complete",
                                  "model_sha256": bundle.sha256_file(csp / "model.joblib")})
    artifacts = {name: bundle.sha256_file(repo / name) for name in bundle._source_artifact_paths()}
    report = {"schema_version": 1, "status": "source_validated_non_authorizing", "passed": True,
              "deep_fit_count": 14, "shallow_fit_count": 1, "source_only": True, "target_fits": 0,
              "external_prediction_authorized": False, "external_predictions_computed": False,
              "counts": {"deep_inner": 8, "deep_final": 6, "shallow": 1, "predictions": 0},
              "artifact_sha256": artifacts,
              "checkpoints": {model: {str(seed): artifacts[
                  f"{bundle.SOURCE_ROOT}/source/{model}/all_source/final_seed_{seed}/checkpoint.pt"]
                  for seed in bundle.SEEDS} for model in bundle.MODELS},
              "csp_model_sha256": bundle.sha256_file(csp / "model.joblib")}
    for key, name in {"pre_fit_freeze_sha256": "pre_fit_freeze.json",
                      "source_files_sha256": "source/source_files.json",
                      "source_metadata_sha256": "source/source_metadata.csv",
                      "source_audit_sha256": "source/source_audit.csv",
                      "source_run_config_sha256": "source/run_config.json",
                      "source_stage_complete_sha256": "source/source_stage_complete.json"}.items():
        report[key] = artifacts[f"{bundle.SOURCE_ROOT}/{name}"]
    _write(root / "source_validation.json", report)

    for dataset, count in bundle.DATASETS.items():
        rows = []
        for subject in range(1, count + 1):
            row = {"subject": subject}
            for path_key, hash_key, suffix in (("npz_path", "npz_sha256", "npz"),
                                               ("metadata_path", "metadata_sha256", "csv")):
                name = f"s{subject:02d}.{suffix}"
                data = f"opaque synthetic {dataset}/{name}".encode()
                _write(epochs / dataset / name, data)
                row[path_key] = f"/workspace/q15-data/epochs/{dataset}/{name}"
                row[hash_key] = _sha(data)
            rows.append(row)
        manifest = {"schema_version": 1, "dataset": dataset,
                    "status": "epochs_verified_non_authorizing", "target_fits": 0,
                    "predictions_computed": False, "expected_subject_ids": list(range(1, count + 1)),
                    "subjects": rows}
        _write(epochs / dataset / "epoch_manifest.json", manifest)
        _write(repo / f"results/Q15-EXTERNAL/manifests/{dataset}.json", manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "Synthetic validated baseline")
    base = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(bundle, "BASE_COMMIT", base)
    return {"repo": repo, "epochs": epochs, "bnci": bnci, "base": base,
            "science": science, "tmp": tmp_path, "report": report}


def _export(snapshot, output="snapshot.tar", repo=None):
    archive = snapshot["tmp"] / output
    manifest = bundle.export_bundle(repo or snapshot["repo"], snapshot["epochs"], snapshot["bnci"],
                                    archive, snapshot["base"], bundle.ORIGIN_JOB_ID, bundle.ORIGIN_POD_ID)
    return archive, manifest


def _rewrite(archive: Path, target: Path, transform) -> Path:
    with tarfile.open(archive, "r:") as source, tarfile.open(target, "w", format=tarfile.USTAR_FORMAT) as out:
        for header in source:
            data = source.extractfile(header).read()
            results = transform(header, data)
            if results is None:
                results = [(header, data)]
            for item, content in results:
                item.size = len(content) if item.isreg() else 0
                out.addfile(item, io.BytesIO(content) if item.isreg() else None)
    return target


def test_roundtrip_pins_baseline_preserves_source_and_is_idempotent(snapshot):
    repo = snapshot["repo"]
    _write(repo / "README.md", b"a later transport-only commit\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "--quiet", "-m", "Later active HEAD")
    head, refs, index = (_git(repo, "rev-parse", "HEAD"), _git(repo, "show-ref"),
                         (repo / ".git/index").read_bytes())
    _write(repo / ".env", b"SECRET_TEST_SENTINEL_DO_NOT_ARCHIVE")
    _write(repo / "results/Q15-E005/source_validation.json", b"dirty unvalidated working tree")
    archive, manifest = _export(snapshot)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "show-ref") == refs and (repo / ".git/index").read_bytes() == index
    with tarfile.open(archive, "r:") as tar:
        assert set(tar.getnames()) == bundle._archive_allowlist() | {"migration_manifest.json"}
        assert all(item.isreg() for item in tar)
    assert len(manifest["files"]) == 233
    assert sum(row["path"].endswith(".npz") for row in manifest["files"]) == 106
    assert sum(row["path"].endswith(".csv") for row in manifest["files"]) == 106
    workspace = snapshot["tmp"] / "new-workspace"
    digest = bundle.sha256_file(archive)
    receipt = bundle.restore_bundle(archive, workspace, digest)
    paths = receipt["paths"]
    assert _git(Path(paths["repo"]), "rev-parse", "HEAD") == snapshot["base"]
    assert _git(Path(paths["repo"]), "remote", "get-url", "origin") == bundle.ORIGIN_URL
    assert receipt["source_fit_count"] == 15 and receipt["source_only_reuse"] is True
    assert receipt["paths_verified"] is True and receipt["archive_sha256"] == digest
    assert receipt["manifest_sha256"] == bundle.sha256_file(paths["manifest"])
    assert bundle.validate_restored_paths(workspace, manifest)
    receipt_bytes = (workspace / "q15-migration/restore_receipt.json").read_bytes()
    assert bundle.restore_bundle(archive, workspace, digest) == receipt
    assert (workspace / "q15-migration/restore_receipt.json").read_bytes() == receipt_bytes
    assert not (Path(paths["repo"]) / ".env").exists()


def test_public_baseline_verifier_preserves_original_models_without_archive(snapshot):
    proof = bundle.verify_source_baseline(snapshot["repo"], snapshot["base"])
    assert proof["source_fit_count"] == 15
    assert proof["deep_fit_count"] == 14 and proof["shallow_fit_count"] == 1
    assert proof["new_source_fits"] == proof["target_fits"] == 0
    assert proof["verified_source_artifacts"] == len(snapshot["report"]["artifact_sha256"])
    assert len(proof["bnci_files"]) == 18
    checkpoint = next((snapshot["repo"] / bundle.SOURCE_ROOT).rglob("checkpoint.pt"))
    checkpoint.write_bytes(b"changed working tree checkpoint")
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.verify_source_baseline(snapshot["repo"], snapshot["base"])
    assert rejection.value.code == "destination_conflict"


def test_shallow_origin_exports_self_contained_history_without_unshallowing(snapshot):
    shallow = snapshot["tmp"] / "shallow"
    subprocess.run(["git", "clone", "--quiet", "--depth", "1", snapshot["repo"].as_uri(), str(shallow)],
                   check=True)
    assert _git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    original_shallow = (shallow / ".git/shallow").read_bytes()
    archive, _ = _export(snapshot, repo=shallow)
    assert (shallow / ".git/shallow").read_bytes() == original_shallow
    receipt = bundle.restore_bundle(archive, snapshot["tmp"] / "restored", bundle.sha256_file(archive))
    restored = Path(receipt["paths"]["repo"])
    assert _git(restored, "rev-parse", "--is-shallow-repository") == "false"
    assert _git(restored, "rev-list", "--count", "HEAD") == "2"


def test_restore_keeps_existing_launcher_jobs_and_flattened_transport_receipt(snapshot):
    archive, _ = _export(snapshot)
    workspace = snapshot["tmp"] / "restored"
    log = workspace / "q15-migration/jobs/new-job/supervisor.log"
    _write(log, b"existing launcher log\n")
    digest = bundle.sha256_file(archive)
    receipt = bundle.restore_bundle(archive, workspace, digest)
    assert log.read_bytes() == b"existing launcher log\n"
    receipt.update(status="raw_originals_verified_ready_for_continuation",
                   object_key="q15/migrations/origin/archive/validated-source-and-epochs.tar",
                   full_get_verified=True, raw_originals_verified=160,
                   ready_for_continuation=True, new_source_fits=0,
                   origin_source_fits=15, target_fits=0, pod_stop_requested=False)
    receipt_path = workspace / "q15-migration/restore_receipt.json"
    _write(receipt_path, receipt)
    existing_bytes = receipt_path.read_bytes()
    assert bundle.restore_bundle(archive, workspace, digest) == receipt
    assert receipt_path.read_bytes() == existing_bytes
    assert log.read_bytes() == b"existing launcher log\n"


@pytest.mark.parametrize("defect", ["unknown_receipt_field", "wrong_origin", "unrelated_custody_file"])
def test_restore_rejects_changed_custody_without_clobbering(snapshot, defect):
    archive, _ = _export(snapshot)
    workspace = snapshot["tmp"] / "restored"
    digest = bundle.sha256_file(archive)
    receipt = bundle.restore_bundle(archive, workspace, digest)
    receipt_path = workspace / "q15-migration/restore_receipt.json"
    if defect == "unknown_receipt_field":
        receipt["untrusted_override"] = True
    elif defect == "wrong_origin":
        receipt["origin_job_id"] = "wrong-job"
    else:
        _write(workspace / "q15-migration/keep.txt", b"unrelated custody content")
    _write(receipt_path, receipt)
    original = receipt_path.read_bytes()
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(archive, workspace, digest)
    assert rejection.value.code == "destination_conflict"
    assert receipt_path.read_bytes() == original


@pytest.mark.parametrize("field,value", [("passed", False), ("deep_fit_count", 13),
                                        ("external_predictions_computed", True)])
def test_export_rejects_unvalidated_committed_source_before_writing(snapshot, monkeypatch, field, value):
    report = dict(snapshot["report"])
    report[field] = value
    _write(snapshot["repo"] / f"{bundle.SOURCE_ROOT}/source_validation.json", report)
    _git(snapshot["repo"], "add", ".")
    _git(snapshot["repo"], "commit", "--quiet", "-m", "Synthetic invalid validation")
    snapshot["base"] = _git(snapshot["repo"], "rev-parse", "HEAD")
    monkeypatch.setattr(bundle, "BASE_COMMIT", snapshot["base"])
    with pytest.raises(bundle.MigrationError, match="provenance gate") as rejection:
        _export(snapshot)
    assert rejection.value.code == "source_not_validated"
    assert not (snapshot["tmp"] / "snapshot.tar").exists()


def test_committed_checkpoint_change_rejected_without_deserializing(snapshot, monkeypatch):
    checkpoint = next((snapshot["repo"] / bundle.SOURCE_ROOT).rglob("checkpoint.pt"))
    checkpoint.write_bytes(b"changed opaque checkpoint")
    _git(snapshot["repo"], "add", ".")
    _git(snapshot["repo"], "commit", "--quiet", "-m", "Synthetic bad checkpoint")
    snapshot["base"] = _git(snapshot["repo"], "rev-parse", "HEAD")
    monkeypatch.setattr(bundle, "BASE_COMMIT", snapshot["base"])
    with pytest.raises(bundle.MigrationError) as rejection:
        _export(snapshot)
    assert rejection.value.code == "source_hash_mismatch"


@pytest.mark.parametrize("relative", ["Cho2017/s01.npz", "Lee2019_MI/s54.csv"])
def test_epoch_bytes_must_match_committed_manifests(snapshot, relative):
    (snapshot["epochs"] / relative).write_bytes(b"changed opaque epochs")
    with pytest.raises(bundle.MigrationError) as rejection:
        _export(snapshot)
    assert rejection.value.code == "epoch_hash_mismatch"
    assert not (snapshot["tmp"] / "snapshot.tar").exists()


def test_change_after_packaging_is_detected_and_partial_archive_removed(snapshot, monkeypatch):
    add = bundle._add_verified_file
    target = snapshot["epochs"] / "Cho2017/s01.npz"

    def changed(archive, path, record):
        add(archive, path, record)
        if path == target:
            path.write_bytes(b"changed after streaming")

    monkeypatch.setattr(bundle, "_add_verified_file", changed)
    with pytest.raises(bundle.MigrationError) as rejection:
        _export(snapshot)
    assert rejection.value.code == "source_changed"
    assert not (snapshot["tmp"] / "snapshot.tar").exists()
    assert not list(snapshot["tmp"].glob(".q15-export-*"))


@pytest.mark.parametrize("defect", ["traversal", "absolute", "symlink", "hardlink", "duplicate",
                                     "credential", "private", "prediction", "missing", "oversized"])
def test_unsafe_archive_rejected_before_destination_mutation(snapshot, defect):
    archive, _ = _export(snapshot)
    first = [True]

    def corrupt(header, data):
        if not first[0]:
            return None
        first[0] = False
        if defect == "missing":
            return []
        if defect == "duplicate":
            return [(header, data), (header, data)]
        if defect in ("symlink", "hardlink"):
            header.type = tarfile.SYMTYPE if defect == "symlink" else tarfile.LNKTYPE
            header.linkname = "/tmp/escape"
        else:
            header.name = {"traversal": "../escape", "absolute": "/tmp/escape",
                           "credential": ".env", "private": "private/token.json",
                           "prediction": "predictions.csv", "oversized": "migration_manifest.json"}[defect]
            if defect == "oversized":
                data = b"x" * (bundle.MAX_MANIFEST_BYTES + 1)
        return [(header, data)]

    bad = _rewrite(archive, snapshot["tmp"] / "bad.tar", corrupt)
    destination = snapshot["tmp"] / "destination"
    with pytest.raises(bundle.MigrationError):
        bundle.restore_bundle(bad, destination, bundle.sha256_file(bad))
    assert not destination.exists()


def test_member_hash_mismatch_and_archive_sha_mismatch_are_distinct(snapshot):
    archive, _ = _export(snapshot)
    destination = snapshot["tmp"] / "destination"
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(archive, destination, "0" * 64)
    assert rejection.value.code == "archive_hash_mismatch" and not destination.exists()

    def changed(header, data):
        if header.name.endswith("s01.npz"):
            return [(header, b"x" * len(data))]

    bad = _rewrite(archive, snapshot["tmp"] / "changed.tar", changed)
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(bad, destination, bundle.sha256_file(bad))
    assert rejection.value.code == "member_hash_mismatch" and not destination.exists()


def test_rewritten_outer_hashes_cannot_override_committed_epoch_provenance(snapshot):
    archive, _ = _export(snapshot)
    data_name = "epochs/Cho2017/s01.npz"
    changed = b"adversarial synthetic epoch"

    def corrupt(header, data):
        if header.name == "migration_manifest.json":
            manifest = json.loads(data)
            for row in manifest["files"]:
                if row["path"] == data_name:
                    row.update(bytes=len(changed), sha256=_sha(changed))
            return [(header, bundle._json_bytes(manifest))]
        if header.name == data_name:
            return [(header, changed)]

    bad = _rewrite(archive, snapshot["tmp"] / "forged.tar", corrupt)
    destination = snapshot["tmp"] / "destination"
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(bad, destination, bundle.sha256_file(bad))
    assert rejection.value.code == "epoch_hash_mismatch" and not destination.exists()


def test_restore_refuses_occupied_paths_and_tampered_idempotent_copy(snapshot):
    archive, _ = _export(snapshot)
    destination = snapshot["tmp"] / "destination"
    sentinel = destination / "q15-execution/repo/keep.txt"
    _write(sentinel, b"existing unrelated work")
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(archive, destination, bundle.sha256_file(archive))
    assert rejection.value.code == "destination_conflict"
    assert sentinel.read_bytes() == b"existing unrelated work"
    assert not (destination / "q15-data").exists()

    second = snapshot["tmp"] / "second"
    bundle.restore_bundle(archive, second, bundle.sha256_file(archive))
    target = second / "q15-data/epochs/Cho2017/s01.npz"
    target.write_bytes(b"changed local restored data")
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(archive, second, bundle.sha256_file(archive))
    assert rejection.value.code == "destination_conflict"
    assert target.read_bytes() == b"changed local restored data"


def test_symlinked_source_directory_and_destination_are_rejected(snapshot):
    actual = snapshot["epochs"] / "Cho2017"
    moved = snapshot["tmp"] / "moved-epochs"
    actual.rename(moved)
    actual.symlink_to(moved, target_is_directory=True)
    with pytest.raises(bundle.MigrationError) as rejection:
        _export(snapshot)
    assert rejection.value.code == "unsafe_path"
    actual.unlink()
    moved.rename(actual)
    archive, _ = _export(snapshot)
    other = snapshot["tmp"] / "other"
    other.mkdir()
    linked = snapshot["tmp"] / "linked"
    linked.symlink_to(other, target_is_directory=True)
    with pytest.raises(bundle.MigrationError) as rejection:
        bundle.restore_bundle(archive, linked, bundle.sha256_file(archive))
    assert rejection.value.code == "unsafe_path" and not list(other.iterdir())


def test_cli_emits_safe_machine_readable_errors_without_file_reads(tmp_path, capsys):
    assert bundle.main(["restore", "--archive", str(tmp_path / "secret.env"),
                        "--expected-archive-sha256", "invalid"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.err)["error"] == "archive_hash_mismatch"
    assert "secret.env" not in output.err
