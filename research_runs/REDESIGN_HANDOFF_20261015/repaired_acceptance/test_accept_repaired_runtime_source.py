"""Synthetic closed-gate tests only; no real runtime imports, EEG or diagnostics."""
import argparse
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

PATH = Path(__file__).with_name('accept_repaired_runtime_source.py')
spec = importlib.util.spec_from_file_location('repair_accept_test_module', PATH)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_no_prohibited_execution_entrypoints():
    tree = ast.parse(PATH.read_text())
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {'Popen', 'urlopen', 'download_wheels', 'prepare', 'execute', 'build_model', 'is_available', 'set_num_threads'}
    assert 'acceptance.run(formal_args)' in PATH.read_text()
    assert 'wrapper.exact_imports(binding_view)' in PATH.read_text()
    assert 'wrapper.run(' not in PATH.read_text()
    assert 'runtime_preparation.json' in PATH.read_text()


def test_in_memory_import_view_does_not_impersonate_receipt():
    receipt = {'environment': '/synthetic/child'}
    donor = {'components': [{'name': 'torch', 'path': '/synthetic/donor/torch'}]}
    assert m.import_binding_view_from_repair(receipt, donor) == {
        'environment': '/synthetic/child', 'linked_gpu_components': {'torch': '/synthetic/donor/torch'},
        'requirements_sha256': m.REQ_SHA}
    assert receipt == {'environment': '/synthetic/child'}


