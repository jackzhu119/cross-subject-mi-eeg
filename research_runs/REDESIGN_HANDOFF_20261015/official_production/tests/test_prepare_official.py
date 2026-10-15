"""Only metadata, temporary synthetic JSON and AST checks; no scientific run."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1] / 'prepare_official.py'
SPEC = importlib.util.spec_from_file_location('paper1_official_prepare_test', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def write(path, data):
    raw = (json.dumps(data) + '\n').encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_default_plan_checks_static_suffix_without_science_imports(capsys, monkeypatch):
    def forbidden(*_):
        pytest.fail('Plan must not load any execution module or data receipt')
    monkeypatch.setattr(M, 'fixed_module', forbidden)
    monkeypatch.setattr(M, 'route', forbidden)
    monkeypatch.setattr(M, 'execute', forbidden)
    monkeypatch.setattr(M, 'SCIENCE_ROOT', M.REPO)
    assert M.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['scientific_suffix_AST_identical'] is True
    assert report['training_authorization'] is False


def test_original_scientific_suffix_is_exact_and_r2_prefix_absent():
    original = (M.REPO / M.ORIGINAL_PREPARE).read_text()
    new = PATH.read_text()
    assert hashlib.sha256(original.encode()).hexdigest() == M.ORIGINAL_PREPARE_SHA
    assert M.suffix_statements(original, 'prepare') == M.suffix_statements(new, '_frozen_prepare_suffix')
    assert M.suffix_statements(original.replace("if len(records)!=18", "if len(records)!=17"), 'prepare') != M.suffix_statements(new, '_frozen_prepare_suffix')
    fn = next(n for n in ast.parse(new).body if isinstance(n, ast.FunctionDef) and n.name == '_frozen_prepare_suffix')
    text = ast.unparse(fn)
    assert 'r2_only' not in text and 'import_from_environment' not in text and 'r2_import_receipt' not in text
    assert 'load_source19' in text and 'source_array_hashes' not in text  # strict array_hashes loop remains original.
    assert "'array_hashes'" in text and 'native_context_hash_changed' in text
    assert 'frozen_target_input_changed' in text and 'complete_roster_required' in text


def test_json_bounds_fifo_symlink_duplicate_and_nonfinite_rejected(tmp_path):
    path = tmp_path / 'record.json'
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match='duplicate'):
        M.metadata(path)
    path.write_text('{"a":NaN}')
    with pytest.raises(ValueError, match='nonfinite'):
        M.metadata(path)
    path.write_bytes(b'x' * (M.MAX_JSON + 1))
    with pytest.raises(ValueError, match='bounded_regular'):
        M.metadata(path)
    link = tmp_path / 'link.json'
    link.symlink_to(path)
    with pytest.raises(ValueError, match='symlink'):
        M.metadata(link)
    fifo = tmp_path / 'fifo.json'
    M.os.mkfifo(fifo)
    with pytest.raises(ValueError, match='bounded_regular'):
        M.metadata(fifo)


def test_attempt_claim_is_exclusive_and_not_original_job(tmp_path):
    path = tmp_path / M.CLAIM
    M.claim(path, {'training_authorization': False, 'new_fits': 0})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        M.claim(path, {'replacement': True})
    assert path.read_bytes() == before
    assert M.OUTPUT_ROOT != M.SCIENCE_ROOT and M.OLD_JOB not in M.OUTPUT_ROOT.parts


def test_target_byte_receipt_alone_cannot_pass_actual_outer_exit(tmp_path):
    summary_path = tmp_path / 'summary.json'
    outer_path = tmp_path / 'outer.json'
    receipt_sha = 'a' * 64
    summary = {'status': 'TARGET174_OFFICIAL_BYTES_RESTORED_SCIENTIFIC_GATES_PENDING',
        'old_task': M.OLD_JOB, 'files_verified': 174, 'verified_bytes': 2515343396,
        'target_bytes_receipt_sha256': receipt_sha, 'script_sha256': M.TARGET_GATE_SHA,
        'training_authorization': False, 'new_source_fits': 0, 'target_fits': 0,
        'target_predictions': 0, 'target_scientific_processing': False}
    summary_sha = write(summary_path, summary)
    outer = {'schema_version': 1, 'status': 'OBSERVED_TARGET_RAW_RESTORE_PROCESS_EXIT',
        'exit_code': 0, 'target_restore_summary_sha256': summary_sha,
        'script_sha256': M.TARGET_GATE_SHA, 'training_authorization': False}
    args = SimpleNamespace(target_restore_summary=summary_path, target_restore_summary_sha256=summary_sha,
        target_restore_outer=outer_path, target_restore_outer_sha256=write(outer_path, outer))
    result = M.target_exit(args, {'receipt_sha256': {'target_bytes': receipt_sha}})
    assert result == (summary_sha, args.target_restore_outer_sha256)
    outer['exit_code'] = 3
    args.target_restore_outer_sha256 = write(outer_path, outer)
    with pytest.raises(ValueError, match='actual_target_outer_exit_zero'):
        M.target_exit(args, {'receipt_sha256': {'target_bytes': receipt_sha}})
    outer['exit_code'] = False
    args.target_restore_outer_sha256 = write(outer_path, outer)
    with pytest.raises(ValueError, match='actual_target_outer_exit_zero'):
        M.target_exit(args, {'receipt_sha256': {'target_bytes': receipt_sha}})


def test_execution_rejects_wrong_runtime_before_reading_eeg_or_claim(monkeypatch):
    monkeypatch.setattr(M.sys, 'prefix', '/synthetic/wrong-runtime')
    monkeypatch.setattr(M, 'route', lambda *_: pytest.fail('No routing/science should be read yet'))
    with pytest.raises(ValueError, match='existing_repaired_cp312_runtime_required'):
        M.execute(SimpleNamespace())


def test_v1_effective_cgroup_fallback_without_host_substitution(tmp_path, monkeypatch):
    for relative, value in {'cpu,cpuacct/cpu.cfs_quota_us': '1020000', 'cpu,cpuacct/cpu.cfs_period_us': '100000',
                            'memory/memory.limit_in_bytes': '61999996928'}.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    original = M.Path
    monkeypatch.setattr(M, 'Path', lambda value: tmp_path if value == '/sys/fs/cgroup' else original(value))
    result = M.current_cgroup()
    assert result['cpu.max'] is None
    assert result['cpu,cpuacct/cpu.cfs_quota_us'] == '1020000'
    assert result['cpu,cpuacct/cpu.cfs_period_us'] == '100000'
    assert result['memory/memory.limit_in_bytes'] == '61999996928'
    assert not any('host' in key or 'cpu_count' in key for key in result)


def test_atomic_output_guard_is_synchronous_and_timer_never_enumerates(tmp_path):
    events = []
    def guard(reservation):
        assert reservation >= 0
        M.owned_bytes(tmp_path)
        events.append('guard')
    def atomic_write(path, obj):
        events.append('write')
        temporary = path.with_name(path.name + '.tmp-synthetic')
        temporary.write_text(json.dumps(obj))
        temporary.replace(path)
        return 'unchanged-return'
    module = SimpleNamespace(write=atomic_write)
    write_guarded, _, _ = M.guarded_io(module, guard)
    assert write_guarded(tmp_path / 'synthetic.json', {'not_EEG': True}) == 'unchanged-return'
    assert events == ['guard', 'write', 'guard']
    assert not (tmp_path / 'synthetic.json.tmp-synthetic').exists()
    tree = ast.parse(PATH.read_text())
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    timer = next(n for n in execute.body if isinstance(n, ast.FunctionDef) and n.name == 'time_guard')
    assert 'owned_bytes' not in ast.unparse(timer) and 'rglob' not in ast.unparse(timer) and 'scandir' not in ast.unparse(timer)

