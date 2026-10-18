#!/usr/bin/env python3
"""Copy frozen small result tables into S1 Data; no numerical recomputation."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'ELIGIBLE_V3_RESULTS_20261018/evidence/paper1_expansion_results.zip'
EXPECTED = 'df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f'
MEMBERS = ['results/comparisons.csv', 'results/condition_summaries.csv',
           'results/csp_condition_summaries.csv', 'results/paired_subject_differences.csv',
           'results/per_subject_metrics.csv', 'results/csp_per_subject_metrics.csv',
           'results/external_subject_seed_metrics.csv', 'results/csp_subject_seed_metrics.csv']


def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Frozen source archive identity mismatch')
    manifest = {'source_commit': '040956085499ed788948de0d5a09cddd9eabca56', 'source_archive_sha256': EXPECTED, 'role': 'Exact frozen small-table copies and explicitly labelled presentation sources. No raw EEG or models.', 'payloads': []}
    with zipfile.ZipFile(SOURCE) as source, zipfile.ZipFile(ROOT / 'S1_Data.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        payloads = [(name, source.read(name)) for name in MEMBERS]
        payloads += [(str(p.relative_to(ROOT)), p.read_bytes()) for folder in ['tables', 'figure_data'] for p in sorted((ROOT / folder).glob('*')) if p.is_file()]
        for name, payload in payloads:
            output.writestr(name, payload)
            manifest['payloads'].append({'path': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        output.writestr('MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'evidence/S1_Data_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'S1_Data_bytes': (ROOT / 'S1_Data.zip').stat().st_size, 'payloads': len(payloads)}))


if __name__ == '__main__':
    main()
