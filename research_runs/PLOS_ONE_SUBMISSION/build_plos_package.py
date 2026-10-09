"""Editorial conversion only: reads frozen text/results, never EEG or models."""
from pathlib import Path
import copy, json, re, hashlib, zipfile, shutil, subprocess, io, ast
from datetime import datetime, timezone
import fitz
from PIL import Image
from docx import Document
from docx.shared import Inches, Pt, Mm, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
import cairosvg

OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[1]; SRC=ROOT/'research_runs/PAPER_FINAL_20261006'
DATA=json.loads((SRC/'manuscript_content.json').read_text()); TITLE=DATA['title']
SHORT='Source-only selection and fixed spectral-sharing pipelines in motor-imagery EEG'
SHA='0c7146895dc46850e4fe7db38bd69d9aea2b41c3'; TAG='plos-one-submission-v1.1'
BASE='https://github.com/jackzhu119/cross-subject-mi-eeg'; IMM=BASE+'/tree/'+SHA
AUTHOR=copy.deepcopy(DATA['authors'][0]); AUTHOR['orcid']='0009-0005-1153-4926'; NOW=datetime.now(timezone.utc).isoformat()
for folder in ['Figures','SupportingInformation','evidence','FigureSources']:(OUT/folder).mkdir(exist_ok=True)
def save(name,text): (OUT/name).write_text(text.rstrip()+'\n')
def jdump(name,d):save(name,json.dumps(d,ensure_ascii=False,indent=2))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

# Journal-specific rearrangement. Every source scientific block is retained.
source=DATA['blocks'];split=148
main=copy.deepcopy(source[:135])
main.pop(2) # Keywords are separate submission metadata, not abstract content.
for b in main:
 if b['type']=='heading':
  t=b['text'];b['text']=re.sub(r'^\d+(?:\.\d+)*\.\s*','',t)
  if b['text']=='Related Work':b['level']=2
  if b['text']=='Conclusion':b['text']='Conclusions'
main[1]['text']=re.sub(r'\b(?:Objective|Approach|Main results|Significance)\.\s*','',main[1]['text'])
# Add ethics/data at the end of Methods; no false institutional determination.
pos=next(i for i,b in enumerate(main) if b.get('text')=='Results')
access=json.loads((OUT/'evidence/research_access_dates.json').read_text())
added=[{'type':'heading','level':2,'text':'Ethics statement'},
 {'type':'paragraph','text':'This study involved secondary analysis of public EEG recordings and recruited no new participants. The Cho2017 and Lee2019 source publications report collection ethics review and written informed consent [7,9]. Those collection approvals are not approvals for this secondary analysis. The author confirms that neither ethics approval nor an exemption was required for this secondary analysis. No formal approval or exemption documentation was obtained for this secondary analysis; this statement records the author’s assessment rather than an institutional or committee determination.'},
 {'type':'paragraph','text':access['methods_access_paragraph']},
 {'type':'paragraph','text':access['methods_identifiability_paragraph']},
 {'type':'heading','level':2,'text':'Data and code availability'},copy.deepcopy(source[136]),
 {'type':'paragraph','text':'The current submission materials and licensing notices are available at https://github.com/jackzhu119/cross-subject-mi-eeg/tree/'+TAG+'. Author-owned original software is licensed under MIT; author-owned original manuscript material and derived outputs are licensed under CC BY 4.0. Third-party recordings, software, fonts and other incorporated materials retain their original terms. These permissions do not alter frozen scientific results or grant third-party rights.'},
 {'type':'heading','level':2,'text':'AI assistance and verification'},copy.deepcopy(source[147]),
 {'type':'paragraph','text':'The underlying Codex model version is not reliably documented in the project records. Saved-result checks compared reported numbers with frozen outputs and archived independent validation reports; these checks did not rerun models or physiology experiments during manuscript preparation. The author reports personal review and revision of the scientific content. No AI tool is an author.'}]
