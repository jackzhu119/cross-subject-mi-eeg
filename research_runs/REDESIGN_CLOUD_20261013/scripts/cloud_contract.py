"""Shared immutable-file and bounded-run contracts; no model execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,re,urllib.request,time,os
ROOT=Path(__file__).resolve().parents[3]
STUDY=Path(__file__).resolve().parents[1]
REPOSITORY='jackzhu119/cross-subject-mi-eeg'
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def read(path):
 p=Path(path)
 if not p.is_file() or p.is_symlink():raise ValueError('required_regular_record_absent:'+p.name)
 return json.loads(p.read_text())
def write(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()));tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def inside(path):
 p=Path(path).resolve()
 if not p.is_relative_to(ROOT.resolve()):raise ValueError('path_outside_code_checkout')
 return p.relative_to(ROOT.resolve()).as_posix()
def public_bytes(commit,path):
 if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('immutable_commit_required')
 req=urllib.request.Request('https://raw.githubusercontent.com/'+REPOSITORY+'/'+commit+'/'+path,headers={'User-Agent':'MI-EEG-exploratory-freeze'})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=45) as r:
    if r.status!=200:raise ValueError('public_readback_not_200')
    return r.read(50*1024**2+1)
  except Exception:
   if attempt==2:raise
   time.sleep(1+attempt)
def verify_public_freeze(job_dir,filename='public_freeze.json',required_paths=()):
 obj=read(Path(job_dir)/filename)
 if obj.get('status')!='PASS' or obj.get('repository')!=REPOSITORY:raise ValueError('public_freeze_not_verified')
 commit=obj.get('commit_sha','');files=obj.get('files',[])
 if not re.fullmatch('[0-9a-f]{40}',commit) or not isinstance(files,(list,dict)):raise ValueError('public_freeze_identity_invalid')
 mapping=files if isinstance(files,dict) else {x.get('path'):x.get('sha256') for x in files}
 if len(mapping)!=len(files) or not files:raise ValueError('freeze_files_empty_or_duplicated')
 for path in required_paths:
  name=inside(path)
  if name not in mapping:raise ValueError('required_freeze_dependency_omitted:'+name)
 for name,expected in mapping.items():
  p=ROOT/name
  if not isinstance(name,str) or inside(p)!=name or p.is_symlink() or not p.is_file():raise ValueError('freeze_path_invalid')
  if sha(p)!=expected:raise ValueError('frozen_local_bytes_changed:'+name)
  committed=subprocess.check_output(['git','-C',str(ROOT),'show',commit+':'+name],stderr=subprocess.DEVNULL)
  if hashlib.sha256(committed).hexdigest()!=expected or hashlib.sha256(public_bytes(commit,name)).hexdigest()!=expected:raise ValueError('frozen_public_or_git_bytes_changed:'+name)
 return obj
