"""Real launcher shell/locking/stdin tests with simulated runtime, never CUDA fits."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
LAUNCH=ROOT/'LAUNCH_ON_GPU.sh'
REV='b'*40

STUB_PYTHON=r'''#!REAL_PYTHON
import json,os,shutil,sys,types,importlib.metadata
from pathlib import Path
shutil.disk_usage=lambda path:types.SimpleNamespace(free=int(os.environ.get('TEST_FREE_BYTES',str(20*1024**3))))
args=sys.argv[1:];root=Path(os.environ['TEST_ROOT']);runtime='runtime-' in str(Path(sys.argv[0]).parent.parent)
if args[:2]==['-m','venv']:
 d=Path(args[-1]);(d/'bin').mkdir(parents=True,exist_ok=True);shutil.copyfile(sys.argv[0],d/'bin/python');(d/'bin/python').chmod(0o755)
 with (root/'venv_calls.jsonl').open('a') as f:f.write(json.dumps(args)+'\n')
 if '--system-site-packages' in args:(d/'.pair').touch()
 raise SystemExit(0)
if args[:2]==['-m','pip']:
 with (root/'pip_calls.jsonl').open('a') as f:f.write(json.dumps(args)+'\n')
 if '-r' in args and os.environ.get('TEST_FAIL_NUMERIC_ONCE')=='1' and not (root/'already_failed').exists():
  (root/'already_failed').touch();raise SystemExit(1)
 d=Path(sys.argv[0]).parent.parent
 if 'torch==2.8.0' in args:(d/'.pair').touch()
 if '-r' in args:(d/'.numeric').touch()
 raise SystemExit(0)
if args and args[0].endswith('cloud_supervisor.py'):
 record={'args':args,'work_root':os.environ.get('MI_EEG_WORK_ROOT'),'stdin':sys.stdin.readline().strip()}
 (root/'supervisor_calls.json').write_text(json.dumps(record));print('SYNTHETIC_STARTUP_CONTROL_ONLY_NO_FITS');raise SystemExit(0)
paired=(Path(sys.argv[0]).parent.parent/'.pair').exists() if runtime else os.environ.get('TEST_HOST_PAIR','1')=='1'
numeric=(Path(sys.argv[0]).parent.parent/'.numeric').exists() if runtime else False
if paired:
 torch=types.ModuleType('torch');torch.__version__='2.8.0+cu128';torch.version=types.SimpleNamespace(cuda='12.8');torch.cuda=types.SimpleNamespace(is_available=lambda:True)
 torch.ones=lambda *a,**kw:types.SimpleNamespace(item=lambda:1.0)
 audio=types.ModuleType('torchaudio');audio.__version__='2.8.0+cu128';sys.modules['torch']=torch;sys.modules['torchaudio']=audio
else:
 import importlib.abc
 class BlockTorch(importlib.abc.MetaPathFinder):
  def find_spec(self,fullname,path=None,target=None):
   if fullname in {'torch','torchaudio'}:raise ImportError('synthetic unavailable host runtime')
 sys.meta_path.insert(0,BlockTorch())
versions={line.split('==')[0]:line.split('==')[1] for line in Path(os.environ['TEST_REQUIREMENTS']).read_text().splitlines() if '==' in line and not line.startswith('#')}
def fake_version(name):
 if not numeric:raise importlib.metadata.PackageNotFoundError(name)
 return versions[name]
importlib.metadata.version=fake_version
if args and args[0]=='-c':code=args[1];sys.argv=['-c',*args[2:]]
else:code=sys.stdin.read();sys.argv=['-',*args[1:]]
exec(compile(code,'<launcher-test-control>','exec'),{'__name__':'__main__'})
'''

@pytest.fixture
def fixture(tmp_path):
 bin_dir=tmp_path/'bin';bin_dir.mkdir();base=tmp_path/'persistent space'/'mi-eeg'
 py=bin_dir/'python3.12';py.write_text(STUB_PYTHON.replace('REAL_PYTHON',sys.executable));py.chmod(0o755)
 git=bin_dir/'git';git.write_text('''#!/bin/bash
if [[ "$1" == clone ]]; then
 target="${@: -1}";mkdir -p "$target/.git" "$target/research_runs/REDESIGN_CLOUD_20261013"
 cp "$TEST_REQUIREMENTS" "$target/research_runs/REDESIGN_CLOUD_20261013/requirements.txt"
fi
if [[ "$3" == rev-parse ]]; then printf '%s\\n' "$TEST_HEAD";fi
''');git.chmod(0o755)
 gpu=bin_dir/'nvidia-smi';gpu.write_text('#!/bin/bash\nexit "${TEST_GPU_ERROR:-0}"\n');gpu.chmod(0o755)
 env={**os.environ,'PATH':str(bin_dir)+':'+os.environ['PATH'],'TEST_ROOT':str(tmp_path),'TEST_REQUIREMENTS':str(ROOT/'requirements.txt'),'TEST_HEAD':REV}
 env.pop('_MI_EEG_BOOTSTRAP_LOCK_FD',None)
 return base,env,py

def run(fixture,*extra,input='synthetic-private-token\n',rate=True):
 base,env,_=fixture
 args=['bash',str(LAUNCH),'--revision',REV,'--work-dir',str(base)]
 if rate:args+=['--hourly-rate','0.31']
 return subprocess.run(args+list(extra),env=env,input=input,text=True,capture_output=True,timeout=20)

def calls(path):
 return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

def test_fresh_exact_host_inherits_and_preserves_private_input(fixture):
 base,env,_=fixture;r=run(fixture)
 assert r.returncode==0,r.stdout+r.stderr
 assert 'SYNTHETIC_STARTUP_CONTROL_ONLY_NO_FITS' in r.stdout
 pip=calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl');assert len(pip)==1 and '-r' in pip[0]
 assert '--system-site-packages' in calls(Path(env['TEST_ROOT'])/'venv_calls.jsonl')[0]
 actual=json.loads((Path(env['TEST_ROOT'])/'supervisor_calls.json').read_text())
 assert actual['work_root']==str(base.resolve()) and actual['stdin']=='synthetic-private-token'
 assert 'synthetic-private-token' not in r.stdout+r.stderr
 assert actual['args'][actual['args'].index('--hourly-rate')+1]=='0.31'

def test_absent_host_pair_installs_official_exact_cuda_pair(fixture):
 _,env,_=fixture;env['TEST_HOST_PAIR']='0';r=run(fixture)
 assert r.returncode==0,r.stdout+r.stderr
 pip=calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl')
 assert len(pip)==2 and 'torch==2.8.0' in pip[0] and 'torchaudio==2.8.0' in pip[0]
 assert pip[0][pip[0].index('--index-url')+1]=='https://download.pytorch.org/whl/cu128'
 assert '-r' in pip[1] and '--system-site-packages' not in calls(Path(env['TEST_ROOT'])/'venv_calls.jsonl')[0]

def test_prior_revision_exact_runtime_reused_without_any_install(fixture):
 base,env,stub=fixture;previous=base/('runtime-'+'c'*40);(previous/'bin').mkdir(parents=True)
 (previous/'bin/python').write_bytes(stub.read_bytes());(previous/'bin/python').chmod(0o755)
 (previous/'.pair').touch();(previous/'.numeric').touch()
 r=run(fixture);assert r.returncode==0,r.stdout+r.stderr
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()
 assert not (Path(env['TEST_ROOT'])/'venv_calls.jsonl').exists()

def test_partial_install_retries_and_never_resets_origin(fixture):
 base,env,_=fixture;env['TEST_FAIL_NUMERIC_ONCE']='1'
 first=run(fixture);assert first.returncode==1 and 'Dependency installation failed' in first.stdout
 origin=(base/'budget_origin.json').read_bytes()
 second=run(fixture);assert second.returncode==0,second.stdout+second.stderr
 assert (base/'budget_origin.json').read_bytes()==origin
 assert len(calls(Path(env['TEST_ROOT'])/'venv_calls.jsonl'))==1
 assert len(calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl'))==2
 third=run(fixture);assert third.returncode==0 and len(calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl'))==2

@pytest.mark.parametrize('rate',['0','0.751','nan','inf','-0.1','token-not-price'])
def test_unapproved_rate_blocks_before_workspace_writes(fixture,rate):
 base,_,_=fixture;r=run(fixture,'--hourly-rate',rate)
 assert r.returncode!=0 and not base.exists()

def test_interactive_rate_and_token_survive_both_wrappers(fixture):
 _,env,_=fixture;r=run(fixture,rate=False,input='0.28\nsynthetic-private-token\n')
 assert r.returncode==0,r.stdout+r.stderr
 actual=json.loads((Path(env['TEST_ROOT'])/'supervisor_calls.json').read_text())
 assert actual['args'][actual['args'].index('--hourly-rate')+1]=='0.28' and actual['stdin']=='synthetic-private-token'

def test_missing_nvidia_driver_blocks_before_any_workspace_write(fixture):
 base,env,_=fixture;env['TEST_GPU_ERROR']='1';r=run(fixture)
 assert r.returncode==2 and 'NVIDIA hardware/driver unavailable' in r.stdout and not base.exists()

def test_eight_hour_origin_blocks_without_clone_or_install(fixture):
 base,env,_=fixture;base.mkdir(parents=True);(base/'budget_origin.json').write_text('{"started_at_utc":"2020-01-01T00:00:00+00:00"}\n')
 before=(base/'budget_origin.json').read_bytes();r=run(fixture)
 assert r.returncode!=0 and 'eight-hour budget clock is exhausted' in r.stdout+r.stderr
 assert (base/'budget_origin.json').read_bytes()==before and not (base/('code-'+REV)).exists()
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()

def test_local_lock_contention_is_clear_and_does_not_touch_workspace(fixture):
 base,_,_=fixture;folder=Path('/tmp')/('mi-eeg-bootstrap-'+str(os.getuid()));folder.mkdir(mode=0o700,exist_ok=True)
 path=folder/(hashlib.sha256(str(base.resolve()).encode()).hexdigest()+'.lock')
 fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);r=run(fixture)
  assert r.returncode!=0 and 'Another launcher is preparing' in r.stdout+r.stderr and not base.exists()
 finally:os.close(fd)

def test_resume_reset_and_r2_options_are_forwarded(fixture):
 base,env,_=fixture;base.mkdir(parents=True);(base/'execution_registration.json').write_text(json.dumps({'job_id':'job-2026-01','code_revision':REV}))
 r=run(fixture,'--resume','job-2026-01','--reset-credentials','--r2')
 assert r.returncode==0,r.stdout+r.stderr
 args=json.loads((Path(env['TEST_ROOT'])/'supervisor_calls.json').read_text())['args']
 assert args[args.index('--resume')+1]=='job-2026-01' and '--reset-credentials' in args and '--r2' in args

def test_code_mismatch_never_installs_dependencies(fixture):
 _,env,_=fixture;env['TEST_HEAD']='c'*40;r=run(fixture)
 assert r.returncode==2 and 'Code revision mismatch' in r.stdout and not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()

def test_malformed_revision_blocks_before_hardware_or_workspace(fixture):
 base,env,_=fixture;r=subprocess.run(['bash',str(LAUNCH),'--revision','bad','--work-dir',str(base)],env=env,text=True,capture_output=True)
 assert r.returncode==2 and not base.exists()

def test_invalid_inherited_lock_is_rejected(fixture):
 base,env,_=fixture;env['_MI_EEG_BOOTSTRAP_LOCK_FD']='999999';r=run(fixture)
 assert r.returncode!=0 and 'Invalid inherited bootstrap lock' in r.stdout+r.stderr and not base.exists()

def test_help_documents_portable_work_directory(fixture):
 _,env,_=fixture;r=subprocess.run(['bash',str(LAUNCH),'--help'],env=env,text=True,capture_output=True)
 assert r.returncode==0 and '--work-dir' in r.stdout and '--reset-credentials' in r.stdout


def test_existing_registration_blocks_reinstall_with_safe_saved_stage(fixture):
 base,env,_=fixture;base.mkdir(parents=True)
 (base/'execution_registration.json').write_text(json.dumps({'job_id':'old-job','code_revision':REV}))
 status=base/('code-'+REV)/'research_runs/REDESIGN_CLOUD_20261013/jobs/old-job/job_status.json'
 status.parent.mkdir(parents=True);status.write_text('{"stage":"source_only_training_exploratory"}')
 r=run(fixture)
 assert r.returncode!=0 and 'EXISTING_JOB_REQUIRES_EXPLICIT_RESUME' in r.stdout and 'source_only_training_exploratory' in r.stdout
 assert 'NOT_OBSERVED' in r.stdout and not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()
 assert not (base/'budget_origin.json').exists()


def test_resume_without_matching_original_registration_is_blocked(fixture):
 base,env,_=fixture;r=run(fixture,'--resume','missing-job')
 assert r.returncode!=0 and 'No existing execution registration' in r.stdout+r.stderr
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()
 (base/'execution_registration.json').write_text(json.dumps({'job_id':'old-job','code_revision':'c'*40}))
 r=run(fixture,'--resume','old-job')
 assert r.returncode!=0 and 'original code revision' in r.stdout+r.stderr
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()


def test_unsafe_or_secret_like_saved_stage_never_echoed(fixture):
 base,_,_=fixture;base.mkdir(parents=True)
 (base/'execution_registration.json').write_text(json.dumps({'job_id':'old-job','code_revision':REV}))
 status=base/('code-'+REV)/'research_runs/REDESIGN_CLOUD_20261013/jobs/old-job/job_status.json'
 status.parent.mkdir(parents=True);status.write_text('{"stage":"unsafe value with spaces and credentials"}')
 r=run(fixture)
 assert r.returncode!=0 and 'unsafe value' not in r.stdout+r.stderr


def test_storage_shortfall_is_reported_before_clone_or_install(fixture):
 base,env,_=fixture;env['TEST_FREE_BYTES']='1';r=run(fixture)
 assert r.returncode!=0 and 'At least 10 GiB' in r.stdout+r.stderr
 assert not (base/('code-'+REV)).exists() and not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()


def test_future_budget_origin_does_not_extend_approved_clock(fixture):
 base,env,_=fixture;base.mkdir(parents=True)
 (base/'budget_origin.json').write_text('{"started_at_utc":"2099-01-01T00:00:00+00:00"}\n')
 r=run(fixture)
 assert r.returncode!=0 and 'Invalid budget origin timestamp' in r.stdout+r.stderr
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()


def test_dangling_registration_symlink_is_rejected(fixture):
 base,_,_=fixture;base.mkdir(parents=True);(base/'execution_registration.json').symlink_to(base/'missing.json')
 r=run(fixture)
 assert r.returncode!=0 and 'Unsafe execution registration' in r.stdout+r.stderr
 assert not (base/'budget_origin.json').exists()
