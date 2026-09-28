"""Direct-script Q13 validator import regression; no EEG fitting or cloud access."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_q13_validator_direct_script_can_import_replay_dependency() -> None:
    # -I excludes the working directory and PYTHONPATH, reproducing the
    # absolute-file batch entrypoint's missing-repository-root failure.
    probe = (
        "import runpy; "
        "validator = runpy.run_path('scripts/validate_q13.py', "
        "run_name='q13_validator_import_probe'); "
        "from scripts import q9_neural; "
        "assert callable(validator['_replay_checkpoint']); "
        "print(q9_neural.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "scripts.q9_neural"


def test_q13_validator_direct_script_help_is_available() -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts/validate_q13.py"), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--data-dir" in result.stdout
    assert "--artifact-only" in result.stdout
