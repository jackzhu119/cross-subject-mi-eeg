"""Focused archive/schema guards; never execute a plan or archived command."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

SPEC = importlib.util.spec_from_file_location('plan_archive_guards', Path(__file__).with_name('audit_plan_run01.py'))
review = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(review)


def packed(tmp_path, name='MANIFEST.json', link=False, duplicate=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as out:
        info = tarfile.TarInfo(name); info.size = 2
        if link:
            info.type = tarfile.SYMTYPE; info.linkname = '/etc/other'
        out.addfile(info, None if link else io.BytesIO(b'{}'))
        if duplicate: out.addfile(info, io.BytesIO(b'{}'))
    raw = buffer.getvalue(); p = tmp_path/'fixture.tar.gz'; p.write_bytes(raw)
    return p, len(raw), hashlib.sha256(raw).hexdigest()


def test_bounded_archive_reader_never_extracts(tmp_path):
    p, count, sha = packed(tmp_path)
    assert review.read_archive(p,count,sha) == {'MANIFEST.json':b'{}'}
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize('name,link,duplicate', [('../escape',False,False),('/escape',False,False),
    ('MANIFEST.json',True,False),('MANIFEST.json',False,True)])
def test_unsafe_members_block(tmp_path,name,link,duplicate):
    p,count,sha=packed(tmp_path,name,link,duplicate)
    with pytest.raises(ValueError,match='unsafe_or_unbounded'):
        review.read_archive(p,count,sha)


@pytest.mark.parametrize('case', ['lowercase_manifest','wrong_payload_field'])
def test_actual_manifest_name_and_payload_schema_are_required_before_source_read(monkeypatch,case):
    files={n:b'{}' for n in review.PAYLOADS}
    if case=='lowercase_manifest': files['manifest.json']=b'{}'
    else: files['MANIFEST.json']=b'{"schema":"paper1-plan-only-evidence-v1","files":[]}'
    monkeypatch.setattr(review,'read_archive',lambda *args:files)
    monkeypatch.setattr(review,'git_bytes',lambda *args:pytest.fail('malformed archive must block before source read'))
    with pytest.raises(ValueError,match='actual_uppercase|actual_manifest_schema'):
        review.audit('synthetic','synthetic')


def test_outer_original_sha_is_mandatory(tmp_path):
    p,count,sha=packed(tmp_path)
    with pytest.raises(ValueError,match='archive_sha256'):
        review.read_archive(p,count,'0'*64)
