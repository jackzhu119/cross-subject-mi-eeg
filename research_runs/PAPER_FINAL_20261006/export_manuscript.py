"""Create consistent English Markdown, DOCX, PDF and standalone LaTeX manuscript exports.

Only archived results are read. No EEG model, training, or prediction is called.
The PDF export is a document-layout export, not evidence of LaTeX compilation.
"""
from pathlib import Path
import csv
import hashlib
import html
import json
import re
import pandas as pd

from docx import Document
from docx.shared import Inches, Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, CondPageBreak

OUT=Path(__file__).resolve().parent
DATA=json.loads((OUT/'manuscript_content.json').read_text())
TITLE=DATA['title'];SUBTITLE=DATA['subtitle'];BLOCKS=DATA['blocks'];REFERENCES=DATA['references']
NUM=json.loads((OUT/'paper_numbers.json').read_text())
AUTHOR=DATA['authors'][0]['name']
AFFILIATION=DATA['authors'][0]['affiliation']
EMAIL=DATA['authors'][0]['email']


def table_column_weights(block):
    """Use the same content-based proportions in every document format."""
    n = len(block['headers'])
    label = block['label']
    if n == 6:
        return [1.25, 1.0, 1.0, 1.0, 2.0, .9] if label.startswith(('Table 8.', 'Methods table M1.')) else [1.45, .62, 1.05, .65, 1.6, .6]
    if n == 5:
        return [1.3, .55, .55, .95, 1.4]
    if n == 4:
        if 'Target information' in label:
            return [1.45, 1.7, 1.2, 2.0]
        return [2.3, 1.9, .7, .6] if 'S3.' in label else [2.9, 1, 1.45, 1]
    if n == 3:
        return [1.5, 2.2, 3.0] if 'Matching and remaining' in label else [3.3, 1.1, 1.3]
    return [1] * n


def _row_flag(row, tag):
    properties = row._tr.get_or_add_trPr()
    flag = OxmlElement('w:' + tag)
    flag.set(qn('w:val'), '1')
    properties.append(flag)

def markdown():
    lines=[f'# {TITLE}','',f'*{SUBTITLE}*','',AUTHOR + ' (corresponding author)', '', AFFILIATION, '', 'Correspondence: ' + EMAIL, '', '7 October 2026','']
    for b in BLOCKS:
        kind=b['type']
        if kind=='heading':lines.extend(['#'*(b['level']+1)+' '+b['text'],''])
        elif kind in ('paragraph','equation'):lines.extend([b['text'],''])
        elif kind=='table':
            lines.extend(['**'+b['label']+'**','','| '+' | '.join(b['headers'])+' |','| '+' | '.join(['---']*len(b['headers']))+' |'])
            lines.extend('| '+' | '.join(row)+' |' for row in b['rows'])
            lines.extend(['',b['note'],''])
        elif kind=='figure':lines.extend([f'![{b["label"]}](figures/{b["name"]}.png)','',f'**{b["label"]}.** {b["caption"]}',''])
    lines.extend(['## References',''])
    lines.extend(f'{i}. {r}' for i,r in enumerate(REFERENCES,1))
    (OUT/'manuscript_en.md').write_text('\n'.join(lines)+'\n')

