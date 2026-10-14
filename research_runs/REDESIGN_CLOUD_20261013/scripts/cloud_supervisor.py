"""Detached bounded cloud workflow. RunPod account API is never used."""
import argparse,json,os,subprocess,sys,time,uuid,socket,platform,importlib.metadata,fcntl,shutil
from pathlib import Path
from datetime import datetime,timezone,timedelta
from cloud_contract import ROOT,STUDY,sha,read,write,inside,now
from cloud_transport import secure_credentials,GitHubPublisher,TransportError
from cloud_locks import local_lock,LockBusy

REPO='jackzhu119/cross-subject-mi-eeg'
JOBS=STUDY/'jobs'
CLOUD_BASE=Path(os.environ.get('MI_EEG_WORK_ROOT','/workspace/mi-eeg-cloud')).resolve()
NAMES=('torch','torchaudio','braindecode','numpy','scipy','pandas','mne','scikit-learn','skorch','einops')

def protocol_files():
 paths=[p for p in STUDY.rglob('*') if p.is_file() and p.suffix in {'.py','.sh','.json','.md','.txt'} and not p.is_relative_to(JOBS) and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and not p.is_relative_to(STUDY/'evidence')]
 v1=ROOT/'research_runs/REDESIGN_SOURCE_SELECTION_20261012';aud=ROOT/'research_runs/REDESIGN_EXPLORATORY_20261013'
 paths += [v1/'scripts'/n for n in ['train_source_selection_core.py','core_source_inputs.py','infer_selection_core.py','analyze_redesign_scores.py','check_dreyer_metadata.py','acquire_dreyer_runs.py']]
 paths += [v1/'config/core_experiment_v1.json',v1/'evidence/dataset_sources/dreyer_nemar_manifest.txt',ROOT/'research_runs/Q8-E001/results/source_files.json',ROOT/'src/mi_eeg/data/q15_context.py']
 paths += [aud/n for n in ['EXPLORATORY_DATA_ACCESS_PLAN.json','config/RAW_QC_RULES_V2.json','evidence/author_prior_use_uncertain.json','evidence/author_conditional_gpu_budget.json','evidence/source_exact_input_fingerprints.csv','evidence/source_exact_input_fingerprints_receipt.json','scripts/acquire_exposure_unconfirmed.py','scripts/audit_acquisition_signal_qc.py','results/raw-qc-543feb2f/raw_only_roster.json','results/raw-qc-543feb2f/raw_only_event_roster.csv','results/raw-qc-543feb2f/full_raw_qc_report.json']]
 return sorted(set(paths))

def checked_code_revision(revision):
 if subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()!=revision:raise ValueError('checkout_revision_mismatch')
 files={}
 for path in protocol_files():
  name=inside(path);committed=subprocess.check_output(['git','-C',str(ROOT),'show',revision+':'+name],stderr=subprocess.DEVNULL)
  import hashlib
  if path.is_symlink() or sha(path)!=hashlib.sha256(committed).hexdigest():raise ValueError('code_differs_from_immutable_revision:'+name)
  files[name]=sha(path)
 return files

def runtime():
 from train_exploratory import runtime_identity
 actual=runtime_identity()
 if actual['packages']['torch'].split('+')[0]!='2.8.0' or actual['packages']['torchaudio'].split('+')[0]!='2.8.0' or actual['runtime_cuda']!='12.8':raise ValueError('required_cuda_torch_pair_not_installed')
 for line in (STUDY/'requirements.txt').read_text().splitlines():
  if '==' in line and not line.startswith('#'):
   name,version=line.split('==')
   if importlib.metadata.version(name)!=version:raise ValueError('dependency_lock_mismatch:'+name)
 return {**actual,'status':'FROZEN_BEFORE_SOURCE_FITS','measured_at_utc':now()}

def select_artifacts(job,completed_only=False):
 accepted=[]
 for p in job.rglob('*'):
  if not p.is_file() or p.is_symlink():continue
  n=p.relative_to(job).as_posix()
  if p.name in {'supervisor.log','.supervisor.lock','publication_manifest.json'} or 'resume_state' in p.name or 'update_intent' in p.name or '.tmp' in p.name:continue
  if p.suffix not in {'.json','.csv','.md','.txt','.sha256','.pt','.npz'}:continue
  if p.suffix=='.npz' and not (n=='target/raw_logits.npz' or n.startswith('target/cells/')):continue
  if p.suffix=='.pt' and p.name!='checkpoint.pt':continue
  if completed_only and n.startswith('source/'):
   if '/inner/' in '/'+n or '/final/' in '/'+n:
    r=p.parent/'fit_receipt.json';a=p.parent/'alias_receipt.json'
    if r.is_file() and read(r).get('status')=='completed':pass
    elif a.is_file() and p.name=='alias_receipt.json':pass
    else:continue
   elif p.name not in {'source_status.json','budget_ledger.json'}:continue
  accepted.append(n)
 return sorted(accepted)

