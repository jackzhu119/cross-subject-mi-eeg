"""Software fixtures only: no real EEG, GPU, neural fit, or target prediction."""
from __future__ import annotations
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest
import torch
from sklearn.metrics import balanced_accuracy_score

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import infer_exploratory as m
import validate_predictions as v
import analyze_exploratory as a


def hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fixture():
    people = ['fixture_person_1', 'fixture_person_2', 'fixture_person_3']
    events = []
    for i, person in enumerate(people):
        for j in range(4):
            hashes = {band: hashlib.sha256(f'{person}:{j}:{band}'.encode()).hexdigest() for band in ('broad', 'mu', 'beta')}
            events.append({'subject_id': person, 'event_id': f'{person}_event_{j}', 'ytrue': j % 2,
                           'epoch_sha256': hash_json(hashes), 'input_sha256': hashes})
    roster = {'participants': people, 'events': events, 'synthetic_fixture': False, 'target_fits': 0,
              'target_predictions_computed': False, 'prior_use': 'unknown', 'independent_confirmation_qualified': False}
    rows, identities, all_logits = [], [], {}
    for arch in v.ARCHITECTURES:
        for rule in v.SELECTORS:
            for seed in v.SEEDS:
                key = (arch, rule, seed)
                owner = ':'.join(map(str, key))
                checkpoint = hashlib.sha256(owner.encode()).hexdigest()
                identity = {'model_arch': arch, 'analysis_selector': rule, 'seed': seed, 'source_only': True,
                            'target_fit_count': 0, 'checkpoint_sha256': checkpoint, 'owner_cell': owner}
                identities.append(identity)
                predictions = []
                for e in events:
                    person_index = people.index(e['subject_id'])
                    pred = e['ytrue']
                    if rule == 'mean_loss':
                        pred = 0 if person_index != 2 else 1 - pred
                    elif arch == 'shared':
                        pred = 1 - pred
                    predictions.append(pred)
                logits = np.asarray([[2.0 if p == 0 else -1.0, -1.0 if p == 0 else 2.0] for p in predictions], dtype=np.float32)
                name = '__'.join(map(str, key))
                all_logits[name] = logits
                probabilities = m.softmax64(logits)
                for e, logit, prob in zip(events, logits, probabilities):
                    rows.append({'subject_id': e['subject_id'], 'event_id': e['event_id'], 'model_arch': arch,
                                 'selector': rule, 'seed': seed, 'ytrue': e['ytrue'], 'ypred': int(np.argmax(logit)),
                                 'epoch_sha256': e['epoch_sha256'], 'checkpoint_sha256': checkpoint, 'owner_cell': owner,
                                 'logit_left': float(logit[0]), 'logit_right': float(logit[1]),
                                 'p_left': float(prob[0]), 'p_right': float(prob[1])})
    return rows, roster, identities, all_logits


def test_default_never_consults_gates_target_or_models(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['infer_exploratory.py'])
    monkeypatch.setattr(m, 'execution_gates', lambda *_: pytest.fail('dry run gates'))
    monkeypatch.setattr(m, 'load_target_inputs', lambda *_: pytest.fail('dry run reads'))
    m.main()
    report = json.loads(capsys.readouterr().out)
    assert report['target_predictions_computed'] is False
    assert report['target_fits'] == report['new_source_fits'] == 0
    assert report['independent_confirmation_qualified'] is False


def test_failed_gates_precede_target_load_and_output_creation(tmp_path, monkeypatch):
    def block(_):
        raise ValueError('public freeze missing')
    monkeypatch.setattr(m, 'execution_gates', block)
    monkeypatch.setattr(m, 'load_target_inputs', lambda *_: pytest.fail('must not read input'))
    job = tmp_path / 'uncreated'
    with pytest.raises(ValueError, match='freeze missing'):
        m.execute(job, tmp_path)
    assert not job.exists()


def uncertain_author():
    return {'status': 'AUTHOR_REPORTED_UNCERTAIN', 'independent_confirmation_qualified': False,
            'prior_proposed_decoder_results_inspected_or_used': None,
            'prior_dataset_scientific_analysis_performed': None,
            'used_in_other_manuscripts_or_projects': None}


