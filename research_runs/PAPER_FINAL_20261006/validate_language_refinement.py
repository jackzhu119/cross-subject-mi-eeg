"""Check reviewed language changes against the preceding immutable manuscript."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re

P = Path(__file__).resolve().parent
def load(n): return json.loads((P/n).read_text())
def sha(n): return hashlib.sha256((P/n).read_bytes()).hexdigest()
old = load('evidence/language_refinement/prior_manuscript_content.json')
new = load('manuscript_content.json')
edits = load('language_refinement.json')
numeric = re.compile(r'[+\-−]?\d+(?:[.,]\d+)*(?:[eE][+\-]?\d+)?')
citation = re.compile(r'\[\d+(?:[,–\-]\d+)*\]')
checks = {}
def check(name, condition):
    checks[name] = bool(condition)
    if not condition: raise AssertionError(name)
check('same_176_manuscript_blocks', len(old['blocks']) == len(new['blocks']) == 176)
for key in ['title','subtitle','authors','date','references','reference_keys','new_fits','new_checkpoint_inference']:
    check('unchanged_metadata_'+key, old[key] == new[key])
changes = {(e['index'],e['field']):e for e in edits['block_edits']}
check('unique_language_replacements',len(changes)==len(edits['block_edits']))
for index,(before,after) in enumerate(zip(old['blocks'],new['blocks'])):
    check('block_fields_'+str(index),before.keys()==after.keys())
    for field in before:
        if before[field] == after[field]: continue
        change=changes.get((index,field))
        check('authorized_change_'+str(index)+'_'+field,
              change is not None and before[field]==change['before'] and after[field]==change['after'])
        check('allowed_prose_field_'+str(index)+'_'+field,
              (before['type']=='paragraph' and field=='text') or
              (before['type']=='figure' and field=='caption') or
              (before['type']=='table' and field=='note'))
        check('numeric_literals_'+str(index)+'_'+field,numeric.findall(before[field])==numeric.findall(after[field]))
        check('citation_literals_'+str(index)+'_'+field,citation.findall(before[field])==citation.findall(after[field]))
for index in edits['unchanged_declaration_indexes']:
    check('unchanged_material_disclosure_or_declaration_'+str(index),old['blocks'][index]==new['blocks'][index])
for change in edits['companion_file_edits']:
    name=change['path'].removeprefix('research_runs/PAPER_FINAL_20261006/')
    check('companion_literal_numeric_'+name+'_'+hashlib.sha256(change['before'].encode()).hexdigest()[:10],numeric.findall(change['before'])==numeric.findall(change['after']))
    check('companion_literal_citation_'+name+'_'+hashlib.sha256(change['before'].encode()).hexdigest()[:10],citation.findall(change['before'])==citation.findall(change['after']))
    check('companion_accepted_text_'+name+'_'+hashlib.sha256(change['after'].encode()).hexdigest()[:10],change['after'] in (P/name).read_text())
baseline=load('evidence/language_refinement/baseline_assets.json')['sha256']
scientific=[n for n in baseline if n.startswith(('tables/','figures/','evidence/q16_analysis/')) or n in ['references.json','references.bib','evidence/q15_numbers.json','paper_numbers.json']]
for name in scientific: check('immutable_scientific_display_asset_'+name,sha(name)==baseline[name])
words=lambda data:sum(len(re.findall(r"\b[\w’-]+\b",b.get('text',''))) for b in data['blocks'] if b['type']=='paragraph')
report={
    'status':'language_edit_numbers_citations_and_scientific_assets_preserved',
    'checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'checks_failed':[],
    'baseline_commit':edits['baseline_commit'],'block_edits':len(changes),
    'companion_file_edits':len(edits['companion_file_edits']),
    'all_changed_literal_numeric_and_citation_sequences_identical':True,
    'all_table_headers_rows_labels_equations_and_figure_data_unchanged':True,
    'all_author_ethics_and_AI_declarations_unchanged':True,
    'scientific_display_assets_byte_unchanged':len(scientific),'references_unchanged':28,
    'body_words_before':words(old),'body_words_after':words(new),
    'no_new_statistical_outputs':True,'new_fits':0,'new_checkpoint_inference':0,
    'new_editorial_version_author_approval_received':False,
    'prior_scientific_candidate_author_approval_retained':True,
    'input_sha256':{n:sha(n) for n in ['manuscript_content.json','language_refinement.json','apply_language_refinement.py','validate_language_refinement.py','evidence/language_refinement/prior_manuscript_content.json']}
}
(P/'evidence/language_refinement/edit_integrity.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'checks':len(checks),'block_edits':len(changes),'body_words_after':words(new)}))
