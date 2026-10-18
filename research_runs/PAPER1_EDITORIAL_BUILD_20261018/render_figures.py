#!/usr/bin/env python3
"""Typography/format-only refresh of the seven existing scientific plots."""
import argparse,importlib.util,json,re,hashlib,subprocess
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    s=importlib.util.spec_from_file_location('original_figure_renderer',args.source/'scripts/build_figures.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    out=args.out/'figures';out.mkdir(exist_ok=True);m.FIGURES=out;m.DATA=args.out/'figure_data';m.TABLES=args.out/'tables'
    plt.rcParams.update({'font.family':'serif','font.serif':['Times'],'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'pdf.use14corefonts':True,'ps.useafm':True,'svg.fonttype':'none','axes.unicode_minus':False,'savefig.facecolor':'white'})
    records=[]
    def save(fig,stem):
        for text in fig.findobj(match=Text):
            text.set_text(text.get_text().translate(str.maketrans({'μ':'mu','β':'beta','→':'to','−':'-','≥':'>=','≤':'<='})))
            text.set_fontfamily('serif');text.set_fontname('Times')
        target=out/(stem+'.eps');fig.savefig(target,format='eps',facecolor='white')
        pdf=out/(stem+'.pdf');fig.savefig(pdf,format='pdf',facecolor='white')
        subprocess.run(['gs','-q','-dSAFER','-dBATCH','-dNOPAUSE','-dEPSCrop','-sDEVICE=png16m','-r300','-dTextAlphaBits=4','-dGraphicsAlphaBits=4','-sOutputFile='+str(out/(stem+'.png')),str(target)],check=True,timeout=45)
        body=target.read_text('latin1');font_names=sorted(set(re.findall(r'/(\S+) [\d.]+ selectfont',body)))
        assert font_names and all(x.startswith('Times-') or x=='Symbol' for x in font_names),font_names
        assert not re.search(r'DejaVu|Liberation|Nimbus|ArialMT',body)
        assert target.stat().st_size<10000000 and fig.get_figwidth()<=7.5 and fig.get_figheight()<=8.75
        with Image.open(out/(stem+'.png')) as im: dims=im.size
        records.append({'figure':stem,'format':'EPS','width_inches':float(fig.get_figwidth()),'height_inches':float(fig.get_figheight()),'bytes':target.stat().st_size,'fonts':font_names,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'preview_pixels':dims,'numerical_inputs_changed':False})
        plt.close(fig)
    m.save=save
    read=m.readcsv;d=args.source/'figure_data'
    comparisons=read(d/'neural_recomputed_comparisons.csv')
    pairs=read(d/'Fig3_primary_participant_changes.csv')
    desc=read(d/'Fig4_descriptive_endpoints.csv')
    chosen=read(d/'Fig5_selected_epochs.csv')
    m.workflow();m.contrasts(comparisons);m.paired(pairs,next(r for r in comparisons if r['name']=='primary_source_expansion_min_recall'));m.descriptives(desc);m.epochs(chosen)
    m.posthoc_contrasts(read(d/'Fig6_review2_posthoc_comparisons.csv'))
    m.fixed_duration_control(read(d/'Fig7_complete_source_expansion_inventory.csv'),read(d/'Fig7_fixed20_seed_differences.csv'))
    (out/'FIGURE_FORMAT_VALIDATION.json').write_text(json.dumps({'status':'PASS','change':'Original seven plot functions and values retained; standard PostScript Times/Symbol fonts, EPS export','new_statistical_tests':0,'figures':records},indent=2)+'\n')
    print(json.dumps({'figures_rendered':len(records),'all_under_10MB':True}))
if __name__=='__main__':main()