def test_unknown_prior_exposure_is_not_transformed_into_never_used():
    assert m.validate_exploratory_author(uncertain_author())['used_in_other_manuscripts_or_projects'] is None


@pytest.mark.parametrize('value', [False, True, 'unknown', 0])
def test_unknown_author_fields_must_remain_actual_null(value):
    author = uncertain_author()
    author['prior_dataset_scientific_analysis_performed'] = value
    with pytest.raises(ValueError, match='rewritten'):
        m.validate_exploratory_author(author)


def test_eval_only_batchnorm_and_parameter_state_unchanged():
    torch.manual_seed(2026)
    model = torch.nn.Sequential(torch.nn.BatchNorm1d(3), torch.nn.Linear(3, 2))
    model.train()
    before = {k: x.clone() for k, x in model.state_dict().items()}
    values = np.arange(195, dtype=np.float32).reshape(65, 3) / 100
    logits, receipt = m.predict_logits(model, values, 'cpu')
    assert logits.shape == (65, 2) and logits.dtype == np.float32
    assert receipt['state_before_sha256'] == receipt['state_after_sha256']
    assert receipt['parameters_and_buffers_unchanged'] is True
    assert not any(module.training for module in model.modules())
    assert all(torch.equal(before[k], x) for k, x in model.state_dict().items())


def test_guard_applies_to_every_batch():
    calls = []
    m.predict_logits(torch.nn.Linear(3, 2), np.ones((129, 3), dtype=np.float32), 'cpu', guard=lambda: calls.append(1))
    assert len(calls) == 3


def test_model_mutating_buffer_even_in_eval_is_blocked():
    class Mutating(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer('counter', torch.zeros(1))
        def forward(self, x):
            self.counter += 1
            return torch.zeros((len(x), 2))
    with pytest.raises(ValueError, match='changed_model_state'):
        m.predict_logits(Mutating(), np.ones((3, 3), dtype=np.float32), 'cpu')


@pytest.mark.parametrize('values', [np.empty((0, 3)), np.array([[float('nan'), 1, 2]])])
def test_empty_or_nonfinite_inputs_blocked(values):
    with pytest.raises(ValueError, match='finite'):
        m.predict_logits(torch.nn.Linear(3, 2), values, 'cpu')


def test_nonbinary_model_logits_blocked():
    with pytest.raises(ValueError, match='binary_model_logits'):
        m.predict_logits(torch.nn.Linear(3, 3), np.ones((2, 3), dtype=np.float32), 'cpu')


def test_nonfixed_batch_size_blocked():
    with pytest.raises(ValueError, match='fixed_nonempty'):
        m.predict_logits(torch.nn.Linear(3, 2), np.ones((2, 3), dtype=np.float32), 'cpu', batch_size=1)


def test_softmax_handles_large_logits_and_first_argmax_ties():
    logits = np.asarray([[100000, 100000], [-100000, 100000]], dtype=np.float32)
    probabilities = m.softmax64(logits)
    np.testing.assert_allclose(probabilities, [[.5, .5], [0, 1]], atol=0)
    assert np.argmax(logits, axis=1).tolist() == [0, 1]


def test_independent_full_coverage_logits_and_labels_reconstruction():
    rows, roster, checkpoints, logits = fixture()
    result = v.validate_records(rows, roster, checkpoints, logits, 3, 12)
    assert result['prediction_rows'] == 216
    assert result['nominal_cells'] == 18
    assert result['largest_independent_softmax_absolute_error'] <= 1e-12


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'truth', 'prediction', 'hash', 'checkpoint', 'logit', 'probability'])
def test_separate_validator_detects_tampered_predictions(mutation):
    rows, roster, checkpoints, logits = fixture()
    if mutation == 'duplicate':
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == 'missing':
        rows.pop()
    elif mutation == 'truth':
        rows[0]['ytrue'] = 1 - rows[0]['ytrue']
    elif mutation == 'prediction':
        rows[0]['ypred'] = 1 - rows[0]['ypred']
    elif mutation == 'hash':
        rows[0]['epoch_sha256'] = '1' * 64
    elif mutation == 'checkpoint':
        rows[0]['checkpoint_sha256'] = '1' * 64
    elif mutation == 'logit':
        rows[0]['logit_left'] += 1
    elif mutation == 'probability':
        rows[0]['p_left'] += 1e-3
    with pytest.raises(ValueError):
        v.validate_records(rows, roster, checkpoints, logits, 3, 12)


