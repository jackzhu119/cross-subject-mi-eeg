"""Read-only editorial/package checks; no scientific execution."""
from pathlib import Path
import hashlib,json,re,zipfile,collections,subprocess
from datetime import datetime,timezone
from docx import Document
from lxml import etree
from PIL import Image
import fitz
P=Path(__file__).resolve().parent;ROOT=P.parents[1];S=ROOT/'research_runs/PAPER_FINAL_20261006'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();checks={}
def check(k,v):checks[k]=bool(v)
baseline=json.loads((P/'evidence/source_protection_baseline.json').read_text())
scientific=baseline['scientific_files']
bad=[k for k,v in scientific.items() if not (ROOT/k).is_file() or h(ROOT/k)!=v]
check('scientific_files_all_hashes_unchanged',not bad)
if bad:print('scientific_files',bad[:5])
archived=json.loads(subprocess.check_output(['git','show','e377c116cb09edafb7be13bde9d85212ca7c8952:research_runs/PLOS_ONE_SUBMISSION/evidence/source_protection_baseline.json'],cwd=ROOT))['jne_files'];revision='0c7146895dc46850e4fe7db38bd69d9aea2b41c3'
proc=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
archived_bad=[]
for key,expected in archived.items():
 proc.stdin.write((revision+':'+key+'\n').encode());proc.stdin.flush();header=proc.stdout.readline().decode().split()
 if len(header)!=3:archived_bad.append(key);continue
 size=int(header[2]);payload=proc.stdout.read(size);proc.stdout.read(1)
 if hashlib.sha256(payload).hexdigest()!=expected:archived_bad.append(key)
proc.stdin.close();proc.wait()
check('immutable_source_archive_all_hashes_verified',not archived_bad)
d=json.loads((S/'manuscript_content.json').read_text());t=json.loads((P/'evidence/editorial_transformations.json').read_text());mapping={int(k):v for k,v in t['citation_old_to_new'].items()};cite=re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]')
def transform(text):
 if 'validation groups [1,2]' not in text:text=cite.sub(lambda m:'['+','.join(str(mapping[int(v)]) for v in m.group(1).replace(' ','').split(','))+']',text)
 text=re.sub(r'\bFigure (\d+)',r'Fig \1',text)
 return re.sub(r'(?<!Appendix, )\b(?:Figure|Fig) S(\d+)',r'S1 Appendix, Fig S\1',text)
main=t['main_blocks'];ap=t['appendix_blocks'];allblocks=main+ap
# Preserve every scientific paragraph/equation exactly except abstract journal labels/citation typography.
for i,b in enumerate(d['blocks']):
 if b['type'] in ['paragraph','equation'] and (3<=i<=134 or 149<=i) and i!=171:
  expected=transform(b['text']);check('source_prose_'+str(i),any(x.get('text')==expected for x in allblocks))
check('appendix_scientific_delivery_statement',any('All manuscript-preparation model fits and checkpoint-inference counts are zero.'in x.get('text','') for x in ap))
# Full scientific tables remain identical, including notes and all displayed p/CI/sample/epoch cells.
science_cells=0
for i,b in enumerate(d['blocks']):
 if b['type']=='table':
  matches=[x for x in allblocks if x.get('label')==transform(b['label'])];check('table_'+str(i)+'_exists',len(matches)==1)
  if matches:
   x=matches[0];check('table_'+str(i)+'_all_cells',x['headers']==[transform(v) for v in b['headers']] and x['rows']==[[transform(v) for v in r] for r in b['rows']] and x['note']==transform(b['note']));science_cells+=sum(len(r) for r in b['rows'])
abstract=(P/'PLOS_ONE_Abstract.txt').read_text().strip();expected=re.sub(r'\b(?:Objective|Approach|Main results|Significance)\.\s*','',d['blocks'][1]['text']);check('abstract_exact_scientific_text',abstract==expected);check('abstract_300_words_no_citations',len(abstract.split())<=300 and not cite.search(abstract));check('abstract_adverse_and_uncertain_results_retained','−1.513' in abstract and '+0.204'in abstract and 'do not establish a decoder mechanism'in abstract)
check('source_grouping_not_corrupted_by_citation_conversion',any('validation groups [1,2], [3,4], [5,6], and [7,8,9]'in x.get('text','') for x in ap))
refs=json.loads((P/'references_plos.json').read_text());check('28_references_preserved',len(refs)==28 and sorted(r['source_citation_number'] for r in refs)==list(range(1,29)))
source_refs={r['key']:r for r in json.loads((S/'references.json').read_text())['references']}
for r in refs:
 old=source_refs[r['key']];check('reference_'+r['key']+'_original_metadata',all(r.get(k)==old.get(k) for k in ['authors','title','doi','year','url']));check('reference_'+r['key']+'_first_six_rule',len(old['authors'])<=6 or 'et al.'in r['vancouver']);check('reference_'+r['key']+'_doi_format',not old.get('doi') or 'doi:'+old['doi']in r['vancouver'])
