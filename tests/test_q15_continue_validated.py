"""Operational continuation doubles: no GPU, optimizer, EEG replay, or live API."""
import hashlib
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "q15_continuation_under_test",
    ROOT / "research_runs/Q15-MIGRATION-20261004/q15_continue_validated.py")
continuation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(continuation)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return path


def receipt_fixture(tmp_path, job_id="new-job"):
    args = continuation.canonical_arguments(SimpleNamespace(
        workspace=str(tmp_path), job_id=job_id, revision=continuation.SCIENTIFIC_REVISION,
        restore_receipt=None, check_only=False))
    for directory in (args.repo, Path(args.bnci_dir), Path(args.epoch_dir)):
        directory.mkdir(parents=True, exist_ok=True)
    identity = {"schema_version": 1, "code_base_commit": continuation.CODE_BASE_COMMIT,
                "scientific_revision": continuation.SCIENTIFIC_REVISION,
                "origin_job_id": continuation.ORIGIN_JOB_ID,
                "origin_pod_id": continuation.ORIGIN_POD_ID, "source_fit_count": 15}
    manifest = write_json(tmp_path / "q15-migration/migration_manifest.json", identity)
    restore = {**identity, "kind": "q15_validated_source_and_epochs_restore",
               "source_only_reuse": True, "paths_verified": True,
               "ready_for_continuation": True, "raw_originals_verified": 160,
               "manifest_sha256": continuation.sha(manifest), "archive_sha256": "f" * 64,
               "paths": {"repo": str(args.repo), "raw_dir": args.bnci_dir,
                         "epoch_dir": args.epoch_dir, "manifest": str(manifest)}}
    write_json(args.restore_receipt, restore)
    return args, restore


def r2_receipt_fixture(tmp_path, args=None, restore=None, source_report=None):
    if args is None:
        args, restore = receipt_fixture(tmp_path)
    artifact = args.repo / "results/Q15-E005/source/EEGNetv4/all_source/final_seed_0/checkpoint.pt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"committed-source-checkpoint-fixture")
    artifacts = {str(artifact.relative_to(args.repo)): continuation.sha(artifact)}
    if source_report is None:
        source_report = {}
    source_report["artifact_sha256"] = artifacts
    write_json(args.repo / "results/Q15-E005/source_validation.json", source_report)
    epochs = {}
    for dataset in continuation.DATASETS:
        recorded = args.repo / "results/Q15-EXTERNAL/manifests" / (dataset + ".json")
        if not recorded.exists():
            write_json(recorded, {"dataset": dataset, "synthetic_manifest": True})
        local = Path(args.epoch_dir) / dataset / "epoch_manifest.json"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(recorded.read_bytes())
        epochs[dataset] = {"path": f"epochs/{dataset}/epoch_manifest.json",
                           "sha256": continuation.sha(recorded)}
    identity = {name: restore[name] for name in ("schema_version", "code_base_commit",
        "scientific_revision", "origin_job_id", "origin_pod_id", "source_fit_count")}
    manifest = {**identity, "kind": "q15_committed_source_and_epochs",
        "restore_method": continuation.R2_RESTORE_METHOD, "bnci_original_count": 18,
        "raw_original_count": 160, "epoch_person_count": 106,
        "source_artifacts": artifacts, "epoch_manifests": epochs}
    manifest_path = Path(restore["paths"]["manifest"])
    write_json(manifest_path, manifest)
    restore.pop("archive_sha256", None)
    restore.update({"kind": continuation.R2_RESTORE_KIND,
        "restore_method": continuation.R2_RESTORE_METHOD, "repository_baseline_verified": True,
        "bnci_originals_verified": 18, "epoch_person_count": 106,
        "manifest_sha256": continuation.sha(manifest_path)})
    write_json(args.restore_receipt, restore)
    return args, restore


