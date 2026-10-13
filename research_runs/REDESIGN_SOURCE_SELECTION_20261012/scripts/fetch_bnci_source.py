"""Download official historical source files and verify their frozen SHA256.
No target data, fitting, credentials, or modification of historical files.
"""
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse,hashlib,json,os,time
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--workers',type=int,default=3);args=parser.parse_args();dest=args.destination.resolve();dest.mkdir(parents=True,exist_ok=True)
records=json.loads((ROOT/'research_runs/Q8-E001/results/source_files.json').read_text());out=ROOT/'research_runs/REDESIGN_SOURCE_SELECTION_20261012/evidence/source_access_receipt.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def get(row):
 n=Path(row['path']).name;p=dest/n;u='https://bnci-horizon-2020.eu/database/data-sets/001-2014/'+n
 if p.is_file() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']:return {'file':n,'bytes':p.stat().st_size,'sha256':row['sha256'],'status':'verified_cached','source_url':u}
 tmp=p.with_suffix('.partial');size=0;h=hashlib.sha256()
 try:
  with urlopen(u,timeout=90) as r,tmp.open('wb') as f:
   if r.status!=200:raise ValueError('unexpected_http_status')
   for b in iter(lambda:r.read(4*1024**2),b''):
    size+=len(b)
    if size>row['bytes']:raise ValueError('source_exceeds_expected_bytes')
    h.update(b);f.write(b)
  if size!=row['bytes'] or h.hexdigest()!=row['sha256']:raise ValueError('source_digest_or_size_mismatch')
  tmp.replace(p);return {'file':n,'bytes':size,'sha256':h.hexdigest(),'status':'downloaded_verified','source_url':u}
 except Exception:
  tmp.unlink(missing_ok=True);raise
receipt={'started_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Official historical BNCI source originals only, no target or model access','destination':str(dest),'files':[],'status':'downloading','new_fits':0,'new_predictions':0}
out.write_text(json.dumps(receipt,indent=2)+'\n')
with ThreadPoolExecutor(max_workers=min(args.workers,4)) as pool:
 futures={pool.submit(get,r):Path(r['path']).name for r in records}
 for f in as_completed(futures):
  try:r=f.result();receipt['files'].append(r);print(json.dumps({'source_file':r['file'],'completed':len(receipt['files']),'expected':18,'digest_verified':True}),flush=True)
  except Exception as e:receipt['status']='failed';receipt['error']={'file':futures[f],'code':type(e).__name__};out.write_text(json.dumps(receipt,indent=2)+'\n');raise
  out.write_text(json.dumps(receipt,indent=2)+'\n')
receipt.update({'status':'all_18_verified','completed_at_utc':datetime.now(timezone.utc).isoformat(),'total_bytes':sum(x['bytes'] for x in receipt['files'])});receipt['files'].sort(key=lambda x:x['file']);out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'status':receipt['status'],'files':18,'bytes':receipt['total_bytes']}))