main[pos:pos]=added
main += [{'type':'heading','level':1,'text':'Acknowledgments'}, {'type':'paragraph','text':'No additional acknowledgments are reported.'}]
# Source-to-destination block mapping remains inspectable in the package.
appendix=copy.deepcopy(source[split+1:]);appendix += [{'type':'heading','level':1,'text':'Detailed reproducible methods'}]
lines=(SRC/'supplementary_methods.md').read_text().splitlines();pending=[];idx=0;mt=0
def flush():
 if pending:appendix.append({'type':'paragraph','text':' '.join(pending)});pending.clear()
while idx<len(lines):
 line=lines[idx]
 if line.startswith('|'):
  flush();cells=[]
  while idx<len(lines) and lines[idx].startswith('|'):
   cells.append([c.strip().replace('`','').replace('**','') for c in lines[idx].strip().strip('|').split('|')]);idx+=1
  mt+=1;appendix.append({'type':'table','label':f'Methods table M{mt}. '+('Equal-person hand power summaries.' if mt==1 else 'All descriptive physiology–accuracy coefficients.'),'headers':cells[0],'rows':cells[2:],'note':'Values repeat the independently checked Q16 results; no additional analysis is performed.'});continue
 if not line.strip():flush()
 elif line.startswith('#'):flush();appendix.append({'type':'heading','level':2,'text':line.lstrip('# ').strip()})
 else:pending.append(line.replace('`','').replace('**','').strip())
 idx+=1
flush()
for b in appendix:
 if b.get('text','').startswith('The manuscript bundle contains'):
  b['text']='The submission materials contain the manuscript, supporting information, standalone figures, frozen derived data and validation evidence. All manuscript-preparation model fits and checkpoint-inference counts are zero. Operational cloud logs are not scientific endpoints. Author declarations and final submission checks are maintained separately from the scientific results.'

# Vancouver order of first appearance after moving data/ethics into Methods.
CITE=re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]'); order=[]
def strs(b):
 return [b.get(k,'') for k in ['text','label','caption','note']]+b.get('headers',[])+[s for row in b.get('rows',[]) for s in row]
for b in main+appendix:
 for t in strs(b):
  for m in ([] if 'validation groups [1,2]' in t else CITE.finditer(t)):
   for n in map(int,m.group(1).replace(' ','').split(',')):
    assert 1<=n<=28,(n,t)
    if n not in order:order.append(n)
assert sorted(order)==list(range(1,29)),order
mapping={old:i+1 for i,old in enumerate(order)}
def edittext(t):
 t=(CITE.sub(lambda m:'['+','.join(str(mapping[int(n)]) for n in m.group(1).replace(' ','').split(','))+']',t) if 'validation groups [1,2]' not in t else t)
 t=re.sub(r'\bFigure (\d+)',r'Fig \1',t)
 return t
for b in main+appendix:
 for k in ['text','label','caption','note']:
  if k in b:b[k]=edittext(b[k])
 if 'headers'in b:b['headers']=[edittext(t) for t in b['headers']];b['rows']=[[edittext(t) for t in r] for r in b['rows']]
# Explicitly point to a named PLOS supporting file, without renumbering its internal scientific tables.
for b in main:
 for k in ['text','caption','note']:
  if k in b:b[k]=re.sub(r'(?<!Appendix, )\b(?:Figure|Fig) S(\d+)',r'S1 Appendix, Fig S\1',b[k])

