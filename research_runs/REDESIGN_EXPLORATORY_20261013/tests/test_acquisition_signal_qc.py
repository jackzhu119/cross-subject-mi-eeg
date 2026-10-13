"""Meaningful synthetic raw-QC/gate tests; no real target decoding."""
import importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import audit_acquisition_signal_qc as qc

def rules():return json.loads(qc.RULES_PATH.read_text())
def cues():return [{'description':str(769+i%2),'onset':float(3+10*i)} for i in range(40)]
def events(c=None,n=450*512):return qc.cue_records(c or cues(),512,n,1,'R1acquisition','f'*64,'registered.edf',rules())

def test_default_is_no_raw_data_or_model_execution():
 p=subprocess.run([sys.executable,str(BASE/'scripts/audit_acquisition_signal_qc.py')],capture_output=True,text=True,check=True)
 x=json.loads(p.stdout);assert x['status']=='DRY_RUN_NO_RAW_EEG_READ' and x['independent_confirmation_qualified'] is False and x['target_predictions_computed'] is False

def test_rule_identity_and_processing():
 r=qc.verified_rules();assert r['provider_montage_exclusions']==[17,41] and r['prior_use']=='unknown'

@pytest.mark.parametrize('field,value',[('independent_confirmation_qualified',0),('model_training_enabled',True),('native_sampling_hz',250),('provider_montage_exclusions',[])])
def test_mutated_rules_rejected(tmp_path,field,value):
 r=rules();r[field]=value;p=tmp_path/'rules.json';p.write_text(json.dumps(r))
 with pytest.raises(ValueError):qc.verified_rules(p)

def test_native_class_mapping_and_grid_and_halfopen_context():
 rows,drops=events();assert len(rows)==40 and not drops and rows[0]['ytrue']==0 and rows[1]['ytrue']==1
 assert rows[0]['cue_sample']==1536 and rows[0]['context_native_start']==768 and rows[0]['context_native_stop']==3840
 assert rows[0]['event_id']=='A01_R1acquisition_cue_01'

def test_incomplete_context_only_technical_exclusion():
 c=cues();c[0]['onset']=1.;rows,drops=events(c);assert len(rows)==39 and len(drops)==1 and drops[0]['reason']=='incomplete_registered_native_six_second_context'

@pytest.mark.parametrize('mutation',['reordered','duplicate','nonfinite','wrongclass'])
def test_event_ambiguity_blocks(mutation):
 c=cues()
 if mutation=='reordered':c[1]['onset']=c[0]['onset']-1
 if mutation=='duplicate':c[1]['onset']=c[0]['onset']
 if mutation=='nonfinite':c[1]['onset']=float('nan')
 if mutation=='wrongclass':c[0]['description']='777'
 with pytest.raises(ValueError):events(c)

def timing_file(tmp_path,stamps):
 p=tmp_path/'test.edf';blocks=[]
 for s in stamps:
  tal=(str(s)+'\x14\x14\x00').encode();blocks.append(b'\0\0'+tal.ljust(32,b'\0'))
 p.write_bytes(b''.join(blocks))
 h={'channels':[{'label':'C3','samples_per_record':1},{'label':'EDF Annotations','samples_per_record':16}], 'sample_bytes':2,'header_bytes':0,'records':len(stamps),'record_duration_seconds':1.}
 return p,h

def test_continuous_record_clock_independently_checked(tmp_path):
 p,h=timing_file(tmp_path,[0.,1.,2.]);r=qc.continuous_record_timing(p,h);assert r['records_verified']==3 and r['continuous_grid_verified']

def test_fake_continuous_header_with_discontinuous_clock_blocks(tmp_path):
 p,h=timing_file(tmp_path,[0.,1.,3.])
 with pytest.raises(ValueError,match='discontinuity'):qc.continuous_record_timing(p,h)

def test_duplicate_fingerprint_not_silently_dropped():
 seen={};qc.record_unique(seen,'same','A01','input')
 with pytest.raises(ValueError,match='exact_duplicate'):qc.record_unique(seen,'same','B61','input')

def test_provider_exclusions_and_minimum_class_counts_frozen():
 r=rules();r['required_participants']=[1,17,41,78]
 inspected=[{'subject_id':qc.subject_name(p),'run':run} for p in r['required_participants'] for run in r['required_runs']]
 e=[{'subject_id':'A01','ytrue':k} for k in (0,1) for _ in range(20)]+[{'subject_id':'B78','ytrue':k} for k in (0,1) for _ in range(19)]
 retained,excluded=qc.eligible_people(e,inspected,r);assert retained==['A01'] and {x['subject_id'] for x in excluded}=={'A17','A41','B78'}

def test_missing_registered_run_is_not_participant_rescue():
 r=rules();r['required_participants']=[1]
 with pytest.raises(ValueError,match='required_two_raw_runs'):qc.eligible_people([], [{'subject_id':'A01','run':'R1acquisition'}],r)

def test_source_copy_reference_scope_and_authentication():
 seen,scope=qc.verify_source_fingerprints(BASE/'evidence/source_exact_input_fingerprints.csv');assert len(seen)==4*2592 and scope['n_source_trials']==2592 and scope['cross_dataset_identity_established'] is False

def test_source_reference_file_tamper_is_rejected(tmp_path):
 csv=tmp_path/'source.csv';csv.write_text('tampered')
 receipt=json.loads((BASE/'evidence/source_exact_input_fingerprints_receipt.json').read_text());(tmp_path/'source_receipt.json').write_text(json.dumps(receipt))
 with pytest.raises(ValueError,match='binding_mismatch'):qc.verify_source_fingerprints(csv)

def test_registration_requires_actual_full_commit():
 with pytest.raises(ValueError,match='full_public_registration'):qc.verify_registration('short')

def test_acquisition_failed_or_wrong_class_receipt_blocks(tmp_path):
 r={'status':'FAIL','evidence_class':qc.CLASS,'independent_confirmation_qualified':False}
 p=tmp_path/'receipt.json';p.write_text(json.dumps(r))
 with pytest.raises(ValueError,match='complete_174'):qc.verified_acquisition(p,tmp_path)

def test_flatline_or_nonfinite_signal_cannot_pass_inspect(tmp_path):
 class Adapter:
  def load_physical_edf(self,*a):return np.zeros((19,230400)),{},cues()
 with pytest.raises(ValueError,match='zero_dynamic_range'):qc.inspect_run(tmp_path/'fixture',{},rules(),modules=(object(),Adapter()))