@pytest.mark.parametrize('wall,remaining,allowed', [(300,310,True),(300,309,False),(120,600,False)])
def test_external_watchdog_matches_reviewed_CPU_wall(monkeypatch,wall,remaining,allowed):
    from datetime import datetime,timezone,timedelta
    current=datetime(2026,10,15,6,0,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current
    monkeypatch.setattr(m,'datetime',Clock)
    gate=argparse.Namespace(max_wall_seconds=wall,end=current+timedelta(seconds=remaining))
    if allowed:m.require_bounded_cpu_window(gate)
    else:
        with pytest.raises(ValueError):m.require_bounded_cpu_window(gate)


@pytest.mark.parametrize('raw', ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_duplicate_or_nonfinite_json_closed(raw):
    with pytest.raises(ValueError): m.parse(raw)


def test_regular_bytes_exact(tmp_path):
    p = tmp_path / 'evidence'; p.write_bytes(b'fixture')
    assert m.regular_bytes(p, 7, size=7, expected=hashlib.sha256(b'fixture').hexdigest()) == b'fixture'


@pytest.mark.parametrize('size,expected,maximum', [(8, None, 8), (None, '0'*64, 8), (None,None,6)])
def test_regular_bytes_changed(tmp_path, size, expected, maximum):
    p = tmp_path / 'evidence'; p.write_bytes(b'fixture')
    with pytest.raises(ValueError): m.regular_bytes(p, maximum, size=size, expected=expected)


def test_parent_symlink_rejected(tmp_path):
    (tmp_path / 'real').mkdir(); (tmp_path / 'link').symlink_to(tmp_path / 'real', target_is_directory=True)
    with pytest.raises(ValueError): m.no_symlink(tmp_path / 'link' / 'x')


def test_original_preparation_receipt_cannot_be_forged(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ENVIRONMENT', tmp_path)
    m.original_preparation_absent()
    (tmp_path / 'runtime_preparation.json').write_text('{}')
    with pytest.raises(ValueError): m.original_preparation_absent()


def test_original_preparation_dangling_symlink_also_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ENVIRONMENT', tmp_path)
    (tmp_path / 'runtime_preparation.json').symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError): m.original_preparation_absent()


def test_source_unrestored_closed_before_mat_read(tmp_path, monkeypatch):
    # A frozen-looking inventory with missing files must fail without imports.
    code = tmp_path / 'code'; data = tmp_path / 'data'
    p = code / m.MANIFEST_REL; p.parent.mkdir(parents=True)
    rows = [{'filename': f'A{i:02d}{s}.mat', 'bytes': 779873902 if (i,s)==(1,'T') else 1,
             'sha256': '0'*64} for i in range(1,10) for s in ('T','E')]
    payload = json.dumps({'files':rows}).encode(); p.write_bytes(payload)
    monkeypatch.setattr(m, 'MANIFEST_SHA', hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match='source_originals_not_restored'):
        m.verify_source_files(data, code)


def test_frozen_source_inventory_cannot_change(tmp_path, monkeypatch):
    p = tmp_path / m.MANIFEST_REL; p.parent.mkdir(parents=True)
    payload = b'{"files":[]}' ; p.write_bytes(payload)
    monkeypatch.setattr(m, 'MANIFEST_SHA', hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match='frozen_source_inventory_changed'):
        m.verify_source_files(tmp_path / 'raw', tmp_path)


def test_output_and_single_claim_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ENVIRONMENT', tmp_path / 'env')
    args = argparse.Namespace(output_dir=tmp_path/'accept', log_file=tmp_path/'accept.log',
        code_dir=tmp_path/'code', data_dir=tmp_path/'data',repair_archive=tmp_path/'repair.tgz',
        diagnostic_package=tmp_path/'full.tgz',formal_acceptance_package=tmp_path/'formal.tgz',
        review_record=tmp_path/'review.json',priority_receipt=tmp_path/'slot.json',source_restore_receipt=tmp_path/'source.json')
    claim = m.fresh_output(args)
    assert claim == tmp_path / 'accept.attempt.json'
    claim.write_text('{}')
    with pytest.raises(ValueError, match='already_consumed'):m.fresh_output(args)


def test_existing_output_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ENVIRONMENT', tmp_path/'env')
    out = tmp_path/'out'; out.mkdir()
    with pytest.raises(ValueError, match='brand_new'):m.fresh_output(argparse.Namespace(output_dir=out))


def test_allocated_does_not_count_donor_symlink_target(tmp_path):
    root=tmp_path/'child';root.mkdir(); donor=tmp_path/'donor';donor.write_bytes(b'x'*8192)
    before=m.allocated(root); (root/'torch').symlink_to(donor)
    assert m.allocated(root)==before


def test_resource_gate_preserves_baseline_and_source_budget(tmp_path, monkeypatch):
    env=tmp_path/'env';env.mkdir();monkeypatch.setattr(m,'ENVIRONMENT',env)
    class Gate:
        max_new_bytes=3*m.GIB;min_free_bytes=10*m.GIB;reserve_bytes=5*m.GIB
        def check(self):pass
    args=argparse.Namespace(data_dir=tmp_path/'data',output_dir=tmp_path/'out',log_file=tmp_path/'log',
        repair_archive=tmp_path/'repair',diagnostic_package=tmp_path/'full',formal_acceptance_package=tmp_path/'formal',source_restore_receipt=tmp_path/'source.json')
    monkeypatch.setattr(m.shutil,'disk_usage',lambda _:argparse.Namespace(free=20*m.GIB))
    report=m.resources(Gate(),args,tmp_path/'claim')
    assert report['observed_total_owned_bytes']==m.BASE_OWNED
    assert report['budget_reset'] is False


@pytest.mark.parametrize('free,cap',[(14*m.GIB,3*m.GIB),(20*m.GIB,1)])
def test_resource_floor_or_original_cap_fail_closed(tmp_path, monkeypatch,free,cap):
    env=tmp_path/'env';env.mkdir();monkeypatch.setattr(m,'ENVIRONMENT',env)
    class Gate:
        max_new_bytes=cap;min_free_bytes=10*m.GIB;reserve_bytes=5*m.GIB
        def check(self):pass
    args=argparse.Namespace(data_dir=tmp_path/'data',output_dir=tmp_path/'out',log_file=tmp_path/'log',
        repair_archive=tmp_path/'repair',diagnostic_package=tmp_path/'full',formal_acceptance_package=tmp_path/'formal',source_restore_receipt=tmp_path/'source.json')
    monkeypatch.setattr(m.shutil,'disk_usage',lambda _:argparse.Namespace(free=free))
    with pytest.raises(ValueError):m.resources(Gate(),args,tmp_path/'claim')


def make_archive(names):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as t:
        for name,kind,body in names:
            info=tarfile.TarInfo(name);info.size=len(body);info.type=kind
            t.addfile(info,io.BytesIO(body) if kind==tarfile.REGTYPE else None)
    return output.getvalue()


@pytest.mark.parametrize('name,kind', [('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),
    ('x/../y',tarfile.REGTYPE),('x\\y',tarfile.REGTYPE),('symlink',tarfile.SYMTYPE)])
def test_archive_unsafe_member_closed(name,kind):
    with pytest.raises(ValueError):m.archive_members(make_archive([(name,kind,b'')]))


def test_archive_duplicate_members_closed():
    with pytest.raises(ValueError):m.archive_members(make_archive([('same',tarfile.REGTYPE,b''),('same',tarfile.REGTYPE,b'')]))


def test_run_invalid_revision_before_package_operations():
    with pytest.raises(ValueError, match='immutable_adapter_revision'):
        m.run(argparse.Namespace(acceptance_revision='main'))


def source_receipt(tmp_path):
    data = tmp_path / 'source'; data.mkdir()
    rows = [{'filename': f'A{i:02d}{s}.mat', 'bytes': 10, 'sha256': 'a'*64}
            for i in range(1,10) for s in ('T','E')]
    value = {'status': 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
        'source_expected_files': 18, 'source_expected_bytes': 779873919,
        'official_manifest_sha256': m.MANIFEST_SHA, 'source_root': str(data),
        'diagnostic_rerun': False, 'runtime_imported': False, 'target_EEG_accessed': False,
        'training_authorization': False, 'budget_reset': False, 'new_fits': 0,
        'files': [dict(row,status='RESTORED_OFFICIAL_EXACT_BYTES') for row in rows],
        'finished_at_utc': '2026-10-15T05:00:00+00:00'}
    path = data/'source_restore_run01.json';path.write_text(json.dumps(value))
    gate = argparse.Namespace(review={'reviewed_at_utc': '2026-10-15T05:01:00+00:00',
        'source_restore_receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return path,data,rows,value,gate


def test_source_restore_receipt_explicit_new_identity(tmp_path):
    path,data,rows,value,gate=source_receipt(tmp_path)
    assert m.source_restore_binding(path,data,rows,gate)==hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('field,value', [('status','old-container-cache'),('source_expected_files',17),
    ('official_manifest_sha256','0'*64),('diagnostic_rerun',True),('runtime_imported',True),
    ('target_EEG_accessed',True),('training_authorization',True),('budget_reset',True),('new_fits',1)])
def test_source_restore_pending_or_scope_changes_blocked(tmp_path,field,value):
    path,data,rows,receipt,gate=source_receipt(tmp_path);receipt[field]=value;path.write_text(json.dumps(receipt))
    gate.review['source_restore_receipt_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):m.source_restore_binding(path,data,rows,gate)


def test_acceptance_review_must_follow_actual_source_restore(tmp_path):
    path,data,rows,receipt,gate=source_receipt(tmp_path)
    gate.review['reviewed_at_utc']='2026-10-15T04:59:00+00:00'
    with pytest.raises(ValueError,match='follow_source_restore'):m.source_restore_binding(path,data,rows,gate)


def test_source_restore_receipt_trial_file_mapping_must_match(tmp_path):
    path,data,rows,receipt,gate=source_receipt(tmp_path)
    receipt['files'][0]['sha256']='b'*64;path.write_text(json.dumps(receipt))
    gate.review['source_restore_receipt_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='strict_source_bytes'):m.source_restore_binding(path,data,rows,gate)


def test_actual_source_restore_receipt_must_be_reviewed_bytes(tmp_path):
    path,data,rows,receipt,gate=source_receipt(tmp_path)
    gate.review['source_restore_receipt_sha256']='0'*64
    with pytest.raises(ValueError,match='not_bound_to_parent_review'):
        m.source_restore_binding(path,data,rows,gate)
