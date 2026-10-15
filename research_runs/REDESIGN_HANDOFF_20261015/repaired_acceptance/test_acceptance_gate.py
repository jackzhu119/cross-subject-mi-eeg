from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('repaired_source_gate_test', HERE/'acceptance_gate.py')
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
NOW = datetime(2026,10,15,5,10,tzinfo=timezone.utc)


@pytest.fixture
def records():
    review = dict(schema_version=1, status='DOT_PARENT_REPAIRED_SOURCE_OPERATION_APPROVED',
        issuer='dot_parent', operation='source_cpu_acceptance', base_revision=g.BASE_REVISION,
        delivery_revision='a'*40, operation_script_sha256='b'*64, gate_sha256=g.digest(g.__file__),
        repair_archive_sha256=g.REPAIR_ARCHIVE_SHA, repair_receipt_sha256=g.REPAIR_RECEIPT_SHA,
        cpu_recovery_grant_sha256=g.GRANT_SHA, cpu_recovery_window_start_utc='2026-10-15T05:07:25Z',
        cpu_recovery_window_end_utc='2026-10-17T05:07:25Z',
        source_restore_receipt_sha256='f'*64,
        reviewed_at_utc='2026-10-15T05:08:00Z', expires_at_utc='2026-10-15T05:28:00Z',
        maximum_wall_seconds=300, review_notes='Synthetic actual-review test only')
    review.update({k:True for k in g.TRUE_REVIEW}); review.update({k:False for k in g.FALSE_REVIEW})
    slot = dict(schema_version=1,status='DOT_OPERATION_SLOT_GRANTED',issuer='dot',
        pod_id='52ivinpjwv947i',container_id='a7d3f0e408a4',operation='source_cpu_acceptance',
        issued_at_utc='2026-10-15T05:08:30Z',not_before_utc='2026-10-15T05:08:30Z',
        expires_at_utc='2026-10-15T05:23:00Z',max_new_bytes=3*g.GIB,min_free_bytes=10*g.GIB,
        paper2_reserve_bytes=5*g.GIB,slot_rationale='Synthetic idle/noninterference check')
    slot.update({k:True for k in g.TRUE_SLOT}); slot.update({k:False for k in g.FALSE_SLOT})
    return review,slot


def validate(records):
    return g.validate(*records,'source_cpu_acceptance','a'*40,'b'*64,g.digest(g.__file__),NOW)


def test_valid_new_review_slot(records):
    assert validate(records)[0] == 300


@pytest.mark.parametrize('key',g.TRUE_REVIEW+g.FALSE_REVIEW)
def test_every_review_condition_enforced(records,key):
    records[0][key]=not records[0][key]
    with pytest.raises(ValueError): validate(records)


@pytest.mark.parametrize('key',g.TRUE_SLOT+g.FALSE_SLOT)
def test_every_slot_condition_enforced(records,key):
    records[1][key]=not records[1][key]
    with pytest.raises(ValueError): validate(records)


@pytest.mark.parametrize('key',['status','issuer','operation','base_revision','delivery_revision',
    'operation_script_sha256','gate_sha256','repair_archive_sha256','repair_receipt_sha256'])
def test_fixed_review_bindings(records,key):
    records[0][key]='other'
    with pytest.raises(ValueError):validate(records)


@pytest.mark.parametrize('which,key,value',[
    (0,'schema_version',True),(0,'maximum_wall_seconds',301),(0,'maximum_wall_seconds',True),
    (0,'reviewed_at_utc','2026-10-15T04:26:22Z'),(0,'reviewed_at_utc','2026-10-15T05:02:00Z'),
    (0,'expires_at_utc','2026-10-17T05:07:26Z'),(0,'review_notes',''),
    (0,'cpu_recovery_grant_sha256','PLAN_ONLY'),
    (0,'cpu_recovery_window_start_utc','2026-10-15T05:00:01Z'),
    (0,'cpu_recovery_window_end_utc','2026-10-15T05:30:01Z'),
    (0,'cpu_recovery_window_end_utc','2026-10-15T05:19:59Z'),
    (0,'source_restore_receipt_sha256',None),
    (1,'status','PLAN_ONLY_NOT_A_DOT_GRANT'),(1,'schema_version',True),
    (1,'pod_id','old'),(1,'container_id','b5646c12356b'),(1,'operation','runtime_preparation'),
    (1,'issued_at_utc','2026-10-15T04:59:00Z'),(1,'expires_at_utc','2026-10-15T05:01:00Z'),
    (1,'expires_at_utc','2026-10-15T05:29:00Z'),(1,'max_new_bytes',3*g.GIB+1),
    (1,'max_new_bytes',0),(1,'min_free_bytes',10*g.GIB-1),(1,'paper2_reserve_bytes',5*g.GIB-1),
    (1,'paper2_reserve_bytes',True),(1,'slot_rationale',''),
    (1,'issued_at_utc','2026-10-15T05:08:30'),(1,'not_before_utc','2026-10-15T05:12:00Z')])
