"""Run03 outer identity tests: temporary paths and a tiny synthetic process only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

WRAPPER = Path(__file__).parents[1] / 'RUN_RUN03_ONCE.sh'
PRODUCTION_CONTROLLER_SHA = '11e02a4f487a74a46ba99567f82d2642f1785323afc2eb58871ec799a7887947'


@pytest.mark.parametrize('actual_exit', [0, 23])
def test_outer_records_actual_synthetic_exit_and_refuses_second_dispatch(tmp_path, actual_exit):
    code, dispatch, cache = (tmp_path / name for name in ('code', 'dispatch', 'cache'))
    for folder in (code, dispatch, cache):
        folder.mkdir()
    controller = code / 'target_restore_run03.py'
    controller.write_text("print('synthetic_process_only')\nraise SystemExit(" + str(actual_exit) + ")\n")
    sha = hashlib.sha256(controller.read_bytes()).hexdigest()
    original = WRAPPER.read_text()
    assert original.count(PRODUCTION_CONTROLLER_SHA) == 1
    script = original.replace('/workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore', str(code))
    script = script.replace('/workspace/paper1-target-dispatch-20261015-run03', str(dispatch))
    script = script.replace('/workspace/paper1-target-recovery-run01', str(cache))
    script = script.replace(PRODUCTION_CONTROLLER_SHA, sha)
    copied = code / WRAPPER.name
    copied.write_text(script)
    paths = {}
    for name in ('review', 'slot', 'head'):
        path = tmp_path / (name + '.json'); path.write_text('{}\n'); paths[name] = str(path)
    env = dict(os.environ, P1_RUN03_REVISION='a' * 40, P1_RUN03_REVIEW=paths['review'],
        P1_RUN03_SLOT=paths['slot'], P1_RUN03_HEAD=paths['head'])
    result = subprocess.run(['bash', str(copied)], env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode == actual_exit, result.stdout + result.stderr
    outer = json.loads((dispatch / 'observed_outer.json').read_text())
    assert outer['exit_code'] == actual_exit and outer['script_sha256'] == sha
    assert outer['target_restore_summary_sha256'] is None and outer['training_authorization'] is False
    completion = json.loads((dispatch / 'completion.json').read_text())
    assert completion['exit_code'] == actual_exit and completion['controller_command_invoked'] is True
    assert completion['stdout']['sha256'] == hashlib.sha256(b'synthetic_process_only\n').hexdigest()
    assert completion['controller_after']['sha256'] == sha
    command = json.loads((dispatch / 'command.json').read_text())
    assert command['argv'][:4] == ['timeout', '--signal=TERM', '--kill-after=5s', '1200s']
    before = {p.name: p.read_bytes() for p in dispatch.iterdir()}
    again = subprocess.run(['bash', str(copied)], env=env, text=True, capture_output=True, timeout=10)
    assert again.returncode == 73
    assert {p.name: p.read_bytes() for p in dispatch.iterdir()} == before
