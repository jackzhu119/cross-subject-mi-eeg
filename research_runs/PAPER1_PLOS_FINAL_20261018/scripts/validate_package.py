#!/usr/bin/env python3
"""Check new manuscript documents, complete supporting data and preserved results."""
import argparse,collections,hashlib,json,re,shutil,zipfile
from pathlib import Path
from datetime import datetime,timezone
import fitz
from docx import Document


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();src,out=a.source,a.out
    checks={}
    def check(k,v):
        checks[k]=bool(v)
        if not v:raise AssertionError(k)
    text=(out/'manuscript_en.md').read_text();abstract=text.split('## Abstract\n\n')[1].split('\n\n## Introduction')[0]
    check('abstract_at_most_300_words',len(abstract.split())<=300)
    check('abstract_no_numeric_references',re.search(r'\[\d',abstract) is None)
    check('full_title_at_most_250_characters',len(text.splitlines()[0][2:])<=250)
    check('short_title_at_most_100_characters',len(re.search(r'^Short title: (.*)',text,re.M)[1])<=100)
    check('supporting_captions_after_references',text.index('## Supporting information')>text.index('## References'))
    check('21_references_retained',len(re.findall(r'^\d+\. ',text.split('## References')[1].split('## Supporting information')[0],re.M))==21)
    check('all_original_reference_entries_unchanged',text.split('## References')[1].split('## Supporting information')[0].strip()==(src/'manuscript_en.md').read_text().split('## References')[1].strip())
    for n in range(1,8):
        paras=re.split(r'\n\s*\n',text)
        i=next(i for i,x in enumerate(paras) if re.search(rf'\bFig {n}\b',x) and not x.startswith('**Fig'))
        check(f'figure_{n}_caption_at_first_citation',paras[i+1].startswith(f'**Fig {n}.'))
    check('captions_numbered_in_order',[int(x) for x in re.findall(r'^\*\*Fig (\d)\.',text,re.M)]==list(range(1,8)))
    for n in range(1,6):
        paras=re.split(r'\n\s*\n',text);i=next(i for i,x in enumerate(paras) if re.search(rf'\bTable {n}\b',x) and not x.startswith('**Table'))
        check(f'table_{n}_at_first_citation',paras[i+1].startswith(f'**Table {n}.'))
    for n in ['S1_Data.zip','S2_Neural_Predictions.csv.gz','S3_CSP_Predictions.csv.gz']:
        check(n+'_unchanged',sha(src/n)==sha(out/n));check(n+'_under_20MB',(out/n).stat().st_size<20000000)
    datafiles=['S4_Additional_descriptives.csv','primary_joint_participant_changes.csv','analysis_plan.json','additional_descriptive_receipt.json']
    with zipfile.ZipFile(out/'S4_Data.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n in datafiles:z.write(out/'evidence/additional_descriptives'/n,n)
        z.write(out/'scripts/analyze_saved_predictions.py','analyze_saved_predictions.py')
        z.writestr('README.txt','Additional post hoc descriptive reconstruction of all 34 source-expansion configurations; zero new hypothesis tests. Metrics calculated within seed, then averaged within participant. See the full audit receipt and analysis script.\n')
    check('S4_Data_under_20MB',(out/'S4_Data.zip').stat().st_size<20000000)
    rec=json.loads((out/'evidence/additional_descriptives/additional_descriptive_receipt.json').read_text())
    check('complete_prediction_reconstruction_passed',rec['status']=='PASS' and rec['n_inventory_values_reproduced']==68 and rec['new_hypothesis_tests']==0)
    check('66_joint_improvements',rec['primary']['both_endpoints_improved']==66)
    check('49_39_percent_gap_reduction',abs(rec['primary']['gap_reduction_relative_percent']-49.39130434782609)<1e-10)
    for s in ['−0.8725','−0.5490','Ten participants declined','Tail cross-entropy supplied the eight adverse','31.01% to 59.64%','85.63% to 68.71%']:
        check('retained_'+s,s in text)
    check('main_Results_lead_with_primary_finding',text.split('## Results')[1].lstrip().startswith('### Source expansion improved'))
    doc=Document(out/'main_manuscript.docx')
    with zipfile.ZipFile(out/'main_manuscript.docx') as z:
        xml=z.read('word/document.xml').decode();settings=z.read('word/settings.xml').decode()
        check('no_docx_protection','w:documentProtection' not in settings)
        check('continuous_line_numbers','w:restart="continuous"' in xml)
        check('no_embedded_main_figures',not any(n.startswith('word/media/') for n in z.namelist()))
        check('page_number_field',b'PAGE' in z.read('word/footer1.xml'))
    check('main_double_spaced',doc.styles['Normal'].paragraph_format.line_spacing==2)
    check('all_5_editable_tables_present',len(doc.tables)==5)
    check('correct_author_metadata',doc.core_properties.author=='Ziyuan Zhu')
    with fitz.open(out/'main_manuscript.pdf') as pdf:
        check('separate_title_page','Abstract' not in pdf[0].get_text() and 'Abstract' in pdf[1].get_text())
        check('main_pdf_all_pages_have_content',all(pg.get_text().strip() for pg in pdf))
    with fitz.open(out/'submission/Cover_Letter.pdf') as pdf:check('cover_letter_one_page',len(pdf)==1)
    cover=(out/'submission/Cover_Letter.md').read_text()
    check('cover_letter_corrects_prior_submission','was rejected on 12 October 2026' in cover and 'Please confirm' in cover)
    figures=json.loads((out/'figures/FIGURE_FORMAT_VALIDATION.json').read_text())['figures']
    check('seven_EPS_figures',len(figures)==7)
    for f in figures:
        check(f['figure']+'_accepted_fonts',f['fonts'] and all(x.startswith('Times-') or x=='Symbol' for x in f['fonts']))
        check(f['figure']+'_size_limits',f['bytes']<10000000 and f['width_inches']<=7.5 and f['height_inches']<=8.75)
        ps=(out/'figures'/(f['figure']+'.eps')).read_text('latin1')
        check(f['figure']+'_no_missing_glyphs','/question glyphshow' not in ps and '/.notdef' not in ps)
    terms=['can','could','may','might','potential','suggest','uncertain','not','no','only']
    screen={word:{'before':len(re.findall(r'\b'+word+r'\b',(src/'manuscript_en.md').read_text(),re.I)),'after':len(re.findall(r'\b'+word+r'\b',text,re.I))} for word in terms}
    (out/'evidence/language_screen.json').write_text(json.dumps({'counts':screen,'interpretation':'Technical negations and evidence qualifiers are retained where needed. Changes were sentence-level, not mechanical token deletion.'},indent=2)+'\n')
    report={'status':'PASS','checked_at_utc':datetime.now(timezone.utc).isoformat(),'passed':len(checks),'failed':0,'checks':checks,'abstract_words':len(abstract.split()),'new_models':0,'new_decoder_inference':0,'new_hypothesis_tests':0,'submission_route_verified':False,'journal_submission_performed':False,'visual_review':'To be recorded after rendered-page inspection; structural checks alone are not visual review.'}
    (out/'evidence/validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    manifest=''.join(sha(f)+'  '+f.relative_to(out).as_posix()+'\n' for f in sorted(out.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name not in ['MANIFEST.sha256','Paper1_PLOS_Final_20261018.zip','Paper1_PLOS_Final_20261018.zip.sha256'])
    (out/'MANIFEST.sha256').write_text(manifest)
    package=out/'Paper1_PLOS_Final_20261018.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file() and f.name not in ['Paper1_PLOS_Final_20261018.zip','Paper1_PLOS_Final_20261018.zip.sha256'] and '__pycache__' not in f.parts:z.write(f,f.relative_to(out).as_posix())
    (out/'Paper1_PLOS_Final_20261018.zip.sha256').write_text(sha(package)+'  '+package.name+'\n')
    print(json.dumps({'status':'PASS','checks':len(checks),'archive_bytes':package.stat().st_size}))
if __name__=='__main__':main()
