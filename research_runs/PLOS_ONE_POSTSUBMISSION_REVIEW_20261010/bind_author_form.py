"""Rebind the administrative checklist to actual candidate PDF line numbers."""
from pathlib import Path
from datetime import datetime,timezone
import fitz,json,hashlib,re
P=Path(__file__).resolve().parent;B=P.parents[1]/'research_runs/PLOS_ONE_SUBMISSION'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); norm=lambda x:re.sub(r'\s+',' ',x).strip()
line={}
for pg in fitz.open(P/'PLOS_ONE_Manuscript_Review.pdf'):
 ll=[l for b in pg.get_text('dict')['blocks'] if 'lines'in b for l in b['lines']]
 gutters=[l for l in ll if l['bbox'][0]<50 and ''.join(s['text'] for s in l['spans']).isdigit()]
 body=[l for l in ll if l['bbox'][0]>=60 and l['bbox'][1]<780]
 for g in gutters:
  near=min(body,key=lambda l:abs(l['bbox'][1]-g['bbox'][1]))
  if abs(near['bbox'][1]-g['bbox'][1])<2:line[int(''.join(s['text'] for s in g['spans']))]=''.join(s['text'] for s in near['spans'])
markers=['This study involved secondary analysis','The retained research records document access','The author reports access only','Data and code availability']
starts=[next(k for k,v in sorted(line.items()) if norm(v).startswith(s)) for s in markers]
ranges={n:[starts[i],starts[i+1]-1] for i,n in enumerate(['secondary_analysis_ethics_author_assessment','documented_access_dates','direct_identifier_access_author_report'])}
access=json.loads((P/'evidence/research_access_dates.json').read_text())
assert norm(' '.join(line[k] for k in range(*[ranges['documented_access_dates'][0],ranges['documented_access_dates'][1]+1])))==norm(access['methods_access_paragraph'])
assert norm(' '.join(line[k] for k in range(*[ranges['direct_identifier_access_author_report'][0],ranges['direct_identifier_access_author_report'][1]+1])))==norm(access['methods_identifiability_paragraph'])
r=json.loads((B/'AuthorForms/form_completion_receipt.json').read_text());r['methods_line_ranges']=ranges;r['completed_at_utc']=datetime.now(timezone.utc).isoformat();r['scope']='Administrative candidate form, not submitted or signed; existing author facts, recorded access dates and actual revised Methods PDF lines. No institutional ethics determination.'
r['q3_retrospective_data_access']=f"Completed; Methods lines {starts[1]}–{starts[3]-1}"
fields={(x['page'],x['field']):x['value'] for x in r['fields']}
fields[(1,'all countries where data collection took place')]=re.sub(r'See Methods lines \d+–\d+\.',f'See Methods lines {starts[0]}–{starts[3]-1}.',fields[(1,'all countries where data collection took place')])
fields[(2,'Please state the line numbers in the Methods where this is reported 1_2')]=f'{starts[1]}–{starts[3]-1}'
d=fitz.open(P/'AuthorForms/PLOS_Human_Participants_Checklist_2026_blank.pdf')
for pg in d:
 for w in pg.widgets():w.field_value=fields[(pg.number+1,w.field_name)];w.update()
out=P/'AuthorForms/PLOS_Human_Participants_Checklist_2026_completed.pdf';tmp=out.with_suffix('.tmp.pdf');d.save(tmp);d.close();tmp.replace(out)
for x in r['fields']:x['value']=fields[(x['page'],x['field'])]
r['manuscript_docx_sha256']=h(P/'PLOS_ONE_Manuscript.docx');r['manuscript_review_pdf_sha256']=h(P/'PLOS_ONE_Manuscript_Review.pdf');r['completed_form_sha256']=h(out);r['candidate_approval']='PENDING_AUTHOR_REVIEW';r['candidate_submitted']=False
(P/'AuthorForms/form_completion_receipt.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
(P/'AuthorForms/README_zh.md').write_text(f'''# 修订候选稿：Human Participants Checklist\n\n保留官方空白模板原始字节；填写版已重新绑定本候选稿实际 PDF Methods 行号，不代表已上传或期刊认可伦理判断。\n\n- 作者对二次分析无需审批/豁免的判断：{starts[0]}–{starts[1]-1} 行。\n- 留存研究访问记录：{starts[1]}–{starts[2]-1} 行。\n- 作者报告身份信息访问范围：{starts[2]}–{starts[3]-1} 行。\n\n本候选版本待作者审读。如编辑允许替换，仍须复核门户生成 PDF 的行号。无正式伦理文件，不虚构机构决定、编号或豁免。官方模板来源与 hash 见 official_template_source.json；实际填写字段与稿件 hash 见 form_completion_receipt.json。原已投稿 v1.1 表单未改。\n''')
print(json.dumps(ranges))
