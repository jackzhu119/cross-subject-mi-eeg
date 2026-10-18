"""Read-only independent arithmetic audit. Never imports study modules or loads models."""
import csv, gzip, hashlib, itertools, json, math, platform
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT=Path('/workspace/shared/paper1-external-audit-20261018')
I=ROOT/'inputs'
R=I/'results'
P=I/'provenance'
config=json.loads((P/'study.json').read_text())
external=json.loads((P/'external_inputs.json').read_text())
freeze=json.loads((R/'selection_freeze.json').read_text())
checks=[]
def chk(name, actual, expected=True):
    ok=bool(actual==expected)
    checks.append({'name':name,'pass':ok,'actual':actual,'expected':expected})
    if not ok: print('FAIL',name,repr(actual),repr(expected),flush=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def jhash(data): return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def ahash(y):
    x=np.ascontiguousarray(y,dtype=np.int64)
    h=hashlib.sha256(json.dumps({'shape':list(x.shape),'dtype':x.dtype.str},sort_keys=True).encode());h.update(memoryview(x).cast('B'));return h.hexdigest()
def table_diff(name, left, right, keys, nums, strings=()):
    chk(name+' rows',len(left),len(right))
    chk(name+' keys duplicates computed',int(left.duplicated(keys).sum()),0)
    chk(name+' keys duplicates saved',int(right.duplicated(keys).sum()),0)
    m=left.merge(right,on=keys,how='outer',suffixes=('_calc','_saved'),indicator=True)
    chk(name+' key match',bool((m['_merge']=='both').all()))
    diffs={}
    for k in nums:
        x=pd.to_numeric(m[k+'_calc']);y=pd.to_numeric(m[k+'_saved'])
        valid=x.notna()|y.notna()
        d=float(np.max(np.abs(x[valid].to_numpy()-y[valid].to_numpy()),initial=0))
        diffs[k]=d;chk(name+' '+k+' abs_error<=1e-12',bool(np.isfinite(d) and d<=1e-12))
    for k in strings: chk(name+' '+k+' exact',bool((m[k+'_calc'].astype(str)==m[k+'_saved'].astype(str)).all()))
    return diffs

package_root=Path('/workspace/shared/runpod-evidence-20261018')
package_evidence=[]
for name,size,digest in [('paper1-eligible-v3-final-evidence-20261018.tar.gz',21250082,'36b47206748b364eabc8f9a6d193d9e13fa54c0a96372b912cfca8179573df5e'),('paper1-eligible-v3-final-evidence-20261018/paper1_expansion_results.zip',21240637,'df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f')]:
    path=package_root/name;chk('package bytes '+name,path.stat().st_size,size);chk('package SHA256 '+name,sha(path),digest);package_evidence.append({'path':str(path),'bytes':size,'sha256':digest})
chk('config duplicate consistency',config,json.loads((P/'code/config/study.json').read_text()))
chk('frozen protocol matches config',freeze['protocol_id'],config['protocol_id'])

expected_people=[f'dreyer:{n:03d}' for n in range(1,88) if n not in [17,41]]
seeds=config['final_seeds'];levels=list(config['source_levels']);pipelines=config['pipelines'];selectors=config['selectors']
chk('roster size',len(expected_people),85);chk('external manifest roster',sorted(external),expected_people)
base_keys=['source_level','pipeline','selector']; group_keys=base_keys+['seed','dataset','subject']
metrics=['ce','ba','min_recall']; results={}; common_refs=None

for kind,filename,seed_filename,person_filename,summary_filename,report_filename in [
 ('neural','external_predictions.csv.gz','external_subject_seed_metrics.csv','per_subject_metrics.csv','condition_summaries.csv','report.json'),
 ('csp','csp_external_predictions.csv.gz','csp_subject_seed_metrics.csv','csp_per_subject_metrics.csv','csp_condition_summaries.csv','csp_report.json')]:
    print('READ',kind,flush=True)
    df=pd.read_csv(R/filename)
    report=json.loads((R/report_filename).read_text())
    chk(kind+' report source_freeze matches freeze',report['source_freeze_sha256'],freeze['freeze_sha256'])
    chk(kind+' report exploratory status',report['study_status'],'exploratory_external')
    conditions=list(itertools.product(levels,pipelines,selectors)) if kind=='neural' else [(l,'CSP_LDA','fixed') for l in levels]
    chk(kind+' rows',len(df),len(conditions)*3*85*80)
    chk(kind+' missing cells',int(df.isna().sum().sum()),0)
    chk(kind+' person roster',sorted(df.subject.unique()),expected_people)
    chk(kind+' seeds',sorted(map(int,df.seed.unique())),sorted(seeds))
    chk(kind+' labels',sorted(map(int,df.y_true.unique())),[0,1])
    chk(kind+' dataset',sorted(df.dataset.unique()),['dreyer'])
    chk(kind+' conditions',sorted(map(tuple,df[base_keys].drop_duplicates().to_numpy().tolist())),sorted(conditions))
    chk(kind+' duplicate trial keys',int(df.duplicated(group_keys+['trial_id']).sum()),0)
    chk(kind+' prediction file hash',sha(R/filename),report['prediction_sha256'])
    chk(kind+' labels agree all conditions/seeds',int(df.groupby(['subject','trial_id'],sort=False).y_true.nunique().max()),1)
    refs=df[['dataset','subject','trial_id','y_true']].drop_duplicates().sort_values(['subject','trial_id']).reset_index(drop=True)
    chk(kind+' unique physical trial count',len(refs),6800)
    if common_refs is not None: chk(kind+' neural label+trial roster exact',refs.equals(common_refs))
    else: common_refs=refs.copy()
    trial_fingerprints={}; identities=[]
    for person,g in refs.groupby('subject',sort=True):
        a=external[person]['audit']; sid=a['subject']
        trial_ids=[f'{sid}/acquisition/R{run}acquisition/trial-{t:03d}' for run in [1,2] for t in range(1,41)]
        chk(kind+' '+person+' canonical trial ids',g.trial_id.tolist(),trial_ids)
        chk(kind+' '+person+' y_hash matches input audit',ahash(g.y_true.to_numpy()),a['y_sha256'])
        chk(kind+' '+person+' run balance',g.assign(run=g.trial_id.str.split('/').str[2]).groupby('run').y_true.agg(['size','sum']).to_numpy().tolist(),[[40,20],[40,20]])
        fp=jhash([[t,int(y)] for t,y in zip(g.trial_id,g.y_true)])
        trial_fingerprints[person]=fp
        identities.append({'subject':person,'provider_subject':a['provider_subject'],'source_subject_id':sid,'n_trials':len(g),'n_left':int((g.y_true==0).sum()),'n_right':int((g.y_true==1).sum()),'trial_manifest_sha256':fp,'label_array_sha256':ahash(g.y_true.to_numpy()),'processed_input_sha256_from_manifest':external[person]['sha256']})
    counts=df.groupby(group_keys,sort=True).agg(n_trials=('y_true','size'),n_right=('y_true','sum'))
    chk(kind+' complete condition-seed-person grid',len(counts),len(conditions)*3*85)
    chk(kind+' cell counts 80,40',counts.to_numpy().tolist(),[[80,40]]*len(counts))
    if kind=='neural':
        logits=df[['logit_left','logit_right']].to_numpy()
        chk(kind+' finite logits',bool(np.isfinite(logits).all()))
        pred=(logits[:,1]>logits[:,0]).astype(np.int8)
        ce=np.logaddexp(0,np.where(df.y_true.to_numpy()==0,logits[:,1]-logits[:,0],logits[:,0]-logits[:,1]))
        tie=int((logits[:,1]==logits[:,0]).sum())
        e=df.groupby(base_keys).epoch.agg(['min','max']).reset_index()
        chk('neural one epoch per selector',bool((e['min']==e['max']).all()))
        chk('neural saved epochs agree frozen choices',all(int(row['min'])==freeze['selections'][row['source_level']][row['pipeline']]['epochs'][row['selector']] for row in e.to_dict('records')))
        alias=df.groupby(['source_level','pipeline','seed','epoch','subject','trial_id'],sort=False)[['logit_left','logit_right']].nunique()
        chk('neural repeated selector aliases identical predictions',int(alias.max().max()),1)
        unique_fits=len(df[['source_level','pipeline','seed','epoch']].drop_duplicates())
        unique_pred=len(alias)
        results['unique_selected_neural_checkpoints']=unique_fits
        results['unique_neural_prediction_rows_after_epoch_alias_dedup']=unique_pred
        results['selected_epochs']=e.to_dict('records')
    else:
        prob=df.p_right.to_numpy()
        chk('csp finite probabilities',bool(np.isfinite(prob).all()))
        chk('csp probability bounds',bool(((prob>=0)&(prob<=1)).all()))
        pred=(prob>0.5).astype(np.int8)
        ce=-np.log(np.maximum(np.where(df.y_true.to_numpy()==1,prob,1-prob),1e-15))
        tie=int((prob==.5).sum())
    correct=(pred==df.y_true.to_numpy())
    work=df[group_keys+['y_true']].copy()
    work['ce']=ce;work['left_correct']=correct&(df.y_true.to_numpy()==0);work['right_correct']=correct&(df.y_true.to_numpy()==1)
    calc=work.groupby(group_keys,sort=True).agg(ce=('ce','mean'),n_trials=('y_true','size'),n_right=('y_true','sum'),left_correct=('left_correct','sum'),right_correct=('right_correct','sum')).reset_index()
    calc['n_left']=calc.n_trials-calc.n_right
    calc['recall_left']=calc.left_correct/calc.n_left;calc['recall_right']=calc.right_correct/calc.n_right
    calc['ba']=(calc.recall_left+calc.recall_right)/2
    calc['min_recall']=calc[['recall_left','recall_right']].min(axis=1)
    calc['trial_manifest_sha256']=calc.subject.map(trial_fingerprints)
    saved=pd.read_csv(R/seed_filename)
    delta_seed=table_diff(kind+' per-person-seed metrics',calc,saved,group_keys,metrics+['recall_left','recall_right','n_trials','n_left','n_right'],['trial_manifest_sha256'])
    calc.to_csv(ROOT/(kind+'_recomputed_subject_seed_metrics.csv'),index=False)
    pk=base_keys+['dataset','subject']
    per=calc.groupby(pk,sort=True)[metrics].mean().reset_index();per['n_seeds']=3;per['trial_manifest_sha256']=per.subject.map(trial_fingerprints)
    delta_person=table_diff(kind+' per-person metrics',per,pd.read_csv(R/person_filename),pk,metrics+['n_seeds'],['trial_manifest_sha256'])
    table_diff(kind+' report JSON per-person metrics',per,pd.DataFrame(report['per_subject_metrics']),pk,metrics+['n_seeds'],['trial_manifest_sha256'])
    per.to_csv(ROOT/(kind+'_recomputed_per_subject_metrics.csv'),index=False)
    boot_indices=np.random.default_rng(config['bootstrap_seed']).integers(0,85,size=(config['bootstrap_replicates'],85))
    def summary(v):
        v=np.asarray(v); n=len(v);mean=float(np.mean(v));sd=float(np.std(v,ddof=1));se=sd/math.sqrt(n);ci=stats.t.interval(.95,n-1,loc=mean,scale=se);bc=np.quantile(v[boot_indices].mean(axis=1),[.025,.975],method='linear')
        return dict(n_subjects=n,mean=mean,sd=sd,se=se,t_ci95_low=float(ci[0]),t_ci95_high=float(ci[1]),bootstrap_ci95_low=float(bc[0]),bootstrap_ci95_high=float(bc[1]))
    sums=[]
    for cond,g in per.groupby(base_keys,sort=True):
        g=g.sort_values('subject')
        chk(kind+' summary ordered people '+str(cond),g.subject.tolist(),expected_people)
        for metric in metrics: sums.append(dict(zip(base_keys,cond))|{'metric':metric}|summary(g[metric]))
    sumdf=pd.DataFrame(sums);numcols=list(summary(np.arange(85)))
    delta_summary=table_diff(kind+' condition summaries',sumdf,pd.read_csv(R/summary_filename),base_keys+['metric'],numcols)
    table_diff(kind+' report JSON summaries',sumdf,pd.DataFrame(report['condition_summaries']),base_keys+['metric'],numcols)
    sumdf.to_csv(ROOT/(kind+'_recomputed_condition_summaries.csv'),index=False)
    results[kind]={'prediction_rows':len(df),'conditions':len(conditions),'condition_seed_combinations':len(conditions)*3,'metric_rows':len(calc),'per_subject_rows':len(per),'ties':tie,'max_seed_metric_abs_errors':delta_seed,'max_person_metric_abs_errors':delta_person,'max_summary_abs_errors':delta_summary,'prediction_sha256':sha(R/filename)}
    if kind=='neural':
        defs=[('primary_source_expansion_min_recall','prespecified_primary','min_recall',('S60','BROAD','tail_min_recall'),('S9','BROAD','tail_min_recall')),('secondary_selector_min_recall','secondary_holm_3','min_recall',('S60','BROAD','tail_min_recall'),('S60','BROAD','mean_ba')),('secondary_larger_source_min_recall','secondary_holm_3','min_recall',('S60','BROAD','tail_min_recall'),('S29','BROAD','tail_min_recall')),('secondary_source_expansion_ba','secondary_holm_3','ba',('S60','BROAD','tail_min_recall'),('S9','BROAD','tail_min_recall'))]
        comp=[];diffrows=[]
        for name,fam,metric,left,right in defs:
            def vals(c): return per.loc[(per[base_keys]==list(c)).all(axis=1)].sort_values('subject')[metric].to_numpy()
            x,y=vals(left),vals(right);d=x-y;test=stats.ttest_rel(x,y)
            c={'name':name,'family':fam,'metric':metric,'left':list(left),'right':list(right),**summary(d),'t_statistic':float(test.statistic),'degrees_of_freedom':84,'p_two_sided':float(test.pvalue),'p_holm':np.nan,'positive':int((d>1e-12).sum()),'negative':int((d< -1e-12).sum()),'equal':int((abs(d)<=1e-12).sum()),'median_difference':float(np.median(d))}
            comp.append(c);diffrows += [{'comparison':name,'dataset':'dreyer','subject':s,'metric':metric,'difference':float(v)} for s,v in zip(expected_people,d)]
        adj=stats.false_discovery_control if False else None
        p=np.array([c['p_two_sided'] for c in comp[1:]]);idx=np.argsort(p,kind='stable');adjusted=np.maximum.accumulate(p[idx]*np.arange(len(p),0,-1));adjusted=np.minimum(adjusted,1)
        for k,v in zip(idx,adjusted):comp[int(k)+1]['p_holm']=float(v)
        cdf=pd.DataFrame(comp);nums=numcols+['t_statistic','degrees_of_freedom','p_two_sided','p_holm']
        table_diff('neural comparisons',cdf,pd.read_csv(R/'comparisons.csv'),['name'],nums)
        table_diff('neural report JSON comparisons',cdf,pd.DataFrame(report['comparisons']),['name'],nums)
        table_diff('neural per-person paired differences',pd.DataFrame(diffrows),pd.read_csv(R/'paired_subject_differences.csv'),['comparison','dataset','subject','metric'],['difference'])
        cdf.to_csv(ROOT/'neural_recomputed_comparisons.csv',index=False);pd.DataFrame(diffrows).to_csv(ROOT/'neural_recomputed_paired_differences.csv',index=False)
        results['comparisons']=[{k:(None if isinstance(v,float) and math.isnan(v) else v) for k,v in c.items()} for c in comp]
        results['tail_min_recall_summaries']=[s for s in sums if s['selector']=='tail_min_recall' and s['metric'] in ['ba','min_recall']]
        results['fixed20_summaries']=[s for s in sums if s['selector']=='fixed20' and s['metric'] in ['ba','min_recall']]
    else:
        chk('csp no hypothesis tests',len(report['comparisons']),0)
        results['csp_summaries']=[s for s in sums if s['metric'] in ['ba','min_recall']]
    print('DONE',kind,results[kind],flush=True)

pd.DataFrame(identities).to_csv(ROOT/'verified_external_identity_roster.csv',index=False)
manifest=json.loads((P/'code/config/dreyer_manifest.json').read_text());files={x['path']:x for x in manifest['files']}
for person,v in external.items():
    a=v['audit']; n=a['provider_subject'];chk(person+' processed input sha internal agreement',v['sha256'],a['npz_sha256']);chk(person+' n_trials',a['n_trials'],80);chk(person+' exact raw EDF roster',sorted(x['path'] for x in a['raw_files']),[f'sourcedata/sub-{n:02d}/eeg/sub-{n:02d}_task-R{run}acquisition_eeg.edf' for run in [1,2]])
    for f in a['raw_files']: chk(person+' raw receipt '+f['path'],[f['sha256'],f['size']],[files[f['path']]['sha256'],files[f['path']]['size']])

# Retain only concise values for repetitive huge successful checks; full script regenerates them.
for c in checks:
    for k in ['actual','expected']:
        if isinstance(c[k],list) and len(c[k])>20: c[k]={'count':len(c[k]),'sha256_canonical_json':jhash(c[k]),'first_3':c[k][:3]}
checks_file=ROOT/'audit_checks.json';checks_file.write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
inputs=[{'path':str(p.relative_to(I)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(I.rglob('*')) if p.is_file()]
results={'audit_scope':'Independent saved-predictions arithmetic audit only; no model deserialization, inference, training, Pod/network access, or source modification. Frozen study modules read as text, not imported.','protocol_id':config['protocol_id'],'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},'package_evidence':package_evidence,'checks_total':len(checks),'checks_failed':sum(not c['pass'] for c in checks),'failed_checks':[c for c in checks if not c['pass']],'script_sha256':sha(__file__),'input_files':inputs,**results}
(ROOT/'audit_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print('FINISHED',len(checks),'checks;',results['checks_failed'],'failed',flush=True)