@pytest.mark.parametrize('value', [True, 'false', None, 0])
def test_confirmation_qualification_must_remain_boolean_false(value):
    _, roster, _, _ = fixture()
    roster['independent_confirmation_qualified'] = value
    with pytest.raises(ValueError, match='exploratory_raw_only'):
        v.validate_roster(roster, 3, 12)


def test_independent_validator_detects_nan_raw_logits():
    rows, roster, checkpoints, logits = fixture()
    logits[next(iter(logits))][0, 0] = np.nan
    with pytest.raises(ValueError, match='finite_float32'):
        v.validate_records(rows, roster, checkpoints, logits, 3, 12)


def test_aliases_cannot_have_disagreeing_outputs():
    rows, roster, checkpoints, logits = fixture()
    checkpoints[1]['owner_cell'] = checkpoints[0]['owner_cell']
    for row in rows:
        if row['model_arch'] == checkpoints[1]['model_arch'] and row['selector'] == checkpoints[1]['analysis_selector'] and row['seed'] == checkpoints[1]['seed']:
            row['owner_cell'] = checkpoints[0]['owner_cell']
    with pytest.raises(ValueError, match='alias_logits'):
        v.validate_records(rows, roster, checkpoints, logits, 3, 12)


def test_paired_analysis_uses_participants_after_equal_seed_average():
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    assert result['participants_n'] == 3
    assert len(result['participant_scores']) == 18
    assert result['bootstrap_replicates'] == 20000
    assert result['bootstrap_rng_seed'] == 20261016
    for score in result['participant_scores']:
        assert score['balanced_accuracy_pp'] == pytest.approx(np.mean(score['seed_ba_pp']))
        for seed, reported in zip(v.SEEDS, score['seed_ba_pp']):
            selected = [r for r in rows if r['subject_id'] == score['subject_id'] and r['model_arch'] == score['model_arch']
                        and r['selector'] == score['selector'] and r['seed'] == seed]
            assert reported == pytest.approx(100 * balanced_accuracy_score([r['ytrue'] for r in selected], [r['ypred'] for r in selected]))
    assert result['primary']['mean_difference_pp'] == pytest.approx((50 + 50 + 100) / 3)


def test_significant_or_adverse_results_never_open_confirmation():
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    assert result['independent_confirmation_qualified'] is False
    assert result['secondary_confirmation_gate_open'] is False
    assert all(r['confirmatory_rejected'] is False for r in [result['primary']] + result['secondary_family'])
    adverse = next(x for x in result['secondary_family'] if x['contrast'] == 'shared_fixed_minus_broad_fixed')
    assert adverse['mean_difference_pp'] == -100
    assert adverse['test_status'] == 'degenerate_zero_variance'
    assert adverse['p_two_sided'] is None
    assert result['adverse_and_null_results_retained'] is True


def test_bootstrap_is_deterministic_and_null_contrast_retained():
    rows, roster, _, _ = fixture()
    first = a.participant_statistics(rows, roster, 3, 12)
    second = a.participant_statistics(rows, roster, 3, 12)
    assert first == second
    null = next(x for x in first['secondary_family'] if x['contrast'] == 'broad_fixed_minus_mean_rank')
    assert null['mean_difference_pp'] == 0 and null['p_two_sided'] is None