def word(filename='manuscript_en.docx'):
    doc=Document();s=doc.sections[0]
    s.page_width=Mm(210);s.page_height=Mm(297)
    s.top_margin=s.bottom_margin=Inches(.8)
    s.left_margin=s.right_margin=Inches(.82)
    printable_width=s.page_width-s.left_margin-s.right_margin
    normal=doc.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(11)
    normal.paragraph_format.space_after=Pt(7)
    for style_name,size in [('Title',19),('Subtitle',11),('Heading 1',13),('Heading 2',11),('Heading 3',11)]:
        style=doc.styles[style_name]
        style.font.name='Times New Roman'
        style.font.size=Pt(size)
        style.font.color.rgb=RGBColor(0,0,0)
        style.font.bold=(style_name!='Subtitle')
        style.paragraph_format.keep_together=True
        if style_name.startswith('Heading'):style.paragraph_format.keep_with_next=True
    doc.styles['Subtitle'].font.italic=True
    doc.add_heading(TITLE,0);doc.add_paragraph(SUBTITLE,'Subtitle')
    doc.add_paragraph(AUTHOR + ' (corresponding author)'); doc.add_paragraph(AFFILIATION); doc.add_paragraph('Correspondence: ' + EMAIL); doc.add_paragraph('7 October 2026')
    for paragraph in doc.paragraphs:
        paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.keep_together=True
    for paragraph in doc.paragraphs[2:]:
        for run in paragraph.runs:run.font.size=Pt(10)
    for b in BLOCKS:
        if b['type']=='heading':doc.add_heading(b['text'],b['level'])
        elif b['type'] in ('paragraph','equation'):
            p=doc.add_paragraph(b['text'])
            if b['type']=='equation':
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.keep_together=True
                p.paragraph_format.space_before=Pt(5)
                for run in p.runs:run.italic=True
        elif b['type']=='table':
            p=doc.add_paragraph();p.add_run(b['label']).bold=True
            p.paragraph_format.keep_with_next=True
            p.paragraph_format.keep_together=True
            t=doc.add_table(rows=1,cols=len(b['headers']));t.style='Light Shading Accent 1'
            t.autofit=False
            weights=table_column_weights(b)
            widths=[int(printable_width*w/sum(weights)) for w in weights]
            for column,width in zip(t.columns,widths):column.width=width
            for cell,text in zip(t.rows[0].cells,b['headers']):cell.text=text
            for row in b['rows']:
                for cell,text in zip(t.add_row().cells,row):cell.text=text
            _row_flag(t.rows[0],'tblHeader')
            for row_index,row in enumerate(t.rows):
                _row_flag(row,'cantSplit')
                for cell,width in zip(row.cells,widths):
                    cell.width=width
                    for cell_paragraph in cell.paragraphs:
                        cell_paragraph.paragraph_format.space_before=Pt(0)
                        cell_paragraph.paragraph_format.space_after=Pt(2)
                        cell_paragraph.paragraph_format.line_spacing=1.0
                        cell_paragraph.paragraph_format.keep_with_next=(row_index==0 or (len(t.rows)<=8 and row_index<len(t.rows)-1))
                        for run in cell_paragraph.runs:
                            run.font.size=Pt(9)
                            run.bold=(row_index==0)
            note=doc.add_paragraph(b['note'])
            note.paragraph_format.keep_together=True
            for run in note.runs:run.font.size=Pt(9)
        elif b['type']=='figure':
            doc.add_picture(str(OUT/'figures'/f'{b["name"]}.png'),width=printable_width)
            doc.paragraphs[-1].paragraph_format.keep_with_next=True
            doc.paragraphs[-1].paragraph_format.keep_together=True
            p=doc.add_paragraph();p.add_run(b['label']+'. ').bold=True;p.add_run(b['caption'])
            p.paragraph_format.keep_together=True
            for run in p.runs:run.font.size=Pt(9)
    doc.add_heading('References',1)
    for i,r in enumerate(REFERENCES,1):doc.add_paragraph(f'[{i}] {r}')
    footer=s.footer.paragraphs[0];footer.text='Source-only MI EEG • 7 October 2026 • Page '
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE')
    field_run=OxmlElement('w:r');run_properties=OxmlElement('w:rPr')
    size=OxmlElement('w:sz');size.set(qn('w:val'),'16');run_properties.append(size)
    field_run.append(run_properties);field_text=OxmlElement('w:t');field_text.text='1';field_run.append(field_text)
    field.append(field_run)
    footer._p.append(field)
    for run in footer.runs:run.font.size=Pt(8)
    update_fields=OxmlElement('w:updateFields');update_fields.set(qn('w:val'),'true')
    doc.settings.element.append(update_fields)
    doc.save(OUT/filename)

