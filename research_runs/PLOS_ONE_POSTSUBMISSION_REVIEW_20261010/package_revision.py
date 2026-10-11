"""Package the internal candidate; never submit, release, or execute scientific models."""
from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).resolve().parent
excluded={'evidence/revision_validation.json','evidence/revision_validation.md','evidence/github_publication_receipt.json','FILE_INVENTORY.txt','SHA256SUMS.txt'}
files=[f for f in P.rglob('*') if f.is_file() and f.relative_to(P).as_posix() not in excluded and not f.name.endswith('Package.zip') and not f.name.endswith('Package.zip.sha256') and '__pycache__' not in f.parts]
files.sort(key=lambda f:f.relative_to(P).as_posix())
h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
(P/'FILE_INVENTORY.txt').write_text('\n'.join(f.relative_to(P).as_posix() for f in files)+'\n')
(P/'SHA256SUMS.txt').write_text('\n'.join(h(f)+'  '+f.relative_to(P).as_posix() for f in files)+'\n')
zpath=P/'PLOS_ONE_Postsubmission_Revision_Candidate_Package.zip'
with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in files+[P/'FILE_INVENTORY.txt',P/'SHA256SUMS.txt']:z.write(f,f.relative_to(P).as_posix())
(zpath.with_name(zpath.name+'.sha256')).write_text(h(zpath)+'  '+zpath.name+'\n')
print(json.dumps({'package':zpath.name,'files':len(files)+2,'bytes':zpath.stat().st_size,'sha256':h(zpath),'adjacent_final_receipts_excluded_for_self_binding':sorted(excluded)}))
