"""Real Linux mutex checks; no GPU, network, credentials, fits, or predictions."""
import fcntl
import importlib
import os
from pathlib import Path
import select
import stat
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
locks = importlib.import_module('cloud_locks')


def holder(root, resource, scope='launch'):
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from cloud_locks import local_lock
with local_lock(sys.argv[4], sys.argv[3], lock_root=sys.argv[2]):
    print('LOCK_HELD', flush=True)
    sys.stdin.readline()
"""
    process = subprocess.Popen([sys.executable, '-c', code, str(SCRIPTS), str(root), str(resource), scope],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        assert ready and process.stdout.readline().strip() == 'LOCK_HELD', 'Real lock holder failed to start'
    except BaseException:
        process.kill(); process.communicate(timeout=5)
        raise
    return process


def release(process):
    process.communicate('\n', timeout=5)
    assert process.returncode == 0


def test_real_other_process_contention_keeps_original_inode_and_owner(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'persistent' / 'job'
    process = holder(root, resource)
    try:
        path = locks.lock_path('launch', resource, root)
        original = path.stat().st_ino
        with pytest.raises(locks.LockBusy) as failure:
            with locks.local_lock('launch', resource, lock_root=root):
                pytest.fail('Second process acquired a live owner mutex')
        assert failure.value.code == 'local_process_lock_busy'
        assert failure.value.scope == 'launch'
        assert failure.value.owner_pid == process.pid
        assert path.stat().st_ino == original
    finally:
        release(process)
    with locks.local_lock('launch', resource, lock_root=root):
        assert path.stat().st_ino == original


def test_repeated_release_uses_same_inode_never_unlinks(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    with locks.local_lock('source', resource, lock_root=root):
        path = locks.lock_path('source', resource, root)
        first = path.stat().st_ino
    for _ in range(3):
        with locks.local_lock('source', resource, lock_root=root):
            assert path.stat().st_ino == first


def test_context_exception_releases_real_mutex(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    with pytest.raises(RuntimeError, match='fixture-failure'):
        with locks.local_lock('supervisor', resource, lock_root=root):
            raise RuntimeError('fixture-failure')
    process = holder(root, resource, 'supervisor')
    release(process)


def test_dead_holder_releases_mutex_without_deleting_lock_or_trusting_pid(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    process = holder(root, resource)
    path = locks.lock_path('launch', resource, root)
    inode = path.stat().st_ino
    process.kill(); process.communicate(timeout=5)
    with locks.local_lock('launch', resource, lock_root=root):
        assert path.stat().st_ino == inode


def test_canonical_resource_aliases_bind_same_live_mutex(tmp_path):
    root, original = tmp_path / 'locks', tmp_path / 'persistent'
    original.mkdir()
    alias = tmp_path / 'alias'; alias.symlink_to(original, target_is_directory=True)
    process = holder(root, original / 'job')
    try:
        assert locks.lock_path('launch', alias / 'job', root) == locks.lock_path('launch', original / 'job', root)
        with pytest.raises(locks.LockBusy):
            with locks.local_lock('launch', alias / 'job', lock_root=root):
                pytest.fail('Canonical alias bypassed the mutex')
    finally:
        release(process)


def test_scopes_and_distinct_resources_are_independent(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    process = holder(root, resource, 'supervisor')
    try:
        with locks.local_lock('source', resource, lock_root=root):
            with locks.local_lock('supervisor', tmp_path / 'different-job', lock_root=root):
                pass
    finally:
        release(process)


def test_flock_descriptor_is_local_even_when_resource_is_workspace(monkeypatch, tmp_path):
    observed = []
    actual = fcntl.flock
    def checked(fd, command):
        observed.append(Path(os.readlink('/proc/self/fd/' + str(fd))))
        return actual(fd, command)
    monkeypatch.setattr(locks.fcntl, 'flock', checked)
    with locks.local_lock('inference', '/workspace/arbitrary-persistent-job', lock_root=tmp_path / 'locks'):
        pass
    assert len(observed) == 2
    assert all(path.parent == tmp_path / 'locks' and '/workspace' not in str(path) for path in observed)


def test_workspace_lock_directory_is_rejected_before_creation():
    with pytest.raises(ValueError, match='local_not_workspace'):
        locks.lock_directory('/workspace/unsafe-test-lock-directory')


def test_symlink_root_or_ancestor_is_rejected_without_touching_destination(tmp_path):
    target = tmp_path / 'target'; target.mkdir(); target.chmod(0o755)
    alias = tmp_path / 'alias'; alias.symlink_to(target, target_is_directory=True)
    for path in (alias, alias / 'child'):
        with pytest.raises(ValueError, match='symlink'):
            locks.lock_directory(path)
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert not (target / 'child').exists()


def test_lockfile_symlink_is_rejected_without_touching_target(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    path = locks.lock_path('launch', resource, root)
    target = tmp_path / 'do-not-edit'; target.write_text('untouched')
    path.symlink_to(target)
    with pytest.raises(OSError):
        with locks.local_lock('launch', resource, lock_root=root):
            pytest.fail('Symlink lock accepted')
    assert target.read_text() == 'untouched'


def test_hardlinked_lockfile_rejected_without_truncation(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    path = locks.lock_path('launch', resource, root)
    path.write_text('do-not-truncate')
    other = tmp_path / 'hardlink'; os.link(path, other)
    with pytest.raises(ValueError, match='identity_invalid'):
        with locks.local_lock('launch', resource, lock_root=root):
            pytest.fail('Shared-inode file accepted')
    assert path.read_text() == other.read_text() == 'do-not-truncate'


def test_lockfiles_are_private_and_never_inherited_by_unrelated_subprocess(tmp_path):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    with locks.local_lock('launch', resource, lock_root=root):
        path = locks.lock_path('launch', resource, root)
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        process = subprocess.run([sys.executable, '-c', 'import os; print(len(os.listdir("/proc/self/fd")))'],
                                 capture_output=True, text=True, check=True)
        assert int(process.stdout.strip()) == 4  # Three standard descriptors and transient directory handle.


def test_directory_owner_mismatch_is_rejected_without_repermissioning(tmp_path, monkeypatch):
    root = tmp_path / 'foreign'; root.mkdir(); root.chmod(0o755)
    actual_owner = root.stat().st_uid
    # Leave real filesystem metadata untouched; simulate a different caller UID.
    monkeypatch.setattr(locks.os, 'getuid', lambda: actual_owner + 1)
    with pytest.raises(ValueError, match='owner_invalid'):
        locks.lock_directory(root)
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_lockfile_owner_mismatch_is_rejected_without_truncation(tmp_path, monkeypatch):
    root, resource = tmp_path / 'locks', tmp_path / 'job'
    path = locks.lock_path('launch', resource, root)
    path.write_text('untouched'); actual_owner = path.stat().st_uid
    # The first UID lookup accepts the already checked directory; the second
    # isolates the file-owner guard using real inode metadata.
    uids = iter((actual_owner, actual_owner + 1))
    monkeypatch.setattr(locks.os, 'getuid', lambda: next(uids))
    with pytest.raises(ValueError, match='identity_invalid'):
        with locks.local_lock('launch', resource, lock_root=root):
            pytest.fail('Foreign lockfile accepted')
    assert path.read_text() == 'untouched'


@pytest.mark.parametrize('scope', ['', '../launch', 'LAUNCH', 'a' * 41])
def test_invalid_scope_fails_before_file_creation(tmp_path, scope):
    root = tmp_path / 'locks'
    with pytest.raises(ValueError, match='scope_invalid'):
        with locks.local_lock(scope, tmp_path / 'job', lock_root=root):
            pytest.fail('Invalid lock scope accepted')
    assert not root.exists()
