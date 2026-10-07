"""Package public manuscript assets; exclude caches and package self-reference."""
from pathlib import Path
import hashlib
import json
import zipfile

OUT = Path(__file__).resolve().parent
ARCHIVE = OUT / 'paper_bundle_zero_calibration_q16_20261006.zip'
exclude = {ARCHIVE.name, ARCHIVE.name + '.sha256', 'MANIFEST.sha256'}
files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in exclude
               and '__pycache__' not in p.parts and p.suffix != '.pyc' and not p.name.startswith('.'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest = '\n'.join(sha(p) + '  ' + p.relative_to(OUT).as_posix() for p in files) + '\n'
(OUT / 'MANIFEST.sha256').write_text(manifest)
with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files + [OUT / 'MANIFEST.sha256']:
        z.write(p, 'PAPER_FINAL_20261006/' + p.relative_to(OUT).as_posix())
(OUT / (ARCHIVE.name + '.sha256')).write_text(sha(ARCHIVE) + '  ' + ARCHIVE.name + '\n')
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    for p in files:
        assert hashlib.sha256(z.read('PAPER_FINAL_20261006/' + p.relative_to(OUT).as_posix())).hexdigest() == sha(p)
print(json.dumps({'status': 'verified', 'files': len(files), 'archive_bytes': ARCHIVE.stat().st_size, 'archive_sha256': sha(ARCHIVE)}))