seen=[]
for x in main+ap:
 for name in ['text','caption','note']:
  text=x.get(name,'')
  if 'validation groups [1,2]'in text:continue
  for m in cite.finditer(text):
   for n in map(int,m.group(1).replace(' ','').split(',')):
    if n not in seen:seen.append(n)
check('Vancouver_first_appearance_continuous',seen==list(range(1,29)))
word=Document(P/'PLOS_ONE_Manuscript.docx');check('main_zero_embedded_images',len(word.inline_shapes)==0);check('main_eight_tables',len(word.tables)==8)
xml=word._element;ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};ln=xml.find('.//w:lnNumType',ns);check('docx_continuous_line_number_setting',ln is not None and ln.get('{'+ns['w']+'}restart')=='continuous');check('docx_page_field',b'PAGE'in (P/'PLOS_ONE_Manuscript.docx').read_bytes() if False else any('PAGE'in p._p.xml for s in word.sections for p in s.footer.paragraphs));check('normal_double_spacing',word.styles['Normal'].paragraph_format.line_spacing==2)
check('headings_max_three',all(not p.style.name.startswith('Heading ') or int(p.style.name.split()[-1])<=3 for p in word.paragraphs))
paragraphs=[p.text for p in word.paragraphs];check('no_main_funding_or_conflict_sections',not any(p in ['Funding','Competing interests','Author contributions'] for p in paragraphs))
check('main_ai_tools_scope_and_verification',all(term in '\n'.join(paragraphs) for term in ['ChatGPT','OpenAI Codex','personally reviewed','model version is not reliably documented','independent validation reports']))
# Confirm every rendered table cell exactly rather than relying only on source JSON.
source_tables=[b for b in main if b['type']=='table']
for n,(tb,b) in enumerate(zip(word.tables,source_tables),1):check('rendered_table_'+str(n)+'_cells',[[c.text for c in row.cells] for row in tb.rows]==[b['headers']]+b['rows'])
for n in range(1,7):
 check('figure_caption_'+str(n),sum(p.startswith(f'Fig {n}. ') for p in paragraphs)==1)
# Captions/tables must immediately follow their first prose citation.
body=list(word.element.body);plabels=[]
for n,node in enumerate(body):
 text=''.join(node.itertext()) if False else ''.join(node.xpath('.//w:t/text()'))
 if node.tag.endswith('}p'):plabels.append((n,text))
for label in [f'Fig {i}'for i in range(1,7)]+[f'Table {i}'for i in range(1,9)]:
 first=[(n,text) for n,text in plabels if re.search(re.escape(label)+r'(?!\d)',text)]
 cap=[(n,text) for n,text in first if text.startswith(label+'.')]
 check(label.replace(' ','_')+'_first_citation_and_adjacent_caption',bool(first and cap and not first[0][1].startswith(label+'.') and cap[0][0]==first[0][0]+1))
figs=json.loads((P/'evidence/figure_conversion.json').read_text());ns_s={'s':'http://www.w3.org/2000/svg'}
for n,r in enumerate(figs,1):
 f=P/'Figures'/f'Fig{n}.tif';im=Image.open(f);check(f'Fig{n}_TIFF_RGB_single_page_LZW',im.format=='TIFF'and im.mode=='RGB'and im.n_frames==1 and im.tag_v2.get(259)==5);check(f'Fig{n}_resolution_dimensions_size',all(300<=v<=600.1 for v in im.info['dpi']) and 6.68<=r['width_cm']<=19.051 and r['height_cm']<=22.231 and f.stat().st_size<10_000_000)
 orig=etree.fromstring((ROOT/r['source']).read_bytes());edit=etree.fromstring((P/'FigureSources'/f'Fig{n}.svg').read_bytes());paths=lambda t:[etree.tostring(e) for e in t.xpath('.//s:path | .//s:image | .//s:use | .//s:clipPath',namespaces=ns_s)]
 check(f'Fig{n}_scientific_paths_and_images_identical',paths(orig)==paths(edit));check(f'Fig{n}_scientific_text_identical',''.join(orig.itertext())==''.join(edit.itertext()));check(f'Fig{n}_8_to_12pt_Arial_text',r['physical_text_pt_range']==[8,12] and r['font_family']=='Arial')
check('Fig1_Q16_baseline_relative_label','Baseline-relative μ/β power'in (P/'FigureSources/Fig1.svg').read_text() and 'ERD / ERS'not in (P/'FigureSources/Fig1.svg').read_text())
# Frozen data byte readback for every ZIP member.
inventory=json.loads((P/'evidence/derived_data_inventory.json').read_text())
with zipfile.ZipFile(P/inventory['archive']) as z:
 check('data_zip_crc',z.testzip() is None)
 for key,rec in inventory['files'].items():check('data_byte_copy_'+key,hashlib.sha256(z.read(key)).hexdigest()==rec['sha256']==h(ROOT/rec['source_path']))
