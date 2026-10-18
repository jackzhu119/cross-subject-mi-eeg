from pathlib import Path
import json,hashlib,platform,re
import numpy as np
import pandas as pd
from scipy import stats
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
SOURCE=args.source
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
PLAN={
 'analysis_class':'additional_post_hoc_descriptive_only',
 'knowledge_state':'Existing paper and outcomes inspected before this specification; this is not preregistration.',
 'scope':'All 32 neural expansion/selector/pipeline contrasts and 2 CSP contrasts against S9; participant and seed units retained.',
 'summaries':['mean and median weaker-class change','paired joint weaker-class/BA improvement counts','absolute recall-gap reduction counts','label-specific and stronger-class recall changes','all-direction inventory'],
 'tie_tolerance_fraction':1e-12,
 'new_hypothesis_tests':0,
 'no_new_models_or_inference':True,
 'input_files':{n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ['S2_Neural_Predictions.csv.gz','S3_CSP_Predictions.csv.gz','figure_data/Fig7_complete_source_expansion_inventory.csv','figure_data/neural_recomputed_paired_differences.csv']}
}
(OUT/'analysis_plan.json').write_text(json.dumps(PLAN,indent=2)+'\n')
metrics=[]
for name,expected,isneural in [('S2_Neural_Predictions.csv.gz',979200,True),('S3_CSP_Predictions.csv.gz',61200,False)]:
 d=pd.read_csv(SOURCE/name);assert len(d)==expected
 print(name,len(d),d.columns.tolist())
 keys=['source_level','pipeline','selector','seed','subject']
 assert not d.duplicated(keys+['trial_id']).any()
 d['pred']=np.where(d.logit_right>d.logit_left,1,0) if isneural else np.where(d.p_right>0.5,1,0)
 d['correct']=(d.pred==d.y_true).astype(int)
 g=d.groupby(keys+['y_true']).agg(n=('correct','size'),hit=('correct','sum'))
 assert (g.n==40).all()
 recalls=(g.hit/g.n).unstack('y_true').rename(columns={0:'recall_left',1:'recall_right'})
 recalls['ba']=recalls.mean(axis=1)
 recalls['min_recall']=recalls[['recall_left','recall_right']].min(axis=1)
 recalls['max_recall']=recalls[['recall_left','recall_right']].max(axis=1)
 recalls['recall_gap']=(recalls.recall_left-recalls.recall_right).abs()
 assert np.allclose(recalls.recall_gap,2*(recalls.ba-recalls.min_recall),atol=1e-15)
 recalls=recalls.reset_index();metrics.append(recalls)
 assert recalls.groupby(keys[:3]+['subject']).size().eq(3).all()
 assert recalls.groupby(keys[:4]).size().eq(85).all()
