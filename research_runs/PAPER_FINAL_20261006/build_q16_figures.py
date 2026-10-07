"""Publication figures for the non-adaptive Q16 descriptive physiology stage.

The workflow is schematic. Numerical figures accept committed Q16 summaries;
this renderer never reads EEG, executes a fit, or computes predictions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

HERE = Path(__file__).resolve().parent
COLOR_LIMIT_DB = 6.0
CHANNELS = ('Fz','FC3','FC1','FCz','FC2','FC4','C5','C3','C1','Cz','C2','C4','C6','CP3','CP1','CPz','CP2','CP4','P1','Pz','P2','POz')
BANDS = ('mu', 'beta')
HANDS = ('left', 'right')
SOURCE_COLOR = '#287681'
TARGET_COLOR = '#9b5c26'
PHYSIO_COLOR = '#6d598c'
WORKFLOW_ROWS = (
    {
        'label': 'A  Source-only learning',
        'color': SOURCE_COLOR,
        'boxes': (
            ('Raw audit + protocol gate', 'Official source metadata\nCommitted preprocessing freeze'),
            ('Source-only selection', 'Held-out source participants\nDuration / model selection'),
            ('Source fitting + freeze', 'Final source-only fits\nCheckpoints + transforms frozen'),
        ),
        'note': 'Q14 PhysioNet and Q15 Cho2017 / Lee2019 use separate source-trained artifacts.',
    },
    {
        'label': 'B  Fixed target evaluation',
        'color': TARGET_COLOR,
        'boxes': (
            ('Target adapter + gate', 'Event/class metadata for eligibility\nand mapping\nCommitted inference freeze'),
            ('Fixed source inference', 'Frozen checkpoints + transforms\nDeterministic operators only'),
            ('Saved predictions → score', 'Ground-truth labels used for scoring only\nNo target fitting or model selection'),
        ),
        'note': 'No target-based model selection, optimization, normalization fit, or feedback to source learning.',
    },
    {
        'label': 'C  Separate descriptive physiology',
        'color': PHYSIO_COLOR,
        'boxes': (
            ('BNCI raw audit', '9 participants × 2 sessions\nPhysiological window eligibility'),
            ('Frozen signal recipe', 'Native-rate Welch band power\nFixed baseline / imagery windows'),
            ('Baseline-relative μ/β power\n+ association', 'Participant-level descriptors\nAssociation with saved binary LOSO BA'),
        ),
        'note': 'No tuning of decoders; a descriptive association does not identify a learned physiological mechanism.',
    },
)


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
        'axes.titlesize': 8.5, 'axes.labelsize': 8, 'xtick.labelsize': 7.5,
        'ytick.labelsize': 7.5, 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.linewidth': .65, 'lines.linewidth': .9, 'pdf.fonttype': 42,
        'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'savefig.dpi': 300})


def save(fig, out, name):
    directory = Path(out) / 'figures'
    directory.mkdir(parents=True, exist_ok=True)
    for ext in ('png','pdf','svg'):
        fig.savefig(directory / f'{name}.{ext}', dpi=300)
    plt.close(fig)


def workflow(out=HERE):
    """Three separated lanes with one forward checkpoint-transfer connection."""
    style()
    fig = plt.figure(figsize=(7.1, 5.05))
    ax = fig.add_axes([.02, .02, .96, .96])
    ax.set(xlim=(0, 10), ylim=(0, 7.3))
    ax.axis('off')
    # Keep coordinates literal so the inline TikZ drawing uses the same geometry.
    xs = (0.15, 3.48, 6.81)
    width, height = 3.04, 1.13
    ys = (5.61, 3.18, .75)
    for y, row in zip(ys, WORKFLOW_ROWS):
        color = row['color']
        ax.text(.15, y + 1.37, row['label'], color=color, fontsize=9.1,
                fontweight='bold', ha='left', va='center')
        for x, (heading, body) in zip(xs, row['boxes']):
            box = FancyBboxPatch((x, y), width, height, boxstyle='round,pad=.045,rounding_size=.08',
                linewidth=.8, edgecolor=color, facecolor=color + '0D')
            ax.add_patch(box)
            ax.text(x + width/2, y + .84, heading, color='#182024', fontsize=7.1,
                    fontweight='bold', ha='center', va='center')
            ax.text(x + width/2, y + .30, body, color='#283238', fontsize=7.25,
                    linespacing=1.2, ha='center', va='center')
        for left, right in zip(xs[:-1], xs[1:]):
            ax.add_patch(FancyArrowPatch((left+width+.07, y+.56), (right-.07,y+.56),
                arrowstyle='-|>', mutation_scale=8.5, linewidth=.9, color=color))
        ax.text(.15, y-.28, row['note'], fontsize=7.15, color='#343c42', ha='left', va='center')
    # Source checkpoint enters only the fixed inference block. Its elbow remains
    # above lane B and does not traverse target metadata or physiology boxes.
    points = [(8.33,5.55),(8.33,4.78),(5.0,4.78),(5.0,4.39)]
    ax.plot([p[0] for p in points[:-1]], [p[1] for p in points[:-1]], color=SOURCE_COLOR, lw=.9)
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle='-|>',
                    mutation_scale=8.5, linewidth=.9, color=SOURCE_COLOR))
    ax.text(6.55, 4.99, 'Frozen source artifacts', color=SOURCE_COLOR, fontsize=7.3, ha='center', va='center')
    # No feedback is stated in words rather than a reverse arrow that could be
    # mistaken for a permitted operation.
    ax.plot([0,10],[2.52,2.52], color='#b8bcc0', lw=.65, ls=(0,(3,3)))
    ax.text(.15,.10,'BA: balanced accuracy. Fixed CAR / resampling / channel maps are operations, not target-fitted parameters.',
            fontsize=6.8, color='#454d52', ha='left', va='center')
    save(fig, out, 'figure_workflow_zero_calibration')



def load_physiology(out, analysis):
    """Read saved summaries with exact person / condition coverage checks."""
    import pandas as pd
    out, analysis = Path(out), Path(analysis)
    paths = {
        'subject': analysis/'subject_band_summary.csv',
        'laterality': analysis/'subject_hand_laterality.csv',
        'joined': analysis/'subject_physiology_performance.csv',
        'association': analysis/'descriptive_associations.csv',
        'summary': analysis/'summary.json',
        'geometry': out/'tables/q16_sensor_geometry.csv',
        'recipe': out/'evidence/q16_plot_recipe.json',
    }
    frames = {key: pd.read_csv(paths[key]) for key in ('subject','laterality','joined','association','geometry')}
    summary = json.loads(paths['summary'].read_text())
    recipe = json.loads(paths['recipe'].read_text())
    assert summary['status'] == 'fixed_BNCI_descriptive_physiology_complete'
    assert summary['new_decoder_fits'] == summary['new_decoder_inference'] == summary['new_checkpoint_inference'] == 0
    assert recipe['geometry_sha256'] == hashlib.sha256(paths['geometry'].read_bytes()).hexdigest()
    assert recipe['color_range_db'] == [-6,6] and recipe['grid']['points_per_axis'] == 161
    assert recipe['inline_TeX_display_grid']['points_per_axis'] == 41
    geometry = frames['geometry'].set_index('channel').loc[list(CHANNELS)]
    assert tuple(geometry.index) == CHANNELS and len(geometry) == 22
    subject = frames['subject']
    assert len(subject) == 1584 and not subject.duplicated(['subject','class_name','channel','band']).any()
    assert set(subject.subject) == set(range(1,10)) and set(subject.channel) == set(CHANNELS)
    assert set(subject.class_name) == {'left_hand','right_hand','feet','tongue'} and set(subject.band) == set(BANDS)
    assert (subject.n_sessions_available == 2).all() and (subject.eligibility_reason == 'eligible').all()
    assert np.isfinite(subject.equal_session_mean_trial_logratio_db).all()
    for name, expected, keys in (
        ('laterality',18,['subject','band']), ('joined',54,['subject','model','band']),
        ('association',6,['model','band'])):
        frame = frames[name]
        assert len(frame) == expected and not frame.duplicated(keys).any()
        assert (frame.eligibility_reason == 'eligible').all()
    assert set(frames['joined'].model) == {'BROAD_EEGNET','MU_BETA_SHARED','CSP4_LDA'}
    assert np.isfinite(frames['joined'].signed_laterality_db).all()
    assert frames['joined'].balanced_accuracy_mean.between(0,1).all()
    return frames, paths


def scalp_grid(geometry, values, resolution=161):
    """The frozen linear interpolator; no smoothing or scalp extrapolation."""
    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import ConvexHull
    points = geometry[['plot_x','plot_y']].to_numpy(float)
    xs = np.linspace(-1,1,resolution)
    xx,yy = np.meshgrid(xs,xs)
    field = np.asarray(LinearNDInterpolator(points,np.asarray(values,float),fill_value=np.nan)(xx,yy))
    hull = points[ConvexHull(points).vertices]
    return xx,yy,field,hull


def scalp_values(subject, band, hand):
    part = subject[(subject.band == band)&(subject.class_name == hand+'_hand')]
    assert len(part) == 9*22 and set(part.subject) == set(range(1,10))
    return part.groupby('channel').equal_session_mean_trial_logratio_db.mean().loc[list(CHANNELS)].to_numpy(float)


def draw_scalp(ax, geometry, values, title):
    from matplotlib.patches import Circle, Polygon
    xx,yy,field,hull = scalp_grid(geometry,values)
    image = ax.pcolormesh(xx,yy,np.ma.masked_invalid(field),cmap='RdBu_r',
                         vmin=-COLOR_LIMIT_DB,vmax=COLOR_LIMIT_DB,shading='nearest',rasterized=False)
    clip=Polygon(hull,closed=True,transform=ax.transData)
    image.set_clip_path(clip)
    ax.add_patch(Circle((0,0),1,fill=False,color='#596067',lw=.7))
    ax.plot([-.11,0,.11],[.992,1.10,.992],color='#596067',lw=.7)
    ax.plot([-.995,-1.045,-1.05,-.995],[-.13,-.09,.09,.13],color='#596067',lw=.7)
    ax.plot([.995,1.045,1.05,.995],[-.13,-.09,.09,.13],color='#596067',lw=.7)
    ax.scatter(geometry.plot_x,geometry.plot_y,s=5,facecolors='none',edgecolors='#202020',lw=.4,zorder=3)
    for channel in ('C3','Cz','C4'):
        p=geometry.loc[channel]
        ax.text(p.plot_x,p.plot_y+.05,channel,fontsize=6.2,ha='center',va='bottom',zorder=4,
                bbox={'facecolor':'white','edgecolor':'none','pad':.12,'alpha':.72})
    ax.set(xlim=(-1.1,1.1),ylim=(-1.07,1.14),aspect='equal',title=title)
    ax.axis('off')
    return image, {'sensor_values_outside_fixed_color_range':int(np.sum(np.abs(values)>COLOR_LIMIT_DB)),
                   'finite_grid_values':int(np.isfinite(field).sum()),
                   'grid_values_outside_fixed_color_range':int(np.sum(np.abs(field[np.isfinite(field)])>COLOR_LIMIT_DB)),
                   'sensor_value_min_db':float(np.min(values)), 'sensor_value_max_db':float(np.max(values))}


def central_profiles(subject, band):
    return {hand:np.array([[float(subject[(subject.subject==person)&(subject.class_name==hand+'_hand')&
                                         (subject.band==band)&(subject.channel==channel)].iloc[0].equal_session_mean_trial_logratio_db)
                            for channel in ('C3','Cz','C4')] for person in range(1,10)]) for hand in HANDS}


def profile_limits(subject):
    data=np.concatenate([v.ravel() for band in BANDS for v in central_profiles(subject,band).values()])
    return min(-8.0,float(np.floor(data.min()))-1),max(4.0,float(np.ceil(data.max()))+1)


def physiology_main(out,frames):
    from matplotlib.lines import Line2D
    subject,geometry=frames['subject'],frames['geometry'].set_index('channel').loc[list(CHANNELS)]
    style()
    fig=plt.figure(figsize=(7.1,5.45))
    report={}
    for column,(band,hand) in enumerate((('mu','left'),('mu','right'),('beta','left'),('beta','right'))):
        ax=fig.add_axes([.022+column*.223,.57,.200,.34])
        band_label='μ (8–13 Hz)' if band=='mu' else 'β (13–30 Hz)'
        image,clip=draw_scalp(ax,geometry,scalp_values(subject,band,hand),
                            f"{'ABCD'[column]}  {band_label}\n{hand.capitalize()}-hand imagery")
        report[f'{band}_{hand}']=clip
    cax=fig.add_axes([.917,.60,.012,.23]);cbar=fig.colorbar(image,cax=cax)
    cbar.set_ticks([-6,-3,0,3,6]);cbar.ax.tick_params(labelsize=6.5,pad=1)
    cbar.set_label('Task / baseline (dB)',fontsize=7,labelpad=1)
    colors={'left':'#287681','right':'#ac5d28'};markers={'left':'o','right':'^'}
    for column,band in enumerate(BANDS):
        ax=fig.add_axes([.085+column*.485,.13,.395,.33])
        profiles=central_profiles(subject,band)
        for hand,offset in (('left',-.045),('right',.045)):
            x=np.arange(3)+offset
            for row in profiles[hand]:
                ax.plot(x,row,color=colors[hand],alpha=.26,linewidth=.6,marker=markers[hand],markersize=2.2)
            ax.plot(x,profiles[hand].mean(axis=0),color=colors[hand],linewidth=1.7,marker=markers[hand],
                    markersize=4.2,label=hand.capitalize()+' hand')
        ax.axhline(0,color='#646b6f',ls=':',lw=.7)
        ax.set(xticks=[0,1,2],xticklabels=['C3','Cz','C4'],xlim=(-.25,2.25),ylim=profile_limits(subject),
               title=f"{'EF'[column]}  {'μ' if band=='mu' else 'β'} sensorimotor profiles",
               ylabel='Task / baseline (dB)' if column==0 else None)
        ax.grid(axis='y',color='#e5e5e5',lw=.45)
        if column==1:ax.legend(frameon=False,fontsize=7.2,loc='lower left',ncol=2,handlelength=1.4,columnspacing=1)
    fig.text(.035,.515,'Maps: equal-participant means; white areas are outside the 22-sensor convex hull. Template sensor geometry.',fontsize=7.1)
    fig.text(.085,.052,'Thin lines: all 9 participants; thick lines: participant means. Negative: lower task power. Positive: higher task power.',fontsize=7.1)
    fig.text(.085,.023,'Fixed baseline −1.5 to −0.5 s; imagery +0.5 to +2.5 s relative to cue. No decoder fitting.',fontsize=7.1)
    save(fig,out,'figure_q16_bnci_physiology')
    return report


MODEL_LABELS={'BROAD_EEGNET':'Broad EEGNet','MU_BETA_SHARED':'Shared μ/β','CSP4_LDA':'CSP4 + LDA'}
MODEL_COLORS={'BROAD_EEGNET':'#287681','MU_BETA_SHARED':'#ac5d28','CSP4_LDA':'#676e74'}



def label_offsets(xs,ys,xlim,ylim):
    """Greedy display-only ID placement; no observation is selected or moved."""
    points=np.column_stack([(np.asarray(xs)-xlim[0])/(xlim[1]-xlim[0])*141,
                            (np.asarray(ys)-ylim[0])/(ylim[1]-ylim[0])*113])
    placed=[];offsets=[]
    candidates=((3,3),(3,-10),(-9,3),(-9,-10),(8,7),(8,-13),(-14,7),(-14,-13))
    def overlap(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
    for index,(x,y) in enumerate(points):
        chosen=candidates[0]
        for dx,dy in candidates:
            box=(x+dx,y+dy,x+dx+5,y+dy+7)
            point_boxes=[(px-3,py-3,px+3,py+3) for j,(px,py) in enumerate(points) if j!=index]
            if not any(overlap(box,b) for b in placed+point_boxes):
                chosen=(dx,dy);break
        dx,dy=chosen;placed.append((x+dx,y+dy,x+dx+5,y+dy+7));offsets.append(chosen)
    return offsets


def physiology_associations(out,frames):
    style()
    joined,stats=frames['joined'],frames['association']
    fig,axes=plt.subplots(2,3,figsize=(7.1,5.15),sharey=True,sharex=True)
    xmin=min(-.25,float(np.floor(joined.signed_laterality_db.min()*2)/2)-.25)
    xmax=max(.25,float(np.ceil(joined.signed_laterality_db.max()*2)/2)+.25)
    ymin=min(40,float(np.floor(joined.balanced_accuracy_mean.min()*100/10)*10))
    ymax=max(100,float(np.ceil(joined.balanced_accuracy_mean.max()*100/10)*10))
    for row,band in enumerate(BANDS):
        for col,model in enumerate(MODEL_LABELS):
            ax=axes[row,col]
            data=joined[(joined.band==band)&(joined.model==model)].sort_values('subject')
            assoc=stats[(stats.band==band)&(stats.model==model)].iloc[0]
            x=data.signed_laterality_db.to_numpy(float);y=data.balanced_accuracy_mean.to_numpy(float)*100
            ax.scatter(x,y,s=22,facecolors=MODEL_COLORS[model],edgecolors='white',lw=.45,zorder=3)
            for i,a,b,offset in zip(data.subject,x,y,label_offsets(x,y,(xmin,xmax),(ymin,ymax))):
                ax.annotate(str(i),(a,b),xytext=offset,textcoords='offset points',fontsize=6.5,ha='left',va='bottom')
            ax.axvline(0,color='#72777b',ls=':',lw=.65)
            ax.axhline(50,color='#72777b',ls=':',lw=.65)
            ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax),title=f"{'ABCDEF'[row*3+col]}  {MODEL_LABELS[model]}: {'μ' if band=='mu' else 'β'}")
            ax.grid(color='#e5e5e5',lw=.4)
            ax.text(.035,.96,f"Spearman ρ = {float(assoc.spearman_rho):+.3f}",transform=ax.transAxes,fontsize=7.2,va='top')
            if col==0:ax.set_ylabel('Saved binary LOSO BA (%)')
            if row==1:ax.set_xlabel('Signed C3 / C4 laterality (dB)')
    fig.subplots_adjust(left=.085,right=.99,top=.935,bottom=.19,wspace=.15,hspace=.40)
    fig.text(.085,.085,'Each panel shows the same 9 participants. BA: mean of three frozen seeds (CSP: one fit).',fontsize=7)
    fig.text(.085,.045,'Negative laterality: lower contralateral than ipsilateral log-ratio; no causal interpretation or p-values.',fontsize=7)
    save(fig,out,'figureS_q16_physiology_associations')
    return {'scatter_points':54,'distinct_participants':9,'statistic':'descriptive Spearman correlation, all six model/band pairs','p_values':False,'fit_lines':False}


def render_physiology(out,analysis):
    out,analysis=Path(out),Path(analysis)
    frames,paths=load_physiology(out,analysis)
    clips=physiology_main(out,frames)
    associations=physiology_associations(out,frames)
    names=('figure_workflow_zero_calibration','figure_q16_bnci_physiology','figureS_q16_physiology_associations')
    record={'schema_version':1,'status':'rendered_pending_independent_visual_inspection',
            'input_sha256':{str(p.relative_to(out)) if p.is_relative_to(out) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
            'artifact_sha256':{f'figures/{n}.{e}':hashlib.sha256((out/'figures'/f'{n}.{e}').read_bytes()).hexdigest() for n in names for e in ('png','pdf','svg')},
            'scalp_maps':clips,'central_profile_points':108,'central_profiles_distinct_people':9,
            'association_figure':associations,'display_grid':{'PNG_PDF_SVG':161,'standalone_inline_TeX':41},
            'fixed_color_limits_db':[-6,6],'new_model_fits':0,'new_predictions':0}
    (out/'evidence/figures_q16.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE)
    parser.add_argument('--analysis', type=Path)
    parser.add_argument('--workflow-only', action='store_true')
    args = parser.parse_args()
    workflow(args.out)
    if args.analysis is not None and not args.workflow_only:
        render_physiology(args.out, args.analysis)
    print(json.dumps({'workflow_rendered': True, 'physiology_rendered': args.analysis is not None and not args.workflow_only,
                      'new_model_fits': 0, 'new_predictions': 0}))


if __name__ == '__main__':
    main()