check('supporting_files_below_20MB',all(f.stat().st_size<20_000_000 for f in (P/'SupportingInformation').iterdir() if f.is_file()))
pdf_info={}
for name in ['PLOS_ONE_Manuscript_Review.pdf','PLOS_ONE_Cover_Letter.pdf','SupportingInformation/S1_Appendix.pdf']:
 pdf=fitz.open(P/name);outside=[];lines=[]
 for pg in pdf:
  for b in pg.get_text('dict')['blocks']:
   if 'lines'not in b:continue
   for line in b['lines']:
    for span in line['spans']:
     box=span['bbox']
     if box[0]<-1 or box[1]<-1 or box[2]>pg.rect.width+1 or box[3]>pg.rect.height+1:outside.append(span['text'])
     if box[0]<50 and span['text'].isdigit():lines.append(int(span['text']))
 check(name+'_no_page_overflow',not outside);check(name+'_text_present',len(''.join(pg.get_text()for pg in pdf))>500)
 if 'Manuscript'in name:check('pdf_continuous_gutter_line_numbers',len(lines)>500 and lines==list(range(lines[0],lines[-1]+1)));check('review_pdf_no_figure_images',all(not pg.get_images()for pg in pdf))
 if 'Cover'in name:check('cover_letter_one_page',len(pdf)==1);check('cover_current_PLOS_target_only','PLOS ONE'in pdf[0].get_text() and not re.search(r'JNE|Journal of Neural Engineering|under consideration|NOT FOR SUBMISSION',pdf[0].get_text()))
 pdf_info[name]={'pages':len(pdf),'sha256':h(P/name),'bytes':(P/name).stat().st_size}
status=json.loads((P/'evidence/source_version.json').read_text());check('current_status_no_previous_journal_block',status['target_journal']=='PLOS ONE' and status['previous_journal_decision']=='REJECTED_AUTHOR_REPORTED' and status['prior_journal_consideration_block'] is False and status['live_submission_portal_accessed'] is False);check('no_new_scientific_execution',d['new_fits']==0 and d['new_checkpoint_inference']==0)
# Current journal-facing files are free from obsolete prior-submission status.
obsolete=re.compile(r'JNE|under consideration at Journal of Neural Engineering|NOT FOR SUBMISSION|JNE under review|plos-one-preparation-v0\.1')
for name in ['PLOS_ONE_Manuscript.docx','PLOS_ONE_Cover_Letter.docx','SupportingInformation/S1_Appendix.docx']:
 doc=Document(P/name);text='\n'.join(p.text for p in doc.paragraphs)
 check('current_target_hygiene_'+name,not obsolete.search(text))
for name in ['README.md','PLOS_ONE_Submission_Checklist_zh.md','PLOS_ONE_Submission_Fields.md','PLOS_ONE_APC_Assistance_Guide_zh.md','PLOS_ONE_Official_Requirements.md','PLOS_ONE_Data_Availability.md','Ethics_and_Author_Boundaries.md','Changes_and_Preservation.md']:
 check('active_admin_target_hygiene_'+name,not obsolete.search((P/name).read_text()))
with zipfile.ZipFile(P/'SupportingInformation/S1_Data.zip') as z:
 check('S1_Data_no_obsolete_editorial_reports',not any(x in z.namelist() for x in ['validation/delivery_validation.json','validation/final_scientific_review.json']))
 check('S1_Data_no_previous_target_status',all(not obsolete.search(z.read(n).decode('utf-8')) for n in z.namelist() if n.endswith(('.json','.md','.txt','.csv'))))
blank=P/'AuthorForms/PLOS_Human_Participants_Checklist_2026_blank.pdf'
check('official_human_data_checklist_original_bytes',h(blank)=='ebf2a9913fe2926669dfb60c1ba5f9f98130b00b9e858bf9b1d243b3707162e4')
check('required_human_data_dates_and_identifiability_action',all(x in (P/'AuthorForms/README_zh.md').read_text() for x in ['日期','识别','Methods']))
failed=[k for k,v in checks.items()if not v]
report={'status':'passed'if not failed else'failed','scope':'Editorial preservation, frozen-byte and package checks only; no new model/scientific experiment execution or independent institutional determination.','checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'failed_checks':failed,'check_count':len(checks),'protected_scientific_files':len(baseline['scientific_files']),'immutable_source_archive_files_verified':len(archived),'displayed_scientific_table_cells_checked':science_cells,'pdfs':pdf_info,'journal_submission_performed':False,'prior_journal_consideration_block':False,'author_final_checks_pending':True,'author_actions':['ORCID','PLOS-format author reading/approval','Institutional secondary-analysis ethics requirements','Actual CRediT roles and output licensing','APC funding/assistance answers','Actual portal confirmations'],'new_model_fits':0,'new_checkpoint_inference':0,'new_q16_scientific_execution':0}
(P/'evidence/plos_delivery_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(checks),'failed':failed,'pdf_pages':{k:v['pages']for k,v in pdf_info.items()}}));raise SystemExit(bool(failed))
