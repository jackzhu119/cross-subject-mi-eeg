"""Safely publish a completed (or failed) research batch without raw EEG data.

Only files in two explicitly named ``results/`` child directories can be
staged. A failed push is *not* treated as a failed experiment: the files and a
``publish_status.json`` receipt remain on the cloud host for a later retry.
The command is intentionally non-interactive and never uses a force push.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_REMOTES = {
    "https://github.com/jackzhu119/cross-subject-mi-eeg.git",
    "git@github.com:jackzhu119/cross-subject-mi-eeg.git",
    "ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git",
}
SAFE_SUFFIXES = {
    ".csv", ".tsv", ".json", ".jsonl", ".txt", ".log", ".md",
    ".png", ".pdf", ".svg", ".npz", ".npy", ".pt", ".pth", ".joblib", ".yaml", ".yml",
}
FORBIDDEN_NAMES = {"publish_status.json", "batch.lock", "q9_batch.lock", "supervisor.pid"}
MAX_GITHUB_FILE_BYTES = 90 * 1024 * 1024
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:(?:OPENSSH|RSA|EC|DSA) )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _inside_results(repo: Path, value: Path) -> Path:
    """Require one direct child of this repository's results directory."""
    results = (repo / "results").resolve()
    chosen = value.resolve()
    if chosen.parent != results or not re.fullmatch(r"Q[0-9]{1,3}-[A-Z0-9]+", chosen.name):
        raise ValueError(f"Not a named direct child of {results}: {chosen}")
    return chosen


def _contains_secret(path: Path) -> bool:
    # Check text-like artifacts before publishing. Large binary checkpoints are
    # permitted only by extension and size; no attempt is made to deserialize.
    if path.suffix.lower() not in {".json", ".jsonl", ".txt", ".log", ".md", ".csv", ".tsv", ".yaml", ".yml"}:
        return False
    with path.open("rb") as stream:
        overlap = b""
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            block = overlap + chunk
            if any(pattern.search(block) for pattern in SECRET_PATTERNS):
                return True
            overlap = block[-128:]
    return False


def collect_candidates(repo: Path, batch_dir: Path, experiment_dir: Path) -> tuple[list[str], list[dict]]:
    """Return explicit stageable paths and exclusions, never a directory glob."""
    batch_dir = _inside_results(repo, batch_dir)
    experiment_dir = _inside_results(repo, experiment_dir)
    if batch_dir == experiment_dir:
        raise ValueError("Batch and experiment directories must differ")
    if not batch_dir.is_dir():
        raise FileNotFoundError(batch_dir)
    results_root = (repo / "results").resolve()
    accepted: list[str] = []
    skipped: list[dict] = []
    for folder in (batch_dir, experiment_dir):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(folder) or not resolved.is_relative_to(results_root):
                raise RuntimeError(f"Refusing result path outside allowed directory: {path}")
            relative = resolved.relative_to(repo.resolve()).as_posix()
            if path.name in FORBIDDEN_NAMES or path.suffix.lower() not in SAFE_SUFFIXES:
                skipped.append({"path": relative, "reason": "extension_or_runtime_file"})
                continue
            if path.stat().st_size > MAX_GITHUB_FILE_BYTES:
                skipped.append({"path": relative, "reason": "over_90_MiB"})
                continue
            if _contains_secret(path):
                # A possible secret is fatal, not an ordinary skip: the operator
                # must inspect it before *any* public publication.
                raise RuntimeError(f"Potential credential in public-result candidate: {relative}")
            accepted.append(relative)
    if not accepted:
        raise RuntimeError("No safe result or batch files available to publish")
    return sorted(set(accepted)), sorted(skipped, key=lambda item: item["path"])


def _git(repo: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
           "SSH_ASKPASS": "/bin/false",
           "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes"}
    return subprocess.run(["git", *args], cwd=repo, env=env,
                          text=True, capture_output=True,
                          timeout=timeout, check=False)