def pdf(filename='manuscript_en.pdf'):
    base=Path('/usr/share/fonts/truetype/dejavu')
    for name,file in [('Paper','DejaVuSerif.ttf'),('PaperBold','DejaVuSerif-Bold.ttf'),('PaperItalic','DejaVuSerif-Italic.ttf'),('Caption','DejaVuSans.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(base/file)))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='PaperBody',fontName='Paper',fontSize=9.8,leading=14.1,alignment=TA_JUSTIFY,spaceAfter=7))
    styles.add(ParagraphStyle(name='PaperTitle',fontName='PaperBold',fontSize=19,leading=24,alignment=TA_CENTER,spaceAfter=10))
    styles.add(ParagraphStyle(name='PaperSubtitle',fontName='PaperItalic',fontSize=10,leading=14,alignment=TA_CENTER,spaceAfter=12))
    styles.add(ParagraphStyle(name='PaperH1',fontName='PaperBold',fontSize=13,leading=17,spaceBefore=13,spaceAfter=7,keepWithNext=True))
    styles.add(ParagraphStyle(name='PaperH2',fontName='PaperBold',fontSize=10.5,leading=15,spaceBefore=9,spaceAfter=5,keepWithNext=True))
    styles.add(ParagraphStyle(name='PaperTableTitle',fontName='PaperBold',fontSize=10.5,leading=15,spaceBefore=9,spaceAfter=5))
    styles.add(ParagraphStyle(name='PaperCaption',fontName='Caption',fontSize=8,leading=11,spaceAfter=9))
    styles.add(ParagraphStyle(name='PaperCell',fontName='Caption',fontSize=7.5,leading=10))
    styles.add(ParagraphStyle(name='PaperEquation',fontName='PaperItalic',fontSize=9.8,leading=14.1,alignment=TA_CENTER,spaceBefore=5,spaceAfter=9))
    styles.add(ParagraphStyle(name='PaperReference',fontName='Caption',fontSize=8,leading=10.5,spaceAfter=6))
    story=[]
    def p(text,style='PaperBody'):return Paragraph(html.escape(text),styles[style])
    story.extend([p(TITLE,'PaperTitle'),p(SUBTITLE,'PaperSubtitle'),p(AUTHOR + ' (corresponding author)','PaperSubtitle'), p(AFFILIATION,'PaperSubtitle'), p('Correspondence: ' + EMAIL,'PaperSubtitle'), p('7 October 2026','PaperCaption')])
    for b in BLOCKS:
        k=b['type']
        if k=='heading':
            if b['text']=='Supplementary material':story.append(PageBreak())
            story.append(p(b['text'],'PaperH1' if b['level']==1 else 'PaperH2'))
        elif k in ('paragraph','equation'):story.append(p(b['text'],'PaperEquation' if k=='equation' else 'PaperBody'))
        elif k=='table':
            n=len(b['headers']);width=6.65*inch
            weights=table_column_weights(b)
            colwidth=[width*w/sum(weights) for w in weights]
            data=[[p(t,'PaperCell') for t in row] for row in [b['headers']]+b['rows']]
            split_range=(3,len(data)-2) if len(data)>5 else None
            t=Table(data,colWidths=colwidth,repeatRows=1,hAlign='LEFT',rowSplitRange=split_range)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7edf4')),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#607080')),('LINEBELOW',(0,-1),(-1,-1),.6,colors.HexColor('#607080')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fb')])]))
            title=p(b['label'],'PaperTableTitle');note=p(b['note'],'PaperCaption')
            table_height=t.wrap(width,100000)[1]
            title_height=title.wrap(width,100000)[1]+title.getSpaceBefore()+title.getSpaceAfter()
            note_height=note.wrap(width,100000)[1]+note.getSpaceAfter()
            frame_height=(11.7-.72-.7)*inch-12
            group=[title,t,Spacer(1,5),note]
            if title_height+table_height+5+note_height<=frame_height:
                story.append(KeepTogether(group))
            else:
                # Reserve label, repeated header and two body rows together.
                # Long tables can still split without creating one-row fragments.
                minimum_start=title_height+sum(t._rowHeights[:3])+2
                story.extend([CondPageBreak(minimum_start),*group])
        elif k=='figure':
            image=Image(str(OUT/'figures'/f'{b["name"]}.png'));ratio=image.imageHeight/image.imageWidth
            image.drawWidth=6.65*inch;image.drawHeight=image.drawWidth*ratio
            story.append(KeepTogether([image,Spacer(1,5),p(b['label']+'. '+b['caption'],'PaperCaption')]))
    story.append(p('References','PaperH1'))
    reference_paragraphs=[p(f'[{i}] {r}','PaperReference') for i,r in enumerate(REFERENCES,1)]
    story.extend(KeepTogether([paragraph]) for paragraph in reference_paragraphs[:-2])
    story.append(KeepTogether(reference_paragraphs[-2:]))
    def footer(c,doc):
        c.saveState();c.setFont('Caption',7);c.setFillColor(colors.HexColor('#607080'))
        c.drawString(.82*inch,.42*inch,'Source-only MI EEG');c.drawRightString(7.48*inch,.42*inch,str(doc.page));c.restoreState()
    SimpleDocTemplate(str(OUT/filename),pagesize=(8.3*inch,11.7*inch),leftMargin=.82*inch,rightMargin=.83*inch,topMargin=.72*inch,bottomMargin=.7*inch,title=TITLE,author=AUTHOR).build(story,onFirstPage=footer,onLaterPages=footer)

def tex_escape(s):
    replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    s=''.join(replacements.get(c,c) for c in s)
    for a,b in [('μ',r'$\mu$'),('β',r'$\beta$'),('Δ',r'$\Delta$'),('θ',r'$\theta$'),('Σ',r'$\Sigma$'),('±',r'$\pm$'),('ρ',r'$\rho$'),('α',r'$\alpha$'),('×',r'$\times$'),('−','-'),('–','--'),('—','---'),('’',"'"),('“','``'),('”',"''"),('≤',r'$\leq$'),('≥',r'$\geq$'),('→',r'$\to$'),('•',r'$\cdot$')]:s=s.replace(a,b)
    return s

def tex_inline_figure(name):
    if 'q16' in name or name == 'figure_workflow_zero_calibration':
        from tex_q16_figures import tex_inline_figure as render
    elif name in {'figure4_q15_external_transfer','figureS2_q15_participant_heterogeneity'}:
        from tex_q15_figures import tex_inline_figure as render
    else:
        from tex_figures import tex_inline_figure as render
    return render(name,OUT,NUM)

def latex():
    lines=[r'\documentclass[11pt]{article}',r'\usepackage[T1]{fontenc}',r'\usepackage[utf8]{inputenc}',r'\usepackage[margin=0.9in]{geometry}',r'\usepackage{amsmath,booktabs,array,longtable,graphicx,hyperref,pgfplots}',r'\usepgfplotslibrary{groupplots}',r'\pgfplotsset{compat=1.18}',r'\hypersetup{hidelinks}',r'\setlength{\emergencystretch}{3em}',r'\title{'+tex_escape(TITLE)+r'\\\large '+tex_escape(SUBTITLE)+'}',r'\author{'+tex_escape(AUTHOR)+r'\\\small '+tex_escape(AFFILIATION)+r'\\\small Correspondence: \texttt{'+tex_escape(EMAIL)+'}}',r'\date{7 October 2026}',r'\begin{document}',r'\maketitle']
    for b in BLOCKS:
        k=b['type']
        if k=='heading':
            if b['text']=='Abstract':lines.append(r'\section*{Abstract}')
            else:lines.append((r'\section*{' if b['level']==1 else r'\subsection*{')+tex_escape(b['text'])+'}')
        elif k=='paragraph':lines.extend([tex_escape(b['text']),''])
        elif k=='equation':lines.extend([r'\begin{equation*}',b['latex'],r'\end{equation*}'])
        elif k=='table':
            n=len(b['headers'])
            weights=table_column_weights(b)
            spec='@{}'+''.join(r'>{\raggedright\arraybackslash}p{'+f'{.88*w/sum(weights):.6f}'+r'\linewidth}' for w in weights)+'@{}'
            header=' & '.join(tex_escape(t) for t in b['headers'])+r' \\'
            lines.extend([r'\par\medskip\noindent\textbf{'+tex_escape(b['label'])+'}',r'\begingroup\small\setlength{\tabcolsep}{4pt}',r'\begin{longtable}{'+spec+'}',r'\toprule',header,r'\midrule\endfirsthead',r'\toprule',header,r'\midrule\endhead',r'\bottomrule\endfoot',r'\bottomrule\endlastfoot'])
            lines.extend(' & '.join(tex_escape(t) for t in row)+r' \\' for row in b['rows'])
            lines.extend([r'\end{longtable}',r'\noindent\footnotesize '+tex_escape(b['note']),r'\par\endgroup\medskip'])
        elif k=='figure':
            lines.extend([r'\begin{figure}[htbp]',r'\centering',r'\resizebox{\linewidth}{!}{'+tex_inline_figure(b['name'])+'}',r'\caption*{\textbf{'+tex_escape(b['label'])+'}. '+tex_escape(b['caption'])+'}',r'\end{figure}'])
    # caption* is explicitly supplied; no external .bib or figure assets are needed.
    lines.insert(5,r'\usepackage{caption}')
    lines.extend([r'\section*{References}',r'\begin{enumerate}'])
    lines.extend(r'\item '+tex_escape(r) for r in REFERENCES)
    lines.extend([r'\end{enumerate}',r'\end{document}'])
    (OUT/'manuscript.tex').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__':
    markdown();word();pdf();latex()
    word_count=sum(len(re.findall(r"\b[\w’-]+\b",b.get('text',''))) for b in BLOCKS if b['type']=='paragraph')
    report={'english_body_words':word_count,'references':len(REFERENCES),'figures':sum(b['type']=='figure' for b in BLOCKS),'tables':sum(b['type']=='table' for b in BLOCKS),'formats':['md','docx','pdf','tex'],'new_fits':0,'new_checkpoint_inference':0,'pdf_export_engine':'ReportLab','latex_compilation_status':'separate_native_check'}
    (OUT/'evidence/export_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
