"""R2 restoration with synthetic bytes and frozen-function doubles only.

These tests never fit a model, load EEG, use CUDA, call an external API, or
stop a real Pod. The real custody schema validates the synthetic receipts.
"""
import hashlib
import importlib.util
import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "research_runs/Q15-MIGRATION-20261004"


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, HELPERS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


restore = load_helper("q15_restore_from_r2")
continuation = load_helper("q15_continue_validated")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return path


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fixture_pipeline(tmp_path, monkeypatch, fail_at=None, fail_backup=False,
                     inventory_counts=(160, 18), capacity=150):
    events, publications = [], []
    args = restore.arguments(tmp_path, "new-job", continuation)
    repo = args.repo
    repo.mkdir(parents=True)
    source_artifact = repo / "results/Q15-E005/source/synthetic-checkpoint.bin"
    source_artifact.parent.mkdir(parents=True)
    source_artifact.write_bytes(b"validated original checkpoint")
    source_report = {"artifact_sha256": {
        str(source_artifact.relative_to(repo)): continuation.sha(source_artifact)}}
    write_json(repo / "results/Q15-E005/source_validation.json", source_report)
    epochs = {}
    for dataset, count in restore.DATASETS.items():
        persons = []
        for subject in range(1, count + 1):
            row = {"subject": subject}
            for field, suffix, checksum in (("npz_path", ".npz", "npz_sha256"),
                                            ("metadata_path", ".csv", "metadata_sha256")):
                path = Path(args.epoch_dir) / dataset / (f"s{subject:02d}" + suffix)
                content = (dataset + str(subject) + suffix).encode()
                row[field], row[checksum] = str(path), digest(content)
            persons.append(row)
        manifest = {"dataset": dataset, "subjects": persons}
        published = write_json(repo / "results/Q15-EXTERNAL/manifests" / (dataset + ".json"), manifest)
        epochs[dataset] = published.read_bytes()

    def event(name):
        events.append(name)
        if fail_at == name:
            raise RuntimeError("FAKE-PRIVATE-SECRET should never appear in public reports")

    def prohibited(*args, **kwargs):
        pytest.fail("A source fit or real scientific computation was attempted")

    def prepare_dataset(dataset, directory):
        event("regenerate-" + dataset)
        for person in json.loads(epochs[dataset])["subjects"]:
            for field, suffix in (("npz_path", ".npz"), ("metadata_path", ".csv")):
                path = Path(person[field])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((dataset + str(person["subject"]) + suffix).encode())
        manifest = Path(directory) / "epoch_manifest.json"
        manifest.write_bytes(epochs[dataset])
        return manifest

    source = SimpleNamespace(_verify_committed_freeze=lambda: event("source-freeze"),
                             run_source=prohibited, _fit=prohibited,
                             _fit_deep=prohibited, _fit_csp=prohibited)
    validator = SimpleNamespace(validate_source=lambda path, write_report=False:
                                (event("source-validation-replay") or dict(source_report)))
    preprocessor = SimpleNamespace(prepare_dataset=prepare_dataset)

    def pod_request(token, pod, method="GET", action=""):
        assert token == "FAKE-RUNPOD" and pod == "new-pod"
        event("stop-new-pod" if action else "reinspect-new-pod")
        return {"pod_id": pod, "http_status": 200}

    @contextmanager
    def lock(path):
        event("acquire-scientific-lock")
        yield
        event("release-scientific-lock")

    cloud = SimpleNamespace(current_pod_id=lambda: "new-pod", runpod_request=pod_request,
                            acquire_job_lock=lock)
    modules = {"q15_source": source, "q15_validate_source": validator,
               "q15_preprocess_external": preprocessor, "q15_cloud.q15_cloud_job": cloud}

    class Publisher:
        def __init__(self, token, branch, path):
            assert token == "FAKE-GITHUB" and branch == "q15/run-new-job"
            self.branch, self.receipts = branch, []

        def commit(self, paths, message):
            state = json.loads(Path(paths[0]).read_text())
            event("publish-" + state["status"])
            publications.append(dict(state))
            verified = not (fail_backup and state["status"] == "r2_restore_failed_or_blocked")
            receipt = {"branch": self.branch, "commit": "a" * 40,
                       "readback_verified": verified}
            self.receipts.append(receipt)
            return receipt

    def preflight(args, publisher):
        event("source-cuda-github-pod-preflight")
        return {"pod_id": "new-pod", "disk_capacity_gb": capacity}

    def git(*arguments):
        if arguments[0] in ("diff", "ls-files"):
            return b""
        if arguments[:1] == ("show",):
            name = arguments[1].rsplit("/", 1)[-1].removesuffix(".json")
            return epochs[name]
        pytest.fail("Unexpected scientific checkout command")

    full = SimpleNamespace(ROOT=repo, PINNED_PATHS=("scripts", "src"), Publisher=Publisher,
        preflight=preflight, git=git, now=lambda: "2026-10-05T00:00:00+00:00",
        atomic_json=write_json, workspace_allocated_bytes=lambda path: 0)

    records = []
    for dataset, count in (("BNCI2014_001", inventory_counts[1]),
                           ("Cho2017", min(52, inventory_counts[0])),
                           ("Lee2019_MI", max(0, inventory_counts[0] - 52))):
        for index in range(count):
            name = dataset + str(index) + ".mat"
            content = name.encode()
            records.append({"dataset": dataset, "file_id": name,
                "path": str(Path(args.raw_dir) / dataset / name),
                "r2_object_key": "synthetic/" + name, "sha256": digest(content),
                "size_bytes": len(content), "md5": hashlib.md5(content).hexdigest()})

    def download(client, bucket, object_key, path, expected_sha, expected_size, expected_md5=None):
        event("download-original")
        content = Path(path).name.encode()
        assert digest(content) == expected_sha and len(content) == expected_size
        assert hashlib.md5(content).hexdigest() == expected_md5
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"verified": True, "sha256": expected_sha, "size_bytes": expected_size}

    transport = SimpleNamespace(
        load_raw_inventory=lambda *a, **k: [row for row in records if row["dataset"] != "BNCI2014_001"],
        load_bnci_inventory=lambda *a, **k: [row for row in records if row["dataset"] == "BNCI2014_001"],
        make_s3=lambda: (event("r2-client") or ("fake-client", "fake-bucket")),
        probe_r2=lambda *a: (event("r2-list-write-readback-delete") or {"verified": True}),
        download_verified=download)
    bundle = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "q15_continue_validated", continuation)
    monkeypatch.setitem(sys.modules, "q15_migration_transport", transport)
    monkeypatch.setitem(sys.modules, "q15_migration_bundle", bundle)
    monkeypatch.setenv("GH_TOKEN", "FAKE-GITHUB")
    monkeypatch.setenv("RUNPOD_API_KEY", "FAKE-RUNPOD")
    monkeypatch.setattr(restore, "ensure_public_baseline", lambda *a, **k:
                        (event("public-baseline") or repo))
    monkeypatch.setattr(restore, "verify_source_checkout", lambda *a:
                        (event("immutable-source-checkpoint-bindings") or {"verified_source_artifacts": 1}))
    monkeypatch.setattr(continuation, "load_restored_full", lambda args: full)
    monkeypatch.setattr(continuation, "restored_module", lambda full, name: modules[name])
    monkeypatch.setattr(continuation, "verify_continuation_head", lambda *a:
                        event("published-resume-head-custody"))
    job_directory = tmp_path / "q15-migration/jobs/new-job"
    job_directory.mkdir(parents=True)
    install = lambda repo, log: event("install-pinned-runtime")
    return SimpleNamespace(args=args, events=events, publications=publications, full=full,
        transport=transport, cloud=cloud, modules=modules, records=records, epochs=epochs,
        job_directory=job_directory, install=install)


