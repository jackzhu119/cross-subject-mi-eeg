"""No-GPU tests for the Q13-only detached cloud chain."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import q13_cloud_chain as chain


def test_check_only_requires_all_18_historical_mat_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    python = tmp_path / "python"
    python.write_text("test", encoding="utf-8")
    data = tmp_path / "mat"
    data.mkdir()
    monkeypatch.setattr(chain.subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(chain.q13_batch, "preflight", lambda **_k: None)
    monkeypatch.setattr(chain.q13_batch, "plan", lambda: [
        {"expected_fits": 837 // 13 + (1 if index < 837 % 13 else 0)}
        for index in range(13)
    ])
    monkeypatch.setattr(chain.q13_e006, "selected_epochs_from_q5",
                        lambda: {str(subject): 20 for subject in range(1, 10)})
    monkeypatch.setattr(chain.q14_source, "source_file_receipt", lambda *_a: [{}] * 17)
    monkeypatch.setattr(chain, "verify_bnci_loader_route", lambda *_a: None)
    with pytest.raises(AssertionError, match="18 Q8-identical"):
        chain.check_only(data, python)
    monkeypatch.setattr(chain.q14_source, "source_file_receipt", lambda *_a: [{}] * 18)
    receipt = chain.check_only(data, python)
    assert receipt["status"] == "preflight_passed_no_training"
    assert receipt["q13_deep_fits"] == 837
    assert receipt["q15_activated"] is False


def test_preflight_refuses_nemar_and_proves_mat_loader_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = tmp_path / "MNE-bnci-data" / "~bci" / "database" / "001-2014"
    canonical.mkdir(parents=True)
    names = [f"A{subject:02d}{suffix}.mat"
             for subject in range(1, 10) for suffix in ("T", "E")]
    files = [{"filename": name} for name in names]
    for name in names:
        (canonical / name).write_bytes(b"frozen-test-mat")
    monkeypatch.delenv("MOABB_DOWNLOAD_PROVIDER", raising=False)
    with pytest.raises(RuntimeError, match="MOABB_DOWNLOAD_PROVIDER=upstream"):
        chain.verify_bnci_loader_route(tmp_path, files)

    monkeypatch.setenv("MOABB_DOWNLOAD_PROVIDER", "upstream")
    dataset_module = ModuleType("moabb.datasets")

    class FakeDataset:
        def __init__(self, *, artifact_handling: str) -> None:
            assert artifact_handling == "annotate_bad"

        def data_path(self, subject: int, *, path: str, force_update: bool) -> list[str]:
            assert path == str(tmp_path)
            assert force_update is False
            return [str(canonical / f"A{subject:02d}{suffix}.mat") for suffix in ("T", "E")]

    dataset_module.BNCI2014_001 = FakeDataset
    monkeypatch.setitem(sys.modules, "moabb.datasets", dataset_module)
    chain.verify_bnci_loader_route(tmp_path, files)

    class WrongRouteDataset(FakeDataset):
        def data_path(self, subject: int, *, path: str, force_update: bool) -> list[str]:
            return [str(tmp_path / "NEMAR" / f"subject_{subject}.set")]

    dataset_module.BNCI2014_001 = WrongRouteDataset
    with pytest.raises(AssertionError, match="outside frozen"):
        chain.verify_bnci_loader_route(tmp_path, files)
    (canonical / "A09E.mat").unlink()
    with pytest.raises(AssertionError, match="absent"):
        chain.verify_bnci_loader_route(tmp_path, files)


def test_cli_preserves_virtualenv_python_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "system_python"
    target.write_text("placeholder", encoding="utf-8")
    virtual = tmp_path / "venv" / "bin" / "python"
    virtual.parent.mkdir(parents=True)
    try:
        virtual.symlink_to(target)
    except OSError:
        pytest.skip("Host cannot create test symlinks")
    captured = {}

    def fake_check(data_dir: Path, python: Path) -> dict:
        captured["data_dir"] = data_dir
        captured["python"] = python
        return {"status": "preflight_passed_no_training"}

    monkeypatch.setattr(chain, "check_only", fake_check)
    monkeypatch.setattr(sys, "argv", ["q13_cloud_chain.py", "--check-only",
                                    "--python", str(virtual),
                                    "--data-dir", str(tmp_path)])
    assert chain.main() == 0
    assert captured["python"] == virtual.absolute()
    assert captured["python"] != target.resolve()


@pytest.mark.parametrize("scientific_pass", [True, False])
@pytest.mark.parametrize("final_publish_pass", [True, False])
def test_chain_only_runs_e006_after_full_q13_pass_and_always_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    scientific_pass: bool, final_publish_pass: bool,
) -> None:
    root = tmp_path / "repo"
    results = root / "results"
    monkeypatch.setattr(chain, "ROOT", root)
    monkeypatch.setattr(chain, "RESULTS", results)
    monkeypatch.setattr(chain, "RELEASE", results / "Q13-RELEASE")
    monkeypatch.setattr(chain, "ORIGINAL", results / "Q13-BATCH")
    monkeypatch.setattr(chain, "AMENDMENT", results / "Q13-E006")
    monkeypatch.setattr(chain, "check_only", lambda *_a: {"status": "preflight_passed_no_training"})
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(
        LOCK_EX=2, LOCK_NB=4, flock=lambda *_a: None))
    called = []
    final_published_snapshot: list[dict] = []

    def fake_run(name: str, _argv: list[str], *, python: Path) -> int:
        del python
        called.append(name)
        if name == "q13_batch":
            chain.atomic_json(chain.ORIGINAL / "batch_status.json", {
                "status": "complete_validated" if scientific_pass else "failed_stopped"})
            chain.atomic_json(chain.ORIGINAL / "validation_report.json", {
                "status": "passed" if scientific_pass else "failed",
                "checkpoint_replays": 837 if scientific_pass else 0})
        if name == "validate_q13_e006":
            chain.atomic_json(chain.AMENDMENT / "validation_report.json", {
                "status": "passed", "checkpoint_replays": 27})
        if name == "q13_postrun_statistics":
            chain.atomic_json(chain.AMENDMENT / "postrun_statistics/analysis_receipt.json", {
                "status": "post_validation_exploratory_statistics_complete"})
        if name == "publish_final_receipt":
            final_published_snapshot.append(chain.read_json(chain.RELEASE / "batch_status.json"))
            return 0 if final_publish_pass else 1
        return 0

    monkeypatch.setattr(chain, "run_logged", fake_run)
    monkeypatch.setattr(chain, "publish_all", lambda *_a: {"all_results": True})
    exit_code = chain.execute(tmp_path, tmp_path / "python")
    receipt = json.loads((chain.RELEASE / "batch_status.json").read_text(encoding="utf-8"))
    assert "publish_final_receipt" in called
    assert final_published_snapshot[0]["final_publication_attempted"] is True
    if final_publish_pass:
        assert receipt == final_published_snapshot[0]
    else:
        assert receipt["publication_pending"] is True
        assert receipt["publication"]["final_release_receipt"] is False
        assert exit_code != 0
    if scientific_pass:
        assert (exit_code == 0) is final_publish_pass
        assert receipt["status"] == "complete_validated"
        assert {"q13_e006", "validate_q13_e006", "q13_postrun_statistics"} <= set(called)
    else:
        assert exit_code != 0
        assert receipt["status"] == "failed_stopped"
        assert "q13_e006" not in called


@pytest.mark.parametrize("q13_returncode,refresh_receipts,may_continue", [
    (1, False, False),  # Batch preflight crashed before replacing an old pass.
    (2, False, False),  # Publication-pending exit does not certify stale science.
    (2, True, True),   # A fresh scientific pass may continue despite pending publication.
])
def test_chain_requires_fresh_q13_validation_before_e006(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    q13_returncode: int, refresh_receipts: bool, may_continue: bool,
) -> None:
    root = tmp_path / "repo"
    results = root / "results"
    monkeypatch.setattr(chain, "ROOT", root)
    monkeypatch.setattr(chain, "RESULTS", results)
    monkeypatch.setattr(chain, "RELEASE", results / "Q13-RELEASE")
    monkeypatch.setattr(chain, "ORIGINAL", results / "Q13-BATCH")
    monkeypatch.setattr(chain, "AMENDMENT", results / "Q13-E006")
    monkeypatch.setattr(chain, "check_only", lambda *_a: {"status": "preflight_passed_no_training"})
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(
        LOCK_EX=2, LOCK_NB=4, flock=lambda *_a: None))
    chain.atomic_json(chain.ORIGINAL / "batch_status.json", {"status": "complete_validated"})
    chain.atomic_json(chain.ORIGINAL / "validation_report.json", {
        "status": "passed", "checkpoint_replays": 837})
    called: list[str] = []

    def fake_run(name: str, _argv: list[str], *, python: Path) -> int:
        del python
        called.append(name)
        if name == "q13_batch":
            if refresh_receipts:
                chain.atomic_json(chain.ORIGINAL / "batch_status.json", {
                    "status": "complete_validated"})
                chain.atomic_json(chain.ORIGINAL / "validation_report.json", {
                    "status": "passed", "checkpoint_replays": 837})
            return q13_returncode
        if name == "validate_q13_e006":
            chain.atomic_json(chain.AMENDMENT / "validation_report.json", {
                "status": "passed", "checkpoint_replays": 27})
        if name == "q13_postrun_statistics":
            chain.atomic_json(chain.AMENDMENT / "postrun_statistics/analysis_receipt.json", {
                "status": "post_validation_exploratory_statistics_complete"})
        return 0

    monkeypatch.setattr(chain, "run_logged", fake_run)
    monkeypatch.setattr(chain, "publish_all", lambda *_a: {"all_results": True})
    exit_code = chain.execute(tmp_path, tmp_path / "python")
    status = chain.read_json(chain.RELEASE / "batch_status.json")
    assert ("q13_e006" in called) is may_continue
    assert status["q13_837_validated"] is may_continue
    assert (exit_code == 0) is may_continue
