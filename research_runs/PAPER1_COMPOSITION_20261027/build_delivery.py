"""Build the small, deterministic code-only school bundle; no dependencies/data."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import tarfile


def build(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    files = sorted(p for p in root.rglob('*') if p.is_file()
                   and not any(part in ('dist', '__pycache__', '.pytest_cache') for part in p.relative_to(root).parts)
                   and p.name not in ('LAUNCH_ON_SCHOOL.sh', 'DELIVERY.json')
                   and p.suffix not in ('.pyc', '.pyo'))
    rows = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    manifest = (json.dumps({'schema_version': 1, 'files': rows}, indent=2, sort_keys=True)+'\n').encode()
    out = root / 'dist/paper1-composition-code.tar.gz'
    out.parent.mkdir(exist_ok=True)
    with out.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w|') as archive:
            for name, data in [('BUNDLE_MANIFEST.json', manifest)] + [(r['path'], (root/r['path']).read_bytes()) for r in rows]:
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                archive.addfile(info, io.BytesIO(data))
    result = {'file': out.name, 'bytes': out.stat().st_size,
              'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'payloads': len(rows),
              'raw_data_or_model_weights': False}
    (root/'dist/bundle_identity.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