def _require_git(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode:
        # Git may echo authenticated URLs in stderr. Keep the public receipt
        # deliberately terse; source files and local commits are preserved.
        raise RuntimeError(f"git {args[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def _preflight(repo: Path) -> None:
    if Path(_require_git(repo, "rev-parse", "--show-toplevel")).resolve() != repo.resolve():
        raise RuntimeError("Git root does not match the research repository")
    remote = _require_git(repo, "remote", "get-url", "origin")
    if remote not in SAFE_REMOTES:
        raise RuntimeError("origin is not the allowlisted public research repository")
    if _require_git(repo, "branch", "--show-current") != "main":
        raise RuntimeError("Automatic publication requires main branch")
    if _require_git(repo, "diff", "--cached", "--name-only"):
        raise RuntimeError("Pre-existing staged changes; refusing to mix commits")
    _require_git(repo, "push", "--dry-run", "origin", "HEAD:main")


def _stage(repo: Path, names: list[str]) -> bool:
    for offset in range(0, len(names), 128):
        _require_git(repo, "add", "--", *names[offset:offset + 128])
    staged = _require_git(repo, "diff", "--cached", "--name-only").splitlines()
    if not set(staged) <= set(names):
        raise RuntimeError("Staged path audit failed")
    return bool(staged)


def _commit(repo: Path, message: str) -> str:
    _require_git(repo, "-c", "user.name=Research Cloud Recorder",
                 "-c", "user.email=research-cloud@localhost", "commit", "-m", message)
    return _require_git(repo, "rev-parse", "HEAD")


def _push(repo: Path, attempts: int) -> None:
    for attempt in range(attempts):
        result = _git(repo, "push", "origin", "HEAD:main", timeout=180)
        if result.returncode == 0:
            return
        if attempt + 1 < attempts:
            time.sleep(min(5 * (2 ** attempt), 40))
    raise RuntimeError(f"GitHub push failed after {attempts} noninteractive attempt(s)")


def publish(repo: Path, batch_dir: Path, experiment_dir: Path, *, attempts: int = 3) -> dict:
    """Publish result data, then publish a final receipt in a separate commit."""
    repo = repo.resolve()
    batch_dir = _inside_results(repo, batch_dir)
    experiment_dir = _inside_results(repo, experiment_dir)
    receipt_path = batch_dir / "publish_status.json"
    previous = _read_json(receipt_path)
    report: dict = {"status": "pending_manual_publish", "attempted_at_utc": _now(),
                    "batch_dir": batch_dir.relative_to(repo).as_posix(),
                    "experiment_dir": experiment_dir.relative_to(repo).as_posix()}
    try:
        if attempts < 1 or attempts > 10:
            raise ValueError("attempts must be between 1 and 10")
        candidates, skipped = collect_candidates(repo, batch_dir, experiment_dir)
        report["candidate_count"] = len(candidates)
        report["skipped_files"] = skipped
        _preflight(repo)
        changed = _stage(repo, candidates)
        batch_state = _read_json(batch_dir / "batch_status.json").get("status", "unknown")
        if changed:
            kind = "complete" if batch_state == "complete_validated" else "partial_or_failed"
            report["result_commit"] = _commit(repo, f"Record {kind} {experiment_dir.name} cloud results and logs")
        else:
            report["result_commit"] = previous.get("result_commit") or _require_git(repo, "rev-parse", "HEAD")
        _push(repo, attempts)
        # Avoid a redundant receipt commit when re-running an already-published
        # batch and no result file changed. Pending receipt commits are pushed
        # above, including after a previous transient network failure.
        if not changed and previous.get("status") in {"pushed", "pushed_with_skipped_files"}:
            return previous
        report["status"] = "pushed_with_skipped_files" if skipped else "pushed"
        report["batch_status"] = batch_state
        report["finished_at_utc"] = _now()
        _atomic_json(receipt_path, report)
        _stage(repo, [receipt_path.relative_to(repo).as_posix()])
        _commit(repo, f"Record {experiment_dir.name} Git publication receipt")
        _push(repo, attempts)
        return report
    except Exception as exc:  # noqa: BLE001 - persist any publication failure as a receipt
        report["status"] = "pending_manual_publish"
        report["reason"] = str(exc)
        report["finished_at_utc"] = _now()
        _atomic_json(receipt_path, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    report = publish(ROOT, args.batch_dir, args.experiment_dir, attempts=args.attempts)
    print(json.dumps({"status": report["status"], "result_commit": report.get("result_commit"),
                      "reason": report.get("reason")}, ensure_ascii=False))
    return 0 if report["status"] in {"pushed", "pushed_with_skipped_files"} else 1


if __name__ == "__main__":
    sys.exit(main())