def test_analysis_blocked_without_actual_validation(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    (target / 'prediction_validation.json').write_text(json.dumps({'status': 'PASS'}))
    with pytest.raises(ValueError):
        a.execute(tmp_path)
    assert not (target / 'analysis.json').exists()


def test_tensor_byte_and_per_window_hash_replay(tmp_path):
    array_hash, _, _, _, _ = m.numerical_helpers()
    person = 'fixture_person'
    cache = tmp_path / 'cache'; cache.mkdir()
    arrays = {band: np.arange(2 * 19 * 320, dtype=np.float32).reshape(2, 19, 320) * factor
              for band, factor in [('broad', .1), ('mu', .2), ('beta', .3)]}
    events = []
    for i in range(2):
        hashes = {band: array_hash(data[i]) for band, data in arrays.items()}
        events.append({'subject_id': person, 'event_id': f'fixture_event_{i}', 'input_sha256': hashes,
                       'epoch_sha256': hash_json(hashes)})
    path = cache / (person + '.npz')
    np.savez(path, **arrays, event_ids=np.asarray([e['event_id'] for e in events]))
    receipt = {'files': [{'subject_id': person, 'bytes': path.stat().st_size, 'sha256': m.sha(path)}]}
    roster = {'participants': [person], 'events': events}
    result, audit = m.load_target_inputs(cache, roster, receipt)
    assert audit['n_events'] == 2 and audit['target_fitted_transforms'] is False
    assert all(np.array_equal(result[b], arrays[b]) for b in arrays)
    np.savez(path, **{b: value + 1 for b, value in arrays.items()}, event_ids=np.asarray([e['event_id'] for e in events]))
    receipt['files'][0].update(bytes=path.stat().st_size, sha256=m.sha(path))
    with pytest.raises(ValueError, match='frozen_target_input_hash'):
        m.load_target_inputs(cache, roster, receipt)


def test_safe_artifact_paths_reject_traversal_absolute_and_symlinks(tmp_path):
    (tmp_path / 'a.json').write_text('{}')
    assert m.inside(tmp_path, 'a.json').is_file()
    (tmp_path / 'alias.json').symlink_to(tmp_path / 'a.json')
    for name in ['../a.json', str(tmp_path / 'a.json'), 'alias.json']:
        with pytest.raises(ValueError):
            m.inside(tmp_path, name)


def test_freeze_cannot_be_opened_by_status_only_or_independence_claim(tmp_path):
    (tmp_path / 'preinference_freeze.json').write_text(json.dumps({'status': 'FROZEN_BEFORE_TARGET_INFERENCE_EXPLORATORY_ONLY',
                                                                'independent_confirmation_qualified': True}))
    with pytest.raises(ValueError, match='actual_preinference'):
        m.verify_freeze(tmp_path, [])


def source_fixture(tmp_path, monkeypatch):
    config = json.loads((m.LEGACY.parent / 'config/core_experiment_v1.json').read_text())
    config_path = tmp_path / 'experiment.json'; config_path.write_text(json.dumps(config))
    monkeypatch.setattr(m, 'CONFIG', config_path)
    source = tmp_path / 'job/source'; source.mkdir(parents=True)
    job = source.parent
    _, _, _, select_epochs, schedule_cells = m.numerical_helpers()
    selections, cells, artifacts, aliases, fits = {}, [], {}, 0, 8
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        artifacts[path.relative_to(job).as_posix()] = m.sha(path)
    save(source / 'source19_input_audit.json', {'status': 'PASS_SOURCE19_INPUTS_ONLY', 'n_binary_trials': 2592,
                                             'n_raw_files': 18, 'target_eeg_read': False})
    save(source / 'runtime_provenance.json', {'software_fixture': True})
    for arch in m.ARCH_MAP:
        curves = []
        for fold, group in enumerate(config['source_validation_groups'], 1):
            path = source / 'inner' / arch / f'fold_{fold:02d}'
            curve = [{'epoch': epoch, 'validation_cross_entropy': 1 / (epoch + fold)} for epoch in range(1, 41)]
            curves.append(curve)
            save(path / 'source_curve.json', curve)
            save(path / 'partition.json', {'software_fixture': True})
            save(path / 'fit_receipt.json', {'status': 'completed', 'architecture': arch, 'seed': config['selection_seed'],
                                            'epochs': 40, 'target_fit': False, 'n_validation_trials': 288 * len(group),
                                            'n_training_trials': 288 * (9 - len(group)), 'curve_sha256': m.sha(path / 'source_curve.json')})
        selection = select_epochs(curves, config['candidate_epochs'])
        selections[arch] = selection
        for cell in schedule_cells(arch, selection, config['final_seeds']):
            cells.append(cell)
            owner = source / 'final' / cell['owner_cell']
            if cell['alias']:
                fit = json.loads((owner / 'fit_receipt.json').read_text())
                save(source / 'final' / cell['cell'] / 'alias_receipt.json', {**cell, 'new_real_neural_fit': False,
                     'owner_checkpoint_sha256': fit['checkpoint_sha256'], 'owner_model_state_sha256': fit['model_state_sha256']})
                aliases += 1
            else:
                owner.mkdir(parents=True, exist_ok=True)
                cp = owner / 'checkpoint.pt'; cp.write_bytes(('software_fixture:' + cell['cell']).encode())
                artifacts[cp.relative_to(job).as_posix()] = m.sha(cp)
                save(owner / 'source_curve.json', {'software_fixture': True})
                save(owner / 'partition.json', {'software_fixture': True})
                save(owner / 'fit_receipt.json', {'status': 'completed', 'architecture': arch, 'seed': cell['seed'],
                     'epochs': cell['epochs'], 'n_training_trials': 2592, 'n_validation_trials': 0,
                     'target_fit': False, 'configuration_sha256': m.sha(config_path), 'checkpoint_sha256': m.sha(cp),
                     'optimizer_updates': 41 * cell['epochs'], 'model_state_sha256': hashlib.sha256(cell['cell'].encode()).hexdigest()})
                fits += 1
    save(source / 'selected_epochs.json', selections)
    save(source / 'source_completion_manifest.json', {'target_fits': 0, 'target_predictions_computed': False,
         'nominal_inner_fits': 8, 'nominal_final_cells': 18, 'actual_new_neural_fits': fits, 'aliases': aliases,
         'selected_epochs': selections, 'final_cells': cells})
    save(source / 'source_validation.json', {'status': 'PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY',
         'qualified_independent_confirmation': False, 'target_fits': 0, 'target_predictions_computed': False,
         'source_completion_manifest_sha256': m.sha(source / 'source_completion_manifest.json'),
         'config_sha256': m.sha(config_path), 'artifact_hashes': dict(artifacts)})
    return job, config


def test_source_selection_and_alias_inventory_reconstructed_from_actual_receipts(tmp_path, monkeypatch):
    job, config = source_fixture(tmp_path, monkeypatch)
    cells, artifacts = m.source_cells(job, config)
    assert len(cells) == 18 and sum(c['alias'] for c in cells) == 6
    assert {c['epochs'] for c in cells} == {20, 40}
    assert 'source/source_validation.json' in artifacts
    assert all(c['source_only'] is True and c['target_fit_count'] == 0 for c in cells)


def test_unbound_source_validation_receipt_cannot_open_inference(tmp_path, monkeypatch):
    job, config = source_fixture(tmp_path, monkeypatch)
    path = job / 'source/source_validation.json'
    value = json.loads(path.read_text()); value['source_completion_manifest_sha256'] = '0' * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='completion_hash'):
        m.source_cells(job, config)


