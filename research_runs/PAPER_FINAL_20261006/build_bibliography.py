"""Export verified reference metadata; standalone manuscript embeds its references."""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'references.json').read_text())['references']
def esc(value):
 s=str(value)
 for a,b in [('&',r'\&'),('%',r'\%'),('_',r'\_')]:s=s.replace(a,b)
 return s
entries=[]
for r in rows:
 assert r.get('verified')
 venue=r.get('venue',r.get('journal',''))
 typ='inproceedings' if any(x in venue for x in ['Learning Representations','Neural Information Processing Systems']) else ('article' if venue and r.get('volume') else 'misc')
 fields={'author':' and '.join(r['authors']) if isinstance(r.get('authors'),list) else r.get('authors',''),'title':'{'+r['title']+'}','year':r['year'],'url':r.get('url','')}
 if venue:fields['booktitle' if typ=='inproceedings' else 'journal' if typ=='article' else 'howpublished']=venue
 for source,target in [('doi','doi'),('volume','volume'),('issue','number'),('pages','pages'),('article_number','pages'),('pages_or_article','pages')]:
  if r.get(source):fields[target]=r[source]
 entries.append('@'+typ+'{'+r['key']+',\n'+',\n'.join('  '+k+' = {'+esc(v)+'}' for k,v in fields.items() if v!='')+'\n}')
(OUT/'references.bib').write_text('\n\n'.join(entries)+'\n')
print(json.dumps({'verified_references_exported':len(entries)}))
