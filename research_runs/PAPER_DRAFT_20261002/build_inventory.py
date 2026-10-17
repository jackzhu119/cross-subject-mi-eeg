"""Inventory completed archived work, without running experimental code."""
from pathlib import Path
import hashlib
import json
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
INPUTS = {}

def read_json(path):
    p = ROOT / path
    INPUTS[path] = hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())

def read_csv(path):
    p = ROOT / path
    INPUTS[path] = hashlib.sha256(p.read_bytes()).hexdigest()
    return pd.read_csv(p)

review = read_json('research_runs/PAPER_DRAFT_20261002/evidence/q4_q11_review.json')
later = read_json('research_runs/PAPER_DRAFT_20261002/evidence/independent_numbers.json')
protocol = read_json('research_runs/PAPER_DRAFT_20261002/evidence/q12_q14_review.json')
rows = {}
for name, arm in review['arms'].items():
    note = arm.get('exploratory_boundary', '')
    reuse = arm.get('reused_from', '')
    fit_scope = 'Archived evaluation models; inner fits not counted here'
    if name.startswith('Q4-A001/'):
        fit_scope = 'Nine new scaler/LDA refits on reused Q4 CSP feature caches; no new CSP fits'
        if 'MI8_' in name or 'MI72_' in name:
            reuse = 'Predictions reproduce the Q4 MI8/full-bank endpoint; not an independent outcome'
    if 'reused_Q' in name:
        fit_scope = 'Saved S3 prediction/model reuse; no new historical fit in Q7 cell'
    rows[name] = dict(arm=name, dataset=arm['dataset'], classes=4,
        n_subjects=arm['n_subjects'], mean_ba=arm['mean_subject_ba'],
        subject_sd_ba=arm['subject_sd_ba'], n_evaluation_cells=arm['n_fits_represented'],
        historical_fit_scope=fit_scope, reuse_note=reuse,
        validation_scope=arm['scientific_validation_status'],
        evidence_path='evidence/q4_q11_review.json', interpretation=note)

aliases = {'Q5-HISTORICAL/RAW_CE_REUSE':'Q5-E001', 'Q8-E001/BROAD_MEAN_RANK':'Q8-E001'}
for original, arm in later['arms'].items():
    name = aliases.get(original, original)
    if name in rows:
        assert abs(rows[name]['mean_ba'] - arm['mean_person_ba']) < 1e-12
        continue
    external = name.startswith('Q14-E002R2/')
    rows[name] = dict(arm=name, dataset='PhysioNet EEGMMIDB v1.0.0' if external else 'BNCI2014_001',
        classes=arm['classes'], n_subjects=arm['n_subjects'], mean_ba=arm['mean_person_ba'],
        subject_sd_ba=arm['sd_person_ba'], n_evaluation_cells=arm['n_evaluation_cells'],
        historical_fit_scope='Seven frozen source models reused; no external fit' if external else 'Archived final evaluation cells; inner fits not counted here',
        reuse_note='87 prior subjects retained; 22 completed under rate amendment' if external else '',
        validation_scope='Saved predictions independently reaggregated; historical receipt scope in q12_q14_review.json',
        evidence_path='evidence/independent_numbers.json',
        interpretation='Separate binary external primary/contextual comparisons' if external else ('Binary source development, separate from four-class results' if arm['classes']==2 else 'Exploratory four-class development'))

inventory = pd.DataFrame(rows.values())
assert inventory.arm.is_unique and inventory.mean_ba.between(0,1).all()
inventory.to_csv(OUT/'tables/completed_internal_inventory.csv',index=False)