def publish(job,publisher,message,paths=None,immutable=False):
 launch=read(job/'launch_record.json');names=paths or select_artifacts(job)
 if job.resolve()!=(JOBS/job.name).resolve():raise ValueError('job_must_use_exact_repository_public_prefix')
 result=publisher.publish_snapshot(job_id=job.name,base_commit=launch['code_revision'],local_root=job,relative_paths=names,message=message,immutable_paths=names if immutable else ())
 if result.get('github_public_readback_verified') is not True:raise ValueError('backup_public_readback_not_verified')
 write(job/'last_publication_receipt.json',result)
 return result

def fetch_snapshot(receipt):
 subprocess.run(['git','-C',str(ROOT),'fetch','--quiet','origin',receipt['commit']],check=True)

def issue_freeze(job,publisher,name,preinference=False):
 paths=select_artifacts(job)
 # Mutable progress files are useful backups, but cannot belong to a science freeze.
 paths=[n for n in paths if not n.endswith(('_status.json','failure.json')) and n not in {'job_status.json','last_publication_receipt.json','completed_backup_receipt.json'} and not n.endswith('_freeze.json')]
 receipt=publish(job,publisher,'Freeze '+('source models before exploratory target inference' if preinference else 'actual runtime and data before source fits'),paths,immutable=True)
 fetch_snapshot(receipt)
 files=dict(read(job/'code_identity.json')['files']);prefix=receipt['artifact_prefix'];bindings={}
 for n in paths:
  public_path=prefix+'/'+n;files[public_path]=sha(job/n);bindings[n]={'public_path':public_path,'sha256':sha(job/n)}
 frozen={'status':'FROZEN_BEFORE_TARGET_INFERENCE_EXPLORATORY_ONLY' if preinference else 'PASS','commit_sha':receipt['commit'],'repository':REPO,'branch':receipt['branch'],'files':files,'artifact_bindings':bindings,'public_readback_verified':True,'independent_confirmation_qualified':False,'target_fits':0,'target_predictions_computed':False,'issued_at_utc':now()}
 write(job/name,frozen)
 return frozen

def status(job,stage,**extras):
 actual={'stage':stage,'updated_at_utc':now(),'job_id':job.name,'pid':os.getpid(),'target_fits':0,'independent_confirmation_qualified':False,'automatic_pod_stop_requested':False,'provider_billing_stop_verified':False}
 if (job/'source/budget_ledger.json').exists():actual.update({k:v for k,v in read(job/'source/budget_ledger.json').items() if k in {'actual_neural_fits_started','actual_neural_fits_completed','optimizer_updates'}})
 else:actual.update(actual_neural_fits_started=0,actual_neural_fits_completed=0,optimizer_updates=0)
 if (job/'target/target_status.json').exists():actual['target_predictions_computed']=read(job/'target/target_status.json').get('target_predictions_computed',False)
 else:actual['target_predictions_computed']=False
 actual.update(extras);write(job/'job_status.json',actual);print(json.dumps(actual),flush=True)

def remaining(job):
 deadline=datetime.fromisoformat(read(job/'budget_authorization.json')['expires_at_utc']);value=(deadline-datetime.now(timezone.utc)).total_seconds()
 if value<=0:raise RuntimeError('approved_wall_clock_budget_exhausted_manual_Pod_stop_required')
 return value

def run_step(job,script,args,publisher,periodic=False):
 remaining(job)
 process=subprocess.Popen([sys.executable,str(STUDY/'scripts'/script),*map(str,args)],start_new_session=True)
 last_count=-1;last_publish=time.monotonic()
 try:
  while process.poll() is None:
   if remaining(job)<=0:raise RuntimeError('budget_deadline_reached')
   if periodic and time.monotonic()-last_publish>=60:
    ledger=job/'source/budget_ledger.json';count=read(ledger).get('actual_neural_fits_completed',0) if ledger.exists() else 0
    if count>last_count:
     # Completed checkpoints are backed up; in-flight batch state stays local.
     publish(job,publisher,'Backup completed source fits '+str(count),select_artifacts(job,completed_only=True))
     last_count=count
    last_publish=time.monotonic()
   time.sleep(min(2,max(.01,remaining(job))))
  if process.returncode:raise RuntimeError('scientific_step_failed:'+script)
 except BaseException:
  import signal
  try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
  except ProcessLookupError:pass
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
  raise