def test_source_checkpoint_mutation_cannot_open_inference(tmp_path, monkeypatch):
    job, config = source_fixture(tmp_path, monkeypatch)
    cp = next((job / 'source/final').glob('**/checkpoint.pt')); cp.write_bytes(b'mutated')
    with pytest.raises(ValueError, match='owner_identity'):
        m.source_cells(job, config)


def test_public_source_receipt_missing_real_checkpoint_hash_blocked(tmp_path, monkeypatch):
    job, config = source_fixture(tmp_path, monkeypatch)
    path = job / 'source/source_validation.json'
    value = json.loads(path.read_text())
    key = next(k for k in value['artifact_hashes'] if k.endswith('checkpoint.pt'))
    del value['artifact_hashes'][key]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='checkpoint_hash_missing'):
        m.source_cells(job, config)


def test_resume_safe_source_alias_hash_cannot_be_changed(tmp_path, monkeypatch):
    job, config = source_fixture(tmp_path, monkeypatch)
    path = next((job / 'source/final').glob('**/alias_receipt.json'))
    value = json.loads(path.read_text()); value['owner_checkpoint_sha256'] = '1' * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='alias_identity'):
        m.source_cells(job, config)


def test_all_prespecified_exploratory_contrasts_and_interaction_retained():
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    extra = {r['contrast']: r for r in result['extra_exploratory_contrasts']}
    assert set(extra) == {'shared_mean_rank_minus_mean_loss', 'shared_mean_loss_minus_broad_mean_loss',
                         'shared_mean_rank_minus_broad_mean_rank', 'interaction_rank_loss_shared_minus_broad'}
    by_condition = {(r['subject_id'], r['model_arch'], r['selector']): r['balanced_accuracy_pp']
                    for r in result['participant_scores']}
    expected = [(by_condition[(p, 'shared', 'mean_rank')] - by_condition[(p, 'shared', 'mean_loss')])
                - (by_condition[(p, 'broad', 'mean_rank')] - by_condition[(p, 'broad', 'mean_loss')])
                for p in roster['participants']]
    assert extra['interaction_rank_loss_shared_minus_broad']['participant_differences_pp'] == expected
    assert all(r['independent_confirmation_qualified'] is False and r['confirmatory_rejected'] is False for r in extra.values())
    assert all('holm_adjusted_p' not in r for r in extra.values())


