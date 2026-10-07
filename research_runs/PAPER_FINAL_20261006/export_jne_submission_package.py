"""Prepare author-approved cover files and a clean submission ZIP; no science."""
from pathlib import Path
import hashlib,json,zipfile
from datetime import datetime,timezone
from xml.sax.saxutils import escape
from docx import Document
from docx.shared import Mm,Pt
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import fitz
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=(P/'cover_letter_JNE_draft.md').read_text()
body=source.split('\n\n',1)[1].split('\n\nThis letter has not been submitted or sent.')[0]
# The formal English letter uses the English signature; the bilingual source
# and author sheet retain the Chinese name. This avoids missing CJK glyphs.
assert 'Ziyuan Zhu (朱子元)' in body
body=body.replace('Ziyuan Zhu (朱子元)','Ziyuan Zhu')
paragraphs=[p.strip() for p in body.split('\n\n') if p.strip()]
doc=Document();sec=doc.sections[0];sec.page_width=Mm(210);sec.page_height=Mm(297)
sec.top_margin=sec.bottom_margin=Mm(22);sec.left_margin=sec.right_margin=Mm(23)
doc.styles['Normal'].font.name='Times New Roman';doc.styles['Normal'].font.size=Pt(11)
for text in paragraphs:doc.add_paragraph(text)
doc.save(P/'cover_letter_JNE.docx')
pdfmetrics.registerFont(TTFont('JNECover','/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'))
style=ParagraphStyle('JNECover',fontName='JNECover',fontSize=10.5,leading=14.5,spaceAfter=8)
SimpleDocTemplate(str(P/'cover_letter_JNE.pdf'),pagesize=(595.276,841.89),leftMargin=65,rightMargin=65,topMargin=62,bottomMargin=62,title='Cover letter — Journal of Neural Engineering',author='Ziyuan Zhu').build([Paragraph(escape(t).replace('\n','<br/>'),style) for t in paragraphs])
preview=fitz.open(P/'cover_letter_JNE.pdf');pdftext=' '.join(page.get_text() for page in preview)
assert '401331' in pdftext and 'Ziyuan Zhu' in pdftext and 'GPT-6' in pdftext and 'AUTHOR ACTION REQUIRED' not in pdftext and '[Supply' not in pdftext
assert '\x00' not in pdftext and '\ufffd' not in pdftext
instructions='''# JNE submission files\n\nThe author confirmed final manuscript/supplement/figure review, sole authorship, personal checking/revision, institutional wording, data-term checks, Github-only public history, no journal/preprint publication and no other-journal consideration. These are author statements, not independently observed human actions.\n\n1. Upload `manuscript_main_en.docx` as the main Word manuscript (PDF copy is included for checking).\n2. Upload `supplementary_materials.pdf` as supplementary material; an editable DOCX copy is also included.\n3. Upload or paste the formal `cover_letter_JNE.pdf`/DOCX cover letter, as permitted by the system.\n4. Figures are supplied in original PNG/PDF formats. Follow JNE's current format/resolution and upload fields. Do not upload both combined and standalone manuscripts as duplicate main papers.\n5. Copy author/contact/declared-use details from the author sheet into the portal. ORCID is not supplied; register if the portal requires it. Verify all cited original sources as required by IOP and check the portal-generated review PDF. The author completes any licensing/submission agreements.\n\nThe AI statement identifies author-reported ChatGPT (GPT-6) and established Codex research/code/figure/drafting uses. No claim that all historical sessions used GPT-6 or that all code/references were personally validated is made. Original EEG, credentials, checkpoints and internal cloud logs are excluded. Derived frozen results and reproducibility evidence remain linked in the manuscript/GitHub archive. Native TeX compilation is not verified; PDFs are inspected ReportLab exports. No journal submission or archive DOI has been created by packaging these files.\n'''
if (P/'language_refinement.json').exists():
 instructions+='\nThe preceding scientific candidate was approved by the author. This language-refined candidate preserves those results and declarations but requires an author read of the revised wording before actual submission. Independent editorial checks do not substitute for that read.\n'
(P/'JNE_submission_README.md').write_text(instructions)
files=[P/name for name in ('manuscript_main_en.docx','manuscript_main_en.pdf','supplementary_materials.docx','supplementary_materials.pdf','cover_letter_JNE.docx','cover_letter_JNE.pdf','author_information_template.md','ai_disclosure_submission_draft.md','references.bib','JNE_submission_README.md')]
files+=sorted(p for p in (P/'figures').iterdir() if p.suffix in ('.png','.pdf'))
assert len(files)==28,len(files)
manifest='\n'.join(sha(p)+'  '+p.relative_to(P).as_posix() for p in files)+'\n'
archive=P/'JNE_submission_package.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for path in files:z.write(path,path.relative_to(P).as_posix())
 z.writestr('MANIFEST.sha256',manifest)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for path in files:assert hashlib.sha256(z.read(path.relative_to(P).as_posix())).hexdigest()==sha(path)
(P/'JNE_submission_package.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
report={'status':'verified_clean_JNE_submission_package_prepared_not_submitted','created_at_utc':datetime.now(timezone.utc).isoformat(),'files':len(files),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'all_archive_member_sha256_match':True,'cover_letter_pdf_pages':len(preview),'cover_letters_only_formal_body_no_internal_action_markers':True,'raw_EEG_included':False,'new_fits':0,'new_checkpoint_inference':0,'journal_submission_performed':False,'input_sha256':{p.relative_to(P).as_posix():sha(p) for p in files},'source_sha256':sha(P/'export_jne_submission_package.py')}
(P/'evidence/author_finalization/submission_package_review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:report[k] for k in ('status','files','archive_bytes','cover_letter_pdf_pages')}))
