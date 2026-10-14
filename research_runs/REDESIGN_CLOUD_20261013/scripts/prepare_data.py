"""Cloud-side verified download and exact frozen-roster reconstruction, no fitting."""
import argparse,csv,hashlib,json,sys,urllib.request,os,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
from cloud_contract import ROOT,STUDY,sha,read,write,now
V1=ROOT/'research_runs/REDESIGN_SOURCE_SELECTION_20261012'
AUDIT=ROOT/'research_runs/REDESIGN_EXPLORATORY_20261013'
sys.path.insert(0,str(AUDIT/'scripts'));sys.path.insert(0,str(V1/'scripts'))
import acquire_exposure_unconfirmed as access
import audit_acquisition_signal_qc as qc
import formal_core_inputs as source

def source_one(row,directory,allow_download=True):
 name=Path(row['path']).name
 if not name.startswith('A') or name not in {f'A{i:02d}{s}.mat' for i in range(1,10) for s in ['T','E']}:raise ValueError('source_path_invalid')
 p=directory/name
 if p.exists():
  if p.is_symlink() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('source_cached_hash_mismatch:'+name)
 else:
  if not allow_download:raise ValueError('r2_only_source_cache_missing')
  tmp=p.with_name(p.name+'.transfer');tmp.unlink(missing_ok=True);size=0
  try:
   with urllib.request.urlopen('https://bnci-horizon-2020.eu/database/data-sets/001-2014/'+name,timeout=90) as r,tmp.open('xb') as f:
    if r.status!=200:raise ValueError('source_http_not_200')
    for chunk in iter(lambda:r.read(1024**2),b''):
     size+=len(chunk)
     if size>row['bytes']:raise ValueError('source_transfer_oversize')
     f.write(chunk)
   if size!=row['bytes'] or sha(tmp)!=row['sha256']:raise ValueError('source_transfer_hash_mismatch')
   tmp.replace(p)
  finally:tmp.unlink(missing_ok=True)
 return {'filename':name,'path':str(p),'bytes':p.stat().st_size,'sha256':row['sha256']}

def verified_tensor(path,arrays,event_ids):
 if path.exists():
  if path.is_symlink():raise ValueError('tensor_symlink_rejected')
  with np.load(path,allow_pickle=False) as d:
   if list(d['event_ids'])!=event_ids or any(not np.array_equal(d[b],v) for b,v in arrays.items()):raise ValueError('tensor_cache_bytes_changed')
 else:
  tmp=path.with_name(path.name+'.tmp')
  with tmp.open('wb') as stream:np.savez(stream,**arrays,event_ids=np.asarray(event_ids))
  tmp.replace(path)
 return sha(path)

