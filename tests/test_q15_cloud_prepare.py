"""Preparation checks do not train or grant scientific clearance."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/q15_cloud/q15_prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def record(data=b"original"):
    return {"path": "A01T.mat", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_resume_rechecks_persisted_bytes_without_download(tmp_path):
    (tmp_path / "A01T.mat").write_bytes(b"original")
    def forbidden(*a, **k):
        pytest.fail("Verified file must not redownload")
    result = prepare.fetch_bnci(record(), tmp_path, forbidden)
    assert result["reused_verified_file"] and result["persisted_readback_verified"]


def test_corrupt_download_never_replaces_old_file(tmp_path):
    old = tmp_path / "A01T.mat"
    old.write_bytes(b"old")
    with pytest.raises(ValueError, match="hash_mismatch"):
        prepare.fetch_bnci(record(), tmp_path, lambda *a, **k: io.BytesIO(b"corrupt!"))
    assert old.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [old]


def test_correct_download_replaces_corrupt_cache_and_rereads(tmp_path):
    (tmp_path / "A01T.mat").write_bytes(b"corrupt")
    result = prepare.fetch_bnci(record(), tmp_path, lambda *a, **k: io.BytesIO(b"original"))
    assert not result["reused_verified_file"]
    assert result["sha256"] == record()["sha256"]


def test_source_path_rejects_wrong_identity_and_symlink(tmp_path):
    with pytest.raises(ValueError):
        prepare.fetch_bnci({**record(), "path": "credentials.json"}, tmp_path)
    (tmp_path / "A01T.mat").symlink_to(tmp_path / "other")
    with pytest.raises(ValueError, match="symlink"):
        prepare.fetch_bnci(record(), tmp_path)


@pytest.mark.parametrize("value", ["../private", "/etc/passwd", "a/../../private", "a\\b"])
def test_external_paths_reject_escape(value):
    with pytest.raises(ValueError):
        prepare.safe_relative(value)


def test_publication_is_atomic_new_branch_with_exact_readback():
    reports = {name: {"fits_started": 0, "status": "blocked"} for name in
               ("preparation_status.json", "bnci_source_receipt.json", "external_observations.json")}
    calls = []
    def api(token, method, path, body=None):
        calls.append((method, path, body))
        if "git/ref/heads/" in path: return {"object": {"sha": "base"}}
        if method == "GET" and "git/commits/" in path: return {"tree": {"sha": "tree"}}
        if "git/trees" in path: return {"sha": "newtree"}
        if "git/commits" in path: return {"sha": "newcommit"}
        if "git/refs" in path: return {}
        name = path.split("/")[-1].split("?")[0]
        return {"content": base64.b64encode(json.dumps(reports[name]).encode()).decode()}
    result = prepare.publish_reports("fake-secret-value", "job001", reports, api)
    assert result["readback_verified"]
    refs = [x[2] for x in calls if x[0] == "POST" and x[1].endswith("git/refs")]
    assert refs == [{"ref": "refs/heads/q15/preparation-job001", "sha": "newcommit"}]
    assert all(x[0] != "PATCH" for x in calls)


def test_publication_rejects_unapproved_files_and_secret_in_reports():
    reports = {name: {} for name in
               ("preparation_status.json", "bnci_source_receipt.json", "external_observations.json")}
    with pytest.raises(ValueError, match="file_set"):
        prepare.publish_reports("fake-secret", "job", {"credentials.json": {}}, lambda *a: {})
    def api(*args):
        return {"object": {"sha": "base"}, "tree": {"sha": "tree"}}
    reports["preparation_status.json"] = {"leak": "fake-secret"}
    with pytest.raises(ValueError, match="content_rejected"):
        prepare.publish_reports("fake-secret", "job", reports, api)


def test_observe_real_mat_structure_never_authorizes(tmp_path):
    np = pytest.importorskip("numpy")
    scipy = pytest.importorskip("scipy.io")
    data = {"srate": 512, "n_imagery_trials": 2, "frame": [-2000, 5000],
            "imagery_left": np.zeros((68, 7168)), "imagery_right": np.zeros((68, 7168)),
            "imagery_event": np.zeros(7168, dtype=np.uint8)}
    data["imagery_event"][[1023, 4607]] = 1
    file = tmp_path / "tiny.mat"
    scipy.savemat(file, {"eeg": data})
    result = prepare.observe_mat(file, "Cho2017")
    assert result["retained_samples_per_class_trial"] == 3584
    assert result["event_index_conversion_frozen"] is False
    assert prepare.SAFETY["fits_started"] == 0
    assert prepare.SAFETY["scientific_audit_passed"] is False
