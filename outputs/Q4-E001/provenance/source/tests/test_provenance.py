"""Guards against silent config drift and overwriting failed runs."""

from pathlib import Path

import pytest

from mi_eeg.provenance import check_declared_constants, require_new_run_directory


def test_failed_run_cannot_be_reused(tmp_path: Path) -> None:
    output = tmp_path / "failed_run"
    require_new_run_directory(output)
    (output / "run_status.json").write_text('{"status":"failed"}')
    with pytest.raises(FileExistsError):
        require_new_run_directory(output)
    assert (output / "run_status.json").read_text() == '{"status":"failed"}'


def test_legacy_config_change_is_rejected() -> None:
    with pytest.raises(ValueError, match="band"):
        check_declared_constants({"filter": {"band": [4, 40]}}, {"filter": {"band": [8, 30]}})