def work(job):
 with local_lock('supervisor',Path(job)):
  return work_locked(job)

def work_locked(job):
 job=Path(job)
 credentials=secure_credentials(enable_r2=read(job/'launch_record.json').get('r2_enabled',False),interactive=False)
 publisher=GitHubPublisher(credentials['GH_TOKEN'],secret_values=list(credentials.values()))
 try:
  status(job,'data_preparation_no_fits')
  if not (job/'data_prepare_receipt.json').exists():
   run_step(job,'prepare_data.py',['--job-dir',job,'--data-dir',read(job/'launch_record.json')['data_dir'],'--execute'],publisher)
  data=read(job/'data_prepare_receipt.json')
  if data.get('status')!='PASS_DATA_PREPARATION_EXPLORATORY':raise ValueError('data_preparation_incomplete')
  target=job/'target';target.mkdir(exist_ok=True)
  for n in ['raw_only_roster.json','raw_only_event_roster.csv','full_raw_qc_report.json','tensor_cache_receipt.json']:
   shutil.copyfile(job/'qc'/n,target/n)
  if not (job/'public_freeze.json').exists():issue_freeze(job,publisher,'public_freeze.json')
  else:fetch_snapshot({'commit':read(job/'public_freeze.json')['commit_sha']})
  if not (job/'source/source_validation.json').exists():
   status(job,'source_only_training_exploratory')
   run_step(job,'train_exploratory.py',['--job-dir',job,'--source-data-dir',data['source_dir'],'--execute'],publisher,True)
   status(job,'source_artifact_validation_no_target_predictions')
   run_step(job,'validate_source.py',['--job-dir',job,'--source-data-dir',data['source_dir'],'--execute'],publisher)
  if read(job/'source/source_validation.json').get('status')!='PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY':raise ValueError('source_validation_incomplete')
  if not (job/'preinference_freeze.json').exists():issue_freeze(job,publisher,'preinference_freeze.json',True)
  else:fetch_snapshot({'commit':read(job/'preinference_freeze.json')['commit_sha']})
  if not (target/'prediction_completion_receipt.json').exists():
   status(job,'exploratory_target_inference_no_target_fitting')
   run_step(job,'infer_exploratory.py',['--job-dir',job,'--tensor-cache',data['tensor_cache'],'--execute'],publisher)
  status(job,'separate_prediction_and_statistical_validation')
  run_step(job,'validate_predictions.py',['--job-dir',job],publisher)
  run_step(job,'analyze_exploratory.py',['--job-dir',job],publisher)
  run_step(job,'validate_analysis.py',['--job-dir',job],publisher)
  stats_receipt=read(target/'statistical_validation.json')
  if (stats_receipt.get('status')!='PASS_SEPARATE_STATISTICAL_NUMERICAL_RECONSTRUCTION_EXPLORATORY' or type(stats_receipt.get('target_fits')) is not int or stats_receipt.get('target_fits')!=0 or stats_receipt.get('independent_confirmation_qualified') is not False or stats_receipt.get('analysis_sha256')!=sha(target/'analysis.json') or stats_receipt.get('predictions_sha256')!=sha(target/'predictions.csv')):raise ValueError('actual_statistical_validation_receipt_missing_or_changed')
  status(job,'science_complete_backup_pending',scientific_result_class='exploratory_prior_exposure_unconfirmed')
  backup=publish(job,publisher,'Complete exploratory evaluation; retain all adverse and null results')
  if backup.get('checkpoint_backup_verified') is not True:raise ValueError('completed_model_checkpoint_backup_not_verified')
  if read(job/'launch_record.json').get('r2_enabled'):
   from cloud_transport import R2CheckpointBackup
   paths=[p for p in job.rglob('*') if p.is_file() and p.suffix in {'.pt','.json','.csv'} and p.name not in {'supervisor.log','.supervisor.lock'}]
   # Explicit backup library performs full byte readback; API accept alone is insufficient.
   r2=R2CheckpointBackup(credentials)
   write(job/'r2_backup_receipt.json',r2.upload_and_verify({p.relative_to(job).as_posix():p for p in paths},key_prefix='redesign/'+job.name))
  status(job,'COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED',github_result_commit=backup['commit'],target_predictions_computed=True,manual_next_step='Use Stop in the cloud provider console. Worker exit does not stop billing.')
  final=publish(job,publisher,'Verified completion and manual stop instructions')
  write(job/'completed_backup_receipt.json',final)
 except BaseException as error:
  code=error.code if isinstance(error,TransportError) else str(error) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__
  # Credential values and arbitrary API response bodies never enter failure records.
  for secret in credentials.values():code=code.replace(secret,'[redacted]')
  status(job,'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED',error_code=code[:400],manual_next_step='Inspect job status/log; stop Pod billing manually if no immediate repair is planned.')
  try:publish(job,publisher,'Record blocked run without changing scientific conditions')
  except Exception:pass
  raise SystemExit(1) from None

