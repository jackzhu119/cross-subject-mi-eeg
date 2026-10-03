"""Local fail-closed orchestration tests; no GPU, training, or live APIs."""
import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("full_q15_cloud", ROOT / "scripts/q15_cloud/q15_full_job.py")
full = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(full)


def test_startup_failure_never_erases_prior_fit_uncertainty(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    exc = full.FullJobError("publication_resume_remote_head_mismatch")
    assert full.startup_failure(exc)["fits_started"] == 0
    (tmp_path / "results/Q15-E005/source").mkdir(parents=True)
    state = full.startup_failure(exc)
    assert state["fits_started"] is None
    assert state["status"] == "resume_blocked"
    assert state["target_fits"] == 0


@pytest.mark.parametrize("relative", ["raw/original.json", "epochs/array.csv", "credentials/token.json",
                                     "results/array.npz", "results/key.env"])
def test_publication_rejects_private_and_array_paths(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("private")
    with pytest.raises(full.FullJobError):
        full.publication_path(path)


def test_publication_rejects_symlinks_and_oversized_files(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    path = tmp_path / "report.json"
    path.write_text("{}")
    link = tmp_path / "linked.json"
    link.symlink_to(path)
    with pytest.raises(full.FullJobError, match="path_unsafe"):
        full.publication_path(link)
    monkeypatch.setattr(full, "MAX_PUBLIC_FILE", 1)
    with pytest.raises(full.FullJobError, match="too_large"):
        full.publication_path(path)


def test_publication_rejects_known_secrets_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    monkeypatch.setattr(full, "git", lambda *args: b"a" * 40)
    monkeypatch.setenv("RUNPOD_API_KEY", "private-runpod-test-key")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"value": "private-runpod-test-key"}))
    def forbidden(*args):
        pytest.fail("No request may run for credential-bearing content")
    publisher = full.Publisher("private-gh-test-key", "q15/run-test", tmp_path / "state.json", forbidden)
    with pytest.raises(full.FullJobError, match="credential"):
        publisher.commit([report], "test")


@pytest.mark.parametrize("defect", ["tree", "mapping", "blob", "branch"])
def test_publication_requires_commit_tree_blob_and_branch_readback(tmp_path, monkeypatch, defect):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    base, commit, tree, blob = "a" * 40, "b" * 40, "c" * 40, "d" * 40
    monkeypatch.setattr(full, "git", lambda *args: base.encode())
    path = tmp_path / "report.json"
    path.write_text('{"target_fits":0}')
    exists = False
    def api(token, method, endpoint, payload=None):
        nonlocal exists
        if method == "GET" and "git/ref/heads/" in endpoint:
            if not exists:
                raise full.FullJobError("github_http_404")
            return {"object": {"sha": base if defect == "branch" else commit}}
        if method == "GET" and endpoint.endswith("git/commits/" + base):
            return {"tree": {"sha": "e" * 40}}
        if method == "POST" and endpoint.endswith("git/blobs"):
            return {"sha": blob}
        if method == "POST" and endpoint.endswith("git/trees"):
            return {"sha": tree}
        if method == "POST" and endpoint.endswith("git/commits"):
            return {"sha": commit}
        if method == "POST" and endpoint.endswith("git/refs"):
            exists = True
            return {}
        if method == "GET" and endpoint.endswith("git/commits/" + commit):
            return {"tree": {"sha": "wrong" if defect == "tree" else tree}}
        if method == "GET" and "git/trees/" in endpoint:
            return {"truncated": False, "tree": [{"path": "report.json", "type": "blob",
                      "mode": "100644", "sha": "wrong" if defect == "mapping" else blob}]}
        if method == "GET" and endpoint.endswith("git/blobs/" + blob):
            body = b"wrong" if defect == "blob" else path.read_bytes()
            return {"encoding": "base64", "content": base64.b64encode(body).decode()}
        pytest.fail("Unexpected API operation")
    publisher = full.Publisher("test-token", "q15/run-test", tmp_path / "publication.json", api)
    with pytest.raises(full.FullJobError):
        publisher.commit([path], "test")
    assert publisher.receipts == []
    assert not publisher.state_path.exists()


def test_resume_receipt_must_match_local_head(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "git", lambda *args: b"a" * 40)
    state = tmp_path / "publication.json"
    full.atomic_json(state, {"branch": "q15/run-test", "receipts": [{"branch": "q15/run-test",
                         "readback_verified": True, "commit": "b" * 40}]})
    with pytest.raises(full.FullJobError, match="local_head_mismatch"):
        full.Publisher("test-token", "q15/run-test", state)


