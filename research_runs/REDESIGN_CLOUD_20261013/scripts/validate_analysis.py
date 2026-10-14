"""Separate CSV-to-estimate reconstruction; imports no production statistic helper."""
import argparse,csv,json,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from scipy import stats
from cloud_contract import read,sha,write,now

SEEDS=[20261013,20261014,20261015]
CONTRASTS={
 'broad_mean_rank_minus_mean_loss':[(1,'broad','mean_rank'),(-1,'broad','mean_loss')],
 'broad_fixed_minus_mean_loss':[(1,'broad','fixed'),(-1,'broad','mean_loss')],
 'broad_fixed_minus_mean_rank':[(1,'broad','fixed'),(-1,'broad','mean_rank')],
 'shared_fixed_minus_broad_fixed':[(1,'shared','fixed'),(-1,'broad','fixed')],
 'shared_mean_rank_minus_mean_loss':[(1,'shared','mean_rank'),(-1,'shared','mean_loss')],
 'shared_mean_loss_minus_broad_mean_loss':[(1,'shared','mean_loss'),(-1,'broad','mean_loss')],
 'shared_mean_rank_minus_broad_mean_rank':[(1,'shared','mean_rank'),(-1,'broad','mean_rank')],
 'interaction_rank_loss_shared_minus_broad':[(1,'shared','mean_rank'),(-1,'shared','mean_loss'),(-1,'broad','mean_rank'),(1,'broad','mean_loss')],
}

def require(value,message):
 if not value:raise ValueError(message)
def close(actual,expected,name):
 if expected is None:require(actual is None,'expected_degenerate_None:'+name)
 else:require(actual is not None and np.allclose(actual,expected,rtol=1e-10,atol=1e-10),'numeric_reconstruction_mismatch:'+name)
