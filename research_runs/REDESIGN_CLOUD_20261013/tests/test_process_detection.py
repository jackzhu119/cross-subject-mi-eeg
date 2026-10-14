"""Process detection regressions: no credentials, EEG, CUDA, fits or inference.

The live tests use inert fixture scripts. They reproduce the launcher's actual
Python-stdin ancestor shape and check that real fixture workers still block.
"""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
supervisor = importlib.import_module('cloud_supervisor')


@pytest.mark.parametrize('argv,expected', [
    (['python', '/fixture/cloud_supervisor.py', 'launch'], '/fixture/cloud_supervisor.py'),
    (['/venv/bin/python3.12', '-u', '/fixture/train_exploratory.py', '--execute'], '/fixture/train_exploratory.py'),
    (['python3', '-BEs', '/fixture/infer_exploratory.py'], '/fixture/infer_exploratory.py'),
    (['python', '-OO', '-I', '/fixture/prepare_data.py'], '/fixture/prepare_data.py'),
    (['python', '-W', 'ignore', '/fixture/train_exploratory.py'], '/fixture/train_exploratory.py'),
    (['python', '-Wignore', '/fixture/train_exploratory.py'], '/fixture/train_exploratory.py'),
    (['python', '-X', 'dev', '/fixture/infer_exploratory.py'], '/fixture/infer_exploratory.py'),
    (['python', '-Xdev', '/fixture/infer_exploratory.py'], '/fixture/infer_exploratory.py'),
    (['python', '--check-hash-based-pycs', 'always', '/fixture/prepare_data.py'], '/fixture/prepare_data.py'),
    (['python', '--', '/fixture/cloud_supervisor.py'], '/fixture/cloud_supervisor.py'),
    (['python', '-', '/fixture/budget_origin.json', '10', 'python', '/fixture/cloud_supervisor.py', 'launch'], None),
    (['python', '-c', 'pass', '/fixture/cloud_supervisor.py'], None),
    (['python', '-cpass', '/fixture/cloud_supervisor.py'], None),
    (['python', '-m', 'fixture.module', '/fixture/cloud_supervisor.py'], None),
    (['python', '-mfixture.module', '/fixture/cloud_supervisor.py'], None),
    (['bash', '-c', 'python /fixture/cloud_supervisor.py'], None),
    (['curl', '/fixture/cloud_supervisor.py'], None),
    (['python', '--version', '/fixture/cloud_supervisor.py'], None),
    (['python', '-h', '/fixture/cloud_supervisor.py'], None),
    (['python'], None),
    ([], None),
])
def test_only_executed_python_script_is_identified(argv, expected):
    assert supervisor.executed_python_script([a.encode() for a in argv]) == expected


class FakeProc:
    def __init__(self, pid, argv):
        self.name = str(pid)
        self.argv = argv

    def __truediv__(self, name):
        assert name == 'cmdline'
        return self

    def read_bytes(self):
        return b'\0'.join(x.encode() for x in self.argv) + b'\0'


def fake_proc_tree(monkeypatch, root, entries):
    class Tree:
        def iterdir(self):
            return iter(entries)
    monkeypatch.setattr(supervisor, 'CLOUD_BASE', root)
    monkeypatch.setattr(supervisor, 'Path', lambda p: Tree() if p == '/proc' else Path(p))


@pytest.mark.parametrize('name', ['cloud_supervisor.py', 'train_exploratory.py', 'infer_exploratory.py', 'prepare_data.py'])
def test_actual_script_same_work_root_blocks(monkeypatch, tmp_path, name):
    pid = os.getpid() + 100000
    script = str(tmp_path / 'code-fixture' / 'scripts' / name)
    fake_proc_tree(monkeypatch, tmp_path, [FakeProc(pid, ['python', '-u', script])])
    with pytest.raises(supervisor.LockBusy) as caught:
        supervisor.reject_other_local_processes()
    assert caught.value.owner_pid == pid
    assert caught.value.scope == 'existing_cloud_supervisor'


