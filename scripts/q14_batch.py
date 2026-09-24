"""One-command, restartable Q14 BNCI development, freeze, external inference and audit.

Run under a server-side detached process (systemd/nohup/tmux) if the local
computer may disconnect. A failed step stops the chain; rerunning resumes
individual fits and target subjects rather than discarding checkpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/Q14-BATCH"


def _step(name: str, args: list[str]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    log = RESULTS / f"{name}.log"
    print(f"Q14 step {name}: {args}", flush=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"\n===== {datetime.now(UTC).isoformat()} start: {name} =====\n")
        stream.flush()
        result = subprocess.run(
            args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False
        )
        stream.write(
            f"\n===== {datetime.now(UTC).isoformat()} exit={result.returncode}: {name} =====\n"
        )
    if result.returncode:
        raise RuntimeError(
            f"Q14 {name} failed with exit {result.returncode}; see {log}. Restart same command after correction."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bnci-data-dir", type=Path, required=True)
    parser.add_argument("--physionet-data-dir", type=Path)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument(
        "--execute-external",
        action="store_true",
        help="After source-only validation/freeze, load and evaluate the independent cohort.",
    )
    args = parser.parse_args()
    if args.execute_external and args.physionet_data_dir is None:
        parser.error("--execute-external requires --physionet-data-dir")
    python = sys.executable
    _step(
        "e001_source",
        [
            python,
            "scripts/q14_source.py",
            "--phase",
            "e001",
            "--data-dir",
            str(args.bnci_data_dir),
            "--device",
            args.device,
        ],
    )
    _step("e001_validate", [python, "scripts/q14_validate.py", "--stage", "e001"])
    _step(
        "e002_source",
        [
            python,
            "scripts/q14_source.py",
            "--phase",
            "e002",
            "--data-dir",
            str(args.bnci_data_dir),
            "--device",
            args.device,
        ],
    )
    _step("e002_freeze", [python, "scripts/q14_validate.py", "--stage", "e002"])
    if args.execute_external:
        _step(
            "e002_external",
            [
                python,
                "scripts/q14_external.py",
                "--data-dir",
                str(args.physionet_data_dir),
                "--device",
                args.device,
            ],
        )
        _step("e002_external_validate", [python, "scripts/q14_validate.py", "--stage", "external"])
    receipt = {
        "status": "complete_external_validated"
        if args.execute_external
        else "complete_source_frozen",
        "experiment_ids": ["Q14-E001", "Q14-E002"],
        "bnci_deep_fits": 140,
        "bnci_shallow_fits": 10,
        "external_target_fits": 0,
        "finished_at_utc": datetime.now(UTC).isoformat(),
    }
    tmp = RESULTS / "completion_receipt.json.tmp"
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, RESULTS / "completion_receipt.json")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