def run_fixture(fixture):
    return restore.restore_from_r2(Path(fixture.args.workspace), "new-job", fixture.job_directory,
                                    Path(fixture.args.workspace) / "private-install.log", fixture.install)


def test_all_178_originals_and_106_epoch_subjects_generate_strict_compatible_receipt(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    receipt = run_fixture(fixture)
    assert fixture.events.count("download-original") == 178
    assert receipt["raw_originals_verified"] == 160 and receipt["bnci_originals_verified"] == 18
    assert receipt["epoch_person_count"] == 106 and receipt["source_fit_count"] == 15
    assert "archive_sha256" not in receipt
    assert continuation.validate_restore_receipt(fixture.args) == receipt
    assert all(row["new_source_fits"] == 0 and row["target_fits"] == 0 for row in fixture.publications)
    events = fixture.events
    assert events.index("immutable-source-checkpoint-bindings") < events.index("source-cuda-github-pod-preflight")
    assert events.index("source-cuda-github-pod-preflight") < events.index("r2-list-write-readback-delete")
    assert events.index("r2-list-write-readback-delete") < events.index("download-original")
    assert events.index("source-validation-replay") < events.index("regenerate-Cho2017")
    assert "stop-new-pod" not in events


@pytest.mark.parametrize("fail_at", ["immutable-source-checkpoint-bindings", "install-pinned-runtime",
    "published-resume-head-custody", "source-cuda-github-pod-preflight"])
def test_preflight_or_resume_identity_failure_never_downloads_or_stops(tmp_path, monkeypatch, fail_at):
    fixture = fixture_pipeline(tmp_path, monkeypatch, fail_at=fail_at)
    with pytest.raises(RuntimeError):
        run_fixture(fixture)
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events
    assert not Path(fixture.args.restore_receipt).exists()


@pytest.mark.parametrize("counts", [(159, 18), (160, 17)])
def test_incomplete_inventory_cannot_download_or_claim_ready(tmp_path, monkeypatch, counts):
    fixture = fixture_pipeline(tmp_path, monkeypatch, inventory_counts=counts)
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert "download-original" not in fixture.events
    assert not Path(fixture.args.restore_receipt).exists()
    assert fixture.events.index("publish-r2_restore_failed_or_blocked") < fixture.events.index("stop-new-pod")


def test_purchased_quota_counts_remaining_bytes_and_headroom_before_transfer(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch, capacity=26)
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert "r2-client" not in fixture.events and "download-original" not in fixture.events
    assert not Path(fixture.args.restore_receipt).exists()


@pytest.mark.parametrize("fail_at", ["r2-list-write-readback-delete", "download-original",
                                     "source-validation-replay", "regenerate-Lee2019_MI"])
def test_authenticated_failed_setup_stops_only_new_pod_after_verified_github_backup(tmp_path, monkeypatch,
                                                                                   fail_at):
    fixture = fixture_pipeline(tmp_path, monkeypatch, fail_at=fail_at)
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert not Path(fixture.args.restore_receipt).exists()
    assert fixture.events.index("publish-r2_restore_failed_or_blocked") < fixture.events.index("reinspect-new-pod")
    assert fixture.events.index("reinspect-new-pod") < fixture.events.index("stop-new-pod")
    state = json.loads((fixture.job_directory / "migration_status.json").read_text())
    assert state["scientific_validation_passed"] is False
    assert "FAKE-PRIVATE-SECRET" not in json.dumps(state)
    stop = json.loads((tmp_path / "q15-execution/jobs/new-job/stop_api_receipt.json").read_text())
    assert stop["pod_id"] == "new-pod" and stop["physical_shutdown_confirmed"] is False


def test_failed_failure_backup_forbids_pod_stop(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch, fail_at="regenerate-Lee2019_MI", fail_backup=True)
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert "stop-new-pod" not in fixture.events and "reinspect-new-pod" not in fixture.events
    assert json.loads((fixture.job_directory / "migration_status.json").read_text())["status"] == (
        "r2_restore_manual_attention_required")


def test_pod_identity_change_after_failure_backup_forbids_stop(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch, fail_at="regenerate-Lee2019_MI")
    identity = iter(("new-pod", "different-pod"))
    fixture.cloud.current_pod_id = lambda: next(identity)
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert "stop-new-pod" not in fixture.events and "reinspect-new-pod" not in fixture.events


def test_remaining_byte_plan_accounts_for_valid_partials_without_treating_them_as_verified(tmp_path):
    complete, partial, missing = (tmp_path / name for name in ("complete.mat", "partial.mat", "missing.mat"))
    complete.write_bytes(b"x" * 9)
    partial.with_suffix(".mat.part").write_bytes(b"x" * 6)
    records = [{"path": str(path), "size_bytes": 10} for path in (complete, partial, missing)]
    assert restore.remaining_download_bytes(records) == 15


def test_full_size_but_corrupt_existing_file_still_reaches_transfer_hash_verification(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    for row in fixture.records:
        path = Path(row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * row["size_bytes"])
    assert restore.remaining_download_bytes(fixture.records) == 0
    run_fixture(fixture)
    assert fixture.events.count("download-original") == 178


@pytest.mark.parametrize("mutation", [{"verified": False}, {"sha256": "f" * 64},
    {"size_bytes": 7}, {"size_bytes": 8.0}, {"size_bytes": True}, {"size_bytes": None}])
def test_download_identity_failure_cannot_be_reported_as_verified(tmp_path, mutation):
    record = {"dataset": "Cho2017", "file_id": "s01.mat", "path": str(tmp_path / "s01.mat"),
              "r2_object_key": "synthetic/s01.mat", "sha256": "a" * 64, "size_bytes": 8}
    transport = SimpleNamespace(download_verified=lambda *args, **kwargs:
        {"verified": True, "sha256": record["sha256"], "size_bytes": 8, **mutation})
    progress = []
    with pytest.raises(restore.RestorationError):
        restore.download_originals(transport, "client", "bucket", [record], lambda *args: progress.append(args))
    assert progress == []


def test_regeneration_requires_byte_identical_original_published_manifest(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    original = fixture.modules["q15_preprocess_external"].prepare_dataset

    def altered(dataset, directory):
        result = original(dataset, directory)
        result.write_text(result.read_text() + " ")
        return result

    fixture.modules["q15_preprocess_external"].prepare_dataset = altered
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert not Path(fixture.args.restore_receipt).exists()


def test_existing_identical_epochs_are_hashed_and_reused_without_regeneration(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    for dataset in restore.DATASETS:
        fixture.modules["q15_preprocess_external"].prepare_dataset(dataset, Path(fixture.args.epoch_dir) / dataset)
    fixture.events.clear()
    run_fixture(fixture)
    assert "regenerate-Cho2017" not in fixture.events and "regenerate-Lee2019_MI" not in fixture.events
    assert "source-validation-replay" in fixture.events


def test_corrupt_processed_artifact_is_regenerated_before_ready(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    for dataset in restore.DATASETS:
        fixture.modules["q15_preprocess_external"].prepare_dataset(dataset, Path(fixture.args.epoch_dir) / dataset)
    (Path(fixture.args.epoch_dir) / "Cho2017/s01.npz").write_bytes(b"corrupt")
    fixture.events.clear()
    run_fixture(fixture)
    assert "regenerate-Cho2017" in fixture.events and "regenerate-Lee2019_MI" not in fixture.events


def test_public_resume_head_uses_same_job_receipt_to_allow_progressed_checkout(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    publication = tmp_path / "q15-execution/jobs/new-job/github_publication_receipt.json"
    write_json(publication, {"readback_verified": True})
    observed = []
    monkeypatch.setattr(restore, "ensure_public_baseline", lambda repo, allow_published_resume=False:
                        (observed.append(allow_published_resume) or repo))
    run_fixture(fixture)
    assert observed == [True]
    assert fixture.events.index("published-resume-head-custody") < fixture.events.index("download-original")


def source_binding_fixture(tmp_path, monkeypatch):
    artifact_name = "results/Q15-E005/source/checkpoint.bin"
    artifact = tmp_path / artifact_name
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"original validated source checkpoint")
    source_report = {"artifact_sha256": {artifact_name: digest(artifact.read_bytes())}}
    validation = write_json(tmp_path / "results/Q15-E005/source_validation.json", source_report)
    requirements = tmp_path / "requirements-q15-runtime.txt"
    requirements.write_bytes(b"numpy==2.5.3\n")
    committed = {
        "results/Q15-E005/source_validation.json": validation.read_bytes(),
        "requirements-q15-runtime.txt": requirements.read_bytes(),
    }
    commands, bindings = [], []

    def public_git(repo, *arguments):
        assert repo == tmp_path
        commands.append(arguments)
        if arguments[0] == "merge-base":
            return b""
        assert arguments[0] == "show" and arguments[1].startswith(restore.BASE + ":")
        return committed[arguments[1].split(":", 1)[1]]

    monkeypatch.setattr(restore, "public_git", public_git)
    bundle = SimpleNamespace(_verify_source_baseline=lambda repo, revision:
                             bindings.append((repo, revision)))
    return SimpleNamespace(repo=tmp_path, bundle=bundle, commands=commands, bindings=bindings,
                            artifact=artifact, validation=validation, requirements=requirements)


def test_source_checkout_requires_scientific_ancestry_and_immutable_ledger_bytes(tmp_path, monkeypatch):
    fixture = source_binding_fixture(tmp_path, monkeypatch)
    proof = restore.verify_source_checkout(fixture.repo, fixture.bundle, continuation)
    assert proof == {"verified_source_artifacts": 1}
    assert fixture.bindings == [(tmp_path, restore.BASE)]
    assert fixture.commands[:2] == [
        ("merge-base", "--is-ancestor", restore.SCIENCE, restore.BASE),
        ("merge-base", "--is-ancestor", restore.BASE, "HEAD")]


@pytest.mark.parametrize("name,expected_code", [
    ("artifact", "public_source_artifact_bytes_changed"),
    ("validation", "public_source_validation_bytes_changed"),
    ("requirements", "pinned_dependency_spec_changed")])
def test_public_source_binding_rejects_rewritten_checkpoint_report_or_runtime_pins(tmp_path, monkeypatch,
                                                                                  name, expected_code):
    fixture = source_binding_fixture(tmp_path, monkeypatch)
    getattr(fixture, name).write_bytes(b"changed")
    with pytest.raises(restore.RestorationError) as error:
        restore.verify_source_checkout(fixture.repo, fixture.bundle, continuation)
    assert error.value.safe_code == expected_code


def test_parallel_transfers_are_bounded_and_verified_before_progress(tmp_path):
    counter_lock = threading.Lock()
    barrier = threading.Barrier(4)
    active, peak = 0, 0

    def download(client, bucket, key, path, sha256, size_bytes, expected_md5=None):
        nonlocal active, peak
        with counter_lock:
            active += 1
            peak = max(peak, active)
        barrier.wait(timeout=5)
        with counter_lock:
            active -= 1
        return {"verified": True, "sha256": sha256, "size_bytes": size_bytes}

    rows = [{"dataset": "Cho2017", "file_id": f"s{subject:02d}.mat", "size_bytes": 8,
             "path": str(tmp_path / (f"s{subject:02d}.mat")), "r2_object_key": str(subject),
             "sha256": "a" * 64} for subject in range(1, 9)]
    progress = []
    result = restore.download_originals(SimpleNamespace(download_verified=download), "client", "bucket", rows,
                                       lambda *args: progress.append(args))
    assert peak == 4 and len(result) == 8
    assert [row[0] for row in progress] == list(range(1, 9))
    assert [row[2] for row in progress] == [8 * number for number in range(1, 9)]


def test_ready_reuse_requires_real_custody_validation_and_never_redownloads(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    first = run_fixture(fixture)
    fixture.events.clear()
    assert run_fixture(fixture) == first
    assert "install-pinned-runtime" in fixture.events
    assert "immutable-source-checkpoint-bindings" in fixture.events
    assert "download-original" not in fixture.events and "regenerate-Cho2017" not in fixture.events
    assert "stop-new-pod" not in fixture.events


def test_ready_reuse_changed_checkpoint_is_rejected_without_download_or_stop(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    run_fixture(fixture)
    fixture.events.clear()
    (fixture.args.repo / "results/Q15-E005/source/synthetic-checkpoint.bin").write_bytes(b"changed")
    with pytest.raises(continuation.ContinuationError):
        run_fixture(fixture)
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events


def test_restore_never_forges_archive_hash_to_reuse_r2_receipt(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    receipt = run_fixture(fixture)
    receipt["archive_sha256"] = "f" * 64
    write_json(fixture.args.restore_receipt, receipt)
    fixture.events.clear()
    with pytest.raises(continuation.ContinuationError) as error:
        run_fixture(fixture)
    assert error.value.safe_code == "r2_restore_archive_identity_forbidden"
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events


def test_archive_restore_receipt_cannot_be_mistaken_for_r2_only_method(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    write_json(fixture.args.restore_receipt, {"kind": "q15_validated_source_and_epochs_restore"})
    with pytest.raises(restore.RestorationError) as error:
        run_fixture(fixture)
    assert error.value.safe_code == "existing_restore_method_conflicts_with_r2_restore"
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events


def test_ready_reuse_still_requires_original_baseline_bindings_even_with_ready_receipt(tmp_path, monkeypatch):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    run_fixture(fixture)
    fixture.events.clear()

    def reject_binding(*args):
        raise restore.RestorationError("public_source_validation_bytes_changed")

    monkeypatch.setattr(restore, "verify_source_checkout", reject_binding)
    with pytest.raises(restore.RestorationError) as error:
        run_fixture(fixture)
    assert error.value.safe_code == "public_source_validation_bytes_changed"
    assert "install-pinned-runtime" not in fixture.events
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events


@pytest.mark.parametrize("reported", [restore.ORIGIN_POD, "different-pod", None])
def test_preflight_pod_identity_mismatch_never_downloads_or_requests_stop(tmp_path, monkeypatch, reported):
    fixture = fixture_pipeline(tmp_path, monkeypatch)
    fixture.full.preflight = lambda *args: {"pod_id": reported, "disk_capacity_gb": 150}
    with pytest.raises(restore.RestorationError):
        run_fixture(fixture)
    assert "download-original" not in fixture.events and "stop-new-pod" not in fixture.events
    assert not Path(fixture.args.restore_receipt).exists()