def reconstruct(rows,roster,result):
 people=roster['participants'];events={e['event_id']:e for e in roster['events']};counts=defaultdict(Counter);seen=set();totals=Counter()
 for r in rows:
  p=r['subject_id'];e=r['event_id'];a=r['model_arch'];s=r['selector'];seed=int(r['seed']);truth=int(r['ytrue']);pred=int(r['ypred']);identity=(e,a,s,seed)
  require(identity not in seen and e in events and p==events[e]['subject_id'] and truth==events[e]['ytrue'] and pred in [0,1],'raw_prediction_identity_or_label_mismatch');seen.add(identity)
  require(a in ['broad','shared'] and s in ['fixed','mean_loss','mean_rank'] and seed in SEEDS,'condition_mismatch')
  counts[p,a,s,seed][truth,'total']+=1;counts[p,a,s,seed][truth,'correct']+=int(truth==pred);counts[p,a,s,seed]['pred',pred]+=1;totals[p,a,s,seed]+=1
 require(len(seen)==len(events)*18,'full_prediction_grid_required')
 values={};dominance={};trials=Counter(e['subject_id'] for e in events.values())
 for p in people:
  for a in ['broad','shared']:
   for s in ['fixed','mean_loss','mean_rank']:
    bas=[];ds=[]
    for seed in SEEDS:
     c=counts[p,a,s,seed];require(totals[p,a,s,seed]==trials[p] and min(c[0,'total'],c[1,'total'])>0,'participant_class_coverage_mismatch')
     bas.append(50*(c[0,'correct']/c[0,'total']+c[1,'correct']/c[1,'total']));ds.append(max(c['pred',0],c['pred',1])/trials[p])
    values[p,a,s]=sum(bas)/3;dominance[p,a,s]=sum(ds)/3
 require(result['participants_n']==len(people) and result['eligible_events']==len(events) and result['participant_order']==people,'reported_population_mismatch')
 require(result['independent_confirmation_qualified'] is False and result['secondary_confirmation_gate_open'] is False and result['target_fits']==0,'false_exploratory_claim')
 reported=result['participant_scores'];require(len(reported)==6*len(people),'reported_participant_grid_incomplete')
 for r in reported:
  key=(r['subject_id'],r['model_arch'],r['selector']);close(r['balanced_accuracy_pp'],values[key],'participant_ba');close(r['mean_seed_prediction_dominance'],dominance[key],'participant_dominance');require(r['class_dominance_flag']==(dominance[key]>=.95),'collapse_flag_mismatch')
 indices=np.random.default_rng(20261016).integers(0,len(people),size=(20000,len(people)));checked=[]
 contrasts=[result['primary']]+result['secondary_family']+result.get('extra_exploratory_contrasts',[])
 require(len({r['contrast'] for r in contrasts})==len(contrasts),'duplicate_reported_contrast')
 for r in contrasts:
  name=r['contrast'];require(name in CONTRASTS,'contrast_definition_unregistered:'+name);d=np.array([sum(coef*values[p,a,s] for coef,a,s in CONTRASTS[name]) for p in people])
  mean=float(np.mean(d));sd=float(np.std(d,ddof=1));close(r['mean_difference_pp'],mean,name);close(r['paired_sd_pp'],sd,name);close(r['participant_differences_pp'],d,name)
  close(r['bootstrap_95_percentile_interval_pp'],np.quantile(d[indices].mean(axis=1),[.025,.975]),name)
  if np.ptp(d)==0 or sd==0:close(r['p_two_sided'],None,name);close(r['t_interval_pp'],None,name)
  else:
   test=stats.ttest_1samp(d,0);ci=stats.t.interval(.95,len(d)-1,loc=mean,scale=sd/math.sqrt(len(d)));close(r['p_two_sided'],float(test.pvalue),name);close(r['t_interval_pp'],ci,name)
   if 'bonferroni_simultaneous_interval_pp' in r:close(r['bonferroni_simultaneous_interval_pp'],stats.t.interval(1-.05/3,len(d)-1,loc=mean,scale=sd/math.sqrt(len(d))),name)
  require(r.get('confirmatory_rejected',False) is False,'confirmation_promoted_by_p_value');checked.append(name)
 secondary=result['secondary_family'];pvals=np.array([1. if r['p_two_sided'] is None else r['p_two_sided'] for r in secondary]);order=np.argsort(pvals,kind='stable');adjust=np.minimum(1,np.maximum.accumulate((len(pvals)-np.arange(len(pvals)))*pvals[order]));back=np.empty(len(pvals));back[order]=adjust
 for i,r in enumerate(secondary):close(r['holm_adjusted_p'],None if r['p_two_sided'] is None else back[i],r['contrast'])
 require(set(checked)==set(CONTRASTS),'planned_contrast_missing')
 return {'participants_n':len(people),'prediction_rows':len(seen),'contrasts_reconstructed':checked,'participant_balanced_accuracy_cells_recomputed':len(values),'t_pvalues_and_intervals_recomputed':True,'participant_bootstrap_recomputed':True,'secondary_Holm_recomputed':True,'absolute_relative_tolerance':1e-10}

def execute(job):
 job=Path(job);analysis=job/'target/analysis.json';result=read(analysis);roster=read(job/'target/raw_only_roster.json');validation=read(job/'target/prediction_validation.json')
 require(validation['status']=='PASS_SEPARATE_PREDICTION_ARTIFACT_VALIDATION_EXPLORATORY' and validation['predictions_sha256']==sha(job/'target/predictions.csv') and result['prediction_validation_sha256']==sha(job/'target/prediction_validation.json'),'validated_predictions_required')
 require(len(roster['participants'])==85 and len(roster['events'])==6800,'actual_frozen_roster_required')
 with (job/'target/predictions.csv').open(newline='') as f:checks=reconstruct(csv.DictReader(f),roster,result)
 receipt={'status':'PASS_SEPARATE_STATISTICAL_NUMERICAL_RECONSTRUCTION_EXPLORATORY',**checks,'checked_at_utc':now(),'analysis_sha256':sha(analysis),'predictions_sha256':sha(job/'target/predictions.csv'),'validator_sha256':sha(__file__),'independent_confirmation_qualified':False,'target_fits':0,'new_model_fits':0,'scope':'Separate per-class/seed/person counts and SciPy t/Holm/bootstrap calculations; no model rerun, no independent human review.'}
 write(job/'target/statistical_validation.json',receipt);return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job-dir',type=Path,required=True);a=p.parse_args();print(json.dumps(execute(a.job_dir)))
