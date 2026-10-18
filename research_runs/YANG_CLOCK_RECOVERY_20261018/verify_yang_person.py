#!/usr/bin/env python3
"""Read-only source preprocessing check of an isolated reviewed code copy."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--raw-yang', type=Path, required=True)
    parser.add_argument('--subject', type=int, default=1)
    args = parser.parse_args()
    code = args.code.resolve(strict=True)
    manifest = json.loads((code / 'BUNDLE_MANIFEST.json').read_text())
    if not manifest.get('recovery_parent_manifest_sha256'):
        raise ValueError('an isolated reviewed recovery copy is required')
    for row in manifest['files']:
        raw = (code / row['path']).read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('reviewed code copy differs from manifest')
    sys.path.insert(0, str(code))
    from p1_data import load_yang_subject, load_filter_bank
    person = load_yang_subject(args.subject, args.raw_yang, load_filter_bank(code/'config/filter_bank18.json'),
                               yang_unit_policy='yang_v5_questionmark_V_scale_invariant')
    print(json.dumps({'status':'PASS_READ_ONLY_SOURCE_PERSON', 'subject':args.subject,
                      'shape':list(person.X.shape), 'class_counts':person.audit['class_counts'],
                      'X_sha256':person.audit['X_sha256'], 'y_sha256':person.audit['y_sha256'],
                      'clock_policies':[r['events']['clock_policy'] for r in person.audit['run_audit']],
                      'scope':'full native files hashed and 600 source trials prepared in memory; no cache writes or training'}, indent=2))


if __name__ == '__main__':
    main()
