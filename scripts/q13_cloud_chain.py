"""Detached, resumable Q13 837 + E006 27 scientific release chain.

This module is deliberately *not* a Q15 launcher. A check-only invocation
verifies the GPU, frozen BNCI bytes and noninteractive Git publication before
any training. The execute path retains failure receipts and attempts Git
publication on normal success or caught failure; power loss and SIGKILL cannot
run its finalizer, so local files must remain available for manual recovery.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import q13_batch, q13_e006, q14_source

RESULTS = ROOT / "results"
RELEASE = RESULTS / "Q13-RELEASE"
ORIGINAL = RESULTS / "Q13-BATCH"
AMENDMENT = RESULTS / "Q13-E006"
EXPERIMENTS = ("Q13-E001", "Q13-E004", "Q13-E005")


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def run_logged(name: str, argv: list[str], *, python: Path) -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    log_path = RELEASE / f"{name}.log"
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n[{now_utc()}] argv={json.dumps(argv)}\n")
        stream.flush()
        process = subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT,
                                 check=False)
        stream.write(f"[{now_utc()}] exit_code={process.returncode}\n")
    return process.returncode


def check_only(data_dir: Path, python: Path) -> dict:
    """No fits: verify Q13 source and publication gates before paid work."""
    if not python.is_absolute() or not python.is_file():
        raise RuntimeError("Use an absolute path to the paper Python interpreter")
    if not data_dir.is_absolute() or not data_dir.is_dir():
        raise RuntimeError("Use an existing absolute BNCI MAT data directory")
    if subprocess.run([str(python), str(ROOT / "scripts/check_paper_env.py")],
                      cwd=ROOT, check=False).returncode:
        raise RuntimeError("Pinned Python/PyTorch/TorchAudio/CUDA check failed")
    q13_batch.preflight(output_root=RESULTS, publish=True, device="cuda")
    files = q14_source.source_file_receipt(data_dir)
    if len(files) != 18:
        raise AssertionError("Exactly 18 Q8-identical BNCI MAT files required")
    plan = q13_batch.plan()
    if len(plan) != 13 or sum(job["expected_fits"] for job in plan) != 837:
        raise AssertionError("Q13 frozen batch no longer plans 13 jobs and 837 fits")
    epochs = q13_e006.selected_epochs_from_q5()
    if set(epochs) != {str(subject) for subject in range(1, 10)}:
        raise AssertionError("E006 historical source-only selections are incomplete")
    return {"status": "preflight_passed_no_training", "q13_jobs": 13,
            "q13_deep_fits": 837, "e006_deep_fits_after_q13_validation": 27,
            "frozen_bnci_mat_files": len(files), "target_fits": 0,
            "q15_activated": False}


def publish_all(python: Path) -> dict[str, bool]:
    """Retry allowlisted publisher; leave local files if GitHub is unavailable."""
    published = {}
    if ORIGINAL.is_dir():
        for experiment in EXPERIMENTS:
            path = RESULTS / experiment
            if path.is_dir():
                published[experiment] = run_logged(
                    f"publish_{experiment}",
                    [str(python), str(ROOT / "scripts/publish_research_run.py"),
                     "--batch-dir", str(ORIGINAL), "--experiment-dir", str(path)],
                    python=python,
                ) == 0
    published["Q13-RELEASE_and_E006"] = run_logged(
        "publish_release_e006",
        [str(python), str(ROOT / "scripts/publish_research_run.py"),
         "--batch-dir", str(RELEASE), "--experiment-dir", str(AMENDMENT)],
        python=python,
    ) == 0
    return published


def execute(data_dir: Path, python: Path) -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    # The descriptor stays open until the entire chain and publication end.
    import fcntl  # Linux only: keep dry-run and test collection platform-neutral.

    with (RELEASE / "queue.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("A Q13 release chain is already running") from exc
        state: dict = {"status": "preflight", "started_at_utc": now_utc(),
                       "q13_837_validated": False, "e006_27_validated": False,
                       "postrun_statistics_complete": False, "q15_activated": False}
        atomic_json(RELEASE / "batch_status.json", state)
        result = 1
        try:
            state["preflight"] = check_only(data_dir, python)
            state["status"] = "running_q13"
            atomic_json(RELEASE / "batch_status.json", state)
            q13_rc = run_logged(
                "q13_batch", [str(python), str(ROOT / "scripts/q13_batch.py"),
                              "--execute", "--publish", "--data-dir", str(data_dir),
                              "--output-root", str(RESULTS), "--device", "cuda",
                              "--python", str(python)], python=python)
            state["q13_batch_exit_code"] = q13_rc
            original = read_json(ORIGINAL / "batch_status.json")
            scientific = read_json(ORIGINAL / "validation_report.json")
            if (original.get("status") != "complete_validated"
                    or scientific.get("status") != "passed"
                    or scientific.get("checkpoint_replays") != 837):
                raise RuntimeError("Q13 837-checkpoint scientific validation did not pass")
            state["q13_837_validated"] = True
            state["status"] = "running_e006"
            atomic_json(RELEASE / "batch_status.json", state)
            if run_logged("q13_e006", [str(python), str(ROOT / "scripts/q13_e006.py"),
                                         "--execute", "--data-dir", str(data_dir)],
                          python=python):
                raise RuntimeError("Q13-E006 27-fit runner failed; see q13_e006.log")
            if run_logged("validate_q13_e006",
                          [str(python), str(ROOT / "scripts/validate_q13_e006.py"),
                           "--data-dir", str(data_dir), "--device", "cuda"],
                          python=python):
                raise RuntimeError("Q13-E006 independent validation failed")
            amended = read_json(AMENDMENT / "validation_report.json")
            if amended.get("status") != "passed" or amended.get("checkpoint_replays") != 27:
                raise RuntimeError("Q13-E006 27-checkpoint replay receipt missing")
            state["e006_27_validated"] = True
            if run_logged("q13_postrun_statistics",
                          [str(python), str(ROOT / "scripts/q13_e006_postrun_stats.py")],
                          python=python):
                raise RuntimeError("Q13 subject-level post-run statistics failed")
            postrun = read_json(AMENDMENT / "postrun_statistics/analysis_receipt.json")
            if postrun.get("status") != "post_validation_exploratory_statistics_complete":
                raise RuntimeError("Q13 post-run statistics receipt missing")
            state["postrun_statistics_complete"] = True
            state["status"] = "complete_validated"
            result = 0
        except Exception as exc:  # noqa: BLE001 - retain complete cloud failure context
            state["status"] = "failed_stopped"
            state["error"] = str(exc)
            state["traceback"] = traceback.format_exc(limit=12)
        finally:
            state["updated_at_utc"] = now_utc()
            atomic_json(RELEASE / "batch_status.json", state)
            try:
                published = publish_all(python)
            except Exception as exc:  # noqa: BLE001 - never erase scientific results
                published = {"publication_exception": False}
                state["publication_error"] = str(exc)
            state["publication"] = published
            if not published or not all(published.values()):
                state["publication_pending"] = True
                result = result or 2
            atomic_json(RELEASE / "batch_status.json", state)
            # A second pass records the final publication summary when possible.
            try:
                published["final_release_receipt"] = run_logged(
                    "publish_final_receipt",
                    [str(python), str(ROOT / "scripts/publish_research_run.py"),
                     "--batch-dir", str(RELEASE), "--experiment-dir", str(AMENDMENT)],
                    python=python,
                ) == 0
            except Exception:  # noqa: BLE001 - local receipt remains authoritative
                published["final_release_receipt"] = False
            if not published["final_release_receipt"]:
                result = result or 2
            state["publication"] = published
            atomic_json(RELEASE / "batch_status.json", state)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.check_only == args.execute or (args.execute and not args.publish):
        parser.error("Choose --check-only, or both --execute --publish")
    # A venv's bin/python is often a symlink. Resolving it to the underlying
    # system interpreter discards the venv's site-packages on Linux.
    data_dir, python = args.data_dir.resolve(), args.python.absolute()
    if args.check_only:
        print(json.dumps(check_only(data_dir, python), indent=2))
        return 0
    return execute(data_dir, python)


if __name__ == "__main__":
    raise SystemExit(main())
