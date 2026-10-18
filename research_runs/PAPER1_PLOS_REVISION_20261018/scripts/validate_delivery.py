#!/usr/bin/env python3
"""Validate an editorial delivery against existing frozen evidence; never run science."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
FROZEN = REPO / 'research_runs/ELIGIBLE_V3_RESULTS_20261018'
BASE = '040956085499ed788948de0d5a09cddd9eabca56'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    checks = []

    def check(name, condition, detail=None):
        checks.append({'check': name, 'passed': bool(condition), 'detail': detail})

    manuscript = (ROOT / 'manuscript_en.md').read_text()
    supplement = (ROOT / 'supplementary_en.md').read_text()
    abstract = manuscript.split('## Abstract\n\n', 1)[1].split('\n\n## Introduction', 1)[0]
    check('abstract_at_most_300_words', len(abstract.split()) <= 300, len(abstract.split()))
    check('no_unresolved_insertion_markers', 'INSERTION_POINT' not in manuscript + supplement)
    check('all_fixed_point_estimates_in_text', all(t in manuscript for t in ['21.1667', '17.1226', '25.2107', '−0.8725', '−3.4935', '1.7484', '−0.5490', '−2.1604', '1.0624', '5.8529', '4.1288', '7.5771', '0.999859']))
    pairs = [('Table2_frozen_comparisons.csv', 'neural_recomputed_comparisons.csv'),
             ('S1_all_neural_condition_summaries.csv', 'neural_recomputed_condition_summaries.csv'),
             ('S2_all_CSP_condition_summaries.csv', 'csp_recomputed_condition_summaries.csv')]
    for table, original in pairs:
        check('exact_frozen_table_copy:' + table, sha(ROOT / 'tables' / table) == sha(FROZEN / 'audits/external' / original))
    comparisons = rows(ROOT / 'tables/Table2_frozen_comparisons.csv')
    check('four_protocol_comparisons_retained', len(comparisons) == 4)
    for row in comparisons:
        formatted = f'{100 * float(row["mean"]):.4f}'.replace('-', '−')
        check('text_matches_frozen_effect:' + row['name'], formatted in manuscript)
        for field in ['t_ci95_low', 't_ci95_high']:
            value = f'{100 * float(row[field]):.4f}'.replace('-', '−')
            check('text_matches_interval:' + row['name'] + ':' + field, value in manuscript)
    neural = rows(ROOT / 'tables/S1_all_neural_condition_summaries.csv')
    conventional = rows(ROOT / 'tables/S2_all_CSP_condition_summaries.csv')
    for row in neural + conventional:
        if row['metric'] in ['ba', 'min_recall']:
            value = f'{100 * float(row["mean"]):.4f}'
            if row['selector'] == 'tail_min_recall' or row['pipeline'] == 'CSP_LDA':
                check('main_descriptive_mean:' + '/'.join(row[k] for k in ['source_level', 'pipeline', 'metric']), value in manuscript)
            if row['pipeline'] != 'CSP_LDA':
                check('supplement_all_condition_mean:' + '/'.join(row[k] for k in ['source_level', 'pipeline', 'selector', 'metric']), value in supplement)
    check('complete_48_rule_summaries', len({(r['source_level'], r['pipeline'], r['selector']) for r in neural}) == 48)
    selected = rows(ROOT / 'tables/S3_all_selected_epochs.csv')
    check('complete_48_epoch_choices', len(selected) == 48 and all(r['min'] == r['max'] for r in selected))
    observed = {r['source_level']: int(r['min']) for r in selected if r['pipeline'] == 'BROAD' and r['selector'] == 'tail_min_recall'}
    check('primary_selected_epochs_27_5_5', observed == {'S9': 27, 'S29': 5, 'S60': 5})
    by = {(r['source_level'], r['metric']): float(r['mean']) for r in neural if r['pipeline'] == 'BROAD' and r['selector'] == 'tail_min_recall'}
    gaps = {level: 200 * (by[level, 'ba'] - by[level, 'min_recall']) for level in ['S9', 'S60']}
    for name, value in [('S9', gaps['S9']), ('S60', gaps['S60']), ('reduction', gaps['S9'] - gaps['S60'])]:
        check('posthoc_algebraic_value:' + name, f'{value:.4f}' in manuscript, value)
    check('posthoc_scope_explicit', 'post hoc' in manuscript and 'no additional hypothesis test' in manuscript)
    check('material_nulls_retained', 'no evidence for additional benefit' in manuscript and 'do not establish equivalence' in manuscript)
    check('exploratory_and_checkpoint_duration_scope', 'prior target exposure was uncertain' in abstract and 'selected training duration changed together' in abstract and 'epoch 27' in manuscript and 'epoch 5' in manuscript)

    before_refs, reference_text = manuscript.split('## References\n\n', 1)
    refs = json.loads((ROOT / 'references.json').read_text())
    ids = [r['number'] for r in refs]
    cited = []
    for group in re.findall(r'\[(\d+(?:[,\s–-]+\d+)*)\]', before_refs):
        for entry in group.replace(' ', '').split(','):
            limits = re.split('[–-]', entry)
            cited.extend(range(int(limits[0]), int(limits[-1]) + 1))
    first_order = list(dict.fromkeys(cited))
    check('consecutive_reference_numbers', ids == list(range(1, len(refs) + 1)))
    check('all_references_cited_and_no_missing', set(cited) == set(ids), first_order)
    check('first_reference_order', first_order == ids)
    listed = [int(n) for n in re.findall(r'^(\d+)\. ', reference_text, flags=re.M)]
    check('manuscript_reference_list_complete', listed == ids)
    for ref in refs:
        check('reference_entry_exact:' + str(ref['number']), ref['vancouver'] in reference_text)
    check('figure_first_mentions_1_to_5', list(dict.fromkeys(re.findall(r'\bFig ([1-5])\b', before_refs.split('## Figure captions')[0]))) == ['1', '2', '3', '4', '5'])
    check('five_captions_present', re.findall(r'^## Fig (\d)\.', manuscript, re.M) == ['1', '2', '3', '4', '5'])
    meta = json.loads((ROOT / 'figures/FIGURE_METADATA.json').read_text())
    check('five_publication_figures', len(meta['figures']) == 5)
    for entry in meta['figures']:
        path = ROOT / 'figures' / (entry['figure'] + '.tif')
        with Image.open(path) as im:
            check('tiff_format:' + path.name, im.mode == 'RGB' and min(im.info['dpi']) >= 300 and path.stat().st_size < 10_000_000 and sha(path) == entry['sha256'])

    for stem, tables, images in [('main_manuscript', 3, 0), ('review_manuscript', 3, 5), ('S1_Appendix', 5, 0)]:
        doc = Document(ROOT / (stem + '.docx'))
        check('editable_table_count:' + stem, len(doc.tables) == tables)
        check('image_count:' + stem, len(doc.inline_shapes) == images)
        numbering = doc.sections[0]._sectPr.xml
        check('continuous_line_numbers:' + stem, 'w:lnNumType' in numbering and 'w:restart="continuous"' in numbering)
        check('double_spaced_12pt_body:' + stem, doc.styles['Normal'].paragraph_format.line_spacing == 2 and doc.styles['Normal'].font.size.pt == 12)
    build = json.loads((ROOT / 'evidence/build_receipt.json').read_text())
    # Renderer checks include actual current source hashes, PDF bounds and lexical coverage.
    check('render_receipt_current_main_source', sha(ROOT / 'manuscript_en.md') in json.dumps(build))
    check('render_receipt_current_supplement_source', sha(ROOT / 'supplementary_en.md') in json.dumps(build))
    for path, checksum in build['output_sha256'].items():
        check('current_export_hash:' + path, sha(ROOT / path) == checksum)
    for name, details in build['document_checks'].items():
        check('export_completeness_and_bounds:' + name, not any(details[k] for k in ['empty_pages', 'text_outside_page', 'authored_lines_missing_from_docx', 'content_tokens_missing_from_pdf', 'forbidden_stale_export_labels']))
    check('no_stale_work_or_old_journal_text', not re.search(r'\bJNE\b|Journal of Neural Engineering|Scientific draft for author review|not submission-ready|experiment remains unexecuted', before_refs + supplement))
    with zipfile.ZipFile(ROOT / 'S1_Data.zip') as archive:
        check('S1_data_crc', archive.testzip() is None)
        manifest = json.loads(archive.read('MANIFEST.json'))
        for item in manifest['payloads']:
            payload = archive.read(item['path'])
            check('S1_data_identity:' + item['path'], len(payload) == item['bytes'] and hashlib.sha256(payload).hexdigest() == item['sha256'])
    check('S1_data_below_supporting_size_limit', (ROOT / 'S1_Data.zip').stat().st_size < 20_000_000)
    changes = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    allowed = str(ROOT.relative_to(REPO)) + '/'
    outside = [name for name in changes if name != 'README.md' and not name.startswith(allowed)]
    check('all_existing_scientific_paths_unchanged', not outside, outside)
    check('frozen_result_archive_unchanged', sha(FROZEN / 'evidence/paper1_expansion_results.zip') == 'df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f')
    result = {'status': 'PASS' if all(c['passed'] for c in checks) else 'FAIL', 'scope': 'Editorial and saved-evidence consistency; no model fit, target inference, raw EEG read, or new statistical test', 'base_commit': BASE, 'checks': checks, 'passed': sum(c['passed'] for c in checks), 'failed': sum(not c['passed'] for c in checks), 'author_approval_of_new_version': 'REQUIRED', 'journal_submission_performed': False}
    (ROOT / 'evidence/delivery_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))
    for item in checks:
        if not item['passed']:
            print(json.dumps(item))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