refdata={r['key']:r for r in json.loads((SRC/'references.json').read_text())['references']}
abbr={'Frontiers in Neuroscience':'Front Neurosci','Journal of Neural Engineering':'J Neural Eng','IEEE Transactions on Rehabilitation Engineering':'IEEE Trans Rehabil Eng','Human Brain Mapping':'Hum Brain Mapp','IEEE Transactions on Biomedical Engineering':'IEEE Trans Biomed Eng','Scandinavian Journal of Statistics':'Scand J Stat','The Annals of Statistics':'Ann Stat','NeuroImage':'Neuroimage','Nature Health':'Nat Health','Clinical Neurophysiology':'Clin Neurophysiol','Neuroscience Letters':'Neurosci Lett','IEEE Journal of Biomedical and Health Informatics':'IEEE J Biomed Health Inform','Bioengineering':'Bioengineering (Basel)'}
def author(a):
 if ','in a:s,g=a.split(',',1)
 elif 'Lopes da Silva'in a:s,g='Lopes da Silva',a.replace('Lopes da Silva','')
 elif re.match(r'^[A-Z](?:\.[A-Z])*\.\s',a):g,s=a.split(' ',1)
 else:
  parts=a.split();s,g=parts[-1],' '.join(parts[:-1])
 initials=''.join(p[0] for p in re.findall(r'[A-Za-zÀ-ž]+',g))
 return s.strip()+' '+initials
refs=[];refrecords=[]
for old in order:
 key=DATA['reference_keys'][old-1];r=copy.deepcopy(refdata[key]);authors=', '.join(author(a) for a in r['authors'][:6])+(', et al.' if len(r['authors'])>6 else '.')
 venue=r.get('journal') or r.get('venue') or r.get('type','Dataset');venue=abbr.get(venue,venue)
 if 'ICLR'in key:venue=r.get('venue',venue)
 if key=='Sagawa2020':venue='International Conference on Learning Representations'
 if key=='Gulrajani2021':venue='International Conference on Learning Representations'
 body=f"{authors} {r['title']}. {venue}. {r['year']}"
 if r.get('volume'):body+=';'+str(r['volume'])
 if r.get('issue'):body+='('+str(r['issue'])+')'
 pages=r.get('pages') or r.get('pages_or_article')
 if pages:body+=':'+str(pages)
 body+='.'
 if r.get('doi'):body+=' doi:'+r['doi']
 else:body+=' Available from: '+r['url']+' [cited 2026 Oct 8].'
 refs.append(body);r['plos_number']=mapping[old];r['source_citation_number']=old;r['vancouver']=body;refrecords.append(r)
jdump('references_plos.json',refrecords);save('references_plos.md','\n'.join(f'{i}. {r}' for i,r in enumerate(refs,1)))
jdump('evidence/editorial_transformations.json',{'source_commit':SHA,'source_tag':'paper-v1.0.2','source_artifact_commit':'b23480d996dd6c78e386686e1110e272decf166f','source_blocks':len(source),'citation_old_to_new':mapping,'first_citation_order_old':order,'main_blocks':main,'appendix_blocks':appendix,'scientific_block_content_preserved':True,'funding_and_competing_interests_moved_to_online_fields':True,'no_new_fits':True,'no_checkpoint_inference':True})

