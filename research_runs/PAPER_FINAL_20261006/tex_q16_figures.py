"""Standalone TikZ counterparts for the workflow and Q16 figures.

Every plotted observation is embedded into the returned TeX. No external
image file is required. This module never computes EEG power or predictions.
"""
from pathlib import Path
from build_q16_figures import WORKFLOW_ROWS


def _escape(value):
    return value.replace('&',r'\&').replace('%',r'\%').replace('μ',r'$\mu$').replace('β',r'$\beta$').replace('×',r'$\times$').replace('→',r'$\rightarrow$')


def workflow_tex():
    colors = ('q16Source','q16Target','q16Physio')
    text = ''.join(r'\definecolor{'+c+'}{HTML}{'+row['color'][1:].upper()+'}\n' for c,row in zip(colors,WORKFLOW_ROWS))
    text = text.replace('}\\n','}\n')
    text += r'\begin{tikzpicture}[x=1.7cm,y=1.6cm,font=\scriptsize]'+'\n'
    text += r'\path[use as bounding box] (0,0) rectangle (10,7.3);'+'\n'
    xs, ys = (.15,3.48,6.81),(5.61,3.18,.75)
    for y,row,color in zip(ys,WORKFLOW_ROWS,colors):
        text += r'\node[anchor=west,text='+color+r',font=\small\bfseries] at (.15,'+str(y+1.37)+') {'+_escape(row['label'])+'};\n'
        for x,(head,body) in zip(xs,row['boxes']):
            text += r'\draw[rounded corners=2pt,draw='+color+r',fill='+color+r'!5,line width=.45pt] ('+str(x)+','+str(y)+') rectangle ('+str(x+3.04)+','+str(y+1.13)+');\n'
            text += r'\node[align=center,font=\scriptsize\bfseries] at ('+str(x+1.52)+','+str(y+.84)+') {'+_escape(head)+'};\n'
            text += r'\node[align=center,font=\scriptsize] at ('+str(x+1.52)+','+str(y+.39)+') {'+_escape(body).replace('\n',r'\\')+'};\n'
        for x,right in zip(xs[:-1],xs[1:]):
            text += r'\draw[->,draw='+color+r',line width=.5pt] ('+str(x+3.11)+','+str(y+.56)+') -- ('+str(right-.07)+','+str(y+.56)+');\n'
        text += r'\node[anchor=west,font=\scriptsize] at (.15,'+str(y-.28)+') {'+_escape(row['note'])+'};\n'
    text += r'\draw[->,draw=q16Source,line width=.5pt] (8.33,5.55) -- (8.33,4.78) -- (5,4.78) -- (5,4.39);'+'\n'
    text += r'\node[text=q16Source,font=\scriptsize] at (6.55,4.99) {Frozen source artifacts};'+'\n'
    text += r'\draw[gray!50,dashed,line width=.4pt] (0,2.52) -- (10,2.52);'+'\n'
    text += r'\node[anchor=west,font=\tiny] at (.15,.10) {BA: balanced accuracy. Fixed CAR / resampling / channel maps are operations, not target-fitted parameters.};'+'\n'
    return text+r'\end{tikzpicture}'+'\n'



def _analysis_dir(out):
    out=Path(out)
    local=out/'evidence/q16_analysis'
    return local if (local/'summary.json').is_file() else out.parent/'Q16-P001-BNCI-20261006'


def _coord(xs,ys):
    return ' '.join(f'({float(x):.10f},{float(y):.10f})' for x,y in zip(xs,ys))


def _rgb(db):
    import matplotlib as mpl
    r,g,b,_=mpl.colormaps['RdBu_r']((max(-6,min(6,float(db)))+6)/12)
    return '{rgb,1:red,'+f'{r:.6f}'+';green,'+f'{g:.6f}'+';blue,'+f'{b:.6f}'+'}'


def scalp_tex(geometry,values,cx,cy,title):
    import numpy as np
    from build_q16_figures import scalp_grid
    xx,yy,field,hull=scalp_grid(geometry,values,resolution=41)
    txt=r'\begin{scope}[shift={('+str(cx)+','+str(cy)+')},scale=1.45]'+'\n'
    txt+=r'\begin{scope}'+'\n'+r'\clip '+' -- '.join(f'({x:.10f},{y:.10f})' for x,y in hull)+r' -- cycle;'+'\n'
    half=.025
    for i,j in zip(*np.where(np.isfinite(field))):
        x,y,v=float(xx[i,j]),float(yy[i,j]),float(field[i,j])
        txt+=r'\fill[fill='+_rgb(v)+',draw=none] '+f'({x-half:.8f},{y-half:.8f}) rectangle ({x+half:.8f},{y+half:.8f});\n'
    txt+=r'\end{scope}'+'\n'
    txt+=r'\draw[gray!70,line width=.4pt] (0,0) circle (1);'+'\n'
    txt+=r'\draw[gray!70,line width=.4pt] (-.11,.992) -- (0,1.10) -- (.11,.992);'+'\n'
    txt+=r'\draw[gray!70,line width=.4pt] (-.995,-.13) -- (-1.045,-.09) -- (-1.05,.09) -- (-.995,.13);'+'\n'
    txt+=r'\draw[gray!70,line width=.4pt] (.995,-.13) -- (1.045,-.09) -- (1.05,.09) -- (.995,.13);'+'\n'
    for name,row in geometry.iterrows():
        txt+=r'\draw[black,line width=.25pt] '+f'({row.plot_x:.10f},{row.plot_y:.10f}) circle (.012);\n'
        if name in ('C3','Cz','C4'):
            txt+=r'\node[font=\tiny,fill=white,fill opacity=.7,text opacity=1,inner sep=.3pt,anchor=south] at '+f'({row.plot_x:.10f},{row.plot_y+.05:.10f})'+' {'+name+'};\n'
    txt+=r'\node[font=\scriptsize,align=center] at (0,1.40) {'+title+'};\n'
    return txt+r'\end{scope}'+'\n'


