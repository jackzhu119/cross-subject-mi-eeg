"""Reproduce paper tables/figures from archived metrics; never fit a model.

The companion independent_numbers audit independently checks predictions.
This script preserves the subject/seed/stratum grain and records every input.
"""
from pathlib import Path
import hashlib
import json
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FIG = OUT / 'figures'
FIG.mkdir(exist_ok=True)
INPUTS = {}

def read(path):
    p = ROOT / path
    INPUTS[path] = hashlib.sha256(p.read_bytes()).hexdigest()
    return pd.read_csv(p)

def read_json(path):
    p = ROOT / path
    INPUTS[path] = hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())

def subjects(path, column=None):
    d = read(path)
    if 'stratum' in d:
        d = d.loc[d.stratum.eq('all')].copy()
    col = column or ('balanced_accuracy' if 'balanced_accuracy' in d else 'EEGNet')
    who = 'subject' if 'subject' in d else 'target'
    if 'seed' in d:
        assert not d.duplicated([who, 'seed']).any(), path
        assert d.groupby(who)['seed'].nunique().eq(3).all(), path
    s = d.groupby(who)[col].mean().sort_index()
    assert s.index.tolist() == list(range(1, 10)), path
    assert np.isfinite(s).all() and s.between(0, 1).all(), path
    return s

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
    'axes.spines.top':False,'axes.spines.right':False,
    'savefig.dpi':200,'pdf.fonttype':42,'svg.fonttype':'none'})
COLORS = {'q5':'#6E7781','rank':'#0072B2','shared':'#D55E00','norm':'#009E73'}

def save(fig, name):
    for ext in ('png','pdf','svg'):
        fig.savefig(FIG / f'{name}.{ext}', bbox_inches='tight')
    plt.close(fig)

q5 = subjects('results/Q5-E001/subject_seed_metrics.csv')
q6 = subjects('research_runs/Q6-E001/results/subject_seed_metrics.csv')
q8 = subjects('research_runs/Q8-E001/results/subject_seed_metrics.csv')
shared = subjects('results/Q9-E001/MU_BETA_SHARED/per_subject_metrics.csv')
q7 = read('research_runs/Q7-E001/analysis/q7_four_cell_summary.csv')
selection = read('research_runs/Q8-E001/results/selection.csv')
q5_selection = read('results/Q5-E001/selection.csv')
q8stat = read_json('research_runs/Q8-E001/analysis/Q5_vs_Q8_paired_statistics.json')
q6stat = read_json('research_runs/Q6-E001/posthoc_analysis/paired_subject_statistics.json')

fig, ax = plt.subplots(1,3,figsize=(12.4,3.5),gridspec_kw={'width_ratios':[1,1.25,1.05]})
def epoch_values(df):
    if not any(k in df for k in ('subject','target')):
        df = df.copy()
        df['subject'] = df['fold'].str.extract(r'loso_s(\d+)', expand=False).astype(int)
    key = 'subject' if 'subject' in df else 'target'
    cols = [k for k in ('selected_epochs','selected_epoch','epochs') if k in df]
    assert cols, list(df.columns)
    x = df.groupby(key)[cols[0]].first().sort_index()
    assert x.index.tolist() == list(range(1,10))
    return x
ep5, ep8 = epoch_values(q5_selection), epoch_values(selection)
ax[0].plot(range(1,10),ep5,'o-',color=COLORS['q5'],label='Mean validation CE')
ax[0].plot(range(1,10),ep8,'s-',color=COLORS['rank'],label='Mean within-fold rank')
ax[0].set(title='A  Source-selected epochs',xlabel='Held-out participant',ylabel='Training epochs',xticks=range(1,10),ylim=(0,40))
ax[0].legend(frameon=False,fontsize=8)
for y,k,label,marker in [(q5,'q5','Mean-CE EEGNet','o'),(q8,'rank','Mean-rank EEGNet','s'),(shared,'shared','Shared mu/beta','^')]:
    ax[1].plot(range(1,10),100*y,marker+'-',color=COLORS[k],label=label)