def pipeline(tmp_path, monkeypatch, fail_at=None, fail_backup=False):
    args, restore = receipt_fixture(tmp_path)
    job = tmp_path / "q15-execution/jobs/new-job"
    job.mkdir(parents=True)
    events, commits, modules = [], [], {}
    monkeypatch.setattr(continuation, "_reject_foreign_scientific_modules", lambda repo: None)

    def event(name):
        events.append(name)
        if name == fail_at:
            raise RuntimeError("private-runpod-key must never be printed")

    def module(name, **attributes):
        path = args.repo / "scripts" / (name.replace(".", "/") + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# restored scientific double\n")
        value = SimpleNamespace(__file__=str(path), **attributes)
        modules[name] = value
        return value

    def forbidden(*args, **kwargs):
        pytest.fail("Source fitting or epoch rewriting is forbidden")

    def committed(path):
        event("verify-committed-" + Path(path).name)

    module("q15_source", _verify_committed_freeze=lambda: event("verify-original-freeze"),
           _assert_committed_unchanged=committed, run_source=forbidden,
           prepare_freeze=forbidden, _fit_deep=forbidden, _fit_csp=forbidden)
    source_report = {"status": "source_validated_non_authorizing", "passed": True,
                     "deep_fit_count": 14, "shallow_fit_count": 1, "target_fits": 0,
                     "source_only": True, "external_prediction_authorized": False,
                     "external_predictions_computed": False,
                     "source_run_config_sha256": "a" * 64}
    report_path = write_json(args.repo / "results/Q15-E005/source_validation.json", source_report)
    run_config = write_json(args.repo / "results/Q15-E005/source/run_config.json",
        {"runtime": {"platform": "old-host", "cuda_device_name": "old-gpu"}})

    def source_validate(output_root, *, write_report):
        assert output_root == args.repo / "results/Q15-E005"
        assert write_report is False
        event("independent-source-replay-readonly")
        return dict(source_report)

    module("q15_validate_source", validate_source=source_validate)
    for dataset, count in continuation.DATASETS.items():
        rows = []
        for subject in range(1, count + 1):
            row = {"subject": subject}
            for field, suffix in (("npz_path", ".npz"), ("metadata_path", ".csv")):
                artifact = Path(args.epoch_dir) / dataset / (f"s{subject:02d}" + suffix)
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(b"processed-fixture")
                row[field] = str(artifact)
            rows.append(row)
        manifest = {"schema_version": 1, "dataset": dataset, "subjects": rows,
                    "status": "epochs_verified_non_authorizing", "target_fits": 0,
                    "predictions_computed": False}
        write_json(args.repo / "results/Q15-EXTERNAL/manifests" / (dataset + ".json"), manifest)
        write_json(Path(args.epoch_dir) / dataset / "epoch_manifest.json", manifest)

    def epoch_validate(path):
        event("raw-to-epoch-replay-" + Path(path).stem)
        return json.loads(Path(path).read_text())

    module("q15_preprocess_external", validate_epoch_manifest=epoch_validate,
           prepare_epochs=forbidden, prepare_dataset=forbidden, preprocess_subject=forbidden)
    freeze_path = args.repo / "results/Q15-EXTERNAL/inference_freeze.json"

    def prepare_freeze(manifests):
        event("prepare-inference-freeze")
        assert set(manifests) == set(continuation.DATASETS)
        return write_json(freeze_path, {"target_fits": 0})

    def run_external(manifests, device):
        assert device == "cuda"
        event("external-inference")

    module("q15_external", prepare_freeze=prepare_freeze,
           verify_freeze=lambda manifests: event("verify-inference-freeze"), run_external=run_external)
    external_report = {"passed": True, "scientific_validation_passed": True,
        "status": "completed_with_calibration_limitations", "target_fits": 0,
        "new_model_fits": 0, "model_state_unchanged": True,
        "source_deep_fit_count": 14, "source_shallow_fit_count": 1,
        "raw_auditor_replayed": True, "raw_to_epoch_replayed": True,
        "frozen_checkpoint_prediction_replayed": True, "statistics_independently_reconstructed": True,
        "calibration_verified": False, "calibration_limitations": continuation.CALIBRATION_LIMITATIONS}
    result_path = args.repo / "results/Q15-EXTERNAL/validation_report.json"

    def external_validate(manifests, *, device_name, write_report):
        assert device_name == "cuda" and write_report is True
        event("independent-external-replay")
        write_json(result_path, external_report)
        return dict(external_report)

    module("q15_validate_external", validate_external=external_validate)

    def pod_request(token, pod, method="GET", action=""):
        assert token == "private-runpod-key" and pod == "new-pod"
        event("stop-new-pod" if action else "reinspect-new-pod")
        return {"pod_id": pod, "http_status": 200}

    cloud = module("q15_cloud.q15_cloud_job", current_pod_id=lambda: "new-pod",
                   runpod_request=pod_request, acquire_job_lock=lambda path: nullcontext())
    monkeypatch.setenv("RUNPOD_API_KEY", "private-runpod-key")
    monkeypatch.setenv("GH_TOKEN", "private-github-key")

    class Publisher:
        def __init__(self, token=None, branch="q15/run-new-job", state_path=None):
            self.receipts = []
            self.head = continuation.CODE_BASE_COMMIT
            self.branch = branch
            self.state_path = state_path

        def verify_access(self):
            event("verify-github-access-and-resume-head")

        def commit(self, paths, message):
            name = ("commit-evidence" if message.startswith("Publish") else
                    "commit-evidence-failure-status" if "evidence failure" in message else
                    "commit-final" if message.startswith("Complete") else
                    "commit-failure" if "failure" in message else
                    "commit-inference-freeze" if message.startswith("Freeze") else "commit-provenance")
            event(name)
            if fail_backup and name == "commit-failure":
                raise RuntimeError("private-github-key unverified backup")
            paths = list(paths)
            commits.append((name, paths))
            for path in paths:
                assert "private-runpod-key" not in Path(path).read_text()
                assert "private-github-key" not in Path(path).read_text()
            self.head = hashlib.sha1(str(len(self.receipts) + 1).encode()).hexdigest()
            receipt = {"readback_verified": True, "branch": self.branch, "commit": self.head,
                "artifact_sha256": {path.relative_to(args.repo).as_posix(): continuation.sha(path)
                                    for path in paths},
                "updated_at_utc": "2026-10-05T00:00:00+00:00",
                "url": "https://github.example.invalid/commit/" + self.head}
            self.receipts.append(receipt)
            return receipt

    publisher = Publisher()

    def preflight(received, received_publisher):
        assert received.revision == continuation.SCIENTIFIC_REVISION
        assert received.bnci_dir == str(tmp_path / "q15-data/raw/BNCI2014_001")
        event("original-full-preflight")
        received_publisher.verify_access()
        return {"pod_id": cloud.current_pod_id(), "gpu_computation_verified": True}

    full = SimpleNamespace(ROOT=args.repo, importlib=SimpleNamespace(import_module=modules.__getitem__),
        now=lambda: "2026-10-04T12:00:00+00:00", atomic_json=write_json,
        git=lambda *arguments: publisher.head.encode(), preflight=preflight, Publisher=Publisher,
        external_artifacts=lambda report: [result_path])
    return SimpleNamespace(args=args, restore=restore, job=job, full=full, publisher=publisher,
        events=events, commits=commits, modules=modules, cloud=cloud, source_report=source_report,
        report_path=report_path, run_config=run_config, external_report=external_report)


def test_complete_reuses_source_and_epochs_before_committed_inference_and_new_pod_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for path in (p.report_path, p.run_config,
                                                  *Path(p.args.epoch_dir).rglob("*.*"))}
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    events = p.events
    assert events.index("verify-original-freeze") < events.index("independent-source-replay-readonly")
    assert events.index("independent-source-replay-readonly") < events.index("raw-to-epoch-replay-Cho2017")
    assert events.index("raw-to-epoch-replay-Lee2019_MI") < events.index("commit-provenance")
    assert events.index("commit-inference-freeze") < events.index("verify-inference-freeze")
    assert events.index("verify-inference-freeze") < events.index("external-inference")
    assert events.index("independent-external-replay") < events.index("commit-final")
    assert events.index("commit-final") < events.index("commit-evidence")
    assert events.index("commit-evidence") < events.index("reinspect-new-pod") < events.index("stop-new-pod")
    assert all(path.read_bytes() == body for path, body in before.items())
    state = json.loads((p.job / "job_status.json").read_text())
    assert state["status"] == "completed_with_calibration_limitations"
    assert state["original_source_fits"] == state["fits_started"] == 15
    assert state["new_source_fits"] == state["target_fits"] == 0
    assert state["source_runtime_provenance_preserved"] is True
    assert state["github_results_backup_verified"] is True
    assert state["results_commit"] == p.publisher.receipts[-2]["commit"]