# Six TIFFs are rendered from source vectors; only text family/size is changed.
# Paths, images, coordinates, values, color scales and error bars remain unchanged.
existing_figures=(OUT/'evidence/figure_conversion.json').exists() and all((OUT/'Figures'/f'Fig{n}.tif').exists() and (OUT/'FigureSources'/f'Fig{n}.svg').exists() for n in range(1,7))
figreport=json.loads((OUT/'evidence/figure_conversion.json').read_text()) if existing_figures else [];ns={'s':'http://www.w3.org/2000/svg'}
for n,b in enumerate([b for b in main if b['type']=='figure'],1):
 if existing_figures:
  assert digest(OUT/'Figures'/f'Fig{n}.tif')==figreport[n-1]['tiff_sha256']
  assert digest(OUT/'FigureSources'/f'Fig{n}.svg')==figreport[n-1]['edited_svg_sha256']
  continue
 orig=SRC/'figures'/(b['name']+'.svg');tree=etree.fromstring(orig.read_bytes());vb=list(map(float,tree.attrib['viewBox'].split()));w,h=vb[2:];scale=min(540/w,630/h);width=w*scale;height=h*scale
 for e in tree.xpath('.//s:text | .//s:tspan',namespaces=ns):
  st=e.get('style','');st=re.sub(r"font-family:\s*[^;]+",'font-family: Arial',st)
  st=re.sub(r'font-size:\s*([\d.]+)px',lambda m:f'font-size: {min(12,max(8,float(m.group(1))*scale))/scale:.6f}px',st)
  if st:e.set('style',st)
 if n==2:
  for gid,offset in [('legend_1',-23),('legend_2',-30)]:
   for group in tree.xpath(f'.//s:g[@id="{gid}"]',namespaces=ns):group.set('transform',f'translate({offset},0)')
 dst=OUT/'FigureSources'/f'Fig{n}.svg';dst.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='utf-8'))
 dpi=600;pxw=round(width/72*dpi);pxh=round(height/72*dpi)
 png=cairosvg.svg2png(bytestring=dst.read_bytes(),output_width=pxw,output_height=pxh)
 im=Image.open(io.BytesIO(png)).convert('RGBA');white=Image.new('RGB',im.size,'white');white.paste(im,mask=im.getchannel('A'))
 target=OUT/'Figures'/f'Fig{n}.tif';white.save(target,compression='tiff_lzw',dpi=(dpi,dpi))
 tree0=etree.fromstring(orig.read_bytes());strip=lambda tr:[etree.tostring(e) for e in tr.xpath('.//s:path | .//s:image | .//s:use | .//s:clipPath',namespaces=ns)]
 assert strip(tree0)==strip(tree)
 figreport.append({'figure':n,'source':str(orig.relative_to(ROOT)),'source_sha256':digest(orig),'edited_svg_sha256':digest(dst),'tiff_sha256':digest(target),'pixels':[pxw,pxh],'dpi':dpi,'width_cm':width/72*2.54,'height_cm':height/72*2.54,'bytes':target.stat().st_size,'font_family':'Arial','physical_text_pt_range':[8,12],'scientific_graphical_elements_identical':True,'text_content_identical':''.join(tree0.itertext())==''.join(tree.itertext()),'changes':'Arial/8–12 pt text; vector rasterization; Fig2 legends translated for readability. No data-point, error-bar, axis or color-scale changes.'})
 assert target.stat().st_size<10_000_000
jdump('evidence/figure_conversion.json',figreport)

# Standalone figure captions are adjacent to the first substantive citation.
short_titles=['Study workflow and source–target information boundaries','Training-duration selection and participant-level internal results','Source composition and matched-runtime controls','Separate-cohort binary transfer','Frozen external evaluation on Cho2017 and Lee2019','Descriptive native BNCI task/baseline power changes']
for n,b in enumerate([b for b in main if b['type']=='figure'],1):b['title']=short_titles[n-1]
def place_floats(blocks):
 floats=[b for b in blocks if b['type']in ['figure','table']];plain=[b for b in blocks if b['type']not in ['figure','table']]
 placed=set();output=[]
 for b in plain:
  # Enforce float order and use the first actual reference in prose.
  output.append(b)
  for f in floats:
   token=f['label'].split('.')[0]
   if id(f) not in placed and token in b.get('text',''):
    output.append(f);placed.add(id(f))
 for f in floats:
  if id(f) not in placed:
   # Some source tables were unreferenced; add a neutral navigation sentence.
   idx=next(i for i,x in enumerate(blocks) if x is f)
   previous=[x for x in blocks[:idx] if x['type'] not in ['figure','table']][-1]
   dest=output.index(previous)+1
   output[dest:dest]=[{'type':'paragraph','text':f"The corresponding saved summary is presented in {f['label'].split('.')[0]}."},f]
 return output
main=place_floats(main)
# Preserve figure order: source first citations are already monotonic; validated later.

