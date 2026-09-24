"""Run an immutable, resumable Q9 job queue on one cloud GPU.

This is an orchestration layer, not a scientific validator. It neither reads
held-out predictions nor selects a model using target performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "research_runs/Q9-E001/Q9_BATCH_MATRIX.json"
DEFAULT_OUTPUT = ROOT / "results"
CODE_FILES = (
    "scripts/q9_batch.py", "scripts/q9_validate_batch.py",
    "scripts/q9_neural.py", "scripts/q9_spatial_psd.py",
    "scripts/q9_spatial_features.py", "scripts/run_eegnet.py",
    "src/mi_eeg/data/bnci_epochs.py", "src/mi_eeg/models/eegnet_training.py",
    "src/mi_eeg/evaluation/splits.py",
)
DEFAULT_TEMPLATES = {
    "neural": [
        "{python}", "scripts/q9_neural.py", "--condition", "{condition}",
        "--phase", "{phase}", "--data-dir", "{data_dir}",
        "--output-root", "{output_root}", "--device", "{device}",
    ],
    "psd": [
        "{python}", "scripts/q9_spatial_psd.py", "--data-dir", "{data_dir}",
        "--output-dir", "{output_root}/Q9-A001",
    ],
}
PSDs = {"PSD44_LDA", "PSD44_LINEAR_SVM"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def safe_name(value: str) -> str:
    if not value or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in value):
        raise ValueError(f"Unsafe job/condition name: {value!r}")
    return value


def _substitute(template: list[str], values: dict[str, str]) -> list[str]:
    if not template or not all(isinstance(item, str) for item in template):
        raise ValueError("Every command template must be a nonempty array of strings")
    # No shell is involved. Template values are arguments, never commands.
    return [item.format_map(values) for item in template]


def build_manifest(
    matrix_path: Path,
    templates: dict,
    selected: list[str],
    data_dir: Path,
    output_root: Path,
    device: str,
    python: str,
) -> dict:
    matrix = read_json(matrix_path)
    catalogue = {entry["name"]: entry for entry in matrix["conditions"]}
    catalogue.update({entry["name"]: entry for entry in matrix["shallow_controls"]})
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select at least one condition, without duplicates")
    unknown = set(selected) - set(catalogue)
    if unknown:
        raise ValueError(f"Unknown Q9 conditions: {sorted(unknown)}")
    if bool(PSDs & set(selected)) and not PSDs <= set(selected):
        raise ValueError("PSD44_LDA and PSD44_LINEAR_SVM must run together in one audited PSD job")
    if device != "cuda":
        raise ValueError("Q9 cloud batch must use a real CUDA device; no CPU-simulation fallback")
    if set(templates) != {"neural", "psd"}:
        raise ValueError("Command templates must contain exactly neural and psd arrays")
    values = {
        "python": python,
        "data_dir": str(data_dir.resolve()),
        "output_root": str(output_root.resolve()),
        "device": device,
    }
    jobs: list[dict] = []
    psd_added = False
    planned_entries = matrix["conditions"] + matrix["shallow_controls"]
    ordered_names = [entry["name"] for _, entry in sorted(
        enumerate(planned_entries),
        key=lambda pair: (0 if pair[1].get("priority", "A") == "A" else 1, pair[0]),
    )]
    for name in ordered_names:
        if name not in selected:
            continue
        entry = catalogue[name]
        if name in PSDs:
            if psd_added:
                continue
            psd_added = True
            jobs.append({
                "job_id": "Q9-A001_PSD44_both", "experiment_id": "Q9-A001",
                "condition": "PSD44_both", "phase": "source_fits",
                "argv": _substitute(templates["psd"], values),
                "completion_status": str((output_root / "Q9-A001/status.json").resolve()),
                "completion_value": "complete",
            })
            continue
        safe_name(name)
        phases = ["selection", "final"] if int(entry["inner_fits"]) else ["final"]
        for phase in phases:
            job_values = {**values, "condition": name, "phase": phase}
            jobs.append({
                "job_id": safe_name(f"{entry['experiment_id']}_{name}_{phase}"),
                "experiment_id": entry["experiment_id"], "condition": name,
                "phase": phase,
                "argv": _substitute(templates["neural"], job_values),
                "completion_status": str((output_root / entry["experiment_id"] / name /
                                          ("selection_provenance.json" if phase == "selection" else "status.json")).resolve()),
                "completion_value": "frozen_before_Q9_target_inference" if phase == "selection" else "complete",
            })
    return {
        "schema_version": 1,
        "created_at_utc": now(),
        "scope": "orchestration_only_no_target_metric_selection",
        "matrix_path": str(matrix_path.resolve()),
        "matrix_sha256": sha256(matrix_path),
        "code_sha256": {name: sha256(ROOT / name) for name in CODE_FILES
                        if (ROOT / name).is_file()},
        "selected_conditions": selected,
        "unselected_planned_conditions": sorted(set(catalogue) - set(selected)),
        "selected_fit_counts": {
            "deep_inner": sum(int(catalogue[name]["inner_fits"]) for name in selected if name not in PSDs),
            "deep_final": sum(int(catalogue[name]["final_fits"]) for name in selected if name not in PSDs),
            "shallow_source": sum(int(catalogue[name]["source_fits"]) for name in selected if name in PSDs),
        },
        "data_dir": str(data_dir.resolve()),
        "output_root": str(output_root.resolve()),
        "device": device,
        "python_executable": python,
        "python_version": platform.python_version(),
        "templates": templates,
        "jobs": jobs,
    }


def stable_manifest(manifest: dict) -> dict:
    return {key: value for key, value in manifest.items() if key != "created_at_utc"}


def _result_complete(job: dict) -> bool:
    marker = job["completion_status"]
    if marker is None:
        return True
    status = read_json(Path(marker))
    return status.get("status") == job["completion_value"]


def _lock(file_path: Path):
    """Exclusive process lock; released automatically on crash/host restart."""
    if os.name != "posix":
        raise RuntimeError("Q9 cloud supervisor requires Linux/POSIX")
    import fcntl

    file_path.parent.mkdir(parents=True, exist_ok=True)
    handle = file_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("Another Q9 batch supervisor holds the lock") from None
    return handle


def run_job(job: dict, batch_dir: Path, env: dict[str, str]) -> None:
    job_dir = batch_dir / "jobs" / job["job_id"]
    status_path = job_dir / "status.json"
    log_path = job_dir / "run.log"
    if status_path.is_file():
        old = read_json(status_path)
        if old.get("status") == "complete":
            if old.get("argv") != job["argv"] or not _result_complete(job):
                raise RuntimeError(f"Completed job receipt does not match current result: {job['job_id']}")
            if sha256(log_path) != old.get("log_sha256"):
                raise RuntimeError(f"Completed job log changed: {job['job_id']}")
            print(f"[resume] validated complete job {job['job_id']}", flush=True)
            return
    job_dir.mkdir(parents=True, exist_ok=True)
    previous_attempts = 0
    if status_path.is_file():
        previous_attempts = int(read_json(status_path).get("attempts", 0))
    started = now()
    atomic_json(status_path, {
        "status": "running", "job_id": job["job_id"], "argv": job["argv"],
        "attempts": previous_attempts + 1, "started_at_utc": started,
    })
    print(f"[start] {job['job_id']} ({started})", flush=True)
    # A restarted interrupted job appends to its old log; the runner itself
    # resumes missing fits and refuses to rewrite validated completed fits.
    with log_path.open("ab") as stream:
        stream.write(f"\n===== ATTEMPT {previous_attempts + 1} {started} =====\n".encode())
        stream.flush()
        process = subprocess.run(job["argv"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, check=False)
    complete = process.returncode == 0
    if complete:
        try:
            complete = _result_complete(job)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            complete = False
    receipt = {
        "status": "complete" if complete else "failed",
        "job_id": job["job_id"], "argv": job["argv"],
        "attempts": previous_attempts + 1, "started_at_utc": started,
        "finished_at_utc": now(), "exit_code": process.returncode,
        "log_path": str(log_path.resolve()), "log_sha256": sha256(log_path),
        "completion_status": job["completion_status"],
        "completion_status_sha256": sha256(Path(job["completion_status"]))
        if complete and job["completion_status"] else None,
    }
    atomic_json(status_path, receipt)
    if not complete:
        raise RuntimeError(f"Q9 job failed or completion receipt missing: {job['job_id']}; see {log_path}")
    print(f"[complete] {job['job_id']}", flush=True)


def _publish(batch_dir: Path, manifest: dict) -> None:
    """Best-effort, credential-free-in-code push of *only* Q9 outputs.

    Existing noninteractive Git credentials are required. No force push and no
    raw data files can enter the staged path set.
    """
    report_path = batch_dir / "publish_status.json"
    report = {"attempted_at_utc": now(), "status": "not_attempted"}
    safe_remotes = {
        "https://github.com/jackzhu119/cross-subject-mi-eeg.git",
        "git@github.com:jackzhu119/cross-subject-mi-eeg.git",
        "ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git",
    }
    git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
               "SSH_ASKPASS": "/bin/false",
               "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes"}

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=ROOT, env=git_env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=90, check=False)

    try:
        if Path(manifest["output_root"]).resolve() != (ROOT / "results").resolve():
            raise RuntimeError("autopush requires repository results/ as output root")
        remote = git("remote", "get-url", "origin")
        if remote.returncode or remote.stdout.strip() not in safe_remotes:
            raise RuntimeError("origin is not the allowlisted public research repository")
        branch = git("branch", "--show-current")
        if branch.returncode or branch.stdout.strip() != "main":
            raise RuntimeError("autopush requires local main branch")
        staged = git("diff", "--cached", "--name-only")
        if staged.returncode or staged.stdout.strip():
            raise RuntimeError("pre-existing staged changes; refusing to combine commits")
        dry = git("push", "--dry-run", "origin", "HEAD:main")
        if dry.returncode:
            raise RuntimeError("noninteractive GitHub push preflight failed; results remain local")
        candidates = []
        skipped_large = []
        for job in manifest["jobs"]:
            folder = ROOT / "results" / job["experiment_id"]
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.relative_to(ROOT)
                if path.suffix.lower() in {".mat", ".pem", ".key", ".env", ".zip", ".tar", ".gz"}:
                    continue
                if path.stat().st_size > 90 * 1024 * 1024:
                    skipped_large.append(relative.as_posix())
                    continue
                candidates.append(relative.as_posix())
        for path in batch_dir.rglob("*"):
            if path.is_file() and not path.is_symlink() and path.name not in {"q9_batch.lock", "publish_status.json"}:
                if path.stat().st_size <= 90 * 1024 * 1024:
                    candidates.append(path.relative_to(ROOT).as_posix())
                else:
                    skipped_large.append(path.relative_to(ROOT).as_posix())
        report["skipped_large_files"] = sorted(skipped_large)
        if not candidates:
            raise RuntimeError("no safe Q9 result files to publish")
        # Explicit relative paths, never `git add -A` or raw data globs.
        for path in sorted(set(candidates)):
            result = git("add", "--", path)
            if result.returncode:
                raise RuntimeError(f"could not stage safe result path {path}")
        staged_now = git("diff", "--cached", "--name-only")
        allowed_prefixes = tuple(f"results/{job['experiment_id']}/" for job in manifest["jobs"]) + ("results/Q9-BATCH/",)
        if staged_now.returncode or any(not line.startswith(allowed_prefixes) for line in staged_now.stdout.splitlines()):
            raise RuntimeError("staged path audit failed")
        if not staged_now.stdout.strip():
            report["status"] = "nothing_new_to_commit"
        else:
            batch_state = read_json(batch_dir / "batch_status.json").get("status")
            message = ("Record complete Q9 cloud batch results and logs"
                       if batch_state == "complete_selected_jobs" else
                       "Record partial Q9 cloud batch and failure logs")
            committed = git("commit", "-m", message)
            if committed.returncode:
                raise RuntimeError("Git commit failed; results remain local")
            pushed = git("push", "origin", "HEAD:main")
            if pushed.returncode:
                raise RuntimeError("GitHub push failed; local commit and results remain intact")
            report["status"] = "pushed_with_large_files_retained_on_cloud" if skipped_large else "pushed"
            report["commit"] = git("rev-parse", "HEAD").stdout.strip()
    except Exception as exc:  # preserve failure state without logging credentials
        report["status"] = "pending_manual_publish"
        report["reason"] = str(exc)
    atomic_json(report_path, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--conditions", required=True, help="Comma-separated exact condition names")
    parser.add_argument("--template-file", type=Path, help="JSON object with neural/psd argv arrays")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--publish", action="store_true", help="Attempt safe noninteractive GitHub push at terminal state")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    selected = [part.strip() for part in args.conditions.split(",") if part.strip()]
    templates = read_json(args.template_file) if args.template_file else DEFAULT_TEMPLATES
    output_root = args.output_root.resolve()
    batch_dir = output_root / "Q9-BATCH"
    manifest = build_manifest(args.matrix.resolve(), templates, selected,
                              args.data_dir.resolve(), output_root, args.device, sys.executable)
    if args.plan_only:
        print(json.dumps({"jobs": manifest["jobs"],
                          "selected_fit_counts": manifest["selected_fit_counts"],
                          "unselected_planned_conditions": manifest["unselected_planned_conditions"]}, indent=2))
        return 0
    batch_dir.mkdir(parents=True, exist_ok=True)
    lock = _lock(batch_dir / "q9_batch.lock")
    try:
        manifest_path = batch_dir / "batch_manifest.json"
        if manifest_path.is_file():
            existing = read_json(manifest_path)
            if stable_manifest(existing) != stable_manifest(manifest):
                raise RuntimeError("Existing Q9 batch manifest differs; refusing protocol drift on resume")
            manifest = existing
        else:
            atomic_json(manifest_path, manifest)
        if not args.data_dir.is_dir():
            raise FileNotFoundError(f"BNCI data directory missing: {args.data_dir}")
        environment = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                       "PYTHONUNBUFFERED": "1", "MNE_DATA": str(args.data_dir.resolve())}
        status = {"status": "running", "started_or_resumed_at_utc": now(),
                  "planned_jobs": len(manifest["jobs"]), "completed_jobs": 0,
                  "manifest_sha256": sha256(manifest_path)}
        atomic_json(batch_dir / "batch_status.json", status)
        try:
            for job in manifest["jobs"]:
                run_job(job, batch_dir, environment)
                status["completed_jobs"] += 1
                atomic_json(batch_dir / "batch_status.json", status)
            validator = subprocess.run([sys.executable, "scripts/q9_validate_batch.py",
                                        "--batch-dir", str(batch_dir)], cwd=ROOT,
                                       env=environment, check=False)
            if validator.returncode:
                raise RuntimeError("Batch-level receipt validation failed")
            status["status"] = "complete_selected_jobs"
            status["finished_at_utc"] = now()
            atomic_json(batch_dir / "batch_status.json", status)
            return_code = 0
        except Exception as exc:
            status["status"] = "failed_stopped"
            status["error"] = str(exc)
            status["traceback"] = traceback.format_exc(limit=10)
            status["stopped_at_utc"] = now()
            atomic_json(batch_dir / "batch_status.json", status)
            return_code = 1
        if args.publish:
            _publish(batch_dir, manifest)
        return return_code
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
