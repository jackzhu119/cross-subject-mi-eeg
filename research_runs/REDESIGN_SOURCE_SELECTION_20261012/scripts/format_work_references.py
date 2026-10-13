"""Format verified work references, preserving the historical bibliographies."""
from pathlib import Path
import json
BASE=Path(__file__).resolve().parents[1]
def main():
    refs=json.loads((BASE/'references.json').read_text())
    lines=[];bib=[]
    for r in refs:
        venue=r.get('journal') or r.get('venue') or r.get('type','')
        pages=r.get('pages') or r.get('pages_or_article')
        doi=r.get('doi');url='https://doi.org/'+doi if doi else r.get('url','')
        authors='; '.join(r['authors']).rstrip('.')
        text=f"{r['work_reference_number']}. {authors}. {r['title'].rstrip('.')}. {venue.rstrip('.')}. {r['year']}"
        if r.get('volume'): text+=';'+str(r['volume'])
        if r.get('issue') and r.get('volume'): text+='('+str(r['issue'])+')'
        if pages: text+=':'+str(pages)
        text+='. '+url+'.'
        lines.append(text)
        fields={'author':' and '.join(r['authors']),'title':r['title'],'year':str(r['year']),'volume':str(r.get('volume','')),'number':str(r.get('issue','')),'pages':str(pages or ''),'doi':doi or '','url':url}
        kind='article' if r.get('journal') or r['key']=='Pfurtscheller1999' else 'misc'
        fields['journal' if kind=='article' else 'howpublished']=venue
        bib.append('@'+kind+'{'+r['key']+',\n'+',\n'.join('  '+k+' = {'+v+'}' for k,v in fields.items() if v)+'\n}')
    (BASE/'REFERENCES.md').write_text('# Working bibliography\n\n'+'\n\n'.join(lines)+'\n')
    (BASE/'references.bib').write_text('\n\n'.join(bib)+'\n')
    p=BASE/'REVISED_MANUSCRIPT.md';s=p.read_text();head,tail=s.split('## References\n',1);after=''
    if '\n## Figures' in tail: after='\n## Figures'+tail.split('\n## Figures',1)[1]
    p.write_text(head+'## References\n\n'+'\n\n'.join(lines)+'\n'+after)
if __name__=='__main__': main()