ax[1].axhline(25,color='#777',ls=':',lw=1)
ax[1].set(title='B  Four-class LOSO (n = 9)',xlabel='Held-out participant',ylabel='Balanced accuracy (%)',xticks=range(1,10),ylim=(20,80))
ax[1].legend(frameon=False,fontsize=8)
conditions = {}
for row in q7.to_dict('records'):
    conditions[(bool(row['normalization']),int(row['fixed_epochs']))]=row
for i,normal in enumerate((False,True)):
    rows=[conditions[(normal,e)] for e in (2,16)]
    ax[2].bar(np.array([0,1])+(i-.5)*.35,[r['BA_mean']*100 for r in rows],.32,
        yerr=[r['BA_seed_std']*100 for r in rows],capsize=3,
        color=COLORS['norm'] if normal else COLORS['q5'],label='SourceNorm' if normal else 'Raw')
ax[2].axhline(25,color='#777',ls=':',lw=1)
ax[2].set(title='C  S3 diagnostic (n = 1)',xlabel='Fixed training duration',ylabel='Balanced accuracy (%)',xticks=[0,1],xticklabels=['2 epochs','16 epochs'],ylim=(0,80))
ax[2].legend(frameon=False,fontsize=8)
fig.tight_layout()
save(fig,'figure1_selection_and_s3')

counts = read('results/Q13-E006/postrun_statistics/source_count_trajectories.csv')
contrasts = read('results/Q13-E006/postrun_statistics/paired_contrasts.csv')
paired = read('results/Q13-E006/postrun_statistics/subject_paired_differences.csv')
fixed20 = subjects('results/Q13-E001/Q8_FIXED20/per_subject_metrics.csv')
matched = subjects('results/Q13-E006/Q8_RAW_CE_MATCHED/per_subject_metrics.csv')
delta = 100*(fixed20-matched)
assert len(delta)==9
row = contrasts.loc[contrasts.contrast.eq('Q8_E006_RAW_CE_minus_Q8_FIXED20')].iloc[0]
assert abs(delta.mean()+100*row.mean_paired_ba_difference)<1e-10
fig, ax=plt.subplots(1,2,figsize=(9.1,3.7))
for method,color,label,offset in [('Q8_BROAD',COLORS['rank'],'Broad EEGNet, fixed 20 epochs',-.025),('Q9_MU_BETA_SHARED',COLORS['shared'],'Shared mu/beta, fixed 20 epochs',.025)]:
    d=counts[counts.method.eq(method)]
    means=d.groupby('source_count').balanced_accuracy.mean()
    assert means.index.tolist()==[2,4,6,8]
    ax[0].plot(means.index,100*means,'o-',color=color,label=label,lw=2)
    for who in range(1,10):
        s=d[d.target.eq(who)].sort_values('source_count')
        ax[0].plot(s.source_count+offset,100*s.balanced_accuracy,color=color,alpha=.18,lw=.7)
ax[0].set(title='A  Source-count sensitivity',xlabel='Source participants',ylabel='Four-class balanced accuracy (%)',xticks=[2,4,6,8],ylim=(20,80))
ax[0].axhline(25,color='#777',ls=':',lw=1);ax[0].legend(frameon=False,fontsize=8)
ax[1].bar(range(1,10),delta,color=[COLORS['rank'] if z>=0 else COLORS['shared'] for z in delta])
ax[1].axhline(0,color='#444',lw=.8)
ax[1].set(title='B  Matched-runtime duration control',xlabel='Held-out participant',ylabel='Fixed 20 - historical CE schedule (pp)',xticks=range(1,10),ylim=(-5,57))
low=-100*row.subject_bootstrap_95ci_high;high=-100*row.subject_bootstrap_95ci_low
ax[1].text(.02,.98,f'Mean {delta.mean():+.2f} pp\n95% CI [{low:+.2f}, {high:+.2f}]\nExact sign-flip p = {row.exact_sign_flip_p_exploratory:.3f}',transform=ax[1].transAxes,va='top',fontsize=8)
fig.tight_layout();save(fig,'figure2_source_count_and_runtime')