def caption_text(b):
 title=b.get('title',b['caption'].split('.')[0]);body=b['caption']
 if body.startswith(title+'.'):body=body[len(title)+1:].strip()
 return b['label']+'. '+title+'. '+body

# Documents: actual Word continuous line numbers and page fields, no main images.
def document(title,blocks,filename,images=False,bibliography=True,cover=False):
 doc=Document();s=doc.sections[0];s.page_width=Mm(210);s.page_height=Mm(297);s.top_margin=s.bottom_margin=Mm(20);s.left_margin=Mm(24);s.right_margin=Mm(18)
 for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3']:
  st=doc.styles[name];st.font.name='Times New Roman';st.font.size=Pt(12);st.font.color.rgb=RGBColor(0,0,0);st.paragraph_format.line_spacing=2 if not cover else 1.05;st.paragraph_format.space_after=Pt(3)
 for name in ['Heading 1','Heading 2','Heading 3']:
  doc.styles[name].font.bold=True;doc.styles[name].paragraph_format.keep_with_next=True
 doc.styles['Title'].font.size=Pt(15 if not cover else 12)
 if not cover:
  ln=OxmlElement('w:lnNumType');ln.set(qn('w:countBy'),'1');ln.set(qn('w:restart'),'continuous');ln.set(qn('w:distance'),'220');s._sectPr.append(ln)
 footer=s.footer.paragraphs[0];footer.alignment=1;field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
 doc.add_heading(title,0)
 if filename.startswith('PLOS_ONE_Manuscript'):
  for t in ['Short title: '+SHORT,AUTHOR['name']+'*',AUTHOR['affiliation'],'*Corresponding author: '+AUTHOR['email'],'ORCID: https://orcid.org/'+AUTHOR['orcid'],'Postal address: '+AUTHOR.get('postal_address','')]:doc.add_paragraph(t)
  doc.add_page_break()
 elif images:doc.add_paragraph('Supporting information for: '+TITLE)
 for b in blocks:
  typ=b['type']
  if typ=='heading':doc.add_heading(b['text'],min(3,b['level']))
  elif typ in ['paragraph','equation']:doc.add_paragraph(b['text'])
  elif typ=='figure':
   if images:doc.add_picture(str(SRC/'figures'/(b['name']+'.png')),width=Inches(6.4))
   doc.add_paragraph(caption_text(b))
  elif typ=='table':
   cap=doc.add_paragraph(b['label']);cap.paragraph_format.keep_with_next=True
   tb=doc.add_table(rows=1,cols=len(b['headers']));tb.style='Table Grid';tb.autofit=False
   for cell,t in zip(tb.rows[0].cells,b['headers']):cell.text=t
   for row in b['rows']:
    for cell,t in zip(tb.add_row().cells,row):cell.text=str(t)
   for i,row in enumerate(tb.rows):
    pr=row._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
    if i==0:pr.append(OxmlElement('w:tblHeader'))
    for cell in row.cells:
     for p in cell.paragraphs:
      p.paragraph_format.line_spacing=2;p.paragraph_format.space_after=Pt(1)
      for run in p.runs:run.font.size=Pt(10)
   doc.add_paragraph(b.get('note',''))
 if bibliography:
  doc.add_heading('References',1)
  for i,r in enumerate(refs,1):doc.add_paragraph(f'{i}. {r}')
 if filename.startswith('PLOS_ONE_Manuscript'):
  doc.add_heading('Supporting information captions',1)
  for t in ['S1 Appendix. Supplementary results, descriptive associations, inventories and detailed reproducible methods. Internal supplementary figures and tables retain their original S numbering.','S1 Data. Frozen participant-level summaries, saved external predictions, descriptive physiological outputs, source-data provenance and validation evidence. Files are CSV/JSON or gzip-compressed CSV; raw EEG and model weights are excluded.']:doc.add_paragraph(t)
 doc.save(OUT/filename)