def prepare(job_dir,data_dir):
 from numerical_review_gate import verify_review
 verify_review(job_dir)
 started_at=now();job_dir=Path(job_dir);data_dir=Path(data_dir);job_dir.mkdir(parents=True,exist_ok=True);data_dir.mkdir(parents=True,exist_ok=True)
 src=data_dir/'bnci';raw=data_dir/'dreyer_acquisition';tensors=data_dir/'dreyer_inputs';src.mkdir(exist_ok=True);raw.mkdir(exist_ok=True);tensors.mkdir(exist_ok=True)
 from r2_only import import_from_environment
 imported=import_from_environment(ROOT,data_dir)
 write(job_dir/'r2_import_receipt.json',imported)
 records=read(ROOT/'research_runs/Q8-E001/results/source_files.json')
 # Historical provenance is an array rather than a gate object.
 if len(records)!=18:raise ValueError('source_manifest_incomplete')
 with ThreadPoolExecutor(max_workers=3) as pool:source_files=list(pool.map(lambda r:source_one(r,src,False),records))
 cfg=read(STUDY/'config/experiment.json');_,source_rows,source_audit=source.load_source19(src,cfg)
 del _
 expected_source=read(AUDIT/'evidence/source_exact_input_fingerprints_receipt.json')['source_file_provenance']
 for key in ('array_hashes','source_labels_sha256','source_metadata_sha256','source_sample_ids_sha256'):
  if source_audit[key]!=expected_source[key]:raise ValueError('frozen_source_input_changed:'+key)
 manifest,_=access.verified_plan();access.author_uncertainty_gate();header=access.import_previous('scripts/check_dreyer_metadata.py','cloud_edf_header')
 acquired=[]
 def one(row):return access.run_one(row,raw,data_dir/'pilot_unused',False,header)
 with ThreadPoolExecutor(max_workers=3) as pool:
  for result in pool.map(one,manifest):
   acquired.append(result);print(json.dumps({'stage':'raw_download_verified','completed':len(acquired),'expected':174}),flush=True)
 write(job_dir/'acquisition_receipt.json',{'status':'ALL_174_HASH_HEADER_EVENT_AUDITED_EXPLORATORY_ONLY_FULL_SIGNAL_QC_PENDING','files':acquired,'errors':[],'target_fits':0,'target_predictions':0,'evidence_class':access.CLASS,'independent_confirmation_qualified':False,'all_174_hash_header_event_audited':True})
 frozen_dir=AUDIT/'results/raw-qc-543feb2f';roster=read(frozen_dir/'raw_only_roster.json');rules=qc.verified_rules();modules=qc.pinned_modules();events_by_file={};by_person={};audit_files=[];tensor_files=[]
 for e in roster['events']:
  events_by_file.setdefault(e['source_file'],[]).append(e);by_person.setdefault(e['subject_id'],[]).append(e)
 from collections import Counter
 seen_native=set()
 for person in range(1,88):
  p_name=qc.subject_name(person);buffers={b:[] for b in ['broad','mu','beta']};ids=[]
  for row in sorted((r for r in manifest if int(access.PATH_PATTERN.fullmatch(r['path']).group(1))==person),key=lambda r:r['path']):
   match=access.PATH_PATTERN.fullmatch(row['path']);entry={**row,'subject':person,'run':match.group(2)}
   signal,cues,drops,file_audit=qc.inspect_run(raw/row['path'],entry,rules,modules)
   native=file_audit['native_signal19_sha256']
   if native in seen_native:raise ValueError('duplicate_native_run')
   seen_native.add(native);audit_files.append(file_audit)
   if person in [17,41]:continue
   if drops:raise ValueError('changed_event_context_eligibility')
   expected=events_by_file[row['path']]
   if len(cues)!=len(expected):raise ValueError('frozen_native_event_count_changed')
   for current,frozen in zip(cues,expected):
    for key in ('event_id','cue_sample','ytrue','context_native_start','context_native_stop'):
     if current[key]!=frozen[key]:raise ValueError('frozen_native_event_changed:'+key)
    context=signal[:,current['context_native_start']:current['context_native_stop']]
    if source.array_hash(context)!=frozen['native_context19_sha256']:raise ValueError('native_context_hash_changed')
    arrays=source.transform_context19(signal,512,current['cue_sample'],rules['input_processing'])
    if any(source.array_hash(a)!=frozen['input_sha256'][band] for band,a in arrays.items()):raise ValueError('frozen_target_input_changed')
    for band,a in arrays.items():buffers[band].append(a)
    ids.append(current['event_id'])
  if person not in [17,41]:
   arrays={band:np.stack(v) for band,v in buffers.items()};p=tensors/(p_name+'.npz');digest=verified_tensor(p,arrays,ids)
   tensor_files.append({'subject_id':p_name,'path':str(p),'bytes':p.stat().st_size,'sha256':digest,'n_events':len(ids)})
  print(json.dumps({'stage':'full_signal_input_reconstruction','people_processed':person,'expected':87,'target_fits':0}),flush=True)
 if len(audit_files)!=174 or len(tensor_files)!=85 or sum(x['n_events'] for x in tensor_files)!=6800:raise ValueError('complete_roster_required')
 q=job_dir/'qc';q.mkdir(exist_ok=True);shutil.copyfile(frozen_dir/'raw_only_roster.json',q/'raw_only_roster.json');shutil.copyfile(frozen_dir/'raw_only_event_roster.csv',q/'raw_only_event_roster.csv')
 write(q/'file_signal_audit.json',{'files':audit_files});write(q/'tensor_cache_receipt.json',{'files':tensor_files,'new_model_fits':0,'target_fits':0,'target_predictions_computed':False,'numerical_execution':source.numerical_identity()})
 report={**read(frozen_dir/'full_raw_qc_report.json'),'started_at_utc':started_at,'finished_at_utc':now(),'cloud_exact_reconstruction':True,'source_frozen_qc_report_sha256':sha(frozen_dir/'full_raw_qc_report.json'),'roster_sha256':sha(q/'raw_only_roster.json'),'file_audit_sha256':sha(q/'file_signal_audit.json'),'tensor_cache_receipt_sha256':sha(q/'tensor_cache_receipt.json'),'acquisition_receipt_sha256':sha(job_dir/'acquisition_receipt.json')}
 report['numerical_execution']=source.numerical_identity()
 # Do not mislabel the old audit timestamp/public registration as newly issued.
 report['public_registration']={'code_revision':read(job_dir/'launch_record.json')['code_revision'],'scope':'New pinned cloud reconstruction; original QC registration is preserved in source_frozen_qc_report.'}
 write(q/'full_raw_qc_report.json',report)
 receipt={'status':'PASS_DATA_PREPARATION_EXPLORATORY','checked_at_utc':now(),'source_dir':str(src),'source_data_dir':str(src),'source_raw_files_verified':18,'qualified_independent_confirmation':False,'source_files':source_files,'source_input_audit':source_audit,'raw_dir':str(raw),'tensor_cache':str(tensors),'roster_path':str(q/'raw_only_roster.json'),'roster_sha256':sha(q/'raw_only_roster.json'),'raw_qc_report_path':str(q/'full_raw_qc_report.json'),'tensor_cache_receipt_path':str(q/'tensor_cache_receipt.json'),'independent_confirmation_qualified':False,'author_prior_use':'unknown','target_fits':0,'target_predictions_computed':False,'source_file_count':18,'target_file_count':174,'retained_participants':85,'retained_events':6800,'exact_frozen_input_reconstruction':True,'numerical_execution':source.numerical_identity()}
 write(job_dir/'data_prepare_receipt.json',receipt);return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-dir',type=Path,required=True);p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('{"status":"DRY_RUN_NO_DATA_NO_FITS"}');return
 prepare(a.job_dir,a.data_dir)
if __name__=='__main__':main()
