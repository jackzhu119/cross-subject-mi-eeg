"""No-network publication tests using a temporary bare Git remote."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import publish_research_run as publisher
from scripts import q10_cloud_queue


def _git(repo: Path, *args: str) -> str:
    process = subprocess.run(["git", *args], cwd=repo, text=True,
                             capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


@pytest.fixture
def local_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "init", "-b", "main")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "README.md").write_text("test repository\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@localhost",
         "commit", "-m", "initialize")
    _git(repo, "push", "origin", "HEAD:main")
    monkeypatch.setattr(publisher, "SAFE_REMOTES", {str(remote)})
    return repo, remote


def test_publishes_only_allowlisted_results_and_receipt(local_git: tuple[Path, Path]) -> None:
    repo, remote = local_git
    batch = repo / "results/Q10-BATCH"
    experiment = repo / "results/Q10-E001"
    (batch / "jobs").mkdir(parents=True)
    experiment.mkdir(parents=True)
    (batch / "batch_status.json").write_text('{"status":"complete_validated"}\n', encoding="utf-8")
    (batch / "jobs/run.log").write_text("real experiment log\n", encoding="utf-8")
    (batch / "batch.lock").write_text("runtime only\n", encoding="utf-8")
    (experiment / "predictions.csv").write_text("subject,y_pred\n1,2\n", encoding="utf-8")
    (experiment / "checkpoint.pt").write_bytes(b"fake test checkpoint")
    (experiment / "raw.mat").write_bytes(b"never public")

    report = publisher.publish(repo, batch, experiment, attempts=1)
    assert report["status"] == "pushed_with_skipped_files"
    assert report["batch_status"] == "complete_validated"
    assert len(report["result_commit"]) == 40
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    files = _git(repo, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main").splitlines()
    assert "results/Q10-BATCH/publish_status.json" in files
    assert "results/Q10-BATCH/jobs/run.log" in files
    assert "results/Q10-E001/predictions.csv" in files
    assert "results/Q10-E001/checkpoint.pt" in files
    assert "results/Q10-E001/raw.mat" not in files
    assert "results/Q10-BATCH/batch.lock" not in files
    before = _git(repo, "rev-parse", "HEAD")
    second = publisher.publish(repo, batch, experiment, attempts=1)
    assert second["status"] == "pushed_with_skipped_files"
    assert _git(repo, "rev-parse", "HEAD") == before


def test_rejects_non_repo_result_path(local_git: tuple[Path, Path]) -> None:
    repo, _ = local_git
    batch = repo / "results/Q10-BATCH"
    batch.mkdir(parents=True)
    with pytest.raises(ValueError, match="direct child"):
        publisher.collect_candidates(repo, batch, repo / "outside/Q10-E001")


def test_secret_in_log_stops_all_publication(local_git: tuple[Path, Path]) -> None:
    repo, _ = local_git
    batch = repo / "results/Q10-BATCH"
    experiment = repo / "results/Q10-E001"
    batch.mkdir(parents=True)
    experiment.mkdir(parents=True)
    (batch / "batch_status.json").write_text('{"status":"failed_stopped"}', encoding="utf-8")
    (batch / "run.log").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
    old_head = _git(repo, "rev-parse", "HEAD")
    report = publisher.publish(repo, batch, experiment, attempts=1)
    assert report["status"] == "pending_manual_publish"
    assert "Potential credential" in report["reason"]
    assert _git(repo, "rev-parse", "HEAD") == old_head
    assert json.loads((batch / "publish_status.json").read_text())["status"] == "pending_manual_publish"


def test_stage_requires_scientific_marker(tmp_path: Path) -> None:
    queue = tmp_path / "Q10-QUEUE"
    queue.mkdir()
    marker = tmp_path / "marker.json"
    marker.write_text('{"status":"failed"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="validation marker"):
        q10_cloud_queue._stage("fake", [sys.executable, "-c", "pass"], queue,
                               marker, "passed_scientific_checks", {})
    assert json.loads((queue / "fake_receipt.json").read_text())["status"] == "failed"


def test_queue_plan_is_fixed_and_side_effect_free(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(q10_cloud_queue, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["q10_cloud_queue.py", "--data-dir", str(tmp_path), "--plan-only"])
    assert q10_cloud_queue.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert (plan["planned_deep_fits"], plan["planned_shallow_fits"]) == (126, 36)
    assert plan["geometry"][-1] == "--resume"
    assert not (tmp_path / "results/Q10-QUEUE").exists()