def physiology_tex(out):
    import numpy as np
    from build_q16_figures import (load_physiology,CHANNELS,scalp_values,central_profiles,profile_limits)
    frames,_=load_physiology(out,_analysis_dir(out))
    subject=frames['subject'];geometry=frames['geometry'].set_index('channel').loc[list(CHANNELS)]
    text=r'\definecolor{q16Left}{HTML}{287681}'+'\n'+r'\definecolor{q16Right}{HTML}{AC5D28}'+'\n'
    text+=r'\begin{tikzpicture}[x=1cm,y=1cm,font=\scriptsize]'+'\n'
    text+=r'\path[use as bounding box] (0,0) rectangle (18.3,12.8);'+'\n'
    panels=(('mu','left'),('mu','right'),('beta','left'),('beta','right'))
    for j,(band,hand) in enumerate(panels):
        title=f"{'ABCD'[j]}: "+(r'$\mu$ (8--13 Hz)' if band=='mu' else r'$\beta$ (13--30 Hz)')+r'\\'+hand.capitalize()+'-hand imagery'
        text+=scalp_tex(geometry,scalp_values(subject,band,hand),2.05+j*4.05,9.82,title)
    # A literal RGB color scale matches matplotlib's fixed diverging map.
    for j in range(96):
        y=8.5+j/96*2.55;v=-6+(j+.5)/96*12
        text+=r'\fill[fill='+_rgb(v)+',draw=none] '+f'(17.45,{y:.8f}) rectangle (17.65,{y+2.55/96:.8f});\n'
    for v in (-6,-3,0,3,6):
        y=8.5+(v+6)/12*2.55
        text+=r'\node[anchor=west,font=\tiny] at '+f'(17.67,{y:.8f})'+' {'+str(v)+'};\n'
    text+=r'\node[rotate=90,font=\tiny] at (18.15,9.78) {Task / baseline (dB)};'+'\n'
    text+=r'\node[anchor=west,font=\scriptsize] at (.35,7.55) {Maps: equal-participant means; white areas are outside the 22-sensor convex hull. Template sensor geometry.};'+'\n'
    low,high=profile_limits(subject)
    for j,band in enumerate(('mu','beta')):
        text+=r'\begin{axis}[at={('+str(1+j*8.75)+r'cm,1.5cm)},anchor=south west,width=7.7cm,height=4.9cm,'
        text+=r'xmin=-.25,xmax=2.25,ymin='+str(low)+',ymax='+str(high)+r',xtick={0,1,2},xticklabels={C3,Cz,C4},'
        text+=r'axis lines=left,tick align=outside,ymajorgrids,grid style={gray!20},title style={font=\scriptsize},label style={font=\scriptsize},tick label style={font=\scriptsize},'
        text+='title={'+('E: ' if j==0 else 'F: ')+(r'$\mu$' if band=='mu' else r'$\beta$')+' sensorimotor profiles},'
        if j==0:text+=r'ylabel={Task / baseline (dB)},'
        text+=r'legend columns=2,legend style={font=\tiny,draw=none,fill=none,at={(.03,.04)},anchor=south west}]'+'\n'
        text+=r'\addplot[gray,densely dotted,no marks,forget plot] coordinates {(-.25,0) (2.25,0)};'+'\n'
        profiles=central_profiles(subject,band)
        for hand,offset,color,mark in (('left',-.045,'q16Left','*'),('right',.045,'q16Right','triangle*')):
            x=np.arange(3)+offset
            for row in profiles[hand]:
                text+=r'\addplot[color='+color+r',opacity=.26,line width=.3pt,mark='+mark+r',mark size=.85pt,forget plot] coordinates {'+_coord(x,row)+'};\n'
            text+=r'\addplot[color='+color+r',line width=.85pt,mark='+mark+r',mark size=1.6pt] coordinates {'+_coord(x,profiles[hand].mean(axis=0))+'};\n'
            text+=r'\addlegendentry{'+hand.capitalize()+' hand}\n'
        text+=r'\end{axis}'+'\n'
    text+=r'\node[anchor=west,font=\scriptsize] at (1,.70) {Thin lines: all 9 participants; thick lines: participant means. Negative: lower task power. Positive: higher task power.};'+'\n'
    text+=r'\node[anchor=west,font=\scriptsize] at (1,.25) {Fixed baseline $-1.5$ to $-0.5$ s; imagery $+0.5$ to $+2.5$ s relative to cue. No decoder fitting.};'+'\n'
    return text+r'\end{tikzpicture}'+'\n'


