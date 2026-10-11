"""Read-only audit of saved prediction CSVs; no EEG/model execution or changes.

All outputs are audit summaries outside the original scientific repository.
No training, prediction inference, threshold changes, shifts, flips or tests.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import numpy as np
import pandas as pd

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
parser.add_argument('--output', type=Path, default=Path('/tmp/q15-archived-csp-audit'))
args = parser.parse_args()
ROOT = args.root.resolve()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
EVIDENCE = {}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def recorded(path):
    rel = path.relative_to(ROOT).as_posix()
    EVIDENCE[rel] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    return json.loads(path.read_text())

def frame(path):
    rel = path.relative_to(ROOT).as_posix()
    EVIDENCE[rel] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    return pd.read_csv(path, dtype={'seed': str})

def score(g):
    left = g.label.to_numpy() == 1
    right = g.label.to_numpy() == 2
    y = g.predicted_label.to_numpy()
    lr = float(np.mean(y[left] == 1))
    rr = float(np.mean(y[right] == 2))
    confusion = [[int(np.sum(left & (y == 1))), int(np.sum(left & (y == 2)))],
                 [int(np.sum(right & (y == 1))), int(np.sum(right & (y == 2)))]]
    return {'n_trials': len(g), 'class_counts': {'left': int(left.sum()), 'right': int(right.sum())},
            'balanced_accuracy': (lr + rr)/2,
            'left_recall': lr, 'right_recall': rr,
            'left_prediction_proportion': float(np.mean(y == 1)),
            'median_p_left': float(np.median(g.p_left)),
            'confusion_rows_actual_left_right_columns_predicted_left_right': confusion}

checks = []
cohorts = {}
sv = recorded(ROOT/'results/Q15-E005/source_validation.json')
ev = recorded(ROOT/'results/Q15-EXTERNAL/validation_report.json')
for report, name in [(sv,'source'),(ev,'external')]:
    expected = report.get('artifact_sha256', {})
    mismatches = []
    for rel, expected_sha in expected.items():
        p = ROOT/rel
        if not p.is_file() or sha(p) != expected_sha:
            mismatches.append(rel)
    checks.append({'check': f'{name}_archived_validation_artifact_hashes',
                   'checked_files': len(expected), 'passed': not mismatches, 'mismatches': mismatches})

for dataset, arm in [('Cho2017','Q15-E006'),('Lee2019_MI','Q15-E007')]:
    p = ROOT/f'results/Q15-EXTERNAL/{arm}/predictions.csv'
    all_rows = frame(p)
    d = all_rows.loc[all_rows.model == 'CSP4_LDA'].copy()
    assert not d.empty and set(d.seed) == {'deterministic'}
    assert not d.sample_id.duplicated().any()
    assert np.array_equal(d.predicted_label.to_numpy(),
                          np.argmax(d[['p_left','p_right']].to_numpy(), axis=1)+1)
    assert np.isfinite(d[['p_left','p_right']].to_numpy()).all()
    assert np.allclose(d[['p_left','p_right']].sum(axis=1), 1, rtol=1e-6, atol=1e-7)
    stats = recorded(ROOT/f'results/Q15-EXTERNAL/{arm}/statistics.json')
    individual = [{'subject': int(s), **score(g)} for s,g in d.groupby('subject', sort=True)]
    primary_ba = float(np.mean([r['balanced_accuracy'] for r in individual]))
    mean_left_share = float(np.mean([r['left_prediction_proportion'] for r in individual]))
    exact_matches = []
    for r in individual:
        record = next(x for x in stats['persons'] if x['subject'] == r['subject'])
        v = record['models']['CSP4_LDA']['per_seed']['deterministic']
        exact_matches.append(abs(r['balanced_accuracy'] - v['balanced_accuracy']) < 1e-14 and
            r['confusion_rows_actual_left_right_columns_predicted_left_right'] ==
            v['confusion_matrix_rows_actual_left_right'])
    assert all(exact_matches)
    assert abs(primary_ba - stats['cohort_equal_person_mean_balanced_accuracy']['CSP4_LDA']) < 1e-14
    cohorts[dataset] = {'experiment_id': arm, 'n_persons': len(individual),
        'n_sessions': int(d[['subject','session']].drop_duplicates().shape[0]),
        'n_original_prediction_rows_all_models': len(all_rows),
        'n_csp_trials': len(d),
        'equal_person_mean_balanced_accuracy': primary_ba,
        'equal_person_mean_left_prediction_proportion': mean_left_share,
        'equal_person_mean_left_recall': float(np.mean([r['left_recall'] for r in individual])),
        'equal_person_mean_right_recall': float(np.mean([r['right_recall'] for r in individual])),
        'pooled_trial_metrics': score(d),
        'binary_label_flip_arithmetic_only_no_new_predictions': {
            'formula': 'For two classes, complementing each stored predicted label gives BA_flip = 1 - BA_original. This is an algebraic identity, not a new intervention/replay.',
            'equal_person_ba_complement': 1-primary_ba,
            'pooled_trial_ba_complement': 1-score(d)['balanced_accuracy'],
            'new_label_flip_experiment_performed': False},
        'per_person': individual,
        'all_original_person_csp_confusion_matrices_and_ba_match': all(exact_matches),
        'p_left_is_stored_model_output_not_verified_calibrated_probability': True,
        'saved_probabilities_and_canonical_argmax_mapping_consistent': True}

q14 = frame(ROOT/'results/Q14-E001/subject_seed_metrics.csv')
q14_csp = q14.loc[q14.model=='CSP4_LDA'].copy()
q14_replay = []
for _,r in q14_csp.iterrows():
    subject = int(r.subject)
    p = ROOT/f'results/Q14-E001/CSP4_LDA/target_{subject:02d}/predictions.csv'
    d = frame(p)
    # The earlier CSV uses y_true/y_pred; do not interpret it as Q15 data.
    label_key = 'label' if 'label' in d else 'y_true'
    predicted_key = 'predicted_label' if 'predicted_label' in d else 'y_pred'
    y,yp = d[label_key].to_numpy(), d[predicted_key].to_numpy()
    ba = float(np.mean([np.mean(yp[y==a]==a) for a in np.unique(y)]))
    assert abs(ba-r.balanced_accuracy)<1e-14 and sha(p)==r.prediction_sha256
    q14_replay.append({'subject':subject,'balanced_accuracy':ba,'prediction_hash_matched':True})

recorded(ROOT/'results/Q15-E005/source/CSP4_LDA/all_source/manifest.json')
recorded(ROOT/'results/Q15-EXTERNAL/inference_freeze.json')
recorded(ROOT/'results/Q15-EXTERNAL/completion_receipt.json')
metadata = {}
for dataset,folder in [('Lee2019_MI','Q15-V001'),('Cho2017','Q15-V002')]:
    r=recorded(ROOT/f'results/{folder}/metadata_audit_receipt.json')
    metadata[dataset]={k:r[k] for k in ['status','n_files','n_subjects','n_labeled_trials',
        'raw_hashes_verified','all_expected_files_hashed','provider_manifest_authenticated',
        'metadata_only','predictions_computed','native_numeric_calibration_verified','target_fits']}
    metadata[dataset]['channel_origin']=r['files'][0]['channel_origin']
    metadata[dataset]['native_label_map']=r['files'][0]['native_label_map']
    metadata[dataset]['canonical_label_map']=r['files'][0]['label_map']
    metadata[dataset]['all_file_canonical_label_maps_consistent']=all(
        item['label_map']=={'left_hand':1,'right_hand':2} for item in r['files'])
    expected_channels=json.loads((ROOT/'results/Q15-EXTERNAL/inference_freeze.json').read_text())['preprocessing']['channels']
    metadata[dataset]['all_files_cover_frozen_canonical_channel_names']=all(
        set(expected_channels).issubset(item['channels']) for item in r['files'])

code_paths=['scripts/q15_source.py','scripts/q15_validate_source.py','scripts/q15_external.py',
            'scripts/q15_validate_external.py','scripts/q15_real_metadata.py',
            'src/mi_eeg/data/q15_context.py','src/mi_eeg/models/q15_csp.py',
            'scripts/q14_source.py','research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json',
            'research_runs/PAPER_FINAL_20261006/evidence/methods_q15.json',
            'research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json']
for rel in code_paths:
    p=ROOT/rel; EVIDENCE[rel]={'sha256':sha(p),'bytes':p.stat().st_size}
model=ROOT/'results/Q15-E005/source/CSP4_LDA/all_source/model.joblib'
EVIDENCE[model.relative_to(ROOT).as_posix()]={'sha256':sha(model),'bytes':model.stat().st_size}
assert sha(model)==sv['csp_model_sha256']
branches=subprocess.run(['gh','api','--paginate','repos/jackzhu119/cross-subject-mi-eeg/branches',
                        '--jq','.[].name'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
report={'schema_version':1,'scope':'Read-only independent audit of archived original predictions and frozen receipts; no EEG execution',
    'created_at_utc':datetime.now(timezone.utc).isoformat(),'repository':'jackzhu119/cross-subject-mi-eeg',
    'baseline_commit':head,'cohorts':cohorts,'hash_checks':checks,
    'original_source_validation':{k:sv[k] for k in ['status','passed','interpretation','counts',
        'csp_coordinate_rule','csp_model_sha256','source_only','target_fits','selected_epochs']},
    'original_external_validation':{k:ev[k] for k in ['status','passed','scientific_validation_passed',
        'raw_auditor_replayed','raw_to_epoch_replayed','frozen_checkpoint_prediction_replayed',
        'statistics_independently_reconstructed','model_state_unchanged','calibration_limitations',
        'target_fits','new_model_fits']},
    'original_metadata_receipts':metadata,
    'frozen_csp_model_artifact': {'path': model.relative_to(ROOT).as_posix(),
        'actual_joblib_bytes_present': True, 'bytes': model.stat().st_size,
        'sha256': sha(model), 'matches_original_source_validation_hash': True,
        'model_deserialized_this_audit': False, 'predictions_executed_this_audit': False},
    'public_frozen_model_readback':json.loads((OUT/'m1_public_model_readback.json').read_text())
        if (OUT/'m1_public_model_readback.json').is_file() else None,
    'earlier_q14_binary_csp_loso':{'equal_person_mean_balanced_accuracy':float(q14_csp.balanced_accuracy.mean()),
        'n_persons':len(q14_csp),'rechecked_prediction_files':q14_replay,
        'not_the_claimed_new_q15_9_fold_loso':True,
        'differences':'Q14 has 22-channel source epochs and earlier preprocessing; Q15 uses 21-channel trial-context CAR plus fixed 20-coordinate Helmert projection.'},
    'missing_report_inputs': [n for n in ['Q15_CSP崩溃_验证报告.md', 'PLOS_ONE_投稿前评审报告.md'] if not (ROOT / 'research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/evidence/author_supplied_reports' / n).is_file()],
    'author_supplied_report_execution_claims_verified_by_this_script': False,
    'unsupported_without_new_report_evidence':[
        'Q15 CSP source resubstitution balanced accuracy of 63.04%',
        'New nine-fold Q15 CSP LOSO balanced accuracy of 61.65%',
        'Any claimed post-hoc intercept shift / centering / target adaptation improvement',
        'Any claimed label-flip sensitivity experiment and numerical results',
        'A proved covariate-shift or faulty-adapter mechanism for left-prediction dominance'],
    'interpretation_limits':[
        'Strong left-prediction dominance is verified descriptively; it is not complete one-class output on all participants.',
        'Original source validation authenticates fit partition, artifact state and declared parameters, not held-out source efficacy.',
        'Raw-to-prediction replay checks consistency with the frozen prospective adapter; it does not independently certify physical electrode order, original Cho reference, voltage calibration or cue hardware latency.',
        'In-sample source training BA, if provided later, would be resubstitution and must not be presented as held-out source performance.',
        'Feature centering or decision-shift estimation using external target inputs is target adaptation even without labels.',
        'Choosing any shift, sign, label map or threshold after inspecting target scores/labels is target-driven tuning and cannot replace the primary frozen zero-target-fit result.',
        'Label-flip complements are arithmetic of stored scores only; no transformed-label prediction files, threshold changes, shift interventions, model executions or statistical tests were conducted.'],
    'public_branches_checked':branches,'evidence_manifest':EVIDENCE,
    'new_model_fits':0,'new_prediction_inference':0,'raw_eeg_access':False,'scientific_repository_modified':False}
OUT.mkdir(exist_ok=True,parents=True)
(OUT/'m1_csp_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report':str(OUT/'m1_csp_audit.json'),'cohort_BA':{k:v['equal_person_mean_balanced_accuracy'] for k,v in cohorts.items()},
                  'hash_checks':checks,'new_model_fits':0,'raw_eeg_access':False},ensure_ascii=False,indent=2))
