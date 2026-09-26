"""Local planning-packet checks; no raw EEG or cloud interaction."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "research_runs/PAPER_RELEASE_20260926/validate_packet.py"
SPEC = importlib.util.spec_from_file_location("paper_packet_validator", VALIDATOR)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_packet_is_consistent_but_not_a_scientific_pass() -> None:
    report = MODULE.validate()
    assert report["status"] == "planning_packet_consistent_not_scientific_validation"
    assert report["q12_q13_new_deep_fits_planned"] == 1215
    assert report["q14_full_independent_validation"] == "pending_cloud_raw_edf"
    assert report["new_training_started_by_this_check"] is False


def test_missing_protocol_blocks_packet(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        MODULE.validate(packet=tmp_path)