qc = []
p2_predictions = read_csv('outputs/P2-E001/predictions.csv')
for item in review['early_binary_QC_inventory']:
    for summary in item['summary']:
        directory = item['artifact_directory']
        stratum = summary.get('test_stratum','clean' if directory.endswith('P2-E001') else 'all')
        mode = summary.get('mode','cross_subject')
        condition = summary.get('condition',summary.get('training_policy','expert_clean_only' if directory.endswith('P2-E001') else 'all_trials'))
        primary = stratum == ('all' if directory.endswith('P2-E002-ALLTRIALS') else 'clean')
        target_trials = int(summary.get('n_test_trials',2346 if stratum=='clean' else 2592))
        if directory.endswith('P2-E001'):
            target_trials = int(((p2_predictions['mode']==mode)&(p2_predictions.model==summary['model'])).sum())
        qc.append(dict(experiment=directory.split('/')[-1],mode=mode,
            condition=condition,model=summary.get('model','CSP4 + shrinkage LDA'),
            test_stratum=stratum,n_subjects=int(summary.get('n_subjects',summary.get('n_subjects_scored',9))),
            n_test_trials=target_trials,
            mean_ba=float(summary['mean_balanced_accuracy']),
            subject_sd_ba=float(summary['sd_balanced_accuracy']),primary_endpoint=primary,
            target_information=item['target_information'],artifact_policy=item['artifact_policy'],
            validation_scope=item['validation_status'],evidence_path='evidence/q4_q11_review.json'))

smoke_status = read_json('outputs/P2-SMOKE-S1B/run_status.json')
smoke_summary = read_csv('outputs/P2-SMOKE-S1B/summary.csv')
smoke_predictions = read_csv('outputs/P2-SMOKE-S1B/predictions.csv')
assert smoke_status['status']=='complete'
for r in smoke_summary.to_dict('records'):
    qc.append(dict(experiment='P2-SMOKE-S1B',mode=r['mode'],condition='expert_clean_only',
        model=r['model'],test_stratum='clean',n_subjects=1,n_test_trials=int((smoke_predictions.model==r['model']).sum()),
        mean_ba=r['mean_balanced_accuracy'],subject_sd_ba='',primary_endpoint=False,
        target_information='Labeled training session from the evaluated person; single-person technical smoke only',
        artifact_policy='Expert-clean;279 total source/target epochs in run receipt',
        validation_scope='Run receipt/summary inspected; no independent scientific validator located',
        evidence_path='outputs/P2-SMOKE-S1B/summary.csv'))
qc_frame=pd.DataFrame(qc)
qc_frame.to_csv(OUT/'tables/early_binary_qc_inventory.csv',index=False)

analyses = [
 ('P1-E001','outputs/P1-E001/data_audit.json','Single-subject acquisition/data audit; no decoder endpoint'),
 ('Q8-A001','research_runs/Q8-A001/analysis/analysis_summary.json','Post-hoc source validation-curve and epoch-selection stability audit; no new fit'),
 ('Q8-A002','research_runs/Q8-A002/analysis/inner_fold_influence_summary.csv','Leave-one-inner-fold-out selection sensitivity on archived curves; no new fit'),
 ('Q8-A003','research_runs/Q8-A003/analysis/candidate_rule_stability_summary.csv','Six candidate aggregation rules, archived curve stability only; not six newly evaluated target models'),
 ('Q10-V001','results/Q10-V001/audit_report.json','Independent archived prediction/partition/statistics audit; not an additional decoder arm'),
 ('Q14-E002','results/Q14-E002/freeze_receipt.json','All-nine-source frozen models;8 inner deep fits,6 final deep fits,1 shallow fit;no target BA at source freeze')]
for _, path, _ in analyses:
    p=ROOT/path
    if p.exists(): INPUTS[path]=hashlib.sha256(p.read_bytes()).hexdigest()
    else:
        # The protocol review is the authoritative source for the source-freeze record.
        raise AssertionError(path)

excluded = [
 ('P2-SMOKE-S1','outputs/P2-SMOKE-S1/run_status.json','Failed CSP API smoke; successful S1B kept separately'),
 ('P4-E001','outputs/P4-E001/run_status.json','Failed EOG channel selection; successful P4-E001B kept separately'),
 ('Q13-E002/Q13-E003','','Superseded unrun branches; no performance invented'),
 ('Q14-E002R1','','Partial87-person external attempt; superseded by amended full109-person R2 without double counting'),
 ('Q14 original aggregate validator','','Retained CSV floating-point serialization failure; separate from later portability amendment'),
 ('Q14-E003','','Unrun external branch; no outcome')]