@pytest.mark.parametrize("failure", ["verify-original-freeze", "independent-source-replay-readonly",
    "raw-to-epoch-replay-Cho2017", "verify-inference-freeze", "independent-external-replay", "commit-final"])
def test_failure_redacts_and_backs_up_before_stopping_only_new_pod(tmp_path, monkeypatch, capsys, failure):
    p = pipeline(tmp_path, monkeypatch, fail_at=failure)
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert p.events.index("commit-failure") < p.events.index("reinspect-new-pod") < p.events.index("stop-new-pod")
    assert p.events.index("commit-failure") < p.events.index("commit-evidence")
    assert p.events.index("commit-evidence") < p.events.index("reinspect-new-pod")
    state = json.loads((p.job / "job_status.json").read_text())
    assert state["scientific_validation_passed"] is False
    assert state["original_source_fits"] == state["fits_started"] == 15
    assert state["new_source_fits"] == state["target_fits"] == 0
    assert "private-runpod-key" not in capsys.readouterr().out
    assert "private-runpod-key" not in json.dumps(state)


def test_unverified_failure_backup_forbids_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch, fail_at="verify-inference-freeze", fail_backup=True)
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "stop-new-pod" not in p.events
    assert json.loads((p.job / "job_status.json").read_text())["status"] == "failed_backup_manual_attention_required"


@pytest.mark.parametrize("preflight_result", [None, {"pod_id": continuation.ORIGIN_POD_ID}, {"pod_id": "other-pod"}])
def test_invalid_or_failed_new_pod_preflight_forbids_inference_and_stop(tmp_path, monkeypatch, preflight_result):
    p = pipeline(tmp_path, monkeypatch)
    def preflight(*args):
        if preflight_result is None:
            raise RuntimeError("invalid new account key")
        return preflight_result
    p.full.preflight = preflight
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "external-inference" not in p.events and "stop-new-pod" not in p.events