q14 = read('results/Q14-E002R2V1/external/subject_primary_contrast.csv')
report14 = read_json('results/Q14-E002R2V1/validation_report.json')
p14 = report14['primary_paired_contrast']
assert len(q14)==109 and q14.subject.is_unique
assert abs(q14.primary_difference_shared_minus_broad.mean()-p14['mean_difference'])<1e-12
fig,ax=plt.subplots(1,2,figsize=(9.1,3.7))
for col,color,label in [('BROAD_EEGNET_BA',COLORS['rank'],'Broad EEGNet'),('MU_BETA_SHARED_BA',COLORS['shared'],'Shared mu/beta'),('CSP4_LDA_BA',COLORS['q5'],'CSP4 + LDA')]:
    values=np.sort(q14[col].to_numpy()*100)
    ax[0].step(values,np.arange(1,len(values)+1)/len(values),where='post',color=color,label=label)
ax[0].axvline(50,color='#777',ls=':',lw=1)
ax[0].set(title='A  Binary external transfer (n = 109)',xlabel='Subject balanced accuracy (%)',ylabel='Cumulative fraction of participants',xlim=(25,100),ylim=(0,1))
ax[0].legend(frameon=False,fontsize=8,loc='upper left')
d14=q14.primary_difference_shared_minus_broad.to_numpy()*100
ax[1].hist(d14,bins=np.linspace(-15,15,25),color=COLORS['shared'],alpha=.8,edgecolor='white')
ax[1].axvline(0,color='#444',lw=1);ax[1].axvline(d14.mean(),color=COLORS['rank'],lw=1.5,ls='--')
ax[1].set(title='B  Frozen primary paired contrast',xlabel='Shared mu/beta - broad EEGNet (pp)',ylabel='Participants')
ci=np.array(p14['subject_bootstrap_percentile_95_ci'])*100
ax[1].text(.02,.98,f'Mean {d14.mean():+.3f} pp\n95% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]\nSign-test p = {p14["two_sided_exact_sign_test_p_excluding_ties"]:.4f}',transform=ax[1].transAxes,va='top',fontsize=8)
fig.tight_layout();save(fig,'figure3_external_primary')

q12=read('results/Q12-BATCH/subject_level_metrics.csv')
rows=[];names=[]
q12_table=[]
order=[('SOURCE_POOLED_WHITEN','Source-pooled whitening'),('SOURCE_BALANCED_ERM','Source-balanced ERM'),('SOURCE_GROUP_DRO','GroupDRO vs balanced ERM'),('CHANNEL_DROPOUT','Channel dropout'),('GAIN_PERTURB','Gain perturbation'),('CHANNEL_AND_GAIN','Dropout + gain')]
balanced=q12[q12.condition.eq('SOURCE_BALANCED_ERM')].set_index('subject').balanced_accuracy_mean.sort_index()
for key,label in order:
    s=q12[q12.condition.eq(key)].set_index('subject').balanced_accuracy_mean.sort_index()
    assert s.index.tolist()==list(range(1,10))
    control=balanced if key=='SOURCE_GROUP_DRO' else q8
    rows.append(100*(s-control).to_numpy());names.append(label)
    q12_table.append({'condition':key,'label':label,'mean_ba':float(s.mean()),'delta_pp':float(100*(s-control).mean()),'control':'SOURCE_BALANCED_ERM' if key=='SOURCE_GROUP_DRO' else 'Q8 historical mean-rank'})
matrix=np.array(rows)
fig,ax=plt.subplots(figsize=(9.1,3.5));maxv=np.max(np.abs(matrix))
im=ax.imshow(matrix,cmap='RdBu',vmin=-maxv,vmax=maxv,aspect='auto')
for i in range(6):
    for j in range(9):
        ax.text(j,i,f'{matrix[i,j]:+.1f}',ha='center',va='center',fontsize=8,color='white' if abs(matrix[i,j])>.65*maxv else '#222')
ax.set(yticks=range(6),yticklabels=names,xticks=range(9),xticklabels=[f'S{i}' for i in range(1,10)],xlabel='Held-out participant',title='Exploratory source-only robustness: paired BA change (pp)')
fig.colorbar(im,ax=ax,label='Balanced-accuracy difference (pp)',pad=.02)
fig.tight_layout();save(fig,'figureS1_robustness_heterogeneity')