allseed=pd.concat(metrics,ignore_index=True)
allseed.to_csv(OUT/'recomputed_subject_seed_metrics.csv',index=False)
people=allseed.groupby(['source_level','pipeline','selector','subject'],sort=True)[['ba','min_recall','max_recall','recall_gap','recall_left','recall_right']].mean().reset_index()
people.to_csv(OUT/'recomputed_participant_metrics.csv',index=False)
rows=[];joint=[]
for (lev,pip,sel), higher in people[people.source_level.ne('S9')].groupby(['source_level','pipeline','selector']):
 lower=people[(people.source_level=='S9')&(people.pipeline==pip)&(people.selector==sel)]
 h=higher.set_index('subject').sort_index();l=lower.set_index('subject').sort_index(); assert h.index.equals(l.index) and len(h)==85
 delta=h[['ba','min_recall','max_recall','recall_gap','recall_left','recall_right']]-l[['ba','min_recall','max_recall','recall_gap','recall_left','recall_right']]
 tol=1e-12
 row=dict(analysis_class='post_hoc_descriptive',higher_source_level=lev,lower_source_level='S9',pipeline=pip,selector=sel,n_participants=85,n_final_seeds=3)
 for m in delta:
  row.update({m+'_lower_percent':100*float(l[m].mean()),m+'_higher_percent':100*float(h[m].mean()),m+'_mean_difference_pp':100*float(delta[m].mean())})
 row.update(weaker_improved=int((delta.min_recall>tol).sum()),weaker_declined=int((delta.min_recall<-tol).sum()),weaker_tied=int((delta.min_recall.abs()<=tol).sum()),ba_improved=int((delta.ba>tol).sum()),ba_declined=int((delta.ba<-tol).sum()),ba_tied=int((delta.ba.abs()<=tol).sum()),both_endpoints_improved=int(((delta.min_recall>tol)&(delta.ba>tol)).sum()),gap_narrowed=int((delta.recall_gap<-tol).sum()),gap_widened=int((delta.recall_gap>tol).sum()),gap_tied=int((delta.recall_gap.abs()<=tol).sum()),median_weaker_change_pp=100*float(delta.min_recall.median()),new_hypothesis_test=False)
 rows.append(row)
 if lev=='S60' and pip=='BROAD' and sel=='tail_min_recall':
  primary=delta
  for sub,r in delta.iterrows():
   joint.append(dict(subject=sub,weaker_change_pp=100*r.min_recall,ba_change_pp=100*r.ba,gap_change_pp=100*r.recall_gap,stronger_change_pp=100*r.max_recall,both_endpoints_improved=bool(r.min_recall>tol and r.ba>tol)))
summary=pd.DataFrame(rows);assert len(summary)==34
summary.to_csv(OUT/'S4_Additional_descriptives.csv',index=False)
pd.DataFrame(joint).to_csv(OUT/'primary_joint_participant_changes.csv',index=False)
expected=pd.read_csv(SOURCE/'figure_data/Fig7_complete_source_expansion_inventory.csv')
for _,r in expected.iterrows():
 s=summary[(summary.higher_source_level==r.higher_source_level)&(summary.pipeline==r.pipeline)&(summary.selector==r.selector)].iloc[0]
 assert abs(s[r.metric+'_mean_difference_pp']-r.difference_pp)<1e-10
arch=pd.read_csv(SOURCE/'figure_data/neural_recomputed_paired_differences.csv')
for name,m in [('primary_source_expansion_min_recall','min_recall'),('secondary_source_expansion_ba','ba')]:
 a=arch[arch.comparison==name].set_index('subject').sort_index();assert np.allclose(a.difference.values,primary[m].values,atol=1e-14,rtol=0)
p=summary[(summary.higher_source_level=='S60')&(summary.pipeline=='BROAD')&(summary.selector=='tail_min_recall')].iloc[0].to_dict()
p['gap_reduction_relative_percent']=100*(1-p['recall_gap_higher_percent']/p['recall_gap_lower_percent'])
p['weaker_relative_increase_percent']=100*(p['min_recall_higher_percent']/p['min_recall_lower_percent']-1)
p['primary_t_recomputed']=float(stats.ttest_1samp(primary.min_recall,0).statistic)
p['primary_p_recomputed']=float(stats.ttest_1samp(primary.min_recall,0).pvalue)
p['ba_t_recomputed']=float(stats.ttest_1samp(primary.ba,0).statistic)
p['neural_positive_contrasts']=int(((summary.pipeline!='CSP_LDA')&(summary.min_recall_mean_difference_pp>0)).sum())*2
p['primary_seed_changes_pp']={str(int(seed)):100*float(g[(g.source_level=='S60')].min_recall.mean()-g[g.source_level=='S9'].min_recall.mean()) for seed,g in allseed[(allseed.pipeline=='BROAD')&(allseed.selector=='tail_min_recall')].groupby('seed')}
(OUT/'additional_descriptive_receipt.json').write_text(json.dumps({'status':'PASS','scope':'Complete saved predictions, not raw EEG replay or new model inference','n_neural_rows':979200,'n_csp_rows':61200,'n_descriptive_contrasts':34,'n_inventory_values_reproduced':68,'primary':p,'new_hypothesis_tests':0,'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},indent=2)+'\n')
print(json.dumps(p,indent=2))
