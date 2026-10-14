"""Consequence-focused mathematical fixtures; no EEG/model execution."""
import sys,copy,hashlib,json
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'scripts'))
from test_infer_exploratory import fixture
from analyze_exploratory import participant_statistics
from validate_analysis import reconstruct

def unequal_fixture():
 rows,roster,_,_=fixture();rows=copy.deepcopy(rows);roster=copy.deepcopy(roster)
 for j in range(3):
  e=copy.deepcopy(roster['events'][0]);old=e['event_id'];e['event_id']=old+'_extra_'+str(j);e['input_sha256']={b:hashlib.sha256((e['event_id']+b).encode()).hexdigest() for b in ['broad','mu','beta']};e['epoch_sha256']=hashlib.sha256(json.dumps(e['input_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest();roster['events'].append(e)
  copies=[]
  for r in rows:
   if r['event_id']==old:
    c=copy.deepcopy(r);c['event_id']=e['event_id'];c['epoch_sha256']=e['epoch_sha256'];copies.append(c)
  rows+=copies
 return rows,roster

def test_unequal_class_counts_recompute_ba_not_pooled_accuracy():
 rows,roster=unequal_fixture();r=participant_statistics(rows,roster,3,15);v=reconstruct(rows,roster,r)
 assert v['participant_balanced_accuracy_cells_recomputed']==18 and len(v['contrasts_reconstructed'])==8
 own=[x for x in r['participant_scores'] if x['subject_id']==roster['participants'][0] and x['model_arch']=='broad' and x['selector']=='mean_loss'][0]
 assert own['balanced_accuracy_pp']==50

@pytest.mark.parametrize('damage',['mean','ci','holm','bootstrap','participant','confirmation','missing_contrast'])
def test_changed_scientific_number_or_claim_fails(damage):
 rows,roster=unequal_fixture();r=participant_statistics(rows,roster,3,15)
 if damage=='mean':r['primary']['mean_difference_pp']+=1
 elif damage=='ci':r['primary']['t_interval_pp'][0]+=1
 elif damage=='holm':r['secondary_family'][0]['holm_adjusted_p']=.123
 elif damage=='bootstrap':r['primary']['bootstrap_95_percentile_interval_pp'][0]+=1
 elif damage=='participant':r['participant_scores'][0]['balanced_accuracy_pp']+=1
 elif damage=='confirmation':r['independent_confirmation_qualified']=True
 else:r['extra_exploratory_contrasts'].pop()
 with pytest.raises(ValueError):reconstruct(rows,roster,r)

def test_identical_conditions_keep_zero_variance_unestimated_t_interval():
 rows,roster,_,_=fixture()
 for row in rows:row['ypred']=row['ytrue']
 r=participant_statistics(rows,roster,3,12);assert r['primary']['p_two_sided'] is None and r['primary']['t_interval_pp'] is None
 assert len(reconstruct(rows,roster,r)['contrasts_reconstructed'])==8

def test_duplicate_rows_cannot_change_sampling_unit():
 rows,roster=unequal_fixture();r=participant_statistics(rows,roster,3,15)
 with pytest.raises(ValueError):reconstruct(rows+[rows[0]],roster,r)
