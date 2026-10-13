"""Software-only fixtures: never read real target EEG or run scientific fits."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest
import torch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("core_inference", SCRIPTS / "infer_selection_core.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from core_source_inputs import CHANNELS19
from train_source_selection_core import select_epochs, schedule_cells


@pytest.mark.parametrize("number,name", [(1, "A01"), (60, "A60"), (61, "B61"), (81, "B81"), (82, "C82"), (87, "C87")])
def test_global_provider_identity_not_renumbered(number, name):
    assert m.subject_name(number) == name
    assert m.event_identity(number, "R1acquisition", 40) == name + "_R1acquisition_cue_40"


@pytest.mark.parametrize("number", [0, 88, True, 1.0])
def test_provider_identity_type_and_bounds(number):
    with pytest.raises(ValueError):
        m.subject_name(number)


def test_online_run_and_invalid_cue_are_not_primary():
    with pytest.raises(ValueError):
        m.event_identity(1, "R3online", 1)
    with pytest.raises(ValueError):
        m.event_identity(1, "R1acquisition", 41)


def test_repo_artifacts_reject_outside_and_symlink(tmp_path):
    study = tmp_path / "study"
    study.mkdir()
    (study / "regular.json").write_text("{}")
    assert m.regular_path("study/regular.json", tmp_path, study) == study / "regular.json"
    for name in ("../regular.json", str(study / "regular.json")):
        with pytest.raises(ValueError):
            m.regular_path(name, tmp_path, study)
    (study / "redirect.json").symlink_to(study / "regular.json")
    with pytest.raises(ValueError):
        m.regular_path("study/redirect.json", tmp_path, study)


def test_default_dryrun_has_no_gates_raw_read_or_model_output(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["infer_selection_core.py"])
    monkeypatch.setattr(m, "execution_gates", lambda *_: pytest.fail("Default must not consult execution gates"))
    monkeypatch.setattr(m, "prepare_target_inputs", lambda *_: pytest.fail("Default must not read EEG"))
    m.main()
    result = json.loads(capsys.readouterr().out)
    assert result["target_predictions_computed"] is False
    assert result["new_source_fits"] == result["target_fits"] == 0
    assert result["status"] == "DRY_RUN_NO_TARGET_EEG_READ_NO_MODEL_OUTPUT"


def test_failed_execution_gate_precedes_target_loading_or_output_creation(tmp_path, monkeypatch):
    def blocked(_):
        raise ValueError("full scientific gates pending")
    monkeypatch.setattr(m, "execution_gates", blocked)
    monkeypatch.setattr(m, "prepare_target_inputs", lambda *_: pytest.fail("Failed gates must precede EEG read"))
    output = tmp_path / "never-created"
    with pytest.raises(ValueError, match="gates pending"):
        m.execute(tmp_path / "source", tmp_path / "target", output)
    assert not output.exists()


def test_missing_author_and_full_cohort_cannot_open_target_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "DATA_GATE", tmp_path / "absent-gate.json")
    with pytest.raises(ValueError, match="absent"):
        m.verify_target_gate(json.loads(m.CONFIG.read_text()))


def test_eval_predictions_preserve_batchnorm_weights_and_buffers():
    torch.manual_seed(123)
    model = torch.nn.Sequential(torch.nn.BatchNorm1d(3), torch.nn.Linear(3, 2))
    model.train()
    before = {key: value.clone() for key, value in model.state_dict().items()}
    values = np.arange(195, dtype=np.float32).reshape(65, 3) / 100
    probabilities, receipt = m.predict_batches(model, values, "cpu")
    assert probabilities.shape == (65, 2)
    np.testing.assert_allclose(probabilities.sum(1), 1, atol=1e-6)
    assert not model.training and receipt["parameters_and_buffers_unchanged"]
    assert receipt["state_before_sha256"] == receipt["state_after_sha256"]
    assert all(torch.equal(before[key], value) for key, value in model.state_dict().items())


def test_eval_guard_runs_before_every_batch_and_does_not_adapt():
    model = torch.nn.Linear(3, 2)
    calls = []
    m.predict_batches(model, np.ones((129, 3), dtype=np.float32), "cpu", guard=lambda: calls.append(1))
    assert len(calls) == 3
    with pytest.raises(ValueError, match="Fixed"):
        m.predict_batches(model, np.ones((2, 3)), "cpu", batch_size=1)


def test_model_that_mutates_buffer_is_rejected():
    class Mutation(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("counter", torch.zeros(1))
        def forward(self, x):
            self.counter += 1
            return torch.zeros((len(x), 2))
    with pytest.raises(ValueError, match="changed"):
        m.predict_batches(Mutation(), np.ones((2, 3)), "cpu")


@pytest.mark.parametrize("values", [np.array([[np.nan, 1, 2]]), np.ones((0, 3))])
def test_nonfinite_or_empty_inputs_rejected(values):
    with pytest.raises(ValueError, match="finite"):
        m.predict_batches(torch.nn.Linear(3, 2), values, "cpu")


def test_invalid_model_output_rejected():
    with pytest.raises(ValueError, match="logits"):
        m.predict_batches(torch.nn.Linear(3, 3), np.ones((2, 3)), "cpu")


def edf_fixture(path, flat=False, unit="uV", continuous=True):
    """Small fully synthetic 19-channel EDF+C with 40 fake class annotations."""
    names = list(CHANNELS19) + ["EDF Annotations"]
    nsign, nsamples, nrecords = len(names), 64, 5
    # Record duration 0.125 s produces the protocol's 512-Hz channel rate.
    def field(value, width):
        value = str(value).encode("ascii")
        assert len(value) <= width
        return value.ljust(width, b" ")
    fixed = (field("0", 8) + field("synthetic fixture only", 80) + field("no scientific data", 80)
             + field("01.01.26", 8) + field("00.00.00", 8) + field(256 + 256 * nsign, 8)
             + field("EDF+C" if continuous else "EDF+D", 44) + field(nrecords, 8) + field(.125, 8) + field(nsign, 4))
    props = [(names, 16), ([""] * nsign, 80), ([unit] * 19 + [""], 8), ([-100] * 19 + [-1], 8),
             ([100] * 19 + [1], 8), ([-32768] * nsign, 8), ([32767] * nsign, 8), ([""] * nsign, 80),
             ([nsamples] * nsign, 8), ([""] * nsign, 32)]
    signals_header = b"".join(field(value, width) for values, width in props for value in values)
    blocks = []
    for record in range(nrecords):
        pieces = []
        for channel in range(19):
            digital = np.zeros(nsamples, dtype="<i2") if flat else (np.arange(nsamples) + record + channel).astype("<i2")
            pieces.append(digital.tobytes())
        tal = b"".join(f"+{record * .125 + cue * .01:.3f}\x14{'769' if (record * 8 + cue) % 2 == 0 else '770'}\x14\x00".encode("ascii") for cue in range(8))
        assert len(tal) <= nsamples * 2
        pieces.append(tal.ljust(nsamples * 2, b"\x00"))
        blocks.append(b"".join(pieces))
    path.write_bytes(fixed + signals_header + b"".join(blocks))
    return {"size": path.stat().st_size, "checksum": m.sha(path)}


def test_edf_digital_to_physical_microvolt_header_conversion(tmp_path):
    path = tmp_path / "synthetic.edf"
    row = edf_fixture(path)
    signal, header, cues = m.load_physical_edf(path, row)
    assert signal.shape == (19, 320) and header["channels"][0]["sampling_frequency_hz"] == 512
    expected = (np.arange(64) + 32768) * 200 / 65535 - 100
    np.testing.assert_allclose(signal[0, :64], expected)
    # A µV-scale header remains µV; the code does not interpret native integers as V.
    assert np.max(np.abs(signal)) < 1
    assert len(cues) == 40 and sum(c["description"] == "769" for c in cues) == 20


@pytest.mark.parametrize("change,message", [("checksum", "bytes"), ("size", "bytes")])
def test_edf_provider_byte_identity_is_mandatory(tmp_path, change, message):
    path = tmp_path / "synthetic.edf"
    row = edf_fixture(path)
    row[change] = "0" * 64 if change == "checksum" else row[change] + 1
    with pytest.raises(ValueError, match=message):
        m.load_physical_edf(path, row)


@pytest.mark.parametrize("options,message", [({"flat": True}, "flatline"), ({"unit": "V"}, "µV"), ({"continuous": False}, "continuous")])
def test_edf_technical_guard_not_score_driven(tmp_path, options, message):
    path = tmp_path / "synthetic.edf"
    row = edf_fixture(path, **options)
    with pytest.raises(ValueError, match=message):
        m.load_physical_edf(path, row)


@pytest.fixture
def source_fixture(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    study = root / "study"
    source = study / "results" / "fixture-source-not-real"
    source.mkdir(parents=True)
    config_path = study / "config.json"
    config_path.write_text(m.CONFIG.read_text())
    monkeypatch.setattr(m, "ROOT", root)
    monkeypatch.setattr(m, "STUDY", study)
    monkeypatch.setattr(m, "CONFIG", config_path)
    config = json.loads(config_path.read_text())
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    selected, cells, aliases, owners = {}, [], 0, 0
    for name in config["architectures"]:
        curves = []
        for fold, group in enumerate(config["source_validation_groups"], 1):
            directory = source / "inner" / name / f"fold_{fold:02d}"
            curve = [{"epoch": e, "validation_cross_entropy": float(e)} for e in range(1, 41)]
            write(directory / "source_curve.json", curve)
            write(directory / "fit_receipt.json", {"status": "completed", "architecture": name, "seed": config["selection_seed"],
                  "epochs": 40, "target_fit": False, "n_validation_trials": 288 * len(group), "n_training_trials": 288 * (9 - len(group)),
                  "curve_sha256": m.sha(directory / "source_curve.json")})
            write(directory / "partition.json", {"synthetic_fixture": True})
            curves.append(curve)
        selection = select_epochs(curves, config["candidate_epochs"])
        selected[name] = selection
        for cell in schedule_cells(name, selection, config["final_seeds"]):
            cells.append(cell)
            owner = source / "final" / cell["owner_cell"]
            if not cell["alias"]:
                owner.mkdir(parents=True)
                (owner / "checkpoint.pt").write_bytes(b"synthetic-not-a-serialized-model" + cell["cell"].encode())
                write(owner / "fit_receipt.json", {"status": "completed", "architecture": name, "seed": cell["seed"], "epochs": cell["epochs"],
                      "n_training_trials": 2592, "n_validation_trials": 0, "target_fit": False, "configuration_sha256": m.sha(config_path),
                      "checkpoint_sha256": m.sha(owner / "checkpoint.pt"), "model_state_sha256": "a" * 64,
                      "optimizer_updates": 41 * cell["epochs"]})
                write(owner / "partition.json", {"synthetic_fixture": True})
                write(owner / "source_curve.json", {"synthetic_fixture": True})
                owners += 1
            else:
                aliases += 1
                write(source / "final" / cell["cell"] / "alias_receipt.json", {**cell, "new_real_neural_fit": False,
                      "owner_checkpoint_sha256": m.sha(owner / "checkpoint.pt"), "owner_model_state_sha256": "a" * 64})
    completion = {"target_fits": 0, "target_predictions_computed": False, "nominal_inner_fits": 8, "nominal_final_cells": 18,
                  "selected_epochs": selected, "actual_new_neural_fits": 8 + owners, "aliases": aliases, "final_cells": cells}
    write(source / "source_completion_manifest.json", completion)
    write(source / "source_independent_validation.json", {"status": "PASS_SOURCE_ONLY_GRID_VALIDATION", "target_predictions_computed": False,
          "target_fits": 0, "source_completion_manifest_sha256": m.sha(source / "source_completion_manifest.json")})
    write(source / "source19_input_audit.json", {"status": "PASS_SOURCE19_INPUTS_ONLY", "n_binary_trials": 2592, "n_raw_files": 18, "target_eeg_read": False})
    write(source / "runtime_provenance.json", {"synthetic_fixture": True})
    write(source / "selected_epochs.json", selected)
    return source


def test_source_schedule_replay_and_declared_same_duration_aliases(source_fixture):
    cells, _, completion = m.source_cells(source_fixture)
    assert len(cells) == 18 and sum(c["alias"] for c in cells) == 6
    assert completion["actual_new_neural_fits"] == 20
    for arch in ("broad", "shared"):
        loss = [c for c in cells if c["model_arch"] == arch and c["analysis_selector"] == "mean_loss"]
        rank = [c for c in cells if c["model_arch"] == arch and c["analysis_selector"] == "mean_rank"]
        assert [c["checkpoint_sha256"] for c in loss] == [c["checkpoint_sha256"] for c in rank]


def test_source_independent_validation_is_mandatory(source_fixture):
    (source_fixture / "source_independent_validation.json").unlink()
    with pytest.raises(ValueError, match="absent"):
        m.source_cells(source_fixture)


def test_source_alias_must_retain_owner_identity(source_fixture):
    path = next(source_fixture.rglob("alias_receipt.json"))
    alias = json.loads(path.read_text())
    alias["owner_checkpoint_sha256"] = "0" * 64
    path.write_text(json.dumps(alias))
    with pytest.raises(ValueError, match="alias"):
        m.source_cells(source_fixture)


def test_changed_source_schedule_cannot_be_selected_using_target(source_fixture):
    path = source_fixture / "selected_epochs.json"
    selected = json.loads(path.read_text())
    selected["BROAD_EEGNET"]["mean_rank"] = 20
    path.write_text(json.dumps(selected))
    with pytest.raises(ValueError, match="schedule"):
        m.source_cells(source_fixture)


def test_preinference_public_freeze_cannot_be_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "FREEZE", tmp_path / "not-created.json")
    with pytest.raises(ValueError, match="absent"):
        m.verify_freeze([], tmp_path / "roster", tmp_path / "manifest")
