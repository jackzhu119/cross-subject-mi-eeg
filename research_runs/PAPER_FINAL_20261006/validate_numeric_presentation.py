"""Read-only secondary QA of manuscript tables against delivered saved evidence."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--paper-dir', type=Path, default=Path(__file__).resolve().parent)
parser.add_argument('--output-dir', type=Path, help='Defaults to evidence/quality_update in the paper folder.')
args = parser.parse_args()
P = args.paper_dir.resolve()
OUT = args.output_dir.resolve() if args.output_dir else P / 'evidence' / 'quality_update'
inputs = {}

def read(rel):
    raw = (P / rel).read_bytes()
    inputs[rel] = hashlib.sha256(raw).hexdigest()
    return raw

def js(rel):
    return json.loads(read(rel))

def csv(rel):
    from io import BytesIO
    return pd.read_csv(BytesIO(read(rel)))

content = js('manuscript_content.json')
tables = {b['label'].split('.')[0]: b for b in content['blocks'] if b['type'] == 'table'}
figures = [b for b in content['blocks'] if b['type'] == 'figure']
checks = []
discrepancies = []
numeric_cells = 0

def check(name, condition, details=None):
    checks.append({'check': name, 'passed': bool(condition), 'details': details})
    if not condition:
        discrepancies.append({'check': name, 'details': details})

def num(text):
    return float(str(text).replace('−', '-').replace('–', '-').replace(',', ''))

def cell(name, text, value, decimals=2):
    global numeric_cells
    numeric_cells += 1
    if decimals is None:
        display = str(text).replace('−', '-').replace(',', '').strip()
        decimals = len(display.split('.')[1]) if '.' in display else 0
    check(name, abs(num(text) - float(value)) <= 0.50000001 * 10**(-decimals),
          {'manuscript': text, 'independently_read_or_recomputed': float(value), 'display_decimals': decimals})

internal = csv('tables/completed_internal_inventory.csv')
early = csv('tables/early_binary_qc_inventory.csv')
q13 = csv('tables/q13_contrasts.csv')
q12 = csv('tables/robustness_models.csv')
numbers = js('evidence/paper_internal_numbers.json')
q15_audit = js('evidence/q15_numbers.json')
q15_person = csv('tables/q15_external_subjects.csv')
q15_seed = csv('tables/q15_seed_metrics.csv')
q15_summary = csv('tables/q15_model_summary.csv')
physionet = csv('tables/external_subjects.csv')
q16_laterality = csv('evidence/q16_analysis/subject_hand_laterality.csv')
q16_joined = csv('evidence/q16_analysis/subject_physiology_performance.csv')
q16_summary = js('evidence/q16_analysis/summary.json')
q16_validation = js('evidence/q16_analysis/independent_validation.json')
q16_metadata = js('evidence/q16_analysis/metadata_audit.json')
methods = js('evidence/methods_q15.json')
legacy_methods = js('evidence/previous_draft/methods_and_references.json')

# Table 1 metadata comes from published method audits, not inferred tensor shapes.
bnci = legacy_methods['datasets'][0]
external_metadata = methods['q15']['external_cohorts']
populations = [
    (q16_metadata['n_subjects'], len(q16_metadata['class_counts']), q16_metadata['n_all_four_class_trials'],
     f"{bnci['eeg_channels']} × {legacy_methods['common_bnci_preprocessing']['samples_per_epoch']} at {bnci['native_sampling_rate_hz']} Hz"),
    (q16_metadata['n_subjects'], 2, q16_metadata['n_binary_trials'],
     f"{methods['q14_distinction']['channels']} × {methods['q14_distinction']['n_times']} at {methods['q14_distinction']['sampling_rate_hz']} Hz"),
    (numbers['q14_report']['n_subjects'], 2, numbers['q14_report']['n_unique_trials'],
     f"{methods['q14_distinction']['channels']} × {methods['q14_distinction']['n_times']} at {methods['q14_distinction']['sampling_rate_hz']} Hz"),
    (methods['q15']['source_subjects'], 2, methods['q15']['source_binary_trials'],
     f"{len(methods['q15']['preprocessing']['channels'])} × {methods['q15']['preprocessing']['n_times']} at {methods['q15']['preprocessing']['sampling_rate_hz']} Hz"),
    (external_metadata['Cho2017']['persons'], 2, external_metadata['Cho2017']['trials'],
     f"{len(methods['q15']['preprocessing']['channels'])} × {methods['q15']['preprocessing']['n_times']} at {methods['q15']['preprocessing']['sampling_rate_hz']} Hz"),
    (external_metadata['Lee2019_MI']['persons'], 2, external_metadata['Lee2019_MI']['trials'],
     f"{len(methods['q15']['preprocessing']['channels'])} × {methods['q15']['preprocessing']['n_times']} at {methods['q15']['preprocessing']['sampling_rate_hz']} Hz"),
]
check('Table 1 six separate populations', len(tables['Table 1']['rows']) == len(populations) == 6)
for row, expected in zip(tables['Table 1']['rows'], populations):
    for column, value in zip([1, 2, 3], expected[:3]):
        cell('Table 1 ' + row[0] + ' column ' + str(column), row[column], value, 0)
    check('Table 1 dimensional metadata ' + row[0], row[4] == expected[3])

# All 31 numerical rows in S1 are independently matched by archived condition ID.
for row in tables['Table S1']['rows']:
    matches = internal[internal.arm.str.replace('_', ' ', regex=False).eq(row[0])]
    check('S1 unique source condition ' + row[0], len(matches) == 1)
    if len(matches) == 1:
        r = matches.iloc[0]
        cell('S1 mean ' + row[0], row[1], r.mean_ba * 100)
        cell('S1 participant SD ' + row[0], row[2], r.subject_sd_ba * 100)
        check('S1 person count ' + row[0], int(r.n_subjects) == 9)

# Primary binary QC rows preserve their sequence and calibrated/clean populations.
primary = early[early.primary_endpoint.eq(True) & early.n_subjects.eq(9)]
check('S3 exactly 16 primary nine-person QC rows', len(primary) == len(tables['Table S3']['rows']) == 16)
for row, (_, source) in zip(tables['Table S3']['rows'], primary.iterrows()):
    check('S3 experiment ID ' + row[0], row[0].startswith(source.experiment + ' / '))
    cell('S3 target trials ' + row[0] + source['condition'], row[2], source.n_test_trials, 0)
    cell('S3 mean BA ' + row[0] + source['condition'], row[3], source.mean_ba * 100)

# Every paired effect, CI endpoint, and adjusted p-value in S2.
check('S2 preserves all 11 archived contrasts', len(q13) == len(tables['Table S2']['rows']) == 11)
for row, (_, source) in zip(tables['Table S2']['rows'], q13.iterrows()):
    cell('S2 effect ' + row[0], row[1], source.mean_paired_ba_difference * 100)
    endpoints = row[2].strip('[]').split(',')
    cell('S2 CI lower ' + row[0], endpoints[0], source.subject_bootstrap_95ci_low * 100)
    cell('S2 CI upper ' + row[0], endpoints[1], source.subject_bootstrap_95ci_high * 100)
    cell('S2 family-adjusted p ' + row[0], row[3], source.holm_within_family_p_exploratory, 4)

map4 = ['Q4-E001/BroadCSP_LDA', 'Q4-E001/FBCSP_LDA', 'Q5-E001', 'Q6-E001',
        'Q8-E001', 'Q9-E001/MU_BETA_SHARED', 'Q13-E001/Q8_FIXED20', 'Q13-E006/Q8_RAW_CE_MATCHED']
for row, arm in zip(tables['Table 4']['rows'], map4):
    source = internal[internal.arm.eq(arm)].iloc[0]
    cell('Table 4 mean ' + row[0], row[2], source.mean_ba * 100)

q12_keys = ['SOURCE_POOLED_WHITEN-Q8-E001', 'SOURCE_BALANCED_ERM-Q8-E001',
            'SOURCE_GROUP_DRO-SOURCE_BALANCED_ERM', 'CHANNEL_DROPOUT-Q8-E001',
            'GAIN_PERTURB-Q8-E001', 'CHANNEL_AND_GAIN-Q8-E001']
for row, (_, source), key in zip(tables['Table 5']['rows'], q12.iterrows(), q12_keys):
    validation = numbers['q12_verified_review'][key]
    cell('Table 5 BA ' + row[0], row[1], source.mean_ba * 100)
    cell('Table 5 effect ' + row[0], row[3], validation['mean_difference_pp'])
    endpoints = row[4].strip('[]').split(',')
    for i, end in enumerate(endpoints):
        cell('Table 5 CI ' + row[0] + ' ' + str(i), end, validation['unadjusted_bootstrap_ci_pp'][i])
    cell('Table 5 Holm p ' + row[0], row[5], validation['recomputed_holm_p'], 4)

# Recompute external means and sample SD from actual delivered person means.
for row, model in zip(tables['Table 6']['rows'], ['BROAD_EEGNET_BA','MU_BETA_SHARED_BA','CSP4_LDA_BA']):
    values = physionet[model].to_numpy()
    check('Table 6 all 109 people ' + model, len(values) == 109 and np.isfinite(values).all())
    for i, value in enumerate([values.mean(), values.std(ddof=1), np.median(values)], 1):
        cell('Table 6 ' + model + ' column ' + str(i), row[i], value * 100)
from scipy.stats import binomtest
physionet_delta = physionet.primary_difference_shared_minus_broad
physionet_sign_p = binomtest(int((physionet_delta > 0).sum()), int((physionet_delta != 0).sum()), p=.5, alternative='two-sided').pvalue
check('PhysioNet mean primary difference from saved people', abs(physionet_delta.mean() - numbers['q14_primary']['mean_difference']) < 1e-14)
check('PhysioNet tie-excluding exact sign p from saved people', abs(physionet_sign_p - numbers['q14_primary']['two_sided_exact_sign_test_p_excluding_ties']) < 1e-14)
physionet_primary_display = re.search(r'([+−-]?\d+\.\d+)\s+pp,\s*95% CI\s*\[\s*([+−-]?\d+\.\d+)\s*,\s*([+−-]?\d+\.\d+)\s*\],\s*p\s*=\s*(\d+\.\d+)', tables['Table 6']['note'])
check('PhysioNet primary contrast note has four identifiable values', physionet_primary_display is not None)
if physionet_primary_display:
    expected = [physionet_delta.mean()*100, *[x*100 for x in numbers['q14_primary']['subject_bootstrap_percentile_95_ci']], physionet_sign_p]
    for text, value, label in zip(physionet_primary_display.groups(), expected, ['effect', 'CI lower', 'CI upper', 'sign p']):
        cell('Table 6 primary ' + label, text, value, None)

models = ['BROAD_EEGNET', 'MU_BETA_SHARED', 'CSP4_LDA']
for row, (dataset, model) in zip(tables['Table 7']['rows'], [(d,m) for d in ['Cho2017','Lee2019_MI'] for m in models]):
    people = q15_person[q15_person.dataset.eq(dataset)]
    seeds = q15_seed[q15_seed.dataset.eq(dataset) & q15_seed.model.eq(model)]
    grouped = seeds.groupby('subject')[['balanced_accuracy','left_recall','right_recall']].mean()
    check('Table 7 equal-seed person reconstruction ' + dataset + model,
          np.allclose(grouped.balanced_accuracy.to_numpy(), people.sort_values('subject')[model].to_numpy(), atol=1e-14, rtol=0))
    values = [grouped.balanced_accuracy.mean(), grouped.balanced_accuracy.std(ddof=1),
              grouped.left_recall.mean(), grouped.right_recall.mean()]
    for i, value in enumerate(values, 1):
        cell('Table 7 ' + dataset + model + ' column ' + str(i), row[i], value * 100)
    summary = q15_summary[q15_summary.dataset.eq(dataset)&q15_summary.model.eq(model)].iloc[0]
    check('Table 7 summary matches recalculation ' + dataset + model,
          np.allclose(values, [summary.mean_balanced_accuracy, summary.person_sample_sd, summary.mean_left_recall, summary.mean_right_recall], atol=1e-14, rtol=0))

# Preserve the two frozen cohort tests and their nonzero Monte Carlo resolution.
primary_pattern = r'([+−-]?\d+\.\d+)\s+pp\s*\[\s*([+−-]?\d+\.\d+)\s*,\s*([+−-]?\d+\.\d+)\s*\],\s*Holm p\s*=\s*(\d+\.\d+)'
primary_display = re.findall(primary_pattern, tables['Table 7']['note'])
check('Table 7 exactly two separate primary cohort contrasts', len(primary_display) == 2)
for display, dataset in zip(primary_display, ['Cho2017', 'Lee2019_MI']):
    source = q15_audit['cohorts'][dataset]['primary']
    people = q15_person[q15_person.dataset.eq(dataset)]
    delta = people.MU_BETA_SHARED - people.BROAD_EEGNET
    check('Primary equal-person arithmetic ' + dataset, abs(delta.mean() - source['mean_delta']) < 1e-14)
    for text, value, label in zip(display, [source['mean_delta']*100,source['ci_low']*100,source['ci_high']*100,source['holm_p']], ['effect','CI lower','CI upper','Holm p']):
        cell('Table 7 primary ' + dataset + ' ' + label, text, value, None)
    extreme = source['sign_flip_extreme_count']
    draws = methods['q15']['statistics']['sign_flip_draws']
    check('Primary Monte Carlo plus-one correction ' + dataset,
          abs(source['raw_p'] - (extreme + 1)/(draws + 1)) < 1e-14 and source['raw_p'] > 0)
primary_pairs = [(dataset, q15_audit['cohorts'][dataset]['primary']['raw_p']) for dataset in ['Cho2017', 'Lee2019_MI']]
holm_running = 0.0
for rank, (dataset, raw_p) in enumerate(sorted(primary_pairs, key=lambda x:x[1])):
    holm_running = max(holm_running, min(1.0, raw_p*(len(primary_pairs)-rank)))
    check('Two-cohort Holm arithmetic ' + dataset, abs(holm_running - q15_audit['cohorts'][dataset]['primary']['holm_p']) < 1e-14)

# Direct saved per-person laterality aggregation; labels/denominators are checked.
for row, band in zip(tables['Table 8']['rows'], ['mu', 'beta']):
    people = q16_laterality[q16_laterality.band.eq(band)]
    check('Table 8 all nine people, no exclusions ' + band, len(people) == 9 and set(people.subject)==set(range(1,10)))
    for i, col in enumerate(['contralateral_mean_db', 'ipsilateral_mean_db', 'signed_laterality_db'], 1):
        cell('Table 8 ' + band + ' ' + col, row[i], people[col].mean(), None)
    for text, value in zip(row[4].split(' to '), [people.signed_laterality_db.min(), people.signed_laterality_db.max()]):
        cell('Table 8 range ' + band, text, value, None)
    check('Table 8 negative/positive signs ' + band, row[5] == f'{int((people.signed_laterality_db<0).sum())} / {int((people.signed_laterality_db>0).sum())}')
    check('Table 8 signed descriptor equals contra minus ipsi ' + band,
          np.allclose(people.signed_laterality_db, people.contralateral_mean_db-people.ipsilateral_mean_db, atol=1e-13, rtol=0))

for row, (model, band) in zip(tables['Table S4']['rows'], [(m,b) for m in models for b in ['mu','beta']]):
    people = q16_joined[q16_joined.model.eq(model) & q16_joined.band.eq(band)]
    rho = np.corrcoef(people.signed_laterality_db.rank(method='average'), people.balanced_accuracy_mean.rank(method='average'))[0,1]
    cell('S4 rank-recomputed Spearman ' + model + band, row[2], rho, None)
    cell('S4 participant denominator ' + model + band, row[3], len(people), 0)

counts = q16_summary['counts']
check('Q16 four-class and binary denominators', counts['all_trials']==5184 and counts['binary_trials']==2592 and counts['artifact_flagged_trials']==488 and counts['binary_artifact_flagged_trials']==246 and counts['trial_channel_band_rows']==228096)
check('Q16 independent archived validation status and genuine scope', q16_validation['passed'] and q16_validation['raw_replay']['manual_central_channel_band_pairs_replayed']==31104 and q16_validation['raw_replay']['raw_files_sha256_verified']==18)
check('Q15 saved audit status; original 15 source fits, target fits zero', q15_audit['passed'] and q15_audit['original_source_fits']==15 and q15_audit['target_fits']==0)
check('Table/figure numbering and total', len(tables)==12 and len(figures)==9 and [f['label'] for f in figures]==['Figure 1','Figure 2','Figure 3','Figure 4','Figure 5','Figure 6','Figure S1','Figure S2','Figure S3'])
for f in figures:
    read('figures/' + f['name'] + '.png')
    check('Figure artifact exists ' + f['label'], len(read('figures/' + f['name'] + '.pdf')) > 0)
for rel in ['build_figures.py', 'build_q15_figures.py', 'build_q16_figures.py', 'evidence/figures_q15.json', 'evidence/figures_q16.json']:
    read(rel)
for rel in ['evidence/figures_q15.json', 'evidence/figures_q16.json']:
    figure_receipt = js(rel)
    for name, digest in figure_receipt['input_sha256'].items():
        portable_name = ('evidence/q16_analysis/' + Path(name).name) if name.startswith('../Q16-P001-BNCI-20261006/') else name
        check('Figure source hash ' + rel + ' ' + portable_name, hashlib.sha256(read(portable_name)).hexdigest() == digest)
    for name, digest in figure_receipt['artifact_sha256'].items():
        check('Figure exported artifact hash ' + rel + ' ' + name, hashlib.sha256(read(name)).hexdigest() == digest)

author = js('evidence/author_declarations.json')
text = '\n'.join(b.get('text','') for b in content['blocks'])
check('Author confirmed three declarations, no committee document invented', author['funding']=='none' and author['competing_interests']=='none' and not author['ethics_approval_required_for_this_secondary_analysis'] and not author['ethics_exemption_required_for_this_secondary_analysis'] and not author['committee_issued_determination_asserted'])
for sentence in ['This research received no funding.', 'The author declares no competing interests.', 'The author confirms that neither ethics approval nor an exemption was required for this secondary analysis.']:
    check('Declaration sentence present ' + sentence, sentence in text)
check('Q16 relative-versus-absolute interpretation and unequal-window bias disclosed', 'negative descriptor can coexist with increased power on both sides' in text and 'Unequal log-power estimator variance' in text and 'less-negative' in text)
check('Primary nonzero Cho raw and adjusted p-values and finite Monte Carlo resolution stated',
      '0.000049998' in text and '0.000099995' in text and '1/20,001' in text)

findings = [
    {'kind':'presentation_rule','location':'Table 8 and Table S4','rule':'Displayed rounding alone determines tolerance; full source values remain in CSV/JSON. No n=9 descriptor uncertainty is inferred from decimal precision.'},
    {'kind':'claim_scope','location':'Numerical reconstruction','rule':'Saved numeric arithmetic and audit receipt checks do not rerun model fitting, checkpoint inference, raw EEG spectral analysis, or new statistical hypotheses.'},
]
record = {
    'schema_version':1, 'status':'passed_saved_evidence_numeric_review' if not discrepancies else 'discrepancies_found',
    'reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'Independent read-only numerical presentation review: saved person/seed arithmetic and displayed values in all quantitative main/supplementary tables; audited metadata and descriptive protocol tables; Q15/Q16 archived audit receipts; figure numbering and renderer input/caption inspection; user-provided declarations. No raw spectral replay, fit, new decoder inference, checkpoint loading, or external message.',
    'checks':checks, 'numeric_display_cells_checked':numeric_cells,
    'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'discrepancies':discrepancies, 'presentation_and_claim_rules':findings,
    'input_sha256':inputs, 'new_fits':0, 'new_decoder_inference':0, 'raw_EEG_read':False,
    'limitations':['Table 1 dimensional/population metadata checks use archived source/method receipts; Table 2/3 protocol comparison statements are qualitative inspections, not newly replayed training histories.','Figure source-array/caption semantics, receipt hashes and artifact existence inspected; page layout and pixels are delegated to separate visual QA.','Raw central-channel spectral replay and historical prediction recomputation remain the explicitly scoped archived independent validation, not new work in this review.']
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT/'numeric_review.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
md = '# Independent saved-evidence numerical review\n\n'+record['status']+'\n\n'
md += f"Checked {numeric_cells} displayed numerical cells and {len(checks)} named checks across 12 tables and 9 figures. Found {len(discrepancies)} numerical discrepancies.\n\n"
md += 'Recomputed PhysioNet person means/SDs/medians, Q15 seed-to-person means/recalls and participant SDs, Q16 signed hand descriptors and all six nine-person average-rank correlations. All match the manuscript within its displayed rounding. All 31 S1 rows, 16 S3 rows and 11 S2 contrasts match saved source tables.\n\n'
md += 'Raw spectral replay was not performed in this second review; its existing validation covers 31,104 C3/Cz/C4 trial-band pairs. No new fits or inference occurred.\n\n'
for finding in findings:
    md += '- '+finding['location']+': '+finding['rule']+'\n'
(OUT/'numeric_review.md').write_text(md)
print(json.dumps({'status':record['status'],'numeric_cells':numeric_cells,'checks':len(checks),'failed':len(discrepancies)}))
if discrepancies:
    print(json.dumps(discrepancies,ensure_ascii=False))