def test_bounds_no_old_slot_or_budget_reset(records,which,key,value):
    records[which][key]=value
    with pytest.raises(ValueError):validate(records)


def test_restore_is_separate_operation_and_wall_cap(records):
    review,slot=records
    review['operation']=slot['operation']='source_raw_restore'
    review['source_restore_receipt_sha256']=None
    review['maximum_wall_seconds']=1200
    assert g.validate(review,slot,'source_raw_restore','a'*40,'b'*64,g.digest(g.__file__),NOW)[0]==1200
    with pytest.raises(ValueError):validate(records)


@pytest.mark.parametrize('which',[0,1])
def test_unknown_review_or_slot_fields_fail(records,which):
    records[which]['silently_extend_budget']=True
    with pytest.raises(ValueError):validate(records)


def test_duplicate_nonfinite_and_symlink_records_rejected(tmp_path):
    p=tmp_path/'record.json'
    for raw in ['{"a":1,"a":2}','{"a":NaN}']:
        p.write_text(raw)
        with pytest.raises(ValueError):g.read_record(p)
    link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(ValueError):g.read_record(link)


def test_gate_replacement_revocation_and_wall(records,tmp_path,monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return NOW
    monkeypatch.setattr(g,'datetime',Clock)
    p,q=tmp_path/'review',tmp_path/'slot'
    p.write_text(json.dumps(records[0]));q.write_text(json.dumps(records[1]))
    gate=g.Gate(p,q,'source_cpu_acceptance','a'*40,'b'*64)
    gate.check()
    replacement=tmp_path/'replacement';replacement.write_bytes(q.read_bytes());replacement.replace(q)
    with pytest.raises(ValueError,match='replaced'):gate.check()
    # Even identical bytes at a different inode are not an unchanged grant.
    gate=g.Gate(p,q,'source_cpu_acceptance','a'*40,'b'*64)
    gate.started-=301
    with pytest.raises(TimeoutError):gate.check()
    q.unlink()
    with pytest.raises(FileNotFoundError):gate.check()


def test_pinned_exact_author_reply_and48hour_record():
    value=json.loads(g.GRANT_PATH.read_text())
    assert g.digest(g.GRANT_PATH)==g.GRANT_SHA
    assert value['author_reply_verbatim']=='我批准48小时，别再问了'
    assert value['author_message_sent_at_utc'] is None
    assert value['do_not_repeat_this_time_authorization_question'] is True
    assert (g.DEADLINE-g.GRANT_START).total_seconds()==172800
    assert value['continuous48paid_hours_financially_verified'] is False


def test_valid_cpu_slot_can_follow_original_fit_deadline(records):
    review,slot=records
    review.update(reviewed_at_utc='2026-10-16T10:00:00Z',expires_at_utc='2026-10-16T10:20:00Z')
    slot.update(issued_at_utc='2026-10-16T10:00:30Z',not_before_utc='2026-10-16T10:00:30Z',
        expires_at_utc='2026-10-16T10:15:00Z')
    now=datetime(2026,10,16,10,1,tzinfo=timezone.utc)
    assert now>g.HISTORICAL_FIT_DEADLINE
    assert g.validate(review,slot,'source_cpu_acceptance','a'*40,'b'*64,g.digest(g.__file__),now)[0]==300


@pytest.mark.parametrize('field,value', [('cpu_recovery_grant_sha256','f'*64),
    ('cpu_recovery_window_start_utc','2026-10-15T05:07:26Z'),
    ('cpu_recovery_window_end_utc','2026-10-17T05:07:26Z')])
def test_new_reply_does_not_allow_unrelated_grant_or_window_reset(records,field,value):
    records[0][field]=value
    with pytest.raises(ValueError):validate(records)


def test_missing_or_modified_author_record_cannot_grant_operation(records,tmp_path,monkeypatch):
    path=tmp_path/'author.json';monkeypatch.setattr(g,'GRANT_PATH',path)
    with pytest.raises(FileNotFoundError):g.Gate(tmp_path/'review',tmp_path/'slot','source_cpu_acceptance','a'*40,'b'*64)
    path.write_text('{}')
    with pytest.raises(ValueError,match='author48hour_record'):g.Gate(tmp_path/'review',tmp_path/'slot','source_cpu_acceptance','a'*40,'b'*64)


def test_author_record_rechecked_during_active_operation(records,tmp_path,monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return NOW
    monkeypatch.setattr(g,'datetime',Clock)
    author=tmp_path/'author.json';author.write_bytes(g.GRANT_PATH.read_bytes())
    monkeypatch.setattr(g,'GRANT_PATH',author)
    p,q=tmp_path/'review',tmp_path/'slot'
    p.write_text(json.dumps(records[0]));q.write_text(json.dumps(records[1]))
    gate=g.Gate(p,q,'source_cpu_acceptance','a'*40,'b'*64);gate.check()
    author.write_text('{}')
    with pytest.raises(ValueError,match='operation_gate_source_changed'):gate.check()