def mdblocks(blocks):
 ss=[]
 for b in blocks:
  if b['type']=='heading':ss.append('#'*(b['level']+1)+' '+b['text'])
  elif b['type']in ['paragraph','equation']:ss.append(b['text'])
  elif b['type']=='figure':ss.append(caption_text(b))
  elif b['type']=='table':ss += ['**'+b['label']+'**','| '+' | '.join(b['headers'])+' |','| '+' | '.join(['---']*len(b['headers']))+' |']+['| '+' | '.join(row)+' |' for row in b['rows']]+[b['note']]
 return '\n\n'.join(ss)
document(TITLE,main,'PLOS_ONE_Manuscript.docx')
save('PLOS_ONE_Manuscript.md','# '+TITLE+'\n\n'+AUTHOR['name']+'\n\n'+AUTHOR['affiliation']+'\n\nORCID: https://orcid.org/'+AUTHOR['orcid']+'\n\n'+mdblocks(main)+'\n\n## References\n\n'+(OUT/'references_plos.md').read_text()+'\n\n## Supporting information captions\n\nS1 Appendix. Supplementary results and detailed reproducible methods.\n\nS1 Data. Frozen derived data and validation evidence.')
document('S1 Appendix',appendix,'SupportingInformation/S1_Appendix.docx',images=True)
save('SupportingInformation/S1_Appendix.md',mdblocks(appendix))
save('PLOS_ONE_Abstract.txt',main[1]['text'])
save('PLOS_ONE_Title_and_Keywords.md',f'# Title\n\n{TITLE}\n\n# Short title\n\n{SHORT}\n\n# Keywords\n\n'+source[2]['text'].replace('Keywords: ',''))

# Frozen derived data archive: byte copies, never recomputed.
entries=[]
for f in sorted((SRC/'tables').glob('*.csv')):entries.append((f,'tables/'+f.name))
for f in sorted((SRC/'evidence/q16_analysis').iterdir()):
 if f.is_file() and f.suffix in ['.csv','.json','.md','.gz']:entries.append((f,'q16/'+f.name))
for name in ['paper_numbers.json'] : entries.append((SRC/name,name))
for name in ['q15_numbers.json','q15_numbers.md','paper_internal_numbers.json','internal_review.json','methods_q15.json'] :entries.append((SRC/'evidence'/name,'validation/'+name))
for code in ['Q15-E006','Q15-E007']:
 for name in ['predictions.csv','statistics.json']:entries.append((ROOT/'results/Q15-EXTERNAL'/code/name,f'q15/{code}/{name}'))
# Literal figure-renderer inputs are copied, not executed or reaggregated.
for node in ast.walk(ast.parse((SRC/'build_figures.py').read_text())):
 if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ['read','read_json','subjects'] and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
  name=node.args[0].value;entries.append((ROOT/name,'figure_inputs/'+name))
for name in ['figures_q15.json','figures_q16.json','q16_plot_recipe.json','source_snapshot.json']:
 entries.append((SRC/'evidence'/name,'validation/'+name))
