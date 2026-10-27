"""Saved-summary arithmetic, fixed families, pairing and partial-run checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'shared')]
from compmi.analysis import (CELLS, aggregate_people, analyze, holm_adjust,
                             _contrast_vectors, _weighted)
from hpcmi.common import atomic_json, canonical_hash, read_json


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.study = {'analysis_seed': 400, 'bootstrap_replicates': 32,
                      'permutation_replicates': 32, 'validation_seeds': [1, 2, 3],
                      'final_seeds': [4, 5, 6]}
        self.tasks = []
        for phase, folds in [('development', range(5)), ('final', [None])]:
            for fold in folds:
                ids = [f'b{fold}', f'y{fold}'] if fold is not None else ['d0', 'd1', 'd2', 'd3']
                for cell in CELLS:
                    for method in ['erm', 'tail', 'weighted_csp_rlda']:
                        seeds = [0] if method == 'weighted_csp_rlda' else self.study['validation_seeds' if phase == 'development' else 'final_seeds']
                        for seed in seeds:
                            ident = f'{phase}-{fold}-{cell}-{method}-{seed}'
                            task = {'id': ident, 'phase': phase, 'fold': fold, 'cell_id': cell,
                                    'method': method, 'seed': seed, 'test_ids': ids,
                                    'family': 'classical' if seed == 0 else 'neural',
                                    'train_trials_sha256': 'a' * 64}
                            self.tasks.append(task)
                            variant = 'outer_fixed40' if phase == 'development' else 'fixed40'
                            base = .5
                            if cell.startswith('s29'):
                                base += int(cell[4:6]) * .01
                            if cell == 's60-matched':
                                base += .08
                            extra = (.03 if cell == 's60-matched' else .01) if method == 'tail' else 0
                            if seed:
                                extra += (seeds.index(seed) - 1) * .001
                            people = []
                            for person in ids:
                                left = base + extra
                                right = left + .1
                                people.append({'person_id': person, 'dataset': {'b': 'bnci', 'y': 'yang', 'd': 'dreyer'}[person[0]],
                                               'seed': seed, 'variant': variant, 'n': 20, 'n_left': 10, 'n_right': 10,
                                               'recall_left': left, 'recall_right': right,
                                               'ba': (left + right) / 2, 'min_recall': left, 'ce': .8 - left/10})
                            run = self.project / 'outputs/runs' / ident
                            atomic_json(run / 'evaluation.json', {'variant': variant, 'model_sha256': 'f' * 64, 'people': people})
                            atomic_json(run / 'complete.json', {**task, 'task_id': ident, 'status': 'complete',
                                                               'model_sha256': 'f' * 64, 'evaluations': {variant: 'evaluation.json'}})
        atomic_json(self.project / 'tasks.json', self.tasks)
        atomic_json(self.project / 'state/plan.json', {'fingerprint': 'frozen', 'tasks_sha256': canonical_hash(self.tasks)})
        atomic_json(self.project / 'config/study.json', self.study)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_grid_fixed_families_and_subset_unit(self):
        self.assertEqual(len(self.tasks), 630)
        result = analyze(self.project)
        self.assertEqual(result['status'], 'complete')
        source = result['domains']['source_fixed40']
        external = result['domains']['external_fixed40']
        self.assertEqual(len(source['comparisons']), 10)
        self.assertEqual({r['cohort'] for r in source['cohort_cell_means']}, {'bnci', 'yang'})
        self.assertTrue(any(r['metric'] == 'ce' for r in source['cell_means']))
        self.assertTrue((self.project / 'outputs/analysis/source_fixed40_cohort_metrics.csv').is_file())
        self.assertNotIn('p_holm', source['comparisons'][0])
        self.assertEqual(sum('p_holm' in r for r in source['comparisons']), 9)
        self.assertEqual(sum('p_holm' in r for r in external['comparisons']), 10)
        self.assertAlmostEqual(source['comparisons'][0]['effect_pp'], 2.)
        self.assertAlmostEqual(source['comparisons'][6]['effect_pp'], 3.)
        self.assertEqual(source['comparisons'][6]['n_participants'], 10)
        self.assertEqual(external['comparisons'][6]['n_participants'], 4)
        self.assertEqual(len(source['classical_reference_differences']), 15 * 2 * 5)
        self.assertTrue((self.project / 'outputs/analysis/source_fixed40_fold_sensitivity.csv').is_file())
        self.assertEqual(analyze(self.project)['domains']['source_fixed40']['comparisons'], source['comparisons'])

    def test_pending_seed_never_becomes_complete_or_smaller_estimate(self):
        task = next(t for t in self.tasks if t['phase'] == 'development' and t['method'] == 'tail')
        (self.project / 'outputs/runs' / task['id'] / 'complete.json').unlink()
        result = analyze(self.project)
        source = result['domains']['source_fixed40']
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(source['comparisons'], [])
        self.assertEqual(len(source['missing_neural_tasks']), 1)
        self.assertFalse(any(row['cell_id'] == task['cell_id'] and row['method'] == 'tail' for row in source['cell_means']))
        self.assertEqual(result['domains']['external_fixed40']['status'], 'complete')

    def test_corrupt_metric_or_task_identity_stops(self):
        task = self.tasks[0]
        path = self.project / 'outputs/runs' / task['id'] / 'evaluation.json'
        value = read_json(path)
        value['people'][0]['ba'] = .999
        atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, 'BA differs'):
            analyze(self.project)

    def test_inference_inputs_cannot_be_silently_replaced(self):
        analyze(self.project)
        task = self.tasks[0]
        path = self.project / 'outputs/runs' / task['id'] / 'evaluation.json'
        value = read_json(path)
        row = value['people'][0]
        row['min_recall'] += .01
        row['recall_left'] += .01
        row['ba'] += .005
        atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, 'inference inputs changed'):
            analyze(self.project)

    def test_completed_trialset_and_model_identity_are_bound(self):
        task = self.tasks[0]
        path = self.project / 'outputs/runs' / task['id'] / 'complete.json'
        value = read_json(path)
        value['train_trials_sha256'] = 'b' * 64
        atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, 'train_trials_sha256'):
            analyze(self.project)
        value['train_trials_sha256'] = task['train_trials_sha256']
        value['model_sha256'] = 'b' * 64
        atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, 'model identity differs'):
            analyze(self.project)

    def test_equal_cohort_weight_and_holm(self):
        self.assertEqual(_weighted([0., 0., 1.], ['bnci', 'bnci', 'yang'], True), .5)
        self.assertAlmostEqual(_weighted([0., 0., 1.], ['bnci', 'bnci', 'yang'], False), 1/3)
        self.assertEqual(holm_adjust([.01, .04, .03]), [.03, .06, .06])


if __name__ == '__main__':
    unittest.main()
