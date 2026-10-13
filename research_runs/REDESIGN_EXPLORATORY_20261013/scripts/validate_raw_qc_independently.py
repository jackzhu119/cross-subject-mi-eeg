"""Independent saved-audit recount plus separate reader/numerical replay.

No audit helper/model/decoder is invoked. All174 files are rehashed and headers
independently parsed; a fixed14-event MNE+SciPy replay checks the frozen inputs.
This does not authenticate original GDF, amplifier calibration or person identity.
"""
from pathlib import Path
import json,hashlib,csv
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from scipy.signal import butter,sosfiltfilt,resample_poly
import mne
BASE=Path(__file__).resolve().parents[1]
V1=BASE.parent/'REDESIGN_SOURCE_SELECTION_20261012'
RESULT=BASE/'results/raw-qc-543feb2f'
CACHE=Path('/workspace/mi-eeg-redesign-data/dreyer_inputs_exploratory_v2')
CHECKS={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def objhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def array_hash(v):
 v=np.ascontiguousarray(v);h=hashlib.sha256();h.update(json.dumps({'shape':list(v.shape),'dtype':v.dtype.str},sort_keys=True).encode());h.update(memoryview(v).cast('B'));return h.hexdigest()
def check(n,b):CHECKS[n]=bool(b)
def header(p):
 with Path(p).open('rb') as f:
  fixed=f.read(256);ns=int(fixed[252:256]);hb=int(fixed[184:192]);nrec=int(fixed[236:244]);sec=float(fixed[244:252]);b=f.read(hb-256)
 offset=0;fields={}
 for key,w in [('name',16),('transducer',80),('unit',8),('pmin',8),('pmax',8),('dmin',8),('dmax',8),('prefilter',80),('samples',8),('reserved',32)]:
  fields[key]=[b[offset+i*w:offset+(i+1)*w].decode('ascii').strip() for i in range(ns)];offset+=ns*w
 return {'labels':fields['name'],'units':fields['unit'],'fields':fields,'records':nrec,'seconds':sec,'header_bytes':hb,'expected_size':hb+2*nrec*sum(int(x) for x in fields['samples']),'edf_c':b'EDF+C' in fixed[192:236]}
def main():
 r=json.loads((RESULT/'full_raw_qc_report.json').read_text());roster=json.loads((RESULT/'raw_only_roster.json').read_text());acq=json.loads((BASE/'evidence/full_acquisition_receipt.json').read_text());rule=json.loads((BASE/'config/RAW_QC_RULES_V2.json').read_text())
 check('actual_QC_PASS_scoped',r['status']=='PASS_RAW_ONLY_FULL_COHORT_QC_EXPLORATORY_OPERATIONAL_SCOPE')
 check('no_independence_or_model_claim',r['independent_confirmation_qualified'] is False and r['target_fits']==r['new_neural_fits']==r['new_source_fits']==0 and r['target_predictions_computed'] is False and r['author_prior_use']=='unknown')
 check('roster_hash',sha(RESULT/'raw_only_roster.json')==r['roster_sha256'])
 check('all_declared_file_count',len(acq['files'])==174)
 channels=rule['input_processing']['channels'];by_path={};hashes=[]
 for a in acq['files']:
  p=Path(a['cache_path']);h=header(p);filehash=sha(p);hashes.append(filehash);by_path[a['path']]=a
  chosen=[h['labels'].index(c) for c in channels] if len(set(h['labels']))==len(h['labels']) and set(channels)<=set(h['labels']) else []
  check('raw_'+a['path'],filehash==a['sha256'] and p.stat().st_size==a['size_bytes']==h['expected_size'] and h['edf_c'] and len(chosen)==19 and all(h['units'][i] in ['uV','µV'] and int(h['fields']['samples'][i])/h['seconds']==512 and float(h['fields']['pmin'][i])<float(h['fields']['pmax'][i]) and int(h['fields']['dmin'][i])<int(h['fields']['dmax'][i]) for i in chosen))
 check('raw_sha_unique',len(set(hashes))==174)
 manifest=json.loads((V1/'evidence/dataset_sources/dreyer_nemar_manifest.txt').read_text());expected={x['path']:x for x in manifest if '/sourcedata/' in '/'+x['path'] and '_task-R' in x['path'] and ('R1acquisition' in x['path'] or 'R2acquisition' in x['path'])}
 check('actual_provider_manifest_bindings',set(expected)==set(by_path) and all(x['checksum']==by_path[p]['sha256'] and x['size']==by_path[p]['size_bytes'] for p,x in expected.items()))
 events=roster['events'];counts=Counter((e['subject_id'],e['ytrue']) for e in events);people=roster['participants']
 check('people_recount',len(people)==r['n_retained_participants']==len(set(e['subject_id'] for e in events)))
 check('event_recount',len(events)==r['n_eligible_events']==len(set(e['event_id'] for e in events)))
 check('both_runs_and_class_min',all({e['run'] for e in events if e['subject_id']==p}=={'R1acquisition','R2acquisition'} and min(counts[p,0],counts[p,1])>=20 for p in people))
 check('provider_hard_exclusions_retained',not {'A17','A41'}&set(people))
 check('actual_class_mapping',all(e['ytrue']==int(e['native_event_code'])-769 and e['label']==e['ytrue']+1 and e['epoch_sha256']==objhash(e['input_sha256']) for e in events))
 keys=[]
 for e in events:
  for band,h in e['input_sha256'].items():keys.append((band,h))
 check('input_fingerprints_unique',len(set(keys))==len(keys))
 src=list(csv.DictReader((BASE/'evidence/source_exact_input_fingerprints.csv').open()));s={(b,x[b+'_sha256']) for x in src for b in ['broad','mu','beta']}
 check('source_target_copy_recount',not s&set(keys) and r['source_target_exact_input_comparison_checked'] is True)
 trec=json.loads((RESULT/'tensor_cache_receipt.json').read_text());cache_checks=[]
 for c in trec['files']:
  check('tensor_file_'+c['subject_id'],sha(c['path'])==c['sha256'])
  with np.load(c['path'],allow_pickle=False) as data:
   es=[e for e in events if e['subject_id']==c['subject_id']]
   cache_checks.append(len(es)==c['n_events']==len(data['event_ids']) and list(data['event_ids'])==[x['event_id'] for x in es] and all(data[b].shape==(len(es),19,320) and np.isfinite(data[b]).all() and all(array_hash(data[b][i])==e['input_sha256'][b] for i,e in enumerate(es)) for b in ['broad','mu','beta']))
 check('all_cached_inputs_rehashed_without_model',all(cache_checks))
 replays=[]
 for person in ['A01','A04','A09','A29','B78','B79','C82']:
  es=[e for e in events if e['subject_id']==person and e['run']=='R1acquisition']
  if not es:continue
  a=by_path[es[0]['source_file']]
  raw=mne.io.read_raw_edf(a['cache_path'],preload=False,verbose='ERROR')
  with np.load(CACHE/(person+'.npz'),allow_pickle=False) as data:
   for e in [es[0],es[1]]:
    x=raw.get_data(picks=channels,start=e['context_native_start'],stop=e['context_native_stop'])*1e6
    x-=x.mean(axis=0,keepdims=True)
    idx=list(data['event_ids']).index(e['event_id']);errors={}
    for band,limits in rule['input_processing']['bands_hz'].items():
     y=sosfiltfilt(butter(4,limits,btype='bandpass',fs=512,output='sos'),x,axis=-1,padtype='odd',padlen=27)
     y=resample_poly(y,5,16,axis=-1,window=('kaiser',5.),padtype='constant',cval=0)[:,320:640].astype(np.float32)
     old=data[band][idx];errors[band]=float(np.max(np.abs(y-old)));check('alternate_MNE_replay_'+e['event_id']+'_'+band,np.allclose(y,old,rtol=1e-5,atol=1e-4))
    replays.append({'event_id':e['event_id'],'reader':'MNE physical SI volts converted to microvolts','max_absolute_difference_microvolts':errors,'tolerance_atol_microvolts':1e-4,'tolerance_rtol':1e-5})
  raw.close()
 failed=[n for n,v in CHECKS.items() if not v]
 out={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_SEPARATE_NUMERICAL_RAW_QC_RECONSTRUCTION' if not failed else 'FAIL_SEPARATE_NUMERICAL_RECONSTRUCTION','scope':'Independent code path: all174 raw files rehashed/header-parsed, all retained cached windows rehashed/recounted, fixed14 events separately read by MNE and independently specified SciPy DSP; not independent human peer review or original-device/person identity proof','check_count':len(CHECKS),'checks':CHECKS,'failed_checks':failed,'replayed_events':replays,'real_files_rehashed':174,'retained_participants':len(people),'events':len(events),'source_fingerprint_events':len(src),'qc_report_sha256':sha(RESULT/'full_raw_qc_report.json'),'roster_sha256':sha(RESULT/'raw_only_roster.json'),'validator_sha256':sha(__file__),'target_fits':0,'target_predictions':0,'new_model_fits':0,'independent_confirmation_qualified':False,'original_GDF_verified':False}
 (BASE/'evidence/full_raw_qc_separate_validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['status','check_count','failed_checks','retained_participants','events']}))
 return bool(failed)
if __name__=='__main__':raise SystemExit(main())
