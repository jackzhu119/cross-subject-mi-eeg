"""Small archive safety fixtures only; no archived command is executed."""
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

SPEC = importlib.util.spec_from_file_location('cp312_metadata_bundle_auditor',
    Path(__file__).with_name('audit_metadata_bundle.py'))
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def archive(extra=None, omit=None):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name in sorted(audit.PAYLOADS | {'manifest.json'}):
            if name == omit:
                continue
            info = tarfile.TarInfo(name); info.size = 2
            tar.addfile(info, io.BytesIO(b'{}'))
        if extra:
            info, raw = extra
            tar.addfile(info, None if not info.isfile() else io.BytesIO(raw))
    return out.getvalue()


def test_only_exact_expected_member_inventory_is_read_without_extraction():
    assert set(audit.read_members(archive())) == audit.PAYLOADS | {'manifest.json'}


@pytest.mark.parametrize('name', ['../escape', '/escape', 'unexpected.sh', 'metadata/./worker.log', 'metadata/worker.log'])
def test_path_escape_unexpected_and_duplicate_members_block(name):
    info = tarfile.TarInfo(name); info.size = 0
    with pytest.raises(ValueError, match='unsafe_duplicate_or_unexpected'):
        audit.read_members(archive((info, b'')))


def test_symlink_payload_blocks():
    info = tarfile.TarInfo('metadata/worker.log'); info.type = tarfile.SYMTYPE; info.linkname = '/tmp/elsewhere'
    with pytest.raises(ValueError, match='unsafe_duplicate_or_unexpected'):
        audit.read_members(archive((info, b''), omit='metadata/worker.log'))


def test_expanded_member_cap_blocks():
    info = tarfile.TarInfo('metadata/worker.log'); info.size = 128 * 1024 + 1
    with pytest.raises(ValueError, match='expansion_limit'):
        audit.read_members(archive((info, b'x' * info.size), omit='metadata/worker.log'))


def test_missing_payload_blocks():
    with pytest.raises(ValueError, match='inventory_mismatch'):
        audit.read_members(archive(omit='metadata/worker.log'))


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]'])
def test_ambiguous_json_blocks(raw):
    with pytest.raises(ValueError):
        audit.parsed(raw)


def test_outer_original_byte_length_and_sha_cannot_be_replaced(tmp_path):
    p = tmp_path / 'counterfeit.tar.gz'; p.write_bytes(b'x' * audit.ARCHIVE_BYTES)
    with pytest.raises(ValueError, match='archive_sha_mismatch'):
        audit.audit(p)
    p.write_bytes(b'')
    with pytest.raises(ValueError, match='bounded_metadata_archive_required'):
        audit.audit(p)


def test_symlink_archive_blocks_even_with_original_claimed_size(tmp_path):
    real = tmp_path / 'payload'; real.write_bytes(b'x' * audit.ARCHIVE_BYTES)
    link = tmp_path / 'link'; link.symlink_to(real)
    with pytest.raises(ValueError, match='bounded_metadata_archive_required'):
        audit.audit(link)
