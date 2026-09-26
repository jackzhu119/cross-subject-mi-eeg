"""Cross-host Q14 validation is explicit, versioned, and inference-free."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import q14_r2_migration, q14_r2_portable_finalize, q14_r2_validate


def test_legacy_validator_still_requires_live_inference_runtime(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(q14_r2_validate, "runtime_receipt", lambda: {"gpu": "other"})
    monkeypatch.setattr(
        q14_r2_migration, "audit_r1_origin", lambda *args: calls.append(args)
    )
    with pytest.raises(AssertionError, match="R2 runtime"):
        q14_r2_validate._origin_for_validation(
            Path("/edf"), {"runtime": {"gpu": "inference"}, "device": "cuda"},
            {}, "freeze", portable=False,
        )
    assert calls == []


def test_portable_custody_compares_saved_historical_runtime_but_records_actual(
    monkeypatch,
) -> None:
    live = {"gpu": "validation-vgpu"}
    historical = {"gpu": "inference-4080"}
    monkeypatch.setattr(q14_r2_validate, "runtime_receipt", lambda: live)
    monkeypatch.setattr(q14_r2_migration, "runtime_receipt", lambda: live)

    def audit(data_dir, device, config, freeze):
        assert q14_r2_migration.runtime_receipt() == historical
        assert (data_dir, device, config, freeze) == (Path("/edf"), "cuda", {}, "freeze")
        return {"custody": "checked"}

    monkeypatch.setattr(q14_r2_migration, "audit_r1_origin", audit)
    observed, origin = q14_r2_validate._origin_for_validation(
        Path("/edf"), {"runtime": historical, "device": "cuda"}, {}, "freeze",
        portable=True,
    )
    assert observed == live
    assert origin == {"custody": "checked"}
    assert q14_r2_migration.runtime_receipt() == live  # Injection did not leak.


def test_portable_results_cannot_alias_original_q14_directory() -> None:
    with pytest.raises(AssertionError, match="versioned Q14-E002R2V1"):
        q14_r2_validate.validate(portable_output_root=q14_r2_validate.RESULT)


def test_manifest_covers_every_subject_and_detects_prediction_mutation(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "repo"
    source = root / "results/Q14-E002R2/external"
    source.mkdir(parents=True)
    monkeypatch.setattr(q14_r2_portable_finalize, "ROOT", root)
    monkeypatch.setattr(q14_r2_portable_finalize, "SOURCE", source)
    for name in (
        "run_config.json", "migration_receipt.json", "metadata_preflight.json",
        "completion_receipt.json", "physionet_SHA256SUMS.txt", "predictions.csv",
    ):
        (source / name).write_text(name, encoding="ascii")
    for subject in range(1, 110):
        folder = source / f"subject_{subject:03d}"
        folder.mkdir()
        (folder / "receipt.json").write_text("receipt", encoding="ascii")
        (folder / "predictions.csv").write_text("prediction", encoding="ascii")
    before = q14_r2_portable_finalize.source_manifest()
    assert len(before) == 6 + 2 * 109
    assert all(item["path"].startswith("results/Q14-E002R2/external/") for item in before)
    (source / "subject_109/predictions.csv").write_text("changed", encoding="ascii")
    assert before != q14_r2_portable_finalize.source_manifest()


def test_portable_dry_run_never_opens_cloud_data(capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["q14_r2_portable_finalize.py"])
    q14_r2_portable_finalize.main()
    assert "zero fits/inference" in capsys.readouterr().out
