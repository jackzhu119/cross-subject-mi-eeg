"""Acceptance/accounting software fixtures; never read EEG or execute models."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/accept_source_numerics.py"
spec = importlib.util.spec_from_file_location("formal_acceptance_guard_tested", PATH)
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


@pytest.fixture
def old_accounting(tmp_path):
    root = tmp_path / "old-work-root"
    root.mkdir()
    revision = "a" * 40
    (root / "execution_registration.json").write_text(json.dumps({
        "job_id": acceptance.EXPECTED_OLD_JOB, "code_revision": revision}))
    (root / "budget_origin.json").write_text(json.dumps({"started_at_utc": "2026-10-14T07:07:45.290107+00:00"}))
    job = root / ("code-" + revision) / "research_runs/REDESIGN_CLOUD_20261013/jobs" / acceptance.EXPECTED_OLD_JOB
    (job / "source").mkdir(parents=True)
    for name in ("launch_record.json", "runtime_lock.json", "budget_authorization.json", "job_status.json",
                 "source/budget_ledger.json"):
        (job / name).write_text(json.dumps({"synthetic_fixture": True, "actual_neural_fits_started": 0,
            "actual_neural_fits_completed": 0, "optimizer_updates": 0,
            "stage": "FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED"}))
    return root, job


def test_old_accounting_is_observed_without_writes_or_resume_authorization(old_accounting):
    root, _ = old_accounting
    before = {str(p): p.read_bytes() for p in root.rglob("*.json")}
    result, hashes = acceptance.saved_records(root)
    assert result["observed"] is True
    assert result["job_id"] == acceptance.EXPECTED_OLD_JOB
    assert result["identity_transition_authorized"] is False
    assert result["budget_transition_authorized"] is False
    assert hashes == {name: hashlib.sha256(data).hexdigest() for name, data in before.items()}
    assert {str(p): p.read_bytes() for p in root.rglob("*.json")} == before


def test_absent_old_work_root_is_unknown_not_a_fresh_registration(tmp_path):
    result, hashes = acceptance.saved_records(tmp_path / "absent")
    assert result["observed"] is False and hashes == {}
    assert not (tmp_path / "absent").exists()
    result, hashes = acceptance.saved_records(None)
    assert result["observed"] is False and hashes == {}


def test_wrong_old_job_is_blocked_without_touching_registration(old_accounting):
    root, _ = old_accounting
    path = root / "execution_registration.json"
    data = json.loads(path.read_text())
    data["job_id"] = "another-job"
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="different_old_task_registration_do_not_touch"):
        acceptance.saved_records(root)
    assert path.read_bytes() == before


@pytest.mark.parametrize("revision", ["a" * 39, "A" * 40, "../unsafe", "invalid"])
def test_invalid_old_revision_never_selects_or_initializes_new_job(old_accounting, revision):
    root, _ = old_accounting
    path = root / "execution_registration.json"
    record = json.loads(path.read_text())
    record["code_revision"] = revision
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="invalid_old_revision"):
        acceptance.saved_records(root)


def test_symlink_accounting_file_is_rejected(old_accounting, tmp_path):
    root, _ = old_accounting
    path = root / "budget_origin.json"
    data = path.read_bytes()
    path.unlink()
    actual = tmp_path / "budget.json"
    actual.write_bytes(data)
    path.symlink_to(actual)
    with pytest.raises(ValueError, match="old_accounting_record_symlink"):
        acceptance.saved_records(root)
    assert actual.read_bytes() == data


def args(tmp_path, output=None, old_root=None):
    return argparse.Namespace(code_revision="b" * 40, old_work_root=old_root,
        output_dir=output or tmp_path / "new-acceptance", data_dir=tmp_path / "raw",
        runtime_role="diagnostic", diagnostic_package=None)


def test_existing_output_is_not_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "exists"
    output.mkdir()
    (output / "original.json").write_text("original")
    monkeypatch.setattr(acceptance, "check_checkout", lambda revision: {"synthetic_checkout": True})
    with pytest.raises(ValueError, match="acceptance_output_already_exists_no_overwrite"):
        acceptance.run(args(tmp_path, output))
    assert (output / "original.json").read_text() == "original"
    assert [p.name for p in output.iterdir()] == ["original.json"]


def test_output_inside_raw_cache_is_rejected_before_creation(tmp_path, monkeypatch):
    command = args(tmp_path)
    command.output_dir = command.data_dir / "acceptance"
    monkeypatch.setattr(acceptance, "check_checkout", lambda revision: {"synthetic_checkout": True})
    with pytest.raises(ValueError, match="acceptance_output_must_be_outside_checkout_and_raw_data"):
        acceptance.run(command)
    assert not command.output_dir.exists() and not command.data_dir.exists()


def test_output_inside_checkout_is_rejected_before_creation(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    monkeypatch.setattr(acceptance, "ROOT", checkout)
    monkeypatch.setattr(acceptance, "check_checkout", lambda revision: {"synthetic_checkout": True})
    output = checkout / "acceptance"
    with pytest.raises(ValueError, match="acceptance_output_must_be_outside_checkout_and_raw_data"):
        acceptance.run(args(tmp_path, output))
    assert not output.exists() and not checkout.exists()


@pytest.mark.parametrize("text,expected", [
    ("from formal_core_inputs import load_source19\n", True),
    ("from core_source_inputs import load_source19\n", False),
    ("from formal_core_inputs import transform_context19\n", False),
    ("x = 'from formal_core_inputs import load_source19'\n", False)])
def test_static_binding_observes_imports_not_strings_or_legacy_loader(tmp_path, text, expected):
    path = tmp_path / "consumer.py"
    path.write_text(text)
    assert acceptance.import_binding(path, "load_source19") is expected


def test_original_failure_accounting_changed_during_acceptance_blocks_report(old_accounting, tmp_path, monkeypatch):
    # Exercise the concurrency guard with tiny in-memory audit fixtures. This
    # deliberately substitutes EEG reconstruction; no source file is opened.
    root, _ = old_accounting
    sys.path.insert(0, str(ROOT / "research_runs/REDESIGN_CLOUD_20261013/scripts"))
    import formal_core_inputs
    monkeypatch.setattr(acceptance, "check_checkout", lambda revision: {"synthetic_checkout": True})
    def changed_accounting(*unused):
        (root / "budget_origin.json").write_text(json.dumps({"changed_by_concurrent_fixture": True}))
        return {}, [{}] * 2592, {"n_raw_files": 18, "n_runs": 108}
    monkeypatch.setattr(formal_core_inputs, "load_source19", changed_accounting)
    monkeypatch.setattr(formal_core_inputs, "verify_source_inputs", lambda *a: True)
    command = args(tmp_path, old_root=root)
    with pytest.raises(ValueError, match="old_accounting_record_changed_during_acceptance"):
        acceptance.run(command)
    assert not (command.output_dir / "formal_source_acceptance.json").exists()
