"""Self-contained numerical TeX versions of every publication figure panel."""
import numpy as np
import pandas as pd
from matplotlib import colormaps

def tex_inline_figure(name, out, numbers):
    internal=pd.read_csv(out/'tables/internal_subjects.csv')
    external=pd.read_csv(out/'tables/external_subjects.csv')
    def coordinates(xs,ys):
        return ' '.join(f'({float(x):.8f},{float(y):.8f})' for x,y in zip(xs,ys))
    def plot(xs,ys,options):
        return r'\addplot['+options+'] coordinates {'+coordinates(xs,ys)+'};\n'
    def legend(text):return r'\addlegendentry{'+text+'}\n'
    def chance(y,x0,x1):return plot([x0,x1],[y,y],'gray,dotted,no marks,forget plot')
    def node(text):return r'\node[anchor=north west,align=left,font=\tiny] at (axis description cs:0.02,0.98) {'+text+'};\n'
    def group_start(n,width,height):
        return '\\begin{tikzpicture}\n\\begin{groupplot}[group style={group size='+str(n)+' by 1,horizontal sep=0.7cm},width='+width+',height='+height+r',font=\scriptsize,legend style={font=\tiny,draw=none,fill=none},axis lines=left,tick align=outside]'+'\n'
    def next_axis(options):return '\\nextgroupplot['+options+']\n'
    def finish():return '\\end{groupplot}\n\\end{tikzpicture}\n'
    if name=='figure1_selection_and_s3':
        s=group_start(3,r'.30\linewidth','4.3cm')
        s+=next_axis(r'title={A: Source-selected epochs},xlabel={Participant},ylabel={Epochs},xmin=.7,xmax=9.3,ymin=0,ymax=40,xtick={1,2,3,4,5,6,7,8,9},legend pos=north east')
        s+=plot(internal.subject,internal.q5_epoch,'gray,mark=*')+legend('Mean CE')
        s+=plot(internal.subject,internal.q8_epoch,'blue,mark=square*')+legend('Mean rank')
        s+=next_axis(r'title={B: Four-class LOSO},xlabel={Participant},ylabel={BA (\%)},xmin=.7,xmax=9.3,ymin=20,ymax=80,xtick={1,2,3,4,5,6,7,8,9},legend pos=north east')
        for column,color,label,marker in [('q5_ba','gray','Mean CE','*'),('q8_ba','blue','Mean rank','square*'),('shared_ba','orange','Shared','triangle*')]:
            s+=plot(internal.subject,100*internal[column],f'{color},mark={marker}')+legend(label)
        s+=chance(25,.7,9.3)
        s+=next_axis(r'title={C: S3 diagnostic},xlabel={Fixed epochs},ylabel={BA (\%)},xmin=-.5,xmax=1.5,ymin=0,ymax=80,xtick={0,1},xticklabels={2,16},legend pos=north west')
        cells=numbers['q7_cells']
        for normal,color,shift,label in [(False,'gray','-4pt','Raw'),(True,'green!60!black','4pt','SourceNorm')]:
            values=[next(r for r in cells if bool(r['normalization'])==normal and int(r['fixed_epochs'])==epoch) for epoch in [2,16]]
            coords=' '.join(f'({i},{100*r["BA_mean"]:.8f}) +- (0,{100*r["BA_seed_std"]:.8f})' for i,r in enumerate(values))
            s+=r'\addplot[ybar,bar width=7pt,bar shift='+shift+',fill='+color+',draw='+color+r',error bars/.cd,y dir=both,y explicit] coordinates {'+coords+'};\n'+legend(label)
        s+=chance(25,-.5,1.5)
        return s+finish()
    if name=='figure2_source_count_and_runtime':
        count=pd.read_csv(out.parents[1]/'results/Q13-E006/postrun_statistics/source_count_trajectories.csv')
        s=group_start(2,r'.46\linewidth','5.1cm')
        s+=next_axis(r'title={A: Source-count sensitivity},xlabel={Source participants},ylabel={Four-class BA (\%)},xmin=1.7,xmax=8.3,ymin=20,ymax=80,xtick={2,4,6,8},legend pos=north west')
        for method,color,label in [('Q8_BROAD','blue','Broad'),('Q9_MU_BETA_SHARED','orange','Shared')]:
            d=count[count.method.eq(method)]
            for _,person in d.groupby('target'):
                person=person.sort_values('source_count')
                s+=plot(person.source_count,100*person.balanced_accuracy,color+',opacity=.18,no marks,forget plot')
            means=d.groupby('source_count').balanced_accuracy.mean()
            assert list(means.index)==[2,4,6,8]
            s+=plot(means.index,100*means,color+',thick,mark=*')+legend(label)
        s+=chance(25,1.7,8.3)
        s+=next_axis(r'title={B: Matched-runtime duration},xlabel={Participant},ylabel={Fixed20 minus historical CE (pp)},xmin=.5,xmax=9.5,ymin=-5,ymax=57,xtick={1,2,3,4,5,6,7,8,9}')
        delta=100*(internal.fixed20_ba-internal.matched_ce_ba)
        for color,mask in [('blue',delta>=0),('orange',delta<0)]:
            s+=plot(internal.subject[mask],delta[mask],color+',fill='+color+'!65,ybar,bar width=11pt')
        s+=chance(0,.5,9.5)
        c=numbers['q13_matched_contrast'];lo=-100*c['subject_bootstrap_95ci_high'];hi=-100*c['subject_bootstrap_95ci_low']
        s+=node(f'Mean {delta.mean():+.2f} pp'+r'\\'+f'95\\% CI [{lo:+.2f}, {hi:+.2f}]'+r'\\'+f'Exact sign-flip p = {c["exact_sign_flip_p_exploratory"]:.3f}')
        return s+finish()
    if name=='figure3_external_primary':
        s=group_start(2,r'.46\linewidth','5.1cm')
        s+=next_axis(r'title={A: Binary external transfer},xlabel={Subject BA (\%)},ylabel={Cumulative fraction},xmin=25,xmax=100,ymin=0,ymax=1,legend pos=north west')
        for column,color,label in [('BROAD_EEGNET_BA','blue','Broad'),('MU_BETA_SHARED_BA','orange','Shared'),('CSP4_LDA_BA','gray','CSP4 + LDA')]:
            y=np.sort(external[column].to_numpy()*100)
            s+=plot(y,np.arange(1,len(y)+1)/len(y),color+',no marks,const plot')+legend(label)
        s+=plot([50,50],[0,1],'gray,dotted,no marks,forget plot')
        s+=next_axis(r'title={B: Frozen primary contrast},xlabel={Shared minus broad (pp)},ylabel={Participants},xmin=-15,xmax=15,ymin=0,ymax=27')
        delta=100*external.primary_difference_shared_minus_broad.to_numpy()
        frequencies,edges=np.histogram(delta,bins=np.linspace(-15,15,25))
        assert frequencies.sum()==109
        s+=plot(edges,list(frequencies)+[0],'ybar interval,fill=orange!80,draw=white')
        s+=plot([0,0],[0,27],'gray,no marks,forget plot')
        s+=plot([delta.mean(),delta.mean()],[0,27],'blue,dashed,thick,no marks,forget plot')
        c=numbers['q14_primary'];lo,hi=[100*v for v in c['subject_bootstrap_percentile_95_ci']]
        s+=node(f'Mean {delta.mean():+.3f} pp'+r'\\'+f'95\\% CI [{lo:+.3f}, {hi:+.3f}]'+r'\\'+f'Sign-test p = {c["two_sided_exact_sign_test_p_excluding_ties"]:.4f}')
        return s+finish()
    assert name=='figureS1_robustness_heterogeneity',name
    robustness=pd.read_csv(out.parents[1]/'results/Q12-BATCH/subject_level_metrics.csv')
    order=[('SOURCE_POOLED_WHITEN','Source-pooled whitening'),('SOURCE_BALANCED_ERM','Source-balanced ERM'),('SOURCE_GROUP_DRO','GroupDRO vs balanced ERM'),('CHANNEL_DROPOUT','Channel dropout'),('GAIN_PERTURB','Gain perturbation'),('CHANNEL_AND_GAIN','Dropout + gain')]
    baseline=internal.set_index('subject').q8_ba.sort_index()
    balanced=robustness[robustness.condition.eq('SOURCE_BALANCED_ERM')].set_index('subject').balanced_accuracy_mean.sort_index()
    matrix=[]
    for key,_ in order:
        values=robustness[robustness.condition.eq(key)].set_index('subject').balanced_accuracy_mean.sort_index()
        assert values.index.tolist()==list(range(1,10))
        matrix.append(100*(values-(balanced if key=='SOURCE_GROUP_DRO' else baseline)).to_numpy())
    matrix=np.array(matrix);limit=np.abs(matrix).max();cmap=colormaps['RdBu']
    s=r'\resizebox{.96\linewidth}{!}{\begin{tikzpicture}[x=.68cm,y=.68cm,font=\small]'+'\n'
    for i,(_,label) in enumerate(order):
        s+=r'\node[anchor=east] at (-.15,'+f'{5-i+.5}'+') {'+label+'};\n'
        for j in range(9):
            value=matrix[i,j];r,g,b,_=cmap((value+limit)/(2*limit))
            name=f'cell{i}{j}';s+=r'\definecolor{'+name+'}{rgb}{'+f'{r:.6f},{g:.6f},{b:.6f}'+'}\n'
            s+=r'\fill['+name+'] '+f'({j},{5-i}) rectangle ({j+1},{6-i});\n'
            text_color='white' if abs(value)>.65*limit else 'black'
            s+=r'\node[text='+text_color+'] at '+f'({j+.5},{5-i+.5})'+' {'+f'{value:+.1f}'+'};\n'
    for j in range(9):s+=r'\node at '+f'({j+.5},-.35)'+' {S'+str(j+1)+'};\n'
    s+=r'\node at (4.5,-.85) {Held-out participant};'+'\n'
    for i in range(60):
        r,g,b,_=cmap(i/59);name=f'legend{i}'
        s+=r'\definecolor{'+name+'}{rgb}{'+f'{r:.6f},{g:.6f},{b:.6f}'+'}\n'
        s+=r'\fill['+name+'] '+f'(9.4,{6*i/60:.6f}) rectangle (9.7,{6*(i+1)/60:.6f});\n'
    for value in [-limit,0,limit]:
        y=3*(value/limit+1);s+=r'\node[anchor=west] at '+f'(9.85,{y:.6f})'+' {'+f'{value:+.1f}'+'};\n'
    s+=r'\node[rotate=90] at (11,3) {BA difference (pp)};'+'\n'
    return s+r'\end{tikzpicture}}'+'\n'