def registered_status(registration):
 old=CLOUD_BASE/('code-'+registration['code_revision'])/'research_runs/REDESIGN_CLOUD_20261013/jobs'/registration['job_id']
 path=old/'job_status.json'
 if not path.is_file():return {'status_file_present':False}
 obj=read(path)
 return {k:obj.get(k) for k in ('stage','pid','actual_neural_fits_started','actual_neural_fits_completed','updated_at_utc')}

def reject_other_local_processes(resume=None):
 """Detect still-running pre-fix launchers without displaying command arguments."""
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
  try:
   arguments=(proc/'cmdline').read_bytes().split(b'\0')
   names=(b'/cloud_supervisor.py',b'/train_exploratory.py',b'/infer_exploratory.py',b'/prepare_data.py')
   if not any(arg.endswith(names) for arg in arguments):continue
   if any(str(CLOUD_BASE).encode() in arg for arg in arguments):
    raise LockBusy('existing_cloud_supervisor',int(proc.name))
  except (PermissionError,FileNotFoundError,ProcessLookupError):continue

def prior_registered_job():
 registration=CLOUD_BASE/'execution_registration.json'
 if registration.exists():return read(registration)
 return None

def launch(args):
 CLOUD_BASE.mkdir(parents=True,exist_ok=True)
 with local_lock('launch',CLOUD_BASE):
  return launch_locked(args)

