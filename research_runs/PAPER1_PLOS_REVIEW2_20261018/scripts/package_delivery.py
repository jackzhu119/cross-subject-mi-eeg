#!/usr/bin/env python3
"""Package validated editorial artifacts; no scientific execution or cloud action."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'Paper1_PLOS_ONE_Review2_20261018.zip'
EXCLUDED = {ARCHIVE.name, ARCHIVE.name + '.sha256', 'MANIFEST.sha256', 'evidence/package_receipt.json'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    validation = json.loads((ROOT / 'evidence/delivery_validation.json').read_text())
    if validation['status'] != 'PASS':
        raise ValueError('A passing current editorial validation is required')
    paths = sorted(p for p in ROOT.rglob('*') if p.is_file() and str(p.relative_to(ROOT)) not in EXCLUDED and '__pycache__' not in p.parts)
    inventory = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    manifest = ROOT / 'MANIFEST.sha256'
    manifest.write_text(''.join(f'{checksum}  {name}\n' for name, checksum in inventory.items()))
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths + [manifest]:
            archive.write(path, str(path.relative_to(ROOT)))
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise ValueError('Editorial package CRC failure')
        for name, checksum in inventory.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != checksum:
                raise ValueError('Editorial package content mismatch: ' + name)
    checksum = digest(ARCHIVE)
    ARCHIVE.with_name(ARCHIVE.name + '.sha256').write_text(f'{checksum}  {ARCHIVE.name}\n')
    receipt = {'status': 'EDITORIAL_PACKAGE_CONTENT_VERIFIED', 'archive': ARCHIVE.name, 'bytes': ARCHIVE.stat().st_size, 'sha256': checksum, 'payload_count': len(paths), 'manifest_sha256': digest(manifest), 'scientific_source_commit': '040956085499ed788948de0d5a09cddd9eabca56', 'editorial_base_commit': validation['base_commit'], 'delivery_validation_sha256': digest(ROOT / 'evidence/delivery_validation.json'), 'no_new_fits_or_inference': True, 'new_posthoc_tests': 4, 'remote_publication': 'PENDING_TOOL_PERMISSION', 'journal_submission_performed': False, 'author_approval_of_new_version': 'REQUIRED', 'archive_identity_exclusions': sorted(EXCLUDED)}
    (ROOT / 'evidence/package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