def test_original_pod_identity_never_even_runs_preflight(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.cloud.current_pod_id = lambda: continuation.ORIGIN_POD_ID
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "original-full-preflight" not in p.events
    assert "external-inference" not in p.events and "stop-new-pod" not in p.events


def test_pod_changed_or_reinspection_wrong_identity_forbids_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.cloud.runpod_request = lambda *args, **kwargs: {"pod_id": "different-pod"}
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "stop-new-pod" not in p.events
    assert json.loads((p.job / "job_status.json").read_text())["stop_error_code"] == "new_pod_reinspection_identity_mismatch"


def test_readonly_preflight_validates_all_reused_inputs_without_publication_or_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.args.check_only = True
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    assert "raw-to-epoch-replay-Lee2019_MI" in p.events
    assert p.commits == [] and "external-inference" not in p.events and "stop-new-pod" not in p.events
    assert not (p.args.repo / "research_runs/Q15-MIGRATION-20261004/jobs/new-job").exists()


def test_failed_check_only_never_publishes_or_stops_new_pod(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch, fail_at="raw-to-epoch-replay-Cho2017")
    p.args.check_only = True
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert p.commits == [] and "reinspect-new-pod" not in p.events and "stop-new-pod" not in p.events
    assert not (p.args.repo / "research_runs/Q15-MIGRATION-20261004/jobs/new-job").exists()
    assert json.loads((p.job / "job_status.json").read_text())["shutdown_status"] == "not_requested_check_only"


def test_external_status_only_pass_cannot_mark_completion(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.modules["q15_validate_external"].validate_external = lambda *args, **kwargs: {"passed": True, "target_fits": 0}
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "commit-final" not in p.events
    assert json.loads((p.job / "job_status.json").read_text())["scientific_validation_passed"] is False


def test_public_migration_provenance_is_explicit_allowlist(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.restore.update({"endpoint": "private-runpod-key", "bucket": "private-github-key",
                      "old_credentials": {"RUNPOD_API_KEY": "private-runpod-key"}})
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    path = next(path for name, paths in p.commits if name == "commit-provenance"
                for path in paths if path.name == "restored_migration_provenance.json")
    value = json.loads(path.read_text())
    assert value["archive_sha256"] == p.restore["archive_sha256"]
    assert value["origin_job_id"] == continuation.ORIGIN_JOB_ID
    assert not {"endpoint", "bucket", "old_credentials", "paths"} & value.keys()


@pytest.mark.parametrize("field,value", [("ready_for_continuation", False), ("raw_originals_verified", 159),
    ("raw_originals_verified", True), ("source_fit_count", 0), ("paths_verified", False),
    ("scientific_revision", "b" * 40), ("archive_sha256", "not-a-digest"),
    ("origin_pod_id", "different-pod")])
def test_invalid_restore_receipt_blocks_before_frozen_import(tmp_path, monkeypatch, field, value):
    args, restore = receipt_fixture(tmp_path)
    restore[field] = value
    write_json(args.restore_receipt, restore)
    monkeypatch.setattr(continuation, "load_restored_full", lambda args: pytest.fail("Must validate before import"))
    with pytest.raises(continuation.ContinuationError):
        continuation.main(["--job-id", "new-job", "--workspace", str(tmp_path)])


def test_restored_manifest_hash_and_identity_must_match_receipt(tmp_path):
    args, restore = receipt_fixture(tmp_path)
    manifest = Path(restore["paths"]["manifest"])
    manifest.write_text(manifest.read_text() + " ")
    with pytest.raises(continuation.ContinuationError, match="hash_changed"):
        continuation.validate_restore_receipt(args)
    value = json.loads(manifest.read_text())
    value["source_fit_count"] = 14
    write_json(manifest, value)
    restore["manifest_sha256"] = continuation.sha(manifest)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError, match="identity"):
        continuation.validate_restore_receipt(args)


def test_old_job_or_alternate_paths_rejected(tmp_path):
    with pytest.raises(continuation.ContinuationError, match="fresh"):
        receipt_fixture(tmp_path, continuation.ORIGIN_JOB_ID)
    args, restore = receipt_fixture(tmp_path)
    restore["paths"]["epoch_dir"] = str(tmp_path / "alternate")
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError, match="canonical"):
        continuation.validate_restore_receipt(args)


def test_changed_local_epoch_manifest_fails_without_rewriting(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    path = Path(p.args.epoch_dir) / "Cho2017/epoch_manifest.json"
    path.write_text(path.read_text() + " ")
    before = path.read_bytes()
    with pytest.raises(continuation.ContinuationError, match="local_epoch"):
        continuation.verify_reused_science(p.args, p.full)
    assert path.read_bytes() == before


def test_source_replay_must_equal_original_report_and_cannot_rewrite_it(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    before = p.report_path.read_bytes()
    p.modules["q15_validate_source"].validate_source = lambda *args, **kwargs: {**p.source_report, "extra": True}
    with pytest.raises(continuation.ContinuationError, match="not_reproduced"):
        continuation.verify_reused_science(p.args, p.full)
    assert p.report_path.read_bytes() == before


def test_duplicate_workspace_lock_never_constructs_publisher_or_enters_failure_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    monkeypatch.setattr(continuation, "load_restored_full", lambda args: p.full)
    def duplicate(path):
        raise continuation.ContinuationError("another_cloud_supervisor_is_active")
    p.cloud.acquire_job_lock = duplicate
    p.full.Publisher = lambda *args: pytest.fail("Duplicate cannot publish")
    monkeypatch.setattr(continuation, "run", lambda *args: pytest.fail("Duplicate cannot handle stop"))
    with pytest.raises(continuation.ContinuationError, match="another_cloud"):
        continuation.main(["--job-id", "new-job", "--workspace", str(tmp_path)])
    assert p.events == []


def test_only_own_verified_publication_receipt_can_advance_restored_head(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.publisher.head = "c" * 40
    with pytest.raises(continuation.ContinuationError, match="unreceipted"):
        continuation.verify_continuation_head(p.args, p.full, p.publisher)
    p.publisher.receipts = [{"readback_verified": True, "commit": p.publisher.head,
                             "branch": "q15/run-" + continuation.ORIGIN_JOB_ID}]
    with pytest.raises(continuation.ContinuationError, match="unreceipted"):
        continuation.verify_continuation_head(p.args, p.full, p.publisher)
    p.publisher.receipts[-1]["branch"] = "q15/run-new-job"
    continuation.verify_continuation_head(p.args, p.full, p.publisher)
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    assert "verify-github-access-and-resume-head" in p.events


def test_unreceipted_starting_head_cannot_be_legitimized_by_failure_publication(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.publisher.head = "c" * 40
    with pytest.raises(continuation.ContinuationError, match="unreceipted"):
        continuation.run(p.args, p.full, p.publisher, p.job, p.restore)
    assert p.events == [] and p.commits == []
    assert not (p.job / "job_status.json").exists()


def test_resume_remote_head_failure_cannot_create_failure_receipt_or_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.publisher.head = "c" * 40
    p.publisher.receipts = [{"readback_verified": True, "commit": p.publisher.head,
                             "branch": "q15/run-new-job"}]
    def reject_remote():
        raise continuation.ContinuationError("publication_resume_remote_head_mismatch")
    p.publisher.verify_access = reject_remote
    with pytest.raises(continuation.ContinuationError, match="remote_head"):
        continuation.run(p.args, p.full, p.publisher, p.job, p.restore)
    assert p.events == [] and p.commits == []
    assert len(p.publisher.receipts) == 1


def test_main_uses_fresh_private_job_receipt_path_and_current_tokens(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    old_private = tmp_path / "q15-execution/jobs" / continuation.ORIGIN_JOB_ID / "credentials.env"
    old_private.parent.mkdir(parents=True)
    old_private.write_text("OLD_PRIVATE_CREDENTIAL_MUST_NOT_BE_READ")
    seen = []
    real_read_text = Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert continuation.ORIGIN_JOB_ID not in path.parts
        return real_read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    monkeypatch.setattr(continuation, "load_restored_full", lambda args: p.full)
    def publisher(token, branch, state_path):
        seen.append((token, branch, state_path))
        return p.publisher
    p.full.Publisher = publisher
    assert continuation.main(["--job-id", "new-job", "--workspace", str(tmp_path)]) == 0
    assert seen == [("private-github-key", "q15/run-new-job", p.job / "github_publication_receipt.json")]


def test_dynamic_runner_is_loaded_only_from_restored_repo_and_compared_with_baseline(tmp_path, monkeypatch):
    args, _ = receipt_fixture(tmp_path)
    path = args.repo / "scripts/q15_cloud/q15_full_job.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\nRESTORED = True\n"
    path.write_bytes(body)
    calls = []
    def git(repo, *arguments):
        calls.append((repo, arguments))
        return body
    monkeypatch.setattr(continuation, "_git", git)
    monkeypatch.setattr(continuation, "_reject_foreign_scientific_modules", lambda repo: None)
    full = continuation.load_restored_full(args)
    assert full.RESTORED and Path(full.__file__) == path
    assert calls == [(args.repo, ("show", continuation.CODE_BASE_COMMIT + ":scripts/q15_cloud/q15_full_job.py"))]
    monkeypatch.setattr(continuation, "_git", lambda *args: b"different pinned runner")
    with pytest.raises(continuation.ContinuationError, match="changed"):
        continuation.load_restored_full(args)


def test_foreign_cached_scientific_module_rejected(tmp_path, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "q15_source", SimpleNamespace(__file__="/foreign/scripts/q15_source.py"))
    with pytest.raises(continuation.ContinuationError, match="foreign_scientific"):
        continuation._reject_foreign_scientific_modules(tmp_path)


def test_duplicate_json_and_arbitrary_exception_text_are_not_trusted(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text('{"passed":true,"passed":false}')
    with pytest.raises(continuation.ContinuationError, match="duplicate"):
        continuation.read_json(path)
    assert continuation.safe_code(RuntimeError("private token")) == "RuntimeError"


def test_r2_only_receipt_needs_no_archive_identity_and_reuses_committed_source(tmp_path):
    args, restore = r2_receipt_fixture(tmp_path)
    assert "archive_sha256" not in restore
    assert continuation.validate_restore_receipt(args) == restore


@pytest.mark.parametrize("field,value", [
    ("restore_method", "different_restore_method"), ("repository_baseline_verified", False),
    ("repository_baseline_verified", 1), ("bnci_originals_verified", 17),
    ("bnci_originals_verified", True), ("raw_originals_verified", 159),
    ("epoch_person_count", 105), ("ready_for_continuation", False),
    ("origin_job_id", "different-job"), ("origin_pod_id", "different-pod"),
    ("source_fit_count", 14), ("code_base_commit", "b" * 40),
    ("scientific_revision", "b" * 40), ("manifest_sha256", "not-a-sha256"),
    ("archive_sha256", "f" * 64), ("archive_sha256", None)])
def test_r2_only_receipt_false_missing_or_wrong_proofs_block_before_import(
        tmp_path, monkeypatch, field, value):
    args, restore = r2_receipt_fixture(tmp_path)
    restore[field] = value
    write_json(args.restore_receipt, restore)
    monkeypatch.setattr(continuation, "load_restored_full",
                        lambda args: pytest.fail("Failed proof must block frozen import"))
    with pytest.raises(continuation.ContinuationError):
        continuation.main(["--job-id", "new-job", "--workspace", str(tmp_path)])


@pytest.mark.parametrize("field", ["restore_method", "repository_baseline_verified",
    "bnci_originals_verified", "epoch_person_count", "ready_for_continuation",
    "raw_originals_verified", "manifest_sha256", "source_only_reuse", "paths_verified"])
def test_r2_only_receipt_requires_every_proof_field(tmp_path, field):
    args, restore = r2_receipt_fixture(tmp_path)
    restore.pop(field)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError):
        continuation.validate_restore_receipt(args)


@pytest.mark.parametrize("field,value", [
    ("kind", "q15_validated_source_and_epochs"), ("restore_method", "different-method"),
    ("bnci_original_count", 17), ("bnci_original_count", True),
    ("raw_original_count", 159), ("epoch_person_count", 105),
    ("archive_sha256", "f" * 64), ("repo_bundle", {})])
def test_r2_only_manifest_requires_reconstruction_identity_and_counts(tmp_path, field, value):
    args, restore = r2_receipt_fixture(tmp_path)
    manifest_path = Path(restore["paths"]["manifest"])
    manifest = continuation.read_json(manifest_path)
    manifest[field] = value
    write_json(manifest_path, manifest)
    restore["manifest_sha256"] = continuation.sha(manifest_path)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError):
        continuation.validate_restore_receipt(args)


def test_r2_only_source_inventory_must_equal_validation_report_and_actual_files(tmp_path):
    args, restore = r2_receipt_fixture(tmp_path)
    manifest_path = Path(restore["paths"]["manifest"])
    manifest = continuation.read_json(manifest_path)
    name = next(iter(manifest["source_artifacts"]))
    artifact = args.repo / name
    artifact.write_bytes(b"changed checkpoint")
    with pytest.raises(continuation.ContinuationError, match="artifact_hash_changed"):
        continuation.validate_restore_receipt(args)
    manifest["source_artifacts"][name] = continuation.sha(artifact)
    write_json(manifest_path, manifest)
    restore["manifest_sha256"] = continuation.sha(manifest_path)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError, match="artifact_inventory_mismatch"):
        continuation.validate_restore_receipt(args)


@pytest.mark.parametrize("name,digest", [("/outside.pt", "a" * 64),
    ("results/Q15-E005/../outside.pt", "a" * 64),
    ("results/Q15-E005/source/model.pt", "invalid"),
    ("results/Q15-E005/source/model.pt", True)])
def test_r2_source_identity_cannot_inject_paths_or_invalid_hashes(tmp_path, name, digest):
    args, restore = r2_receipt_fixture(tmp_path)
    manifest_path = Path(restore["paths"]["manifest"])
    manifest = continuation.read_json(manifest_path)
    manifest["source_artifacts"] = {name: digest}
    write_json(args.repo / "results/Q15-E005/source_validation.json",
               {"artifact_sha256": manifest["source_artifacts"]})
    write_json(manifest_path, manifest)
    restore["manifest_sha256"] = continuation.sha(manifest_path)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError, match="artifact_identity_invalid"):
        continuation.validate_restore_receipt(args)


@pytest.mark.parametrize("change", ["dataset-missing", "path-changed", "digest-invalid",
                                    "local-modified", "committed-modified"])
def test_r2_only_epoch_identity_is_bound_to_committed_and_local_manifest(tmp_path, change):
    args, restore = r2_receipt_fixture(tmp_path)
    manifest_path = Path(restore["paths"]["manifest"])
    manifest = continuation.read_json(manifest_path)
    row = manifest["epoch_manifests"]["Cho2017"]
    if change == "dataset-missing":
        manifest["epoch_manifests"].pop("Cho2017")
    elif change == "path-changed":
        row["path"] = "epochs/alternate/epoch_manifest.json"
    elif change == "digest-invalid":
        row["sha256"] = "not-a-sha256"
    elif change == "local-modified":
        (Path(args.epoch_dir) / "Cho2017/epoch_manifest.json").write_bytes(b"changed")
    else:
        (args.repo / "results/Q15-EXTERNAL/manifests/Cho2017.json").write_bytes(b"changed")
    write_json(manifest_path, manifest)
    restore["manifest_sha256"] = continuation.sha(manifest_path)
    write_json(args.restore_receipt, restore)
    with pytest.raises(continuation.ContinuationError):
        continuation.validate_restore_receipt(args)


def test_r2_reconstruction_pipeline_preserves_original_training_and_publishes_no_archive_claim(
        tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    p.args, p.restore = r2_receipt_fixture(tmp_path, p.args, p.restore, p.source_report)
    assert continuation.validate_restore_receipt(p.args) == p.restore
    before = {path: path.read_bytes() for path in (p.report_path, p.run_config,
                                                  *Path(p.args.epoch_dir).rglob("*.*"))}
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    assert all(path.read_bytes() == body for path, body in before.items())
    path = next(path for name, paths in p.commits if name == "commit-provenance"
                for path in paths if path.name == "restored_migration_provenance.json")
    provenance = continuation.read_json(path)
    assert provenance["restore_method"] == continuation.R2_RESTORE_METHOD
    assert "archive_sha256" not in provenance
    assert provenance["original_source_fits"] == 15
    assert provenance["new_source_fits"] == provenance["target_fits"] == 0
    assert p.events.index("independent-source-replay-readonly") < p.events.index("commit-provenance")
    assert p.events.index("commit-final") < p.events.index("stop-new-pod")


def test_public_result_evidence_refers_to_preceding_commit_and_excludes_private_fields(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    original_commit = p.publisher.commit

    def private_receipt_fields(paths, message):
        receipt = original_commit(paths, message)
        receipt.update({"private_endpoint": "private-runpod-key", "token": "private-github-key",
                        "url": "https://private.example.invalid/private-github-key"})
        return receipt

    p.publisher.commit = private_receipt_fields
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    evidence_path = p.args.repo / "research_runs/Q15-MIGRATION-20261004/jobs/new-job/publication_evidence.json"
    evidence = continuation.read_json(evidence_path)
    result_receipt, evidence_receipt = p.publisher.receipts[-2:]
    assert evidence["publication_purpose"] == "scientific_results"
    assert evidence["verified_commit"] == result_receipt["commit"]
    assert evidence["verified_commit"] != evidence_receipt["commit"]
    assert evidence["artifact_sha256"] == result_receipt["artifact_sha256"]
    assert evidence["readback_verified"] is True
    assert evidence["physical_shutdown_confirmed"] is False
    assert not {"url", "private_endpoint", "token", "evidence_commit"} & evidence.keys()
    assert "private-github-key" not in evidence_path.read_text()
    assert "private-runpod-key" not in evidence_path.read_text()
    state = continuation.read_json(p.job / "job_status.json")
    assert state["github_results_backup_verified"] is True
    assert state["results_commit"] == evidence["verified_commit"]


def test_failed_science_status_has_verified_failure_evidence_before_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch, fail_at="verify-inference-freeze")
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    evidence = continuation.read_json(p.args.repo /
        "research_runs/Q15-MIGRATION-20261004/jobs/new-job/publication_evidence.json")
    state = continuation.read_json(p.job / "job_status.json")
    assert evidence["publication_purpose"] == "failure_status"
    assert evidence["verified_commit"] == p.publisher.receipts[-2]["commit"]
    assert state["github_failure_backup_verified"] is True
    assert state["failure_commit"] == evidence["verified_commit"]
    assert state["github_results_backup_verified"] is False
    assert "results_commit" not in state
    assert state["scientific_validation_passed"] is False


def test_evidence_commit_failure_never_stops_even_if_diagnostic_backup_succeeds(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch, fail_at="commit-evidence")
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "commit-final" in p.events and "commit-evidence-failure-status" in p.events
    assert "reinspect-new-pod" not in p.events and "stop-new-pod" not in p.events
    state = continuation.read_json(p.job / "job_status.json")
    assert state["status"] == "failed_backup_manual_attention_required"
    assert state["shutdown_status"] == "not_requested_publication_evidence_unverified"
    assert state["github_results_backup_verified"] is True
    assert state["scientific_validation_passed"] is True


def test_unverified_evidence_readback_never_stops(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    original_commit = p.publisher.commit

    def unverified(paths, message):
        receipt = original_commit(paths, message)
        if message.startswith("Publish"):
            receipt["readback_verified"] = False
        return receipt

    p.publisher.commit = unverified
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "reinspect-new-pod" not in p.events and "stop-new-pod" not in p.events
    state = continuation.read_json(p.job / "job_status.json")
    assert state["backup_error_code"] == "continuation_publication_readback_unverified"


def test_failure_evidence_readback_failure_never_stops(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch, fail_at="verify-inference-freeze")
    original_commit = p.publisher.commit

    def reject_evidence(paths, message):
        if message.startswith("Publish"):
            raise RuntimeError("private-github-key evidence failure")
        return original_commit(paths, message)

    p.publisher.commit = reject_evidence
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "commit-failure" in p.events
    assert "reinspect-new-pod" not in p.events and "stop-new-pod" not in p.events
    assert continuation.read_json(p.job / "job_status.json")["status"] == "failed_backup_manual_attention_required"


@pytest.mark.parametrize("hashes", [{"unexpected/private/path.json": "a" * 64},
                                     {"results/Q15-EXTERNAL/validation_report.json": "invalid"}])
def test_result_evidence_rejects_unrecognized_artifact_inventory_before_stop(tmp_path, monkeypatch, hashes):
    p = pipeline(tmp_path, monkeypatch)
    original_commit = p.publisher.commit

    def corrupt_result_receipt(paths, message):
        receipt = original_commit(paths, message)
        if message.startswith("Complete"):
            receipt["artifact_sha256"] = hashes
        return receipt

    p.publisher.commit = corrupt_result_receipt
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    assert "reinspect-new-pod" not in p.events and "stop-new-pod" not in p.events
    assert continuation.read_json(p.job / "job_status.json")["backup_error_code"] == \
        "publication_evidence_artifact_identity_invalid"


def enable_manual_pipeline(p, monkeypatch, inherited_key=False):
    p.args.manual_stop = True
    if inherited_key:
        monkeypatch.setenv("RUNPOD_API_KEY", "private-runpod-key")
    else:
        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    def forbidden_api(*args, **kwargs):
        pytest.fail("Manual stop must never call the frozen automatic preflight or any RunPod API")

    p.full.preflight = p.cloud.runpod_request = forbidden_api

    def preflight(args, full, publisher):
        p.events.append("manual-runtime-preflight")
        publisher.verify_access()
        return {"pod_id": "new-pod", "pod_identity_authenticated": False,
                "pod_identity_source": "pod_environment_only", "disk_capacity_gb": None,
                "workspace_available_bytes": 150 * 1024**3,
                "workspace_purchased_quota_verified": False,
                "workspace_capacity_check_method":
                    "filesystem_available_bytes_purchased_quota_unverified",
                "gpu_computation_verified": True}

    monkeypatch.setattr(continuation, "manual_preflight", preflight)


@pytest.mark.parametrize("inherited_key", [False, True])
def test_manual_complete_publishes_validated_results_and_never_contacts_runpod(
        tmp_path, monkeypatch, capsys, inherited_key):
    p = pipeline(tmp_path, monkeypatch)
    enable_manual_pipeline(p, monkeypatch, inherited_key)
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 0
    assert p.events.index("independent-source-replay-readonly") < p.events.index("commit-provenance")
    assert p.events.index("commit-inference-freeze") < p.events.index("external-inference")
    assert p.events.index("independent-external-replay") < p.events.index("commit-final")
    assert p.events.index("commit-final") < p.events.index("commit-evidence")
    state = continuation.read_json(p.job / "job_status.json")
    assert state["status"] == "completed_with_calibration_limitations"
    assert state["scientific_validation_passed"] is True
    assert state["github_results_backup_verified"] is True
    assert state["fits_started"] == state["original_source_fits"] == 15
    assert state["new_source_fits"] == state["target_fits"] == 0
    assert state["automatic_shutdown_enabled"] is False
    assert state["auto_shutdown_enabled"] is False
    assert state["automatic_pod_stop_enabled"] is False
    assert state["runpod_api_checked"] is False
    assert state["manual_stop_required"] is True
    assert state["shutdown_status"] == "manual_stop_required"
    assert state["pod_identity_authenticated"] is False
    assert state["pod_identity_source"] == "pod_environment_only"
    assert state["disk_capacity_gb"] is None and state["workspace_purchased_quota_verified"] is False
    assert not (p.job / "stop_api_receipt.json").exists()
    assert "new_pod_stop_api_accepted" not in capsys.readouterr().out
    public = p.args.repo / "research_runs/Q15-MIGRATION-20261004/jobs/new-job"
    assert continuation.read_json(public / "job_status.json")["manual_stop_required"] is True
    evidence = continuation.read_json(public / "publication_evidence.json")
    assert evidence["readback_verified"] is True
    assert evidence["publication_purpose"] == "scientific_results"
    assert evidence["physical_shutdown_confirmed"] is False


@pytest.mark.parametrize("inherited_key", [False, True])
@pytest.mark.parametrize("failure,fail_backup", [
    ("verify-original-freeze", False), ("verify-inference-freeze", False),
    ("independent-external-replay", False), ("commit-evidence", False),
    ("verify-inference-freeze", True)])
def test_manual_science_or_publication_failure_never_contacts_runpod_or_claims_completion(
        tmp_path, monkeypatch, failure, fail_backup, inherited_key):
    p = pipeline(tmp_path, monkeypatch, fail_at=failure, fail_backup=fail_backup)
    enable_manual_pipeline(p, monkeypatch, inherited_key)
    assert continuation.run(p.args, p.full, p.publisher, p.job, p.restore) == 1
    state = continuation.read_json(p.job / "job_status.json")
    assert state["status"] in ("failed_or_blocked", "failed_backup_manual_attention_required")
    assert state["new_source_fits"] == state["target_fits"] == 0
    assert state["automatic_pod_stop_enabled"] is False
    assert state["manual_stop_required"] is True
    assert state["shutdown_status"] == "manual_stop_required"
    assert state["physical_shutdown_confirmed"] is False
    assert not (p.job / "stop_api_receipt.json").exists()
    if not fail_backup and failure != "commit-evidence":
        assert state["scientific_validation_passed"] is False
        evidence = continuation.read_json(p.args.repo /
            "research_runs/Q15-MIGRATION-20261004/jobs/new-job/publication_evidence.json")
        assert evidence["publication_purpose"] == "failure_status"
        assert evidence["readback_verified"] is True


def test_manual_main_flag_is_forwarded_and_check_only_does_not_publish_or_stop(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    enable_manual_pipeline(p, monkeypatch)
    monkeypatch.setattr(continuation, "load_restored_full", lambda args: p.full)
    assert continuation.main(["--job-id", "new-job", "--workspace", str(tmp_path),
                              "--manual-stop", "--check-only"]) == 0
    assert "manual-runtime-preflight" in p.events
    assert "raw-to-epoch-replay-Lee2019_MI" in p.events
    assert p.commits == [] and "external-inference" not in p.events
    state = continuation.read_json(p.job / "job_status.json")
    assert state["status"] == "continuation_ready_no_new_fits_or_predictions"
    assert state["shutdown_status"] == "manual_stop_required"
    assert not (p.job / "stop_api_receipt.json").exists()


def manual_runtime_fixture(tmp_path, monkeypatch):
    p = pipeline(tmp_path, monkeypatch)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    p.args.manual_stop = True
    p.full.REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
    p.full.PINNED_PATHS = ["scripts", "src", "requirements-q15-runtime.txt"]
    p.full.workspace_allocated_bytes = lambda path: 3 * 1024**3
    (p.args.repo / "requirements-q15-runtime.txt").write_text("# exact fixture pin\nnumpy==2.5.3\n")
    p.full.git = lambda *args: (b"https://github.com/jackzhu119/cross-subject-mi-eeg.git\n"
                              if args == ("remote", "get-url", "origin") else b"")
    monkeypatch.setattr(continuation.sys, "version_info", (3, 12, 0))
    monkeypatch.setattr(continuation.os, "statvfs", lambda path:
                        SimpleNamespace(f_bavail=40 * 1024**3, f_frsize=1))
    versions = {"torchaudio": "2.8.0+cu128", "numpy": "2.5.3"}
    monkeypatch.setattr(continuation.importlib.metadata, "version", versions.__getitem__)
    output = SimpleNamespace(shape=(2, 2))
    tensor = SimpleNamespace(item=lambda: 1)
    finite = SimpleNamespace(all=lambda: SimpleNamespace(item=lambda: True))
    shapes = []

    class Model:
        def eval(self):
            return self

        def __call__(self, zero):
            assert zero == "zeros"
            return output

    torch = SimpleNamespace(__version__="2.8.0+cu128", version=SimpleNamespace(cuda="12.8"),
        cuda=SimpleNamespace(is_available=lambda: True, empty_cache=lambda: p.events.append("cuda-empty-cache")),
        ones=lambda *args, **kwargs: tensor, inference_mode=lambda: nullcontext(),
        device=lambda name: name, isfinite=lambda result: finite,
        zeros=lambda shape, **kwargs: (shapes.append(shape), "zeros")[1])
    real_import = continuation.importlib.import_module
    monkeypatch.setattr(continuation.importlib, "import_module",
                        lambda name: torch if name == "torch" else real_import(name))
    source = p.modules["q15_source"]
    source.derive_config = lambda: {"synthetic": True}
    source.MODELS = ["BROAD_EEGNET", "EEGConformer"]
    source._build_model = lambda *args: Model()
    p.cloud.runpod_request = lambda *args, **kwargs: pytest.fail("Manual runtime cannot contact RunPod")
    return p, torch, versions, shapes


def test_manual_runtime_preflight_preserves_code_github_and_zero_input_gpu_guards(tmp_path, monkeypatch):
    p, _torch, _versions, shapes = manual_runtime_fixture(tmp_path, monkeypatch)
    result = continuation.manual_preflight(p.args, p.full, p.publisher)
    assert result["pod_id"] == "new-pod"
    assert result["pod_identity_authenticated"] is False
    assert result["pod_identity_source"] == "pod_environment_only"
    assert result["runpod_api_checked"] is False
    assert result["automatic_shutdown_enabled"] is False
    assert result["disk_capacity_gb"] is None
    assert result["workspace_available_bytes"] == 40 * 1024**3
    assert result["workspace_purchased_quota_verified"] is False
    assert result["workspace_capacity_check_method"] == \
        "filesystem_available_bytes_purchased_quota_unverified"
    assert result["runtime_distributions"] == {"numpy": "2.5.3"}
    assert result["gpu_computation_verified"] is True
    assert result["cuda_zero_input_architecture_probe_verified"] is True
    assert result["eeg_loaded_for_runtime_probe"] is False
    assert shapes == [(2, 21, 320), (2, 2, 21, 320)]
    assert p.events == ["verify-github-access-and-resume-head", "cuda-empty-cache"]
    assert "RUNPOD_API_KEY" not in continuation.os.environ


@pytest.mark.parametrize("change,code", [
    ("missing-github", "github_credentials_required"),
    ("wrong-origin", "repository_origin_mismatch"),
    ("changed-pinned-code", "pinned_execution_code_or_contract_changed"),
    ("untracked-pinned-code", "untracked_execution_code_or_contract_rejected"),
    ("low-filesystem-space", "workspace_filesystem_headroom_below_25_gib"),
    ("wrong-cuda-runtime", "pinned_cuda_runtime_unavailable"),
    ("wrong-torchaudio", "pinned_torchaudio_runtime_unavailable"),
    ("wrong-distribution", "pinned_runtime_distribution_mismatch"),
    ("unfrozen-requirements", "runtime_requirement_not_exact_pin"),
    ("bad-computation", "gpu_computation_probe_failed")])
def test_manual_runtime_preflight_rejects_scientific_runtime_or_storage_failure_without_api(
        tmp_path, monkeypatch, change, code):
    p, torch, versions, shapes = manual_runtime_fixture(tmp_path, monkeypatch)
    if change == "missing-github":
        monkeypatch.delenv("GH_TOKEN")
    elif change == "wrong-origin":
        p.full.git = lambda *args: b"https://github.com/foreign/repo.git"
    elif change in ("changed-pinned-code", "untracked-pinned-code"):
        original = p.full.git
        command = "diff" if change == "changed-pinned-code" else "ls-files"
        p.full.git = lambda *args: b"unexpected change" if args[0] == command else original(*args)
    elif change == "low-filesystem-space":
        monkeypatch.setattr(continuation.os, "statvfs", lambda path:
                            SimpleNamespace(f_bavail=24 * 1024**3, f_frsize=1))
    elif change == "wrong-cuda-runtime":
        torch.version.cuda = "12.7"
    elif change == "wrong-torchaudio":
        versions["torchaudio"] = "2.8.0"
    elif change == "wrong-distribution":
        versions["numpy"] = "2.4.0"
    elif change == "unfrozen-requirements":
        (p.args.repo / "requirements-q15-runtime.txt").write_text("numpy>=2.5\n")
    elif change == "bad-computation":
        torch.ones = lambda *args, **kwargs: SimpleNamespace(item=lambda: 0)
    with pytest.raises(continuation.ContinuationError, match=code):
        continuation.manual_preflight(p.args, p.full, p.publisher)
    assert shapes == []