methods=[]
method_paths=[('Q5 mean CE','results/Q5-E001/subject_seed_metrics.csv'),('Q6 source normalization','research_runs/Q6-E001/results/subject_seed_metrics.csv'),('Q8 mean rank','research_runs/Q8-E001/results/subject_seed_metrics.csv'),('Q9 8-30 Hz','results/Q9-E001/MID_8_30/per_subject_metrics.csv'),('Q9 mu only','results/Q9-E001/MU_8_13/per_subject_metrics.csv'),('Q9 beta only','results/Q9-E001/BETA_13_30/per_subject_metrics.csv'),('Q9 shared mu/beta','results/Q9-E001/MU_BETA_SHARED/per_subject_metrics.csv'),('Q10 CSP8 + EEGNet','results/Q10-E001/MU_BETA_CSP8_EEGNET/per_subject_metrics.csv'),('Q10 PCA8 + EEGNet','results/Q10-E001/MU_BETA_PCA8_EEGNET/per_subject_metrics.csv'),('Q11 capacity-matched broad','results/Q11-E001/BROAD_CAPACITY_MATCHED/per_subject_metrics.csv'),('Q11 independent two-band','results/Q11-E001/TWO_BAND_INDEPENDENT/per_subject_metrics.csv'),('Q11 early stack','results/Q11-E001/TWO_BAND_EARLY_STACK/per_subject_metrics.csv'),('Q11 four-band shared','results/Q11-E001/FOUR_BAND_SHARED/per_subject_metrics.csv')]
for label,path in method_paths:
    s=subjects(path);methods.append({'label':label,'path':path,'mean_ba':float(s.mean()),'subject_sd':float(s.std(ddof=1)),'subjects':{str(k):float(v) for k,v in s.items()}})
(OUT/'tables').mkdir(exist_ok=True)
pd.DataFrame([{k:v for k,v in row.items() if k!='subjects'} for row in methods]).to_csv(OUT/'tables'/'four_class_models.csv',index=False)
pd.DataFrame({'subject':range(1,10),'q5_ba':q5.to_numpy(),'q6_ba':q6.to_numpy(),'q8_ba':q8.to_numpy(),'shared_ba':shared.to_numpy(),'q5_epoch':ep5.to_numpy(),'q8_epoch':ep8.to_numpy(),'fixed20_ba':fixed20.to_numpy(),'matched_ce_ba':matched.to_numpy()}).to_csv(OUT/'tables'/'internal_subjects.csv',index=False)
pd.DataFrame(q12_table).to_csv(OUT/'tables'/'robustness_models.csv',index=False)
q14.to_csv(OUT/'tables'/'external_subjects.csv',index=False)
contrasts.to_csv(OUT/'tables'/'q13_contrasts.csv',index=False)
data={'q5_mean':float(q5.mean()),'q6_mean':float(q6.mean()),'q8_mean':float(q8.mean()),'shared_mean':float(shared.mean()),'q8_delta_pp':float(100*(q8-q5).mean()),'q8_median_delta_pp':float(100*(q8-q5).median()),'q8_original_statistics':q8stat,'q6_original_statistics':q6stat,'q13_fixed20_mean':float(fixed20.mean()),'q13_matched_ce_mean':float(matched.mean()),'q13_fixed20_minus_ce_pp':float(delta.mean()),'q13_matched_contrast':row.to_dict(),'q14_report':report14,'q14_primary':p14,'q14_means':{k:float(q14[k].mean()) for k in ['BROAD_EEGNET_BA','MU_BETA_SHARED_BA','CSP4_LDA_BA']},'q7_cells':q7.to_dict('records'),'four_class_models':methods,'q12_models':q12_table,'input_sha256':INPUTS,'new_fits':0,'new_checkpoint_inference':0}
(OUT/'paper_numbers.json').write_text(json.dumps(data,indent=2)+'\n')
snapshot={'github_main_reviewed':'adb2d406b4300e2c8e4d5112969291c0331f3ed5','local_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'sources':INPUTS,'task_scope':'completed non-Q15 evidence only','new_model_fits':0,'new_checkpoint_inference':0,'research_chat_project_name':'科研','research_chat_history_available':False,'research_chat_access_note':'Project metadata identified; thread-history tool did not return within bounded attempts.'}
(OUT/'evidence'/'source_snapshot.json').write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'figures':4,'source_files':len(INPUTS),'internal_subjects':9,'external_subjects':109,'new_fits':0}))
