#!/usr/bin/env python3
"""Independent saved-logit arithmetic/identity audit; no training or inference.

Reads the immutable exported tar directly, using numpy.load(allow_pickle=False).
Does not import project code, model libraries, EEG or model checkpoint files.
Does not repeat confidence-interval/permutation resampling.
"""
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
import hashlib,io,json,statistics,sys,tarfile,time
import numpy as np

ARCHIVE=Path('/workspace/paper1-hpc-artifacts/uploaded-results-20261027/paper1-results-b96a3fcaacf91017.tar.gz')
EXPECTED='b96a3fcaacf910175ced585a0b06e141cab48cfb14edd277ce8072cd0cbff329'
OUT=Path(__file__).resolve().parent
METHODS=['erm','groupdro','tail','consistency','tail_consistency']
DOMAINS={'nested_outer':('development','outer_best'),'external_fixed40':('final','fixed40'),'external_source_selected':('final','source_selected')}

def canonical(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()

started=utc();t0=time.monotonic()
report={'scope':'independent saved predictions and point-estimate arithmetic only','started_at_utc':started,
 'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
 'runtime':{'python':sys.version.split()[0],'numpy':np.__version__},
 'model_fits':0,'optimizer_updates':0,'model_inference':0,'raw_eeg_read':False,'model_checkpoints_read':False,
 'resampling_recomputed':False,'p_values_and_cis_independently_recomputed':False,
 'checks':0,'failures':[],'max_numeric_difference':{},'evaluation_audits':[],'domain_audits':{},
 'boundaries':['No raw EEG or checkpoint forward-pass reproduction.',
 'Inner validation predictions are not in the selected export; best-epoch checks use saved validation scores.',
 'Bootstrap confidence intervals and permutation p values were not independently rerun.',
 'Trial/session coverage is checked against saved task/summary inventories and cross-model trial identities, not original raw event files.']}

def require(test,code,detail=None):
 report['checks']+=1
 if not bool(test):
  report['failures'].append({'code':code,'detail':detail})

def close(actual,saved,key,detail=None,atol=1e-12):
 diff=abs(float(actual)-float(saved));report['max_numeric_difference'][key]=max(report['max_numeric_difference'].get(key,0),diff)
 require(np.isfinite(actual) and np.isfinite(saved) and diff<=atol, key,{'difference':diff,'context':detail})

require(report['archive_sha256']==EXPECTED,'archive_sha256')
with tarfile.open(ARCHIVE,'r:gz') as tar:
 payload={m.name:tar.extractfile(m).read() for m in tar if m.isfile()}
def read(name):return json.loads(payload[name])
manifest=read('EXPORT_MANIFEST.json');tasks=read('tasks.json');plan=read('state/plan.json');selection=read('state/selection.json');study=read('config/study.json')
require(len(tasks)==90 and len({t['id'] for t in tasks})==90,'unique_90_tasks')
require(Counter(t['phase'] for t in tasks)=={'development':75,'final':15},'phase_counts')
require(len([p for p in payload if p.endswith('.npz')])==9015,'exported_9015_npz')
require(set(payload)=={r['path'] for r in manifest['selected_files']}|{'EXPORT_MANIFEST.json'},'manifest_inventory')

completions={};by_domain={k:[] for k in DOMAINS};label_registry={};population_registry={};domain_seen=defaultdict(set);all_trial_rows=0;npz_count=0;eval_count=0;unique_model_sha=set()
for task in tasks:
 run='outputs/runs/'+task['id'];complete=read(run+'/complete.json');completions[task['id']]=complete
 require(complete['status']=='complete' and complete['task_id']==task['id'],'complete_identity',task['id'])
 require(complete['global_step']==complete['optimizer_updates']==5120 and complete['epochs_completed']==40,'complete_update_counts',task['id'])
 for key in ('method','phase','fold','seed','selected_epoch'):
  require(complete.get(key)==task.get(key),'complete_task_'+key,task['id'])
 for variant,relative in complete['evaluations'].items():
  summary_path=run+'/'+relative;summary=read(summary_path);folder=str(PurePosixPath(summary_path).parent)
  candidates=sorted(name for name in payload if name.startswith(folder+'/') and name.endswith('.npz'))
  expected_people={r['person_id']:r for r in summary['people']};counts={};ids_by_person=defaultdict(set);sessions_by_person=defaultdict(set);session_pairs=set();all_eval_ids=set()
  require(set(expected_people)==set(task['test_ids']) and len(expected_people)==len(summary['people']),'summary_people',summary_path)
  require(summary['variant']==variant and summary['model_sha256'].startswith(PurePosixPath(folder).name),'summary_model_variant',summary_path)
  unique_model_sha.add(summary['model_sha256'])
  for name in candidates:
   npz_count+=1
   try:
    with np.load(io.BytesIO(payload[name]),allow_pickle=False) as z:
     require(set(z.files)=={'logits','y','trial_ids','identity'},'npz_keys',name)
     logits=np.asarray(z['logits']);y=np.asarray(z['y']);trial_ids=np.asarray(z['trial_ids']);ident=json.loads(str(z['identity'].item()))
   except Exception as e:
    report['failures'].append({'code':'npz_read','detail':{'name':name,'type':type(e).__name__}});continue
   person=ident.get('person_id');session=ident.get('session');n=len(y)
   require(person in expected_people,'shard_person',name)
   require(ident.get('model_sha256')==summary['model_sha256'] and ident.get('seed')==task['seed'] and ident.get('variant')==variant,'shard_identity',name)
   require(isinstance(session,str) and bool(session),'session_identity',name)
   require((person,session) not in session_pairs,'duplicate_person_session',name);session_pairs.add((person,session))
   expected_key=canonical({'person':person,'session':session})[:24]+'.npz'
   require(PurePosixPath(name).name==expected_key,'shard_filename_identity',name)
   require(logits.shape==(n,2) and y.shape==(n,) and trial_ids.shape==(n,) and n>0,'shard_shapes',name)
   require(np.isfinite(logits).all() and np.issubdtype(y.dtype,np.integer) and np.isin(y,[0,1]).all(),'finite_logits_binary_y',name)
   ids=[str(x) for x in trial_ids.tolist()]
   require(len(set(ids))==n,'duplicate_trial_within_session',name)
   local=person.split('__',1)[1] if isinstance(person,str) and '__' in person else ''
   require(all(x.startswith(local+'/') for x in ids),'trial_person_prefix',name)
   require(not (ids_by_person[person]&set(ids)),'duplicate_trial_within_person_eval',name)
   require(not (all_eval_ids&set(ids)),'duplicate_trial_across_people_eval',name)
   ids_by_person[person].update(ids);all_eval_ids.update(ids);sessions_by_person[person].add(session)
   pred=logits.argmax(axis=1);zz=logits.astype(np.float64)
   ce=float(np.logaddexp(0,zz[np.arange(n),1-y]-zz[np.arange(n),y]).sum())
   row={'n':n,'n_left':int((y==0).sum()),'n_right':int((y==1).sum()),
        'correct_left':int(((y==0)&(pred==0)).sum()),'correct_right':int(((y==1)&(pred==1)).sum()),'sum_ce':ce}
   total=counts.setdefault(person,{k:0 for k in row})
   for k,v in row.items():total[k]+=v
   for tid,label in zip(ids,y.tolist()):
    key=(person,tid)
    if key in label_registry:require(label_registry[key]==int(label),'label_consistency_across_models',{'person':person,'trial':tid})
    else:label_registry[key]=int(label)
   all_trial_rows+=n
   if npz_count%1000==0:print(json.dumps({'stage':'npz_audit','completed_shards':npz_count,'trial_predictions':all_trial_rows}),flush=True)
  require(set(counts)==set(expected_people),'actual_shard_people_cover_summary',summary_path)
  for person,saved in expected_people.items():
   if person not in counts:continue
   total=counts[person]
   for k in ('n','n_left','n_right','correct_left','correct_right'):
    require(total[k]==saved[k],'person_'+k,{'summary':summary_path,'person':person,'actual':total[k],'saved':saved[k]})
   close(total['sum_ce'],saved['sum_ce'],'person_sum_ce',person,atol=1e-9)
   left=total['correct_left']/total['n_left'];right=total['correct_right']/total['n_right']
   metrics={'recall_left':left,'recall_right':right,'ba':(left+right)/2,'min_recall':min(left,right),'ce':total['sum_ce']/total['n']}
   for k,v in metrics.items():close(v,saved[k],'person_'+k,person)
   require(saved['seed']==task['seed'] and saved['variant']==variant,'person_seed_variant',person)
   require(person.startswith(saved['dataset']+'__'),'dataset_person_consistency',person)
   population=frozenset(ids_by_person[person])
   if person in population_registry:require(population_registry[person]==population,'trial_population_cross_model',person)
   else:population_registry[person]=population
   for domain,(phase,wanted) in DOMAINS.items():
    if task['phase']==phase and variant==wanted:
     seen_key=(domain,task['method'],task['seed'])
     compound={(person,x) for x in population}
     require(not (domain_seen[seen_key]&compound),'trial_duplicate_across_outer_folds',{'domain':domain,'task':task['id']})
     domain_seen[seen_key].update(compound)
     by_domain[domain].append({'method':task['method'],'person_id':person,'dataset':saved['dataset'],'seed':task['seed'],'n':total['n'],**metrics})
  eval_count+=1
  report['evaluation_audits'].append({'task_id':task['id'],'variant':variant,'model_sha256':summary['model_sha256'],
    'people':len(counts),'sessions':len(session_pairs),'shards':len(candidates),'trial_predictions':sum(c['n'] for c in counts.values()),'actual_trial_identities_unique':True})

require(npz_count==9015,'all_9015_read');require(eval_count==105,'all_105_eval_summaries')
# Check source-only duration selection from saved validation-score histories.
records={r['task_id']:r for r in selection['source_records']};selected={}
for method in METHODS:
 choices=[]
 for task in [x for x in tasks if x['phase']=='development' and x['method']==method]:
  c=completions[task['id']];history=c['validation_history'];require(len(history)==40,'validation_history_40',task['id'])
  score_key='source_equal_cohort_mean_min_recall'
  best=max(x[score_key] for x in history);earliest=min(x['epoch'] for x in history if x[score_key]==best)
  require(c['best_epoch']==earliest,'recorded_inner_argmax_earliest_tie',task['id'])
  record=records[task['id']]
  require(record['best_epoch']==earliest and record['complete_sha256']==canonical(c),'selection_source_binding',task['id'])
  choices.append(earliest)
 selected[method]=int(statistics.median(choices));require(selection['selected_epochs'][method]==selected[method],'method_median_epoch',method)
for task in [x for x in tasks if x['phase']=='final']:
 require(task['selected_epoch']==selected[task['method']],'final_selected_epoch',task['id'])
report['source_selected_epochs']=selected

for domain,rows in by_domain.items():
 grouped=defaultdict(list)
 for r in rows:grouped[(r['method'],r['person_id'])].append(r)
 people={}
 for key,rr in grouped.items():
  require(len(rr)==3 and len({x['seed'] for x in rr})==3,'person_three_seeds',{'domain':domain,'key':key})
  require(len({x['dataset'] for x in rr})==len({x['n'] for x in rr})==1,'person_seed_count_stability',{'domain':domain,'key':key})
  people[key]={'method':key[0],'person_id':key[1],'dataset':rr[0]['dataset'],'n_trials':rr[0]['n'],'n_seeds':3,
    **{m:float(np.mean([x[m] for x in rr])) for m in ('ba','min_recall','recall_left','recall_right')}}
 saved=read('outputs/analysis/'+domain+'.json');saved_people=read('outputs/analysis/'+domain+'_participants.json')
 require(len(people)==len(saved_people),'domain_person_rows',domain)
 for r in saved_people:
  x=people[(r['method'],r['person_id'])]
  for k in ('dataset','n_trials','n_seeds'):require(x[k]==r[k],'saved_aggregated_'+k,domain)
  for metric in ('ba','min_recall','recall_left','recall_right'):close(x[metric],r[metric],'seed_averaged_'+metric,domain)
 roster=sorted(person for method,person in people if method=='erm')
 require(len(roster)==(60 if domain=='nested_outer' else 85),'domain_people_count',domain)
 weights={p:1/len(roster) for p in roster}
 if domain=='nested_outer':
  cohorts=Counter(people['erm',p]['dataset'] for p in roster)
  weights={p:1/(len(cohorts)*cohorts[people['erm',p]['dataset']]) for p in roster}
 recomputed_means=[]
 for row in saved['method_means']:
  value=sum(weights[p]*people[row['method'],p][row['metric']] for p in roster)
  close(value,row['mean'],'domain_method_mean',{'domain':domain,'method':row['method'],'metric':row['metric']})
  close(value*100,row['mean_percent'],'domain_method_mean_percent',domain)
  recomputed_means.append({**row,'recomputed_mean':value})
 comparisons=[]
 for row in saved['comparisons']:
  prefix='tail_consistency-minus-';require(row['contrast'].startswith(prefix),'comparison_name',row['contrast'])
  comparator=row['contrast'][len(prefix):].rsplit('-',1)[0];metric=row['endpoint']
  delta=np.array([people['tail_consistency',p][metric]-people[comparator,p][metric] for p in roster])
  effect=float(sum(weights[p]*d for p,d in zip(roster,delta)))
  close(effect,row['effect'],'domain_effect',{'domain':domain,'contrast':row['contrast']})
  close(effect*100,row['effect_pp'],'domain_effect_pp',domain)
  for key,actual in [('improved',int((delta>1e-12).sum())),('declined',int((delta< -1e-12).sum())),('numerically_unchanged',int((np.abs(delta)<=1e-12).sum()))]:
   require(actual==row[key],'domain_change_count_'+key,{'domain':domain,'contrast':row['contrast']})
  comparisons.append({'contrast':row['contrast'],'recomputed_effect_pp':effect*100,
      'reported_p_raw':row['p_raw'],'p_ci_independently_recomputed':False})
 report['domain_audits'][domain]={'people':len(roster),'method_means':recomputed_means,'comparisons':comparisons}

report.update(stage='PASS' if not report['failures'] else 'FAIL',prediction_shards_read=npz_count,
 selected_evaluations_rebuilt=eval_count,total_trial_prediction_rows=all_trial_rows,
 unique_physical_person_trial_pairs=len(label_registry),unique_model_sha256=len(unique_model_sha),
 completed_at_utc=utc(),elapsed_seconds=round(time.monotonic()-t0,3),failure_count=len(report['failures']))
report['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'prediction_arithmetic_audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
summary={k:v for k,v in report.items() if k not in ('evaluation_audits','domain_audits','failures')}
summary['failures']=report['failures'][:10]
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,indent=2),flush=True)
sys.exit(0 if not report['failures'] else 3)
