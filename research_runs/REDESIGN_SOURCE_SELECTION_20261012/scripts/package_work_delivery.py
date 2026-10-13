"""Bundle this separate research work delivery, never a submission/release."""
from pathlib import Path
import hashlib,json,zipfile
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parents[1]
EXCLUDE={'WORK_PACKAGE_MANIFEST.json','CHECKSUMS.sha256','Research_Work_Package.zip','Research_Work_Package.zip.sha256','github_publication_receipt.json'}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    verdict=json.loads((BASE/'evidence/final_work_delivery_validation.json').read_text())
    if verdict['failed_checks'] or verdict['submission_ready'] is not False:
        raise ValueError('Work package requires scoped technical PASS and explicit not-submission-ready state')
    paths=sorted(p for p in BASE.rglob('*') if p.is_file() and p.name not in EXCLUDE and not any(x in p.parts for x in ['__pycache__','.pytest_cache']) and p.suffix not in ['.pyc','.log'])
    raw=[str(p) for p in paths if p.suffix.lower() in {'.mat','.edf','.bdf','.gdf','.npz'}]
    if raw:raise ValueError('Raw EEG is not bundled')
    manifest={'built_at_utc':datetime.now(timezone.utc).isoformat(),'status':'TECHNICAL_WORK_PACKAGE_NOT_SUBMISSION_READY','science_scope':'historical audit + completed retrospective source CSP + conditional future neural/inference software; no independent target result','files':{str(p.relative_to(BASE)):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in paths},'new_real_source_csp_fits':10,'new_real_neural_fits':0,'target_fits':0,'new_target_predictions':0,'formal_release_created':False,'new_DOI_created':False,'submission_ready':False}
    m=BASE/'WORK_PACKAGE_MANIFEST.json';m.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    c=BASE/'CHECKSUMS.sha256';c.write_text('\n'.join(v['sha256']+'  '+name for name,v in manifest['files'].items())+'\n'+digest(m)+'  WORK_PACKAGE_MANIFEST.json\n')
    bundle=BASE/'Research_Work_Package.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths+[m,c]:z.write(p,p.relative_to(BASE))
    with zipfile.ZipFile(bundle) as z:
        for name,v in manifest['files'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=v['sha256']:raise ValueError('Bundle read-back mismatch')
    (BASE/'Research_Work_Package.zip.sha256').write_text(digest(bundle)+'  '+bundle.name+'\n')
    print(json.dumps({'status':manifest['status'],'files':len(paths)+2,'bytes':bundle.stat().st_size,'sha256':digest(bundle),'submission_ready':False}))
if __name__=='__main__':main()
