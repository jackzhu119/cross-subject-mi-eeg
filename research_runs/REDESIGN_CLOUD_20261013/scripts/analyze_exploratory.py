#!/usr/bin/env python3
"""Participant-level exploration after separately validated fixed predictions.

The planned primary/secondary and prespecified exploratory contrasts,
null/adverse outputs and class-collapse
summaries are retained. No statistical threshold can promote this unknown-
exposure external cohort to independent confirmation. No model is run here.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
LEGACY = ROOT / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'
if str(LEGACY) not in sys.path:
    sys.path.insert(0, str(LEGACY))
# Numerical/statistical helpers only. The old confirmatory gate is never used.
from analyze_redesign_scores import paired_stats, holm_adjust
from validate_predictions import ARCHITECTURES, SELECTORS, SEEDS, digest, read_json, require, validate_roster
BOOTSTRAPS = 20000
BOOTSTRAP_SEED = 20261016


def participant_statistics(rows, roster, expected_participants=85, expected_events=6800):
    people, events = validate_roster(roster, expected_participants, expected_events)
    expected = {(person, event, arch, selector, seed) for person, event in events
                for arch in ARCHITECTURES for selector in SELECTORS for seed in SEEDS}
    cells = {}
    for row in rows:
        key = (row['subject_id'], row['event_id'], row['model_arch'], row['selector'], int(row['seed']))
        require(key in expected and key not in cells, 'analysis_duplicate_or_unexpected_prediction_cell')
        label, fingerprint = events[(key[0], key[1])]
        require(int(row['ytrue']) == label and row['epoch_sha256'] == fingerprint and int(row['ypred']) in (0, 1),
                'analysis_prediction_label_or_fingerprint_changed')
        cells[key] = (label, int(row['ypred']))
    require(set(cells) == expected, 'analysis_prediction_coverage_incomplete')
    participant_scores, by_condition = [], collections.defaultdict(dict)
    for person in people:
        own_events = [event for p, event in events if p == person]
        for arch in ARCHITECTURES:
            for selector in SELECTORS:
                seed_scores, dominance, dominant_classes, recalls_by_seed = [], [], [], []
                for seed in SEEDS:
                    truth, prediction = np.asarray([cells[(person, event, arch, selector, seed)] for event in own_events]).T
                    recalls = [float((prediction[truth == c] == c).mean()) for c in (0, 1)]
                    counts = np.bincount(prediction, minlength=2)
                    seed_scores.append(50 * sum(recalls))
                    recalls_by_seed.append(recalls)
                    dominance.append(float(counts.max() / len(prediction)))
                    dominant_classes.append(int(counts.argmax()))
                value = float(np.mean(seed_scores))
                row = {'subject_id': person, 'model_arch': arch, 'selector': selector, 'eligible_trials': len(own_events),
                       'seed_ba_pp': seed_scores, 'balanced_accuracy_pp': value, 'seed_class_recalls': recalls_by_seed,
                       'seed_prediction_dominance': dominance, 'seed_dominant_class': dominant_classes,
                       'mean_seed_prediction_dominance': float(np.mean(dominance)),
                       'class_dominance_flag': float(np.mean(dominance)) >= .95}
                participant_scores.append(row)
                by_condition[(arch, selector)][person] = value
    # Resample participants, preserving paired models/selectors and the already
    # averaged three-seed scores; never treat seeds or trials as extra people.
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(0, len(people), (BOOTSTRAPS, len(people)))
    def differences(first, second):
        return np.asarray([by_condition[first][p] - by_condition[second][p] for p in people])
    primary = paired_stats(differences(('broad', 'mean_rank'), ('broad', 'mean_loss')), indices)
    primary.update(contrast='broad_mean_rank_minus_mean_loss', role='planned_primary_contrast_exploratory_only',
                   statistical_threshold_passed=primary['p_two_sided'] is not None and primary['p_two_sided'] < .05,
                   confirmatory_rejected=False, independent_confirmation_qualified=False)
    specifications = [('broad_fixed_minus_mean_loss', ('broad', 'fixed'), ('broad', 'mean_loss')),
                      ('broad_fixed_minus_mean_rank', ('broad', 'fixed'), ('broad', 'mean_rank')),
                      ('shared_fixed_minus_broad_fixed', ('shared', 'fixed'), ('broad', 'fixed'))]
    secondary = []
    for name, first, second in specifications:
        delta = differences(first, second)
        stats = paired_stats(delta, indices)
        simultaneous = paired_stats(delta, indices, alpha=.05 / 3)
        secondary.append(stats | {'contrast': name, 'role': 'planned_secondary_contrast_exploratory_only',
                                   'ordinary_95_interval_multiplicity_adjusted': False,
                                   'bonferroni_simultaneous_interval_pp': simultaneous['t_interval_pp'],
                                   'confirmatory_rejected': False, 'independent_confirmation_qualified': False})
    for record, p in zip(secondary, holm_adjust([x['p_two_sided'] for x in secondary])):
        record['holm_adjusted_p'] = p
        record['nominal_threshold_passed'] = record['p_two_sided'] is not None and record['p_two_sided'] < .05
        record['holm_threshold_passed_exploratory_only'] = p is not None and p < .05
        record['confirmation_role'] = 'exploratory_estimation_only_regardless_of_p_value'
    # Already prespecified in the frozen SAP. These additional contrasts remain
    # exploratory and outside the three-comparison secondary Holm family.
    extra_specifications = [
        ('shared_mean_rank_minus_mean_loss', ('shared', 'mean_rank'), ('shared', 'mean_loss')),
        ('shared_mean_loss_minus_broad_mean_loss', ('shared', 'mean_loss'), ('broad', 'mean_loss')),
        ('shared_mean_rank_minus_broad_mean_rank', ('shared', 'mean_rank'), ('broad', 'mean_rank'))]
    extra_contrasts = []
    for name, first, second in extra_specifications:
        stats = paired_stats(differences(first, second), indices)
        extra_contrasts.append(stats | {'contrast': name,
            'role': 'prespecified_exploratory_not_in_secondary_Holm_family',
            'ordinary_95_interval_multiplicity_adjusted': False,
            'confirmatory_rejected': False, 'independent_confirmation_qualified': False,
            'nominal_threshold_passed': stats['p_two_sided'] is not None and stats['p_two_sided'] < .05})
    interaction = (differences(('shared', 'mean_rank'), ('shared', 'mean_loss'))
                   - differences(('broad', 'mean_rank'), ('broad', 'mean_loss')))
    stats = paired_stats(interaction, indices)
    extra_contrasts.append(stats | {'contrast': 'interaction_rank_loss_shared_minus_broad',
        'contrast_definition': '(shared_mean_rank - shared_mean_loss) - (broad_mean_rank - broad_mean_loss)',
        'role': 'prespecified_exploratory_not_in_secondary_Holm_family',
        'ordinary_95_interval_multiplicity_adjusted': False,
        'confirmatory_rejected': False, 'independent_confirmation_qualified': False,
        'nominal_threshold_passed': stats['p_two_sided'] is not None and stats['p_two_sided'] < .05})
    descriptives = []
    for arch in ARCHITECTURES:
        for selector in SELECTORS:
            records = [r for r in participant_scores if r['model_arch'] == arch and r['selector'] == selector]
            values = np.asarray([r['balanced_accuracy_pp'] for r in records])
            flags = sum(r['class_dominance_flag'] for r in records)
            descriptives.append({'model_arch': arch, 'selector': selector, 'participants_n': len(people),
                                 'participant_mean_ba_pp': float(values.mean()), 'participant_median_ba_pp': float(np.median(values)),
                                 'class_dominance_flag_count': flags, 'class_dominance_flag_fraction': flags / len(people),
                                 'below_chance_ba_count': int((values < 50).sum()), 'minimum_participant_ba_pp': float(values.min()),
                                 'tenth_percentile_participant_ba_pp': float(np.quantile(values, .1)),
                                 'role': 'descriptive_exploratory_not_confirmatory'})
    return {'schema_version': 2, 'results_role': 'exposure_unconfirmed_exploratory_external_evaluation',
            'prior_use': 'unknown', 'independent_confirmation_qualified': False,
            'cohort_id': 'Dreyer2023', 'participants_n': len(people), 'eligible_events': len(events),
            'participant_order': people, 'participant_seed_unit': 'participant after equal mean over three final seeds',
            'primary': primary, 'secondary_family': secondary, 'secondary_confirmation_gate_open': False,
            'extra_exploratory_contrasts': extra_contrasts,
            'participant_scores': participant_scores, 'condition_descriptives': descriptives,
            'bootstrap_replicates': BOOTSTRAPS, 'bootstrap_rng_seed': BOOTSTRAP_SEED,
            'all_planned_contrasts_reported': True, 'adverse_and_null_results_retained': True,
            'equivalence_or_noninferiority_established': False, 'target_fits': 0, 'model_fits_started_by_analysis': 0,
            'target_predictions_computed_by_analysis': False,
            'limitations': ['Prior dataset exposure remains unknown; technical PASS and p-values do not establish independence.',
                            'Participants are the sampling unit; seeds and trials are not independent participant replications.',
                            'Paired-t assumptions apply; bootstrap intervals are conditional on these fixed source checkpoints.',
                            'The fixed broad/shared contrast compares complete pipelines, not an isolated causal spectral-sharing factor.',
                            'Acquisition crops overlap provider sham/visual feedback; sensor decoding is not a causal physiological mechanism.',
                            'No equivalence, clinical utility, online validation, universal calibration-free or SOTA claim is established.']}


def execute(job):
    job = Path(job).resolve()
    target = job / 'target'
    validation = read_json(target / 'prediction_validation.json')
    require(validation.get('status') == 'PASS_SEPARATE_PREDICTION_ARTIFACT_VALIDATION_EXPLORATORY'
            and validation.get('independent_confirmation_qualified') is False
            and validation.get('predictions_sha256') == digest(target / 'predictions.csv')
            and validation.get('raw_logits_sha256') == digest(target / 'raw_logits.npz')
            and validation.get('roster_sha256') == digest(target / 'raw_only_roster.json')
            and validation.get('completion_receipt_sha256') == digest(target / 'prediction_completion_receipt.json')
            and validation.get('source_validation_sha256') == digest(job / 'source/source_validation.json')
            and validation.get('validator_sha256') == digest(HERE / 'validate_predictions.py')
            and validation.get('config_sha256') == digest(STUDY / 'config/experiment.json'),
            'real_current_separate_prediction_validation_required')
    with (target / 'predictions.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    result = participant_statistics(rows, read_json(target / 'raw_only_roster.json'))
    result.update(predictions_sha256=digest(target / 'predictions.csv'), roster_sha256=digest(target / 'raw_only_roster.json'),
                  prediction_validation_sha256=digest(target / 'prediction_validation.json'),
                  analysis_code_sha256=digest(Path(__file__)))
    from infer_exploratory import write_json
    write_json(target / 'analysis.json', result)
    with (target / 'participant_scores.csv').open('w', newline='') as stream:
        fields = ['subject_id', 'model_arch', 'selector', 'eligible_trials', 'balanced_accuracy_pp',
                  'mean_seed_prediction_dominance', 'class_dominance_flag']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(result['participant_scores'])
    lines = ['# Exploratory external evaluation', '',
             '**Prior exposure remains unknown. This is not independent confirmation.**', '',
             '| Pipeline | Selector | Participant-mean balanced accuracy (%) | Below chance (n) | Dominance flag (n) |',
             '|---|---|---:|---:|---:|']
    for row in result['condition_descriptives']:
        lines.append(f"| {row['model_arch']} | {row['selector']} | {row['participant_mean_ba_pp']:.4f} | {row['below_chance_ba_count']} | {row['class_dominance_flag_count']} |")
    def interval_text(value):
        if value is None:
            return 'not estimable (zero empirical variance)'
        return f'[{value[0]:.4f}, {value[1]:.4f}]'
    lines += ['', '| Planned contrast | Mean difference (pp) | Paired-t 95% CI (pp) | Bootstrap 95% interval (pp) | Nominal p | Holm p (secondary family) |',
              '|---|---:|---|---|---:|---:|']
    for row in [result['primary']] + result['secondary_family']:
        lines.append(f"| {row['contrast']} | {row['mean_difference_pp']:.4f} | {interval_text(row['t_interval_pp'])} | {interval_text(row['bootstrap_95_percentile_interval_pp'])} | {row['p_two_sided']} | {row.get('holm_adjusted_p', 'not in secondary family')} |")
    lines += ['', '| Prespecified exploratory contrast | Mean difference (pp) | Paired-t 95% CI (pp) | Bootstrap 95% interval (pp) | Nominal p |',
              '|---|---:|---|---|---:|']
    for row in result['extra_exploratory_contrasts']:
        lines.append(f"| {row['contrast']} | {row['mean_difference_pp']:.4f} | {interval_text(row['t_interval_pp'])} | {interval_text(row['bootstrap_95_percentile_interval_pp'])} | {row['p_two_sided']} |")
    lines += ['', 'The primary contrast, all three planned secondary contrasts and all four prespecified exploratory contrasts are retained regardless of direction or significance. The secondary Holm adjustment covers its three declared comparisons; the four additional exploratory contrasts report nominal p-values and unadjusted intervals without confirmation claims. Seeds are averaged within each participant before paired analysis. No target fitting, adaptation, or eligibility changes occurred.', '']
    (target / 'RESULTS_EXPLORATORY.md').write_text('\n'.join(lines))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir', required=True, type=Path)
    args = parser.parse_args()
    result = execute(args.job_dir)
    print(json.dumps({'status': 'exploratory_statistics_written', 'participants_n': result['participants_n'],
                      'independent_confirmation_qualified': False, 'target_fits': 0}))


if __name__ == '__main__':
    main()
