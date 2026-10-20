#!/usr/bin/env python3
"""Re-render Figure 1 changing only critique-identified panel F wording."""
from pathlib import Path
import importlib.util, hashlib, json, re, subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research_runs/PAPER1_PLOS_FINAL_20261018/scripts/legacy_figure_renderer.py'
OUT=ROOT/'research_runs/PAPER1_REVIEW_20261020/figures'
OUT.mkdir(parents=True,exist_ok=True)
source=SRC.read_text(encoding='utf-8')
updates={
 'F   Evidence checks with defined scope':'F   Reproducibility resources',
 'Source identities / contracts / checkpoint and selector bindings':'Input identities / processing / source checkpoint selections',
 'Saved predictions → participant metrics → four frozen contrasts':'Saved predictions to participant metrics and paired comparisons',
 '1,179 external arithmetic checks passed; no checkpoint-forward replay':'Supporting tables, scripted checks and scope details in S1 Appendix',
}
for a,b in updates.items():
    assert source.count(a)==1,(a,source.count(a))
    source=source.replace(a,b)
spec=importlib.util.spec_from_loader('isolated_original_fig1',loader=None)
m=importlib.util.module_from_spec(spec)
m.__file__=str(SRC)
exec(compile(source,str(SRC),'exec'),m.__dict__)
plt.rcParams.update({'font.family':'serif','font.serif':['Times'],'font.size':9,
 'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,
 'legend.fontsize':8,'pdf.use14corefonts':True,'ps.useafm':True,
 'svg.fonttype':'none','axes.unicode_minus':False,'savefig.facecolor':'white'})
def save_only_fig1(fig,stem):
    assert stem=='Fig1_workflow'
    for t in fig.findobj(match=Text):
        t.set_text(t.get_text().translate(str.maketrans({'μ':'mu','β':'beta','→':'to','−':'-','≥':'>=','≤':'<='})))
        t.set_fontfamily('serif');t.set_fontname('Times')
    eps=OUT/(stem+'.eps')
    fig.savefig(eps,format='eps',facecolor='white')
    fig.savefig(OUT/(stem+'.pdf'),format='pdf',facecolor='white')
    subprocess.run(['gs','-q','-dSAFER','-dBATCH','-dNOPAUSE','-dEPSCrop',
     '-sDEVICE=png16m','-r300','-dTextAlphaBits=4','-dGraphicsAlphaBits=4',
     '-sOutputFile='+str(OUT/(stem+'.png')),str(eps)],check=True,timeout=45)
    body=eps.read_text('latin1')
    fonts=sorted(set(re.findall(r'/(\S+) [\d.]+ selectfont',body)))
    assert fonts and all(x.startswith('Times-') or x=='Symbol' for x in fonts),fonts
    assert eps.stat().st_size<10_000_000
    with Image.open(OUT/(stem+'.png')) as im:
        assert im.width>1000 and im.height>1000
    plt.close(fig)
m.save=save_only_fig1
m.workflow()
r={'status':'PASS','scope':'Figure 1 panel F label only',
  'source_renderer_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),
  'text_substitutions':updates,'other_panels_untouched':True,'no_new_data':True,
  'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir()}}
(OUT/'Fig1_REVIEW_VALIDATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','files':list(r['output_sha256'])}))