def test_external_artifact_allowlist_cannot_include_arrays_or_other_experiments(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    for relative in ("results/Q15-EXTERNAL/raw.pt", "results/Q14-E001/report.json"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        with pytest.raises(full.FullJobError):
            full.external_artifacts({"artifact_sha256": {relative: full.sha(path)}})


def pipeline(tmp_path, monkeypatch, fail_at=None, fail_publication=False):
    """Instrument exact gate order with doubles; no scientific claim is made."""
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(full, "ROOT", root)
    events, modules = [], {}
    job = tmp_path / "jobs/test"
    job.mkdir(parents=True)
    args = SimpleNamespace(job_id="test", workspace=str(tmp_path), raw_dir=str(tmp_path / "raw"),
                           bnci_dir=str(tmp_path / "bnci"), epoch_dir=str(tmp_path / "epochs"))
    monkeypatch.setattr(full, "preflight", lambda *args: {"pod_id": "current-pod"})
    provenance = root / "research_runs/Q8-E001/results/source_files.json"
    full.atomic_json(provenance, [{"path": f"A{index}.mat"} for index in range(18)])
    def file(relative, value=None):
        path = root / relative
        full.atomic_json(path, {} if value is None else value)
        return path
    def event(name):
        events.append(name)
        if name == fail_at:
            raise full.FullJobError("test_gate_rejected")
    modules["q15_cloud.q15_prepare"] = SimpleNamespace(fetch_bnci=lambda record, directory: {"file_id": record["path"]})
    def source_audit(directory):
        event("bnci-audit")
        return {"status": "source_metadata_passed_non_authorizing", "target_fits": 0,
                "n_files": 18, "source_training_authorized": False}
    modules["mi_eeg.data.q15_context"] = SimpleNamespace(audit_bnci_source=source_audit)
    manifests = {dataset: file("results/Q15-METADATA/" + dataset + ".json", {"dataset": dataset})
                 for dataset in ("Cho2017", "Lee2019_MI")}
    def audit_inventory(path):
        event("raw-audit-" + json.loads(path.read_text())["dataset"])
        return {"status": "metadata_passed_non_authorizing", "target_fits": 0,
                "synthetic_fixture": False, "source_training_authorized": False,
                "external_prediction_authorized": False}
    modules["q15_real_metadata"] = SimpleNamespace(build_manifests=lambda *args: manifests,
                                                   audit_inventory=audit_inventory)
    receipts = {dataset: root / ("results/receipt-" + dataset + ".json") for dataset in manifests}
    source = SimpleNamespace(AUDIT_RECEIPTS=receipts, FREEZE=root / "results/Q15-E005/pre_fit_freeze.json")
    for name in ("CONTRACT", "CONTRACT_CHECKER", "Q14_CONFIG", "Q8_SOURCE_PROVENANCE",
                 "DEPENDENCY_SPEC", "BNCI_LOADER", "EEGNET_HELPER", "METADATA_AUDITOR", "SOURCE_SCRIPT"):
        setattr(source, name, file("protocol/" + name + ".json"))
    source.q14_source = SimpleNamespace(__file__=str(file("protocol/helper.json")))
    def freeze():
        event("prepare-source-freeze")
        return file("results/Q15-E005/pre_fit_freeze.json")
    source.prepare_freeze = freeze
    source._verify_committed_freeze = lambda: event("verify-source-freeze")
    def fit(*args):
        event("fit-source")
    source.run_source = fit
    modules["q15_source"] = source
    source_result = file("results/Q15-E005/source/report.json")
    def validate_source():
        event("validate-source")
        file("results/Q15-E005/source_validation.json")
        return {"passed": True, "deep_fit_count": 14, "shallow_fit_count": 1,
                "artifact_sha256": {"results/Q15-E005/source/report.json": full.sha(source_result)}}
    modules["q15_validate_source"] = SimpleNamespace(validate_source=validate_source)
    def epochs(*args):
        event("prepare-epochs")
        return manifests
    def validate_epochs(path):
        event("validate-epochs")
        return json.loads(path.read_text())
    modules["q15_preprocess_external"] = SimpleNamespace(prepare_epochs=epochs, validate_epoch_manifest=validate_epochs)
    def inference_freeze(*args):
        event("prepare-inference-freeze")
        return file("results/Q15-EXTERNAL/inference_freeze.json")
    modules["q15_external"] = SimpleNamespace(prepare_freeze=inference_freeze,
        verify_freeze=lambda *args: event("verify-inference-freeze"),
        run_external=lambda *args: event("predict-external"))
    external_result = file("results/Q15-EXTERNAL/report.json")
    def external_validate(*args, **kwargs):
        event("validate-external")
        file("results/Q15-EXTERNAL/validation_report.json")
        return {"passed": True, "target_fits": 0,
                "artifact_sha256": {"results/Q15-EXTERNAL/report.json": full.sha(external_result)}}
    modules["q15_validate_external"] = SimpleNamespace(validate_external=external_validate)
    real_import = full.importlib.import_module
    monkeypatch.setattr(full.importlib, "import_module", lambda name: modules.get(name) or real_import(name))
    from q15_cloud import q15_cloud_job
    monkeypatch.setattr(q15_cloud_job, "current_pod_id", lambda: "current-pod")
    def runpod(token, pod, method="GET", action=""):
        event("stop-pod" if action else "verify-current-pod")
        return {"http_status": 200, "pod_id": pod}
    monkeypatch.setattr(q15_cloud_job, "runpod_request", runpod)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-private-key")
    class Publisher:
        def __init__(self):
            self.receipts = []
        def commit(self, paths, message):
            name = ("commit-source-freeze" if "Freeze Q15 preprocessing" in message
                    else "commit-inference-freeze" if "Freeze Q15 source checkpoints" in message
                    else "commit-final" if "Complete Q15" in message
                    else "commit-failure" if "failure" in message
                    else "commit-inputs" if "Audit all" in message else "commit-artifacts")
            event(name)
            if fail_publication:
                raise full.FullJobError("test_backup_failed")
            self.receipts = [*self.receipts, {"readback_verified": True}]
    return args, Publisher(), job, events


def test_complete_order_requires_two_committed_gates_and_independent_validators(tmp_path, monkeypatch):
    args, publisher, job, events = pipeline(tmp_path, monkeypatch)
    assert full.run(args, publisher, job) == 0
    assert events.index("bnci-audit") < events.index("commit-inputs")
    assert events.index("raw-audit-Lee2019_MI") < events.index("commit-inputs")
    assert events.index("commit-inputs") < events.index("prepare-source-freeze")
    assert events.index("commit-source-freeze") < events.index("verify-source-freeze") < events.index("fit-source")
    assert events.index("validate-source") < events.index("prepare-epochs")
    assert events.index("validate-epochs") < events.index("prepare-inference-freeze")
    assert events.index("commit-inference-freeze") < events.index("verify-inference-freeze") < events.index("predict-external")
    assert events.index("validate-external") < events.index("commit-final") < events.index("stop-pod")


@pytest.mark.parametrize("failure", ["bnci-audit", "raw-audit-Cho2017", "prepare-source-freeze", "verify-source-freeze"])
def test_prefit_gate_failure_starts_no_fit_and_backs_up_before_current_pod_stop(tmp_path, monkeypatch, failure):
    args, publisher, job, events = pipeline(tmp_path, monkeypatch, fail_at=failure)
    # No source execution output exists before any fit; avoid the simulated report as resume evidence.
    import shutil
    shutil.rmtree(full.ROOT / "results/Q15-E005/source")
    assert full.run(args, publisher, job) == 1
    assert "fit-source" not in events and "predict-external" not in events
    assert events.index("commit-failure") < events.index("verify-current-pod") < events.index("stop-pod")
    status = json.loads((job / "job_status.json").read_text())
    assert status["fits_started"] == 0 and status["scientific_validation_passed"] is False


def test_unverified_backup_forbids_stop_and_completion(tmp_path, monkeypatch):
    args, publisher, job, events = pipeline(tmp_path, monkeypatch, fail_at="fit-source", fail_publication=True)
    assert full.run(args, publisher, job) == 1
    assert "stop-pod" not in events
    status = json.loads((job / "job_status.json").read_text())
    assert status["status"] == "failed_backup_manual_attention_required"
    assert status["scientific_validation_passed"] is False


def test_failed_fit_count_remains_unknown(tmp_path, monkeypatch):
    args, publisher, job, _events = pipeline(tmp_path, monkeypatch, fail_at="fit-source")
    assert full.run(args, publisher, job) == 1
    status = json.loads((job / "job_status.json").read_text())
    assert status["fits_started"] is None
    assert status["scientific_validation_passed"] is False


def test_final_publication_failure_removes_false_completion(tmp_path, monkeypatch):
    args, publisher, job, events = pipeline(tmp_path, monkeypatch, fail_at="commit-final")
    assert full.run(args, publisher, job) == 1
    status = json.loads((job / "job_status.json").read_text())
    assert status["status"] == "failed_or_blocked"
    assert status["scientific_validation_passed"] is False
    assert events.index("commit-failure") < events.index("stop-pod")


def test_exception_text_never_enters_public_error_code():
    assert full.safe_code(RuntimeError("a-secret-token private request payload")) == "RuntimeError"


def test_duplicate_supervisor_cannot_enter_failure_or_stop_handler(tmp_path, monkeypatch):
    from q15_cloud import q15_cloud_job
    monkeypatch.setattr(full, "Publisher", lambda *args: SimpleNamespace())
    def locked(path):
        raise q15_cloud_job.IntegrityError("another_cloud_supervisor_is_active")
    monkeypatch.setattr(q15_cloud_job, "acquire_job_lock", locked)
    monkeypatch.setattr(full, "run", lambda *args: pytest.fail("Duplicate must not enter work/failure/stop"))
    with pytest.raises(q15_cloud_job.IntegrityError, match="already|another"):
        full.main(["--job-id", "test", "--revision", "a" * 40, "--workspace", str(tmp_path),
                   "--control-dir", str(tmp_path / ".q15-cloud")])


def test_alternate_active_lock_is_rejected_before_worker(tmp_path):
    with pytest.raises(full.FullJobError, match="alternate_active"):
        full.main(["--job-id", "test", "--revision", "a" * 40, "--workspace", str(tmp_path),
                   "--control-dir", str(tmp_path / "different-lock")])