def test_unequal_class_and_trial_counts_use_balanced_accuracy_and_equal_participant_weight():
    rows, roster, _, _ = fixture()
    person = roster['participants'][0]
    first_event = next(e for e in roster['events'] if e['subject_id'] == person and e['ytrue'] == 0)
    for j in range(4):
        hashes = {band: hashlib.sha256(f'unequal_fixture:{j}:{band}'.encode()).hexdigest() for band in ('broad', 'mu', 'beta')}
        event = {'subject_id': person, 'event_id': f'unequal_fixture_extra_event_{j}', 'ytrue': 0,
                 'epoch_sha256': hash_json(hashes), 'input_sha256': hashes}
        roster['events'].append(event)
        templates = [copy.deepcopy(r) for r in rows if r['subject_id'] == person and r['event_id'] == first_event['event_id']]
        for row in templates:
            row.update(event_id=event['event_id'], epoch_sha256=event['epoch_sha256'])
            rows.append(row)
    result = a.participant_statistics(rows, roster, 3, 16)
    selected = [r for r in result['participant_scores'] if r['model_arch'] == 'broad' and r['selector'] == 'mean_loss']
    assert selected[0]['eligible_trials'] == 8
    assert selected[0]['balanced_accuracy_pp'] == 50  # Ordinary accuracy would be 75%.
    condition = next(r for r in result['condition_descriptives'] if r['model_arch'] == 'broad' and r['selector'] == 'mean_loss')
    assert condition['participant_mean_ba_pp'] == pytest.approx((50 + 50 + 0) / 3)
    assert condition['participant_mean_ba_pp'] != pytest.approx(40)  # Pooled-trial BA.


def test_paired_t_and_interval_agree_with_separate_scipy():
    from scipy.stats import ttest_1samp
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    stats = result['primary']
    independent = ttest_1samp(stats['participant_differences_pp'], 0)
    interval = independent.confidence_interval(.95)
    assert stats['t_statistic'] == pytest.approx(independent.statistic)
    assert stats['p_two_sided'] == pytest.approx(independent.pvalue)
    np.testing.assert_allclose(stats['t_interval_pp'], [interval.low, interval.high], rtol=1e-12)


def test_holm_secondary_adjustment_agrees_with_manual_ordered_reconstruction():
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    family = result['secondary_family']
    raw = [r['p_two_sided'] for r in family]
    order = np.argsort([1 if p is None else p for p in raw], kind='stable')
    adjusted = [None] * 3
    running = 0
    for rank, index in enumerate(order):
        running = max(running, (3 - rank) * (1 if raw[index] is None else raw[index]))
        if raw[index] is not None:
            adjusted[index] = min(1, running)
    assert [r['holm_adjusted_p'] for r in family] == adjusted


def test_new_statistical_summary_passes_root_separate_numerical_reconstruction():
    import validate_analysis
    rows, roster, _, _ = fixture()
    result = a.participant_statistics(rows, roster, 3, 12)
    checks = validate_analysis.reconstruct(rows, roster, result)
    assert len(checks['contrasts_reconstructed']) == 8
    assert checks['participant_balanced_accuracy_cells_recomputed'] == 18
    assert checks['participant_bootstrap_recomputed'] is True
    assert checks['secondary_Holm_recomputed'] is True