def launch_locked(args):
 reject_other_local_processes(args.resume)
 previous_registration=prior_registered_job()
 if previous_registration and not args.resume:
  print(json.dumps({'status':'EXISTING_BUDGETED_JOB_DO_NOT_START_DUPLICATE','job_id':previous_registration['job_id'],'code_revision':previous_registration['code_revision'],'existing_status':registered_status(previous_registration),'next_step':'Use --resume with the same immutable revision; do not create a second experiment.'}))
  return
 if args.resume:
  if previous_registration and (previous_registration['job_id']!=args.resume or previous_registration['code_revision']!=args.code_revision):raise ValueError('registered_job_or_revision_mismatch')
  checked_code_revision(args.code_revision)
  job=JOBS/args.resume
  if not job.is_dir():raise ValueError('resume_job_not_found_in_this_code_revision')
  record=read(job/'launch_record.json');actual=runtime()
  from train_exploratory import validate_runtime,validate_budget
  validate_runtime(actual,read(job/'runtime_lock.json'));validate_budget(read(job/'budget_authorization.json'),actual)
  if actual['gpu_uuid']!=read(job/'runtime_lock.json')['gpu_uuid'] or actual['machine_hostname']!=read(job/'runtime_lock.json')['machine_hostname']:raise ValueError('resume_requires_original_machine_and_budget')
  remaining(job)
 else:
  files=checked_code_revision(args.code_revision);actual=runtime()
  value=args.hourly_rate
  if value is None:value=float(input('Actual total running server price in USD/hour (visible input, <=0.75): ').strip())
  if not 0<value<=.75:raise ValueError('hourly_rate_outside_approved_budget')
  started=datetime.fromisoformat(args.launch_started_at)
  if started.tzinfo is None or started>datetime.now(timezone.utc):raise ValueError('launch_timestamp_invalid')
  job=JOBS/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-exploratory-'+uuid.uuid4().hex[:8]);job.mkdir(parents=True)
  record={'job_id':job.name,'code_revision':args.code_revision,'data_dir':str(CLOUD_BASE/'data'),'launch_started_at_utc':started.isoformat(),'r2_enabled':args.r2,'prior_use':'unknown','independent_confirmation_qualified':False,'RunPod_API_required':False,'manual_billing_control_required':True}
  write(job/'launch_record.json',record);write(job/'code_identity.json',{'code_revision':args.code_revision,'files':files})
  write(CLOUD_BASE/'execution_registration.json',{'job_id':job.name,'code_revision':args.code_revision,'created_at_utc':now(),'approved_total_budget_usd':10,'scope':'One exploratory source-selection core job only'})
  write(job/'runtime_lock.json',actual)
  write(job/'budget_authorization.json',{'status':'PASS_BOUNDED_MACHINE_BUDGET','config_sha256':sha(STUDY/'config/experiment.json'),'machine_hostname':actual['machine_hostname'],'gpu_uuid':actual['gpu_uuid'],'maximum_neural_fits':26,'maximum_optimizer_updates':34440,'maximum_gpu_hours':8,'maximum_total_usd':10,'approved_hourly_rate_usd':value,'non_gpu_reserved_usd':2,'target_fits_authorized':False,'target_predictions_authorized':True,'optional_grouping_authorized':False,'authorized_at_utc':started.isoformat(),'expires_at_utc':(started+timedelta(hours=8)).isoformat(),'approval_basis':'Existing author conditional US$10 approval plus explicit request for executable cloud training package; actual provider quote supplied at launch.','provider_billing_control':'AUTHOR_MANUAL_STOP_NOT_AUTOMATICALLY_VERIFIED'})
 print(json.dumps({'stage':'credential_and_publication_preflight','job_id':job.name,'job_directory':str(job),'fits_started':0 if not (job/'source/budget_ledger.json').exists() else read(job/'source/budget_ledger.json').get('actual_neural_fits_started',0),'next_step_if_blocked':'Use --resume with this job ID and --reset-credentials after correcting token permissions.'}),flush=True)
 # Preflight GitHub write/readback before downloading or fitting; no RunPod API.
 creds=secure_credentials(enable_r2=record['r2_enabled'],reset=args.reset_credentials)
 publisher=GitHubPublisher(creds['GH_TOKEN'],secret_values=list(creds.values()))
 publish(job,publisher,'Preflight new cloud job; no fits started',['launch_record.json','runtime_lock.json','budget_authorization.json','code_identity.json'],True)
 # Refuse concurrent launch of the same job before spawning another worker.
 previous=job/'job_status.json'
 if previous.exists():
  state=read(previous);pid=state.get('pid')
  if isinstance(pid,int):
   try:os.kill(pid,0)
   except ProcessLookupError:pass
   else:
    if state.get('stage') not in {'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED','COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED'}:raise ValueError('existing_worker_pid_alive_do_not_duplicate')
  if state.get('stage')=='COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED':print('Job is already complete; do not retrain. Stop the Pod manually.');return
 with (job/'supervisor.log').open('ab') as log:
  worker=subprocess.Popen([sys.executable,str(Path(__file__)),'work','--job-dir',str(job)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 for _ in range(40):
  if worker.poll() is not None:raise ValueError('worker_startup_failed_inspect_job_log')
  if previous.exists() and read(previous).get('pid')==worker.pid:break
  time.sleep(.25)
 else:raise ValueError('worker_startup_unverified_do_not_relaunch_without_status_check')
 print(json.dumps({'status':'DETACHED_WORKER_STARTED_NOT_SCIENTIFICALLY_COMPLETE','job_id':job.name,'pid':worker.pid,'status_file':str(previous),'log_file':str(job/'supervisor.log'),'results_branch':'https://github.com/'+REPO+'/tree/redesign/run-'+job.name,'target_fits':0,'independent_confirmation_qualified':False,'automatic_pod_stop':False,'manual_stop_required':True}))


def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='operation',required=True);l=sub.add_parser('launch');l.add_argument('--code-revision',required=True);l.add_argument('--launch-started-at',required=True);l.add_argument('--hourly-rate',type=float);l.add_argument('--resume');l.add_argument('--r2',action='store_true');l.add_argument('--reset-credentials',action='store_true');w=sub.add_parser('work');w.add_argument('--job-dir',type=Path,required=True);args=p.parse_args()
 try:launch(args) if args.operation=='launch' else work(args.job_dir)
 except LockBusy as e:print(json.dumps({'status':'LOCK_BUSY_NO_NEW_WORKER_STARTED','error_code':e.code,'lock_scope':e.scope,'owner_pid':e.owner_pid,'next_step':'An actual local mutex is occupied. Check the existing job; do not delete locks or start duplicate fits.'}));raise SystemExit(2) from None
 except TransportError as e:print(json.dumps({'status':'NOT_STARTED_OR_BLOCKED','error_code':e.code}));raise SystemExit(2) from None
 except Exception as e:print(json.dumps({'status':'NOT_STARTED_OR_BLOCKED','error_class':type(e).__name__,'next_step':'Inspect the job log; no automatic Pod stop or paid budget expansion is performed.'}));raise SystemExit(2) from None
if __name__=='__main__':main()