def associations_tex(out):
    import numpy as np
    from build_q16_figures import load_physiology,label_offsets
    frames,_=load_physiology(out,_analysis_dir(out));joined=frames['joined'];stats=frames['association']
    xmin=min(-.25,float(np.floor(joined.signed_laterality_db.min()*2)/2)-.25)
    xmax=max(.25,float(np.ceil(joined.signed_laterality_db.max()*2)/2)+.25)
    ymin=min(40,float(np.floor(joined.balanced_accuracy_mean.min()*100/10)*10))
    ymax=max(100,float(np.ceil(joined.balanced_accuracy_mean.max()*100/10)*10))
    text=r'\definecolor{q16Broad}{HTML}{287681}'+'\n'+r'\definecolor{q16Shared}{HTML}{AC5D28}'+'\n'+r'\definecolor{q16Csp}{HTML}{676E74}'+'\n'
    text+=r'\begin{tikzpicture}[font=\scriptsize]'+'\n'
    text+=r'\begin{groupplot}[group style={group size=3 by 2,horizontal sep=.62cm,vertical sep=1.35cm},width=.31\linewidth,height=4.1cm,'
    text+=r'axis lines=left,tick align=outside,grid=major,grid style={gray!20},clip=false,title style={font=\scriptsize},label style={font=\scriptsize},tick label style={font=\scriptsize},'
    text+='xmin='+str(xmin)+',xmax='+str(xmax)+',ymin='+str(ymin)+',ymax='+str(ymax)+']\n'
    models=(('BROAD_EEGNET','Broad EEGNet','q16Broad'),('MU_BETA_SHARED',r'Shared $\mu/\beta$','q16Shared'),('CSP4_LDA','CSP4 + LDA','q16Csp'))
    for row,band in enumerate(('mu','beta')):
        for col,(model,label,color) in enumerate(models):
            text+=r'\nextgroupplot[title={'+f"{'ABCDEF'[row*3+col]}: "+label+': '+(r'$\mu$' if band=='mu' else r'$\beta$')+'}'
            if col==0:text+=r',ylabel={Saved binary LOSO BA (\%)}'
            if row==1:text+=r',xlabel={Signed C3/C4 laterality (dB)}'
            text+=']\n'
            data=joined[(joined.band==band)&(joined.model==model)].sort_values('subject')
            assoc=stats[(stats.band==band)&(stats.model==model)].iloc[0]
            x=data.signed_laterality_db.to_numpy(float);y=data.balanced_accuracy_mean.to_numpy(float)*100
            text+=r'\addplot[gray,densely dotted,no marks,forget plot] coordinates {'+_coord([0,0],[ymin,ymax])+'};\n'
            text+=r'\addplot[gray,densely dotted,no marks,forget plot] coordinates {'+_coord([xmin,xmax],[50,50])+'};\n'
            text+=r'\addplot[color='+color+r',only marks,mark=*,mark size=1.7pt] coordinates {'+_coord(x,y)+'};\n'
            for person,a,b,(dx,dy) in zip(data.subject,x,y,label_offsets(x,y,(xmin,xmax),(ymin,ymax))):
                text+=r'\node[anchor=south west,font=\tiny,xshift='+str(dx)+'pt,yshift='+str(dy)+'pt] at (axis cs:'+f'{a:.10f},{b:.10f}'+') {'+str(person)+'};\n'
            text+=r'\node[anchor=north west,font=\scriptsize] at (axis description cs:.035,.96) {Spearman $\rho='+f'{float(assoc.spearman_rho):+.3f}'+'$};\n'
    text+=r'\end{groupplot}'+'\n'
    text+=r'\node[anchor=north west,font=\scriptsize,align=left] at (current bounding box.south west) {Each panel: the same 9 participants. BA: three frozen seeds (CSP: one fit).\\Negative laterality: lower contralateral than ipsilateral log-ratio; no causal interpretation or $p$-values.};'+'\n'
    return text+r'\end{tikzpicture}'+'\n'


def tex_inline_figure(name: str, out: Path, numbers=None) -> str:
    """Preserve the manuscript exporter's name / directory / optional-data API."""
    del numbers
    if name == 'figure_workflow_zero_calibration':
        return workflow_tex()
    if name == 'figure_q16_bnci_physiology':
        return physiology_tex(out)
    if name == 'figureS_q16_physiology_associations':
        return associations_tex(out)
    raise ValueError(f'Unknown Q16 figure: {name}')