with zipfile.ZipFile(OUT/'SupportingInformation/S1_Data.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f,dst in entries:z.write(f,dst)
 z.writestr('SOURCE_MANIFEST.json',json.dumps({'source_commit':SHA,'files':{dst:{'source_path':str(f.relative_to(ROOT)),'sha256':digest(f),'bytes':f.stat().st_size} for f,dst in entries},'new_scientific_results':False,'raw_eeg_included':False},indent=2))
 z.writestr('README.txt','Frozen byte copies only. Original scientific sources and code are at '+IMM+'. No raw EEG or model weights.\nAuthor-owned original derived outputs are licensed under CC BY 4.0; author-owned original code is MIT-licensed. Third-party provider material and dependencies retain their terms. See the current '+TAG+' release LICENSING.md for scope. No scientific members were recomputed.\n')
assert (OUT/'SupportingInformation/S1_Data.zip').stat().st_size<20_000_000
jdump('evidence/derived_data_inventory.json',{'source_commit':SHA,'archive':'SupportingInformation/S1_Data.zip','archive_sha256':digest(OUT/'SupportingInformation/S1_Data.zip'),'files':{dst:{'source_path':str(f.relative_to(ROOT)),'sha256':digest(f)} for f,dst in entries}})

cover=[{'type':'paragraph','text':'Dear Editors,'},
 {'type':'paragraph','text':'Please consider this Research Article, “'+TITLE+'”, for publication in PLOS ONE.'},
 {'type':'paragraph','text':'The study examines how source-only training-duration selection and participant heterogeneity constrain claims about calibration-free motor-imagery EEG decoding. It combines a model-selection audit with frozen external evaluation and retains adverse and uncertain findings. The contribution is a reproducible selection and evaluation evidence chain, rather than a new state-of-the-art domain-generalization algorithm. A separate sensor-level physiological analysis is descriptive and does not establish a decoder mechanism.'},
 {'type':'paragraph','text':'The manuscript provides documented methods, participant-level outcomes, uncertainty estimates and explicit limitations. Code, manuscript candidates and frozen research outputs are publicly accessible on GitHub. The author reports no prior journal or preprint-platform publication. Original EEG is obtained from the original providers; saved predictions, derived summaries and validation evidence are supplied or linked. AI assistance and author verification are disclosed in the Methods. Funding and competing-interest statements are provided in the submission fields.'},
 {'type':'paragraph','text':'I am the sole and corresponding author and have approved the manuscript. I take responsibility for its scientific content. I have no opposed reviewers. Suggested Academic Editors are Marie-Constance Corsi (Inria Centre de Recherche de Paris) and Cota Navin Gupta (Indian Institute of Technology Guwahati), whose expertise covers EEG motor imagery, decoding and signal analysis.'},
 {'type':'paragraph','text':'Sincerely,\n'+AUTHOR['name']+'\n'+AUTHOR['affiliation']+'\n'+AUTHOR['email']+'\nORCID: https://orcid.org/'+AUTHOR['orcid']}]
document('Cover letter — PLOS ONE Research Article',cover,'PLOS_ONE_Cover_Letter.docx',bibliography=False,cover=True)
save('PLOS_ONE_Cover_Letter.md',mdblocks(cover))
jdump('evidence/source_version.json',{'checked_at_utc':NOW,'target_journal':'PLOS ONE','source_branch':'paper/zero-calibration-q16-20261006','source_branch_commit':SHA,'latest_verified_manuscript_tag':'paper-v1.0.2','artifact_commit':'b23480d996dd6c78e386686e1110e272decf166f','scientific_protected_count':16417,'source_validation_bindings_checked':230,'source_delivery_checks':680,'previous_journal_decision':'REJECTED_AUTHOR_REPORTED','decision_report_date':'2026-10-09','live_submission_portal_accessed':False,'prior_journal_consideration_block':False,'plos_formal_submission':'NOT_SUBMITTED_PORTAL_ACTIONS_REMAIN','new_formatted_version_author_approval':'APPROVED_AUTHOR_REPORTED_WITH_AUTHORIZED_DECLARATION_UPDATES','orcid':AUTHOR['orcid'],'no_direct_identifying_information_author_reported':True,'formal_secondary_analysis_ethics_document':False,'self_paid_publication_charge':True,'original_output_licensing_authorized':True,'new_model_fits':0,'new_checkpoint_inference':0,'new_q16_scientific_execution':0})
print(json.dumps({'main_blocks':len(main),'appendix_blocks':len(appendix),'abstract_words':len(main[1]['text'].split()),'refs':len(refs),'data_archive_bytes':(OUT/'SupportingInformation/S1_Data.zip').stat().st_size,'new_fits':0}))