@pytest.mark.parametrize('shape', ['stdin', 'command', 'module', 'shell', 'own_pid', 'unrelated_root'])
def test_nonworker_mentions_are_ignored(monkeypatch, tmp_path, shape):
    script = str(tmp_path / 'code-fixture' / 'scripts' / 'cloud_supervisor.py')
    pid = os.getpid() + 100000
    argv = {
        'stdin': ['python', '-', str(tmp_path / 'budget_origin.json'), '10', 'python', script, 'launch'],
        'command': ['python', '-c', 'pass', script],
        'module': ['python', '-m', 'fixture.module', script],
        'shell': ['bash', '-c', 'python ' + script],
        'own_pid': ['python', script],
        'unrelated_root': ['python', str(tmp_path.parent / 'other-cloud-root' / 'cloud_supervisor.py')],
    }[shape]
    if shape == 'own_pid':
        pid = os.getpid()
    fake_proc_tree(monkeypatch, tmp_path, [FakeProc(pid, argv)])
    supervisor.reject_other_local_processes()


def test_script_operand_with_unrelated_executed_program_is_ignored(monkeypatch, tmp_path):
    mentioned = str(tmp_path / 'scripts' / 'cloud_supervisor.py')
    actual = str(tmp_path / 'scripts' / 'inert_fixture.py')
    fake_proc_tree(monkeypatch, tmp_path, [FakeProc(os.getpid() + 100000, ['python', actual, mentioned])])
    supervisor.reject_other_local_processes()


def test_work_root_prefix_sibling_is_not_same_work_root(monkeypatch, tmp_path):
    sibling = Path(str(tmp_path) + '-other') / 'scripts' / 'cloud_supervisor.py'
    fake_proc_tree(monkeypatch, tmp_path, [FakeProc(os.getpid() + 100000, ['python', str(sibling)])])
    supervisor.reject_other_local_processes()


def test_real_stdin_ancestor_with_launch_operand_is_not_a_worker(tmp_path):
    """Exact run_bounded argv shape; its spawned detector must ignore parent."""
    script = tmp_path / 'code-fixture' / 'scripts' / 'cloud_supervisor.py'
    child_code = (
        'import sys,json;sys.path.insert(0,sys.argv[1]);import cloud_supervisor as s;'
        'from pathlib import Path;s.CLOUD_BASE=Path(sys.argv[2]);'
        's.reject_other_local_processes();print(json.dumps({"fixture_detector_passed":True}))'
    )
    wrapper_code = (
        'import subprocess,sys\n'
        f'p=subprocess.run([sys.executable,"-c",{child_code!r},{str(SCRIPTS)!r},{str(tmp_path)!r}],capture_output=True,text=True)\n'
        'sys.stdout.write(p.stdout);sys.stderr.write(p.stderr);raise SystemExit(p.returncode)\n'
    )
    command = [sys.executable, '-', str(tmp_path / 'budget_origin.json'), '10',
               sys.executable, str(script), 'launch']
    result = subprocess.run(command, input=wrapper_code, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, 'Inert stdin ancestor was incorrectly treated as an existing worker'
    assert json.loads(result.stdout) == {'fixture_detector_passed': True}


@pytest.mark.parametrize('invocation', ['absolute', 'relative', 'python_options'])
def test_real_same_root_inert_worker_still_blocks(tmp_path, monkeypatch, invocation):
    """The fixture is only a ready marker plus stdin wait, never scientific code."""
    script = tmp_path / 'code-fixture' / 'scripts' / 'cloud_supervisor.py'
    script.parent.mkdir(parents=True)
    script.write_text('import sys\nprint("fixture_ready",flush=True)\nsys.stdin.readline()\n')
    argv = {
        'absolute': [sys.executable, '-u', str(script)],
        'relative': [sys.executable, '-u', script.name],
        'python_options': [sys.executable, '-W', 'ignore', '-X', 'dev', '-u', str(script)],
    }[invocation]
    worker = subprocess.Popen(argv, cwd=script.parent, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert worker.stdout.readline().strip() == 'fixture_ready'
        monkeypatch.setattr(supervisor, 'CLOUD_BASE', tmp_path)
        with pytest.raises(supervisor.LockBusy) as caught:
            supervisor.reject_other_local_processes()
        assert caught.value.owner_pid == worker.pid
    finally:
        # Close only this test-owned fixture. No real job or mutex is touched.
        worker.communicate(input='fixture_done\n', timeout=10)

