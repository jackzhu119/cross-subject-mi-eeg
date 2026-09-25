"""No-network safety checks; these tests never invoke a real shutdown."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import autodl_queue_shutdown as watch


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_live_worker_prevents_poweroff_even_after_other_queue_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _json(tmp_path / "Q10-QUEUE/batch_status.json", {"status": "failed_stopped"})
    _json(tmp_path / "Q14-QUEUE/batch_status.json", {"status": "running"})
    monkeypatch.setattr(watch, "_scientific_state", lambda _results: (False, {}))
    decision, _, _ = watch.assess(tmp_path, {"Q10": False, "followup": True})
    assert decision == "wait"


def test_completion_requires_independent_science_and_both_finished_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _json(tmp_path / "Q10-QUEUE/batch_status.json", {"status": "complete_validated"})
    _json(tmp_path / "Q14-QUEUE/batch_status.json", {"status": "complete_validated"})
    monkeypatch.setattr(watch, "_scientific_state",
                        lambda _results: (False, {"Q10": True, "Q11": True, "Q14": False}))
    decision, _, _ = watch.assess(tmp_path, {"Q10": False, "followup": False})
    assert decision == "failure_candidate"
    monkeypatch.setattr(watch, "_scientific_state",
                        lambda _results: (True, {"Q10": True, "Q11": True, "Q14": True}))
    decision, _, _ = watch.assess(tmp_path, {"Q10": False, "followup": False})
    assert decision == "success_candidate"


def test_failure_attempts_publish_then_requests_shutdown_even_if_git_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A failed training run still keeps a cloud-local receipt and asks AutoDL
    # to stop accruing charges after all actual workers have gone.
    for batch, _experiment in watch.PAIRS:
        (tmp_path / batch).mkdir(parents=True, exist_ok=True)
    calls: list[tuple[str, str]] = []
    shutdown_calls: list[bool] = []

    def pending(_python: str, _results: Path, batch: str, experiment: str) -> bool:
        calls.append((batch, experiment))
        return False

    monkeypatch.setattr(watch, "_publish_once", pending)
    report = watch.finish(tmp_path, python="python", decision="failure_candidate",
                          reason="worker stopped", checks={"Q10": False}, attempts=1,
                          pause_seconds=0, execute_shutdown=True,
                          shutdown=lambda: shutdown_calls.append(True))
    assert report["status"] == "failed_or_pending"
    assert shutdown_calls == [True]
    assert calls[-1] == watch.PAIRS[-1]
    receipt = watch._read(tmp_path / "Q14-QUEUE/autoshutdown_receipt.json")
    assert receipt["github_publication_pending"] is True
    assert receipt["status"] == "failed_or_pending"


def test_success_publishes_receipt_last_before_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for batch, _experiment in watch.PAIRS:
        (tmp_path / batch).mkdir(parents=True, exist_ok=True)
    order: list[tuple[str, str]] = []
    monkeypatch.setattr(watch, "_publish_once",
                        lambda _python, _results, batch, experiment:
                        order.append((batch, experiment)) or True)
    shutdown_calls: list[bool] = []
    report = watch.finish(tmp_path, python="python", decision="success_candidate",
                          reason="all checks passed",
                          checks={"Q10": True, "Q11": True, "Q14": True},
                          attempts=1, pause_seconds=0, execute_shutdown=True,
                          shutdown=lambda: shutdown_calls.append(True))
    assert report["status"] == "complete_published"
    assert order == list(watch.PAIRS)
    assert shutdown_calls == [True]


def test_dry_run_never_publishes_or_calls_shutdown(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    for batch, _experiment in watch.PAIRS:
        (tmp_path / batch).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(watch, "_publish_once",
                        lambda *_args: pytest.fail("Dry run attempted a Git publication"))
    report = watch.finish(tmp_path, python="python", decision="success_candidate",
                          reason="validated",
                          checks={"Q10": True, "Q11": True, "Q14": True},
                          attempts=1, pause_seconds=0, execute_shutdown=False,
                          shutdown=lambda: pytest.fail("Dry run called shutdown"))
    assert report["status"] == "dry_run_success_candidate"
    assert watch._read(tmp_path / "Q14-QUEUE/autoshutdown_receipt.json")["status"] == (
        "dry_run_success_candidate")


def test_non_autodl_workspace_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="/root/autodl-tmp"):
        watch._cloud_guard(Path("/tmp/not-an-autodl-research-repo"))


@pytest.mark.parametrize(
    ("skipped", "expected"),
    [
        ([{"path": "results/Q10-BATCH/batch.lock",
           "reason": "extension_or_runtime_file"},
          {"path": "results/Q10-BATCH/publish_status.json",
           "reason": "extension_or_runtime_file"}], True),
        ([{"path": "results/Q10-E001/fold/checkpoint.pt",
           "reason": "over_90_MiB"}], False),
    ],
)
def test_publication_requires_no_material_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    skipped: list[dict], expected: bool,
) -> None:
    batch = tmp_path / "Q10-BATCH"
    _json(batch / "publish_status.json",
          {"status": "pushed_with_skipped_files", "experiment_dir": "results/Q10-E001",
           "skipped_files": skipped})
    monkeypatch.setattr(watch.subprocess, "run",
                        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0))
    assert watch._publish_once("python", tmp_path, "Q10-BATCH", "Q10-E001") is expected


def test_stale_or_reused_pid_does_not_count_as_active(tmp_path: Path) -> None:
    pid_file = tmp_path / "supervisor.pid"
    pid_file.write_text("1\n", encoding="ascii")
    assert not watch._worker_alive(pid_file, "q10_cloud_queue.py")
    pid_file.write_text("garbage\n", encoding="ascii")
    assert not watch._worker_alive(pid_file, "q10_cloud_queue.py")