for _,path,_ in excluded:
    if path: read_json(path)

def md_table(frame, columns):
    text=['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']
    for row in frame[columns].itertuples(index=False,name=None):
        text.append('| '+' | '.join(str(v).replace('|','/') for v in row)+' |')
    return '\n'.join(text)

display=inventory.copy();display['BA (%)']=display.mean_ba.map(lambda x:f'{x*100:.2f}')
qdisplay=qc_frame.copy();qdisplay['BA (%)']=qdisplay.mean_ba.map(lambda x:f'{x*100:.2f}')
parts=['# Completed experiment inventory — 2 October 2026','',
 'This inventory covers completed pre-Q15 research. All values are equal-person balanced accuracy; neural seeds and predefined source subsets are averaged within person. It is a descriptive record, not a target-selected leaderboard. The inventory counts rows/conditions, not independent hypotheses or a cumulative training budget. No training, preprocessing or new prediction was run to create it.','',
 '## Four-class development, binary source development, and external evaluation','',
 md_table(display,['arm','classes','n_subjects','BA (%)','reuse_note']), '',
 'The CSV retains subject SD, evaluation-cell counts, validation scope and evidence paths. Q4-A001 reuses source-fitted CSP feature caches but refits scaler/LDA nine times per arm; k8/k72 endpoints reproduce prior Q4 predictions. Q7 A/D reuse saved S3 fits. Q13 k8 points reuse fixed20 anchors and its historical raw-CE comparator reuses Q5. These repeated endpoints do not provide independent replications.','',
 'Q9 top-level batch status proves orchestration only. Its archived prediction/partition/statistical audit and present arithmetic checks are recorded separately; do not infer full raw/checkpoint replay from a batch-success label. Q12/Q13 have experiment-specific passing historical scientific replay receipts. Q14 source receipts and external portable saved-probability/event checks have narrower scopes, described in the paper.','',
 '## Earlier binary pipeline and artifact/EOG checks','',
 md_table(qdisplay,['experiment','mode','condition','model','test_stratum','n_subjects','BA (%)']), '',
 'P2 within-session and cross-session modes use labeled calibration from the evaluated person. Only cross-subject LOSO excludes both target sessions. P2-E001 uses 2,346 expert-clean left/right trials: within-session/LOSO each evaluate all 2,346, whereas cross-session evaluates 1,183 trials from the later session. P2-E002-ALLTRIALS scores 2,592 and changes both source and target populations. Some archived all-trial metadata retains earlier clean-name fields; the effective population is 2,592.','',
 'P3 scores clean targets as primary and reports all/flagged strata as secondary. Its source-all versus source-clean conditions share target identities. P4-E001B is the successful retry: regression coefficients are fit on clean source data, then applied using three synchronous target EOG channels. That condition is EOG-assisted, and neither lower correlation nor its scores proves selective ocular-artifact removal. The S1B single-person smoke uses labeled within-person data and has no located independent scientific validator.','',
 '## Completed audits and source-only analyses','']
for name,path,note in analyses: parts.append(f'- **{name}**: {note}. Source: `{path}`'+(' (source-freeze details supported by `evidence/q12_q14_review.json`).' if not (ROOT/path).exists() else '.'))
parts.extend(['','## Retained failures, partial runs, and unrun branches',''])
for name,path,note in excluded: parts.append(f'- **{name}**: {note}.'+(f' Source: `{path}`.' if path else ' See versioned protocol review.'))
parts.extend(['','No failed/unrun record is assigned invented performance. Q15 and its raw-data transfer/contract work do not enter this manuscript.',''])
(OUT/'supplementary_completed_experiment_inventory.md').write_text('\n'.join(parts))
(OUT/'evidence/inventory_provenance.json').write_text(json.dumps({'input_sha256':INPUTS,'inventory_rows':len(inventory),'early_binary_rows':len(qc_frame),'fits_started':0,'new_predictions':0,'source_files_modified':False},indent=2)+'\n')
print(json.dumps({'inventory_rows':len(inventory),'early_binary_rows':len(qc_frame),'fits_started':0}))
