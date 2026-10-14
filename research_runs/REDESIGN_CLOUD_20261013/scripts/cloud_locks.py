"""Real process mutexes on the container-local filesystem, never EEG volumes.

Persistent files store scientific state; flock is used only under /tmp. Locks
coordinate processes in this OS/container, not separate Pods on a shared volume.
A lock conflict is not a stale-file test and is never repaired by unlinking it.
"""
from pathlib import Path
from contextlib import contextmanager
import fcntl,hashlib,json,os,re,stat

class LockBusy(RuntimeError):
    code='local_process_lock_busy'
    def __init__(self,scope,owner_pid=None):
        self.scope=scope;self.owner_pid=owner_pid
        super().__init__('local_process_lock_busy:'+scope)

def lock_directory(lock_root=None):
    root=Path(lock_root) if lock_root is not None else Path('/tmp')/('mi-eeg-cloud-locks-'+str(os.getuid()))
    root=root.absolute()
    if root==Path('/workspace') or Path('/workspace') in root.parents:raise ValueError('locks_must_use_local_not_workspace_filesystem')
    for p in [root,*root.parents]:
        if p.is_symlink():raise ValueError('lock_directory_symlink_forbidden')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    st=root.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid():raise ValueError('lock_directory_owner_invalid')
    os.chmod(root,0o700)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('local_lock_directory_permissions_unsupported')
    return root

def lock_path(scope,resource,lock_root=None):
    if not isinstance(scope,str) or not re.fullmatch('[a-z0-9_-]{1,40}',scope):raise ValueError('lock_scope_invalid')
    key=hashlib.sha256((scope+'\0'+str(Path(resource).resolve())).encode()).hexdigest()
    return lock_directory(lock_root)/(scope+'-'+key+'.lock')

@contextmanager
def local_lock(scope,resource,*,lock_root=None):
    path=lock_path(scope,resource,lock_root)
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    acquired=False
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1:raise ValueError('local_lock_file_identity_invalid')
        os.fchmod(fd,0o600)
        if stat.S_IMODE(os.fstat(fd).st_mode)!=0o600:raise ValueError('local_lock_file_permissions_invalid')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            owner=None
            try:
                os.lseek(fd,0,os.SEEK_SET);value=json.loads(os.read(fd,512));p=value.get('pid')
                if type(p) is int and p>0:owner=p
            except (ValueError,OSError,AttributeError):pass
            raise LockBusy(scope,owner) from None
        acquired=True
        os.ftruncate(fd,0);os.write(fd,json.dumps({'pid':os.getpid(),'scope':scope}).encode());os.fsync(fd)
        yield {'scope':scope,'pid':os.getpid(),'path':str(path)}
    finally:
        if acquired:
            fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
