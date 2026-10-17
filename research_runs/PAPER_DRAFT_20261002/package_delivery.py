"""Package this paper directory only; retain inspectable SHA-256 integrity."""
from pathlib import Path
import hashlib
import json
import zipfile

OUT=Path(__file__).resolve().parent
allowed={'.md','.json','.csv','.py','.tex','.pdf','.docx','.png','.svg'}
files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.suffix in allowed
             and not p.name.startswith('preview_') and '__pycache__' not in p.parts)
assert all(p.resolve().is_relative_to(OUT.resolve()) for p in files)
assert not any('Q15' in p.relative_to(OUT).as_posix() for p in files)
required=['manuscript_en.pdf','manuscript_en.docx','manuscript_en.md','manuscript.tex','中文说明.md','README.md','evidence/delivery_validation.json']
assert all(OUT/name in files for name in required)
validation=json.loads((OUT/'evidence/delivery_validation.json').read_text())
assert validation['status']=='delivery_document_and_evidence_checks_passed'
hashes={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
manifest=OUT/'MANIFEST.sha256'
manifest.write_text(''.join(f'{digest}  {path}\n' for path,digest in hashes.items()))
files.append(manifest)
bundle=OUT/'paper_bundle_20261002.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for p in files:archive.write(p,arcname=OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(bundle) as archive:
    assert archive.testzip() is None
    for path,digest in hashes.items():
        assert hashlib.sha256(archive.read(OUT.name+'/'+path)).hexdigest()==digest,path
digest=hashlib.sha256(bundle.read_bytes()).hexdigest()
(OUT/'paper_bundle_20261002.zip.sha256').write_text(digest+'  '+bundle.name+'\n')
print(json.dumps({'bundle':str(bundle),'files':len(files),'bytes':bundle.stat().st_size,'sha256':digest,'fits_started':0},ensure_ascii=False))
