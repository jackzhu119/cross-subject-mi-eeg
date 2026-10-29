"""Render original manuscript figures from frozen, reviewed aggregate evidence.

No EEG, checkpoint loading, model inference, fit, test, bootstrap or permutation
is performed. Figure 1 displays all 85 saved participant contrasts. Figure 2
uses all 12 saved W contrasts and their original pointwise bootstrap intervals.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parent
FIGURES = ROOT / 'figures'
DATA = ROOT / 'figure_data'
TEAL, BLUE, GRAY, GOLD = '#007C83', '#285B9D', '#697481', '#C38518'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_rows(filename):
    manifest = json.loads((DATA/'FIGURE_SOURCE_MANIFEST.json').read_text())
    row = next(v for v in manifest['frozen_files'] if v['path'] == filename)
    path = DATA/filename
    if sha(path) != row['sha256'] or path.stat().st_size != row['bytes']:
        raise ValueError('Frozen figure source changed: '+filename)
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def save_figure(fig, stem):
    FIGURES.mkdir(exist_ok=True)
    paths = []
    for extension in ('svg','pdf','png'):
        target = FIGURES/(stem+'.'+extension)
        fig.savefig(target, dpi=300, facecolor='white')
        paths.append({'path':str(target.relative_to(ROOT)), 'bytes':target.stat().st_size,
                      'sha256':sha(target)})
    plt.close(fig)
    return paths


def participant_figure():
    rows = frozen_rows('Fig1_primary_participant_changes.csv')
    if len(rows)!=85 or len({r['subject'] for r in rows})!=85:
        raise ValueError('Expected the 85 unique, paired external participants')
    ba = np.array([float(r['ba_change_pp']) for r in rows])
    weak = np.array([float(r['weaker_change_pp']) for r in rows])
    both = (ba>1e-10)&(weak>1e-10)
    improve = weak>1e-10
    if both.sum()!=66 or improve.sum()!=72:
        raise ValueError('Saved primary participant benefit counts changed')
    if not np.allclose([ba.mean(),weak.mean()], [5.852941176470588,21.166666666666668],rtol=0,atol=1e-11):
        raise ValueError('Primary participant means differ from the reviewed evidence')
    fig, ax = plt.subplots(figsize=(7.4,5.5))
    fig.subplots_adjust(left=.13,right=.97,bottom=.15,top=.79)
    fig.text(.13,.95,'Source cohort expansion improves weaker-class coverage',
             fontsize=13.3,weight='bold',ha='left',va='top')
    fig.text(.13,.895,'Study 1  |  S60 minus S9  |  85 paired external participants',
             fontsize=9.5,color=GRAY,ha='left',va='top')
    ax.set_xlim(-22,36);ax.set_ylim(-48,75)
    ax.add_patch(Rectangle((0,0),36,75,facecolor='#ECF6F6',edgecolor='none',zorder=0))
    ax.axhline(0,color='#7D8790',lw=.9,zorder=1)
    ax.axvline(0,color='#7D8790',lw=.9,zorder=1)
    ax.scatter(ba[~both],weak[~both],s=35,color=GRAY,alpha=.78,
               edgecolor='white',linewidth=.55,label='Other observed changes (19)',zorder=2)
    ax.scatter(ba[both],weak[both],s=37,color=TEAL,alpha=.78,
               edgecolor='white',linewidth=.55,label='Both endpoints improved (66)',zorder=3)
    ax.scatter([ba.mean()],[weak.mean()],marker='D',s=87,color=GOLD,edgecolor='white',
               linewidth=1.1,label='Cohort mean',zorder=4)
    ax.text(.04,.95,'72/85 improved on weaker-class recall',transform=ax.transAxes,
            fontsize=9.1,color='#263A47',ha='left',va='top')
    ax.text(.98,.05,'Mean changes\nBA +5.85 pp\nW +21.17 pp',transform=ax.transAxes,
            fontsize=9.0,color='#263A47',ha='right',va='bottom')
    ax.set_xlabel('Change in balanced accuracy (percentage points)',labelpad=8)
    ax.set_ylabel('Change in weaker-class recall (percentage points)',labelpad=8)
    ax.set_xticks([-20,-10,0,10,20,30])
    ax.set_yticks([-40,-20,0,20,40,60])
    ax.grid(True,axis='both',color='#E6E9EB',lw=.55,zorder=-1)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(frameon=False,loc='lower left',bbox_to_anchor=(0,1.025),ncol=3,fontsize=8.0,handletextpad=.4,borderaxespad=0,columnspacing=1.1)
    return save_figure(fig,'Fig1_primary_participant_changes'), {
        'n_participants':85,'both_endpoints_improved':int(both.sum()),
        'weaker_class_improved':int(improve.sum()),'ba_mean_difference_pp':float(ba.mean()),
        'W_mean_difference_pp':float(weak.mean()),'all_participant_points_displayed':True,
        'inferential_statistics_recomputed':False}


def objective_figure():
    rows = frozen_rows('Fig2_objective_profiles.csv')
    domains = [('nested_outer','A','Nested source evaluation\n60 participants'),
               ('external_fixed40','B','External fixed 40 epochs\n85 participants'),
               ('external_source_selected','C','External source selected\n85 participants')]
    comparators = ['erm','groupdro','tail','consistency']
    labels = ['TC − ERM','TC − GroupDRO','TC − TAIL','TC − Consistency']
    colors = [BLUE,TEAL,GRAY,GRAY]
    if len(rows)!=12 or len({(r['domain'],r['comparator']) for r in rows})!=12:
        raise ValueError('Expected all 12 saved participant-level W contrasts')
    fig, axs = plt.subplots(1,3,figsize=(7.8,4.65),sharex=True,sharey=True)
    fig.subplots_adjust(left=.185,right=.98,bottom=.22,top=.71,wspace=.15)
    fig.text(.04,.97,'Training objectives produce distinct weaker-class profiles',
             fontsize=12.0,weight='bold',ha='left',va='top')
    fig.text(.04,.91,'Study 2  |  TC is compared with every registered comparator',
             fontsize=9.2,color=GRAY,ha='left',va='top')
    fig.text(.04,.86,'Dots: saved paired estimates; lines: pointwise 95% bootstrap intervals',
             fontsize=8.6,color=GRAY,ha='left',va='top')
    values=[]
    for ax,(domain,letter,title) in zip(axs,domains):
        ax.axvline(0,color='#7D8790',ls='--',lw=.85,zorder=1)
        ax.set_title(letter+'  '+title,loc='left',fontsize=8.8,pad=12,weight='bold')
        for index,(comparator,color) in enumerate(zip(comparators,colors)):
            row = next(r for r in rows if r['domain']==domain and r['comparator']==comparator)
            effect,low,high = (float(row[k]) for k in ['effect_pp','ci95_low_pp','ci95_high_pp'])
            if not low<=effect<=high:raise ValueError('Invalid confidence interval')
            y=3-index
            ax.errorbar([effect],[y],xerr=[[effect-low],[high-effect]],fmt='o',
                        color=color,ecolor=color,elinewidth=1.6,markersize=5.6,capsize=3.2,
                        markeredgecolor='white',markeredgewidth=.6,zorder=3)
            ax.text(effect,y+.18,f'{effect:+.2f}',fontsize=7.8,ha='center',va='bottom',color=color)
            values.append({'domain':domain,'comparator':comparator,'effect_pp':effect,
                           'ci95_low_pp':low,'ci95_high_pp':high})
        ax.set_xlim(-3,12);ax.set_ylim(-.42,3.63)
        ax.set_xticks([0,4,8,12]);ax.set_yticks([3,2,1,0],labels)
        ax.tick_params(axis='x',labelsize=8)
        ax.tick_params(axis='y',labelsize=8.4,length=0,pad=7)
        ax.grid(axis='x',color='#E8EBED',lw=.6)
        ax.spines[['top','right','left']].set_visible(False)
    fig.text(.58,.10,'Difference in weaker-class recall (percentage points)',
             ha='center',va='center',fontsize=9.5)
    fig.text(.04,.035,'External panels use the same previously exposed 85-person cohort and are exploratory.',
             ha='left',va='center',fontsize=8.1,color=GRAY)
    return save_figure(fig,'Fig2_objective_profiles'),{
        'saved_contrasts_displayed':12,'comparators':comparators,'domains':[d[0] for d in domains],
        'all_saved_pointwise_intervals_retained':True,'inferential_statistics_recomputed':False,
        'new_comparisons_or_tests':False,'values':values}


def main():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.5,
                         'axes.labelsize':9.5,'axes.titlesize':10.5,
                         'axes.edgecolor':'#77818B','axes.linewidth':.75,
                         'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
                         'savefig.bbox':None})
    p1,q1=participant_figure();p2,q2=objective_figure()
    report={'status':'numerical_and_artifact_checks_passed_visual_review_pending',
            'figure_1':q1,'figure_2':q2,'outputs':p1+p2,
            'build_script_sha256':sha(Path(__file__)),
            'matplotlib':matplotlib.__version__,'numpy':np.__version__,
            'no_raw_EEG_or_model_weights_read':True,'no_training_or_inference':True}
    (DATA/'FIGURE_QA.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'figures':2,'outputs':6,'primary_people':85,'objective_contrasts':12}))


if __name__=='__main__':main()
