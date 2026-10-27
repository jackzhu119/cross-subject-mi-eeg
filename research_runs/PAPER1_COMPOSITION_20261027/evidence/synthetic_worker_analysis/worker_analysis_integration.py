"""Synthetic CPU integration only; executes two real workers and their analysis loader."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

ROOT = Path('/workspace/paper1-hpc-20261023/research_runs/PAPER1_COMPOSITION_20261027')
sys.path[:0] = [str(ROOT), str(ROOT / 'shared')]
import numpy as np
import torch
from compmi import analysis, classical, worker

def load_fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    out = Path(__file__).with_suffix('')
    out.mkdir(exist_ok=False)
    started = time.time()
    wf = load_fixture('test_worker')
    cf = load_fixture('test_classical')
    fixture = wf.WorkerTests()
    fixture.setUp()
    fixture.root = out
    fixture.whitelist = {person: [0, 1, 2, 3] for person in fixture.ids}
    fixture.config['classical'] = cf.SETTINGS.copy()
    fixture.task.update(cell_id='s60-all', pool='s60')
    nproject = fixture.project('neural')
    with (out / 'neural.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
         patch.object(worker, 'Registry', return_value=fixture.registry), \
         patch('compmi.plan.task_trialset', return_value=fixture.whitelist):
        ncode = worker.run_task(nproject, fixture.task['id'], 'cpu')
    assert ncode == 0, (nproject / 'outputs/runs/synthetic/error.json').read_text()
    ctask = dict(fixture.task, id='synthetic-classical', family='classical', method='weighted_csp_rlda', seed=0)
    cproject = fixture.project('classical', ctask)
    with (out / 'classical.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
         patch.object(classical, 'Registry', return_value=fixture.registry), \
         patch('compmi.plan.task_trialset', return_value=fixture.whitelist):
        ccode = classical.run_task(cproject, ctask['id'])
    assert ccode == 0, (cproject / 'outputs/runs/synthetic-classical/error.json').read_text()
    result = {'scope': 'Synthetic CPU worker-to-analysis integration; no EEG or GPU',
              'runtime': {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': np.__version__},
              'source_trials_per_person_per_class': 2, 'batch_size': 128,
              'reports': [], 'product_files_changed': False}
    for family, project, task, code in [('neural', nproject, fixture.task, ncode), ('classical', cproject, ctask, ccode)]:
        rows, evidence, missing = analysis._load_rows(project, [task], 'outer_fixed40')
        people = analysis.aggregate_people(rows, [821])
        assert not missing and len(rows) == len(people) == len(evidence) == 1
        run = project / 'outputs/runs' / task['id']
        complete = json.loads((run / 'complete.json').read_text())
        assert complete['optimizer_updates'] == (6 if family == 'neural' else 0)
        assert complete['validation_history'] == [] and complete['epoch_selection'] is False
        assert rows[0]['n'] == 4 and rows[0]['n_left'] == rows[0]['n_right'] == 2
        assert people[0]['n_seeds'] == 1 and people[0]['n_trials'] == 4
        shards = list(run.glob('evaluations/**/*.npz'))
        assert len(shards) == 2
        for p in shards:
            with np.load(p, allow_pickle=False) as npz:
                assert set(npz.files) == {'logits', 'y', 'trial_ids', 'identity'}
                identity = json.loads(npz['identity'].item())
                assert identity['model_sha256'] == complete['model_sha256']
                assert identity['seed'] == task['seed'] and identity['variant'] == 'outer_fixed40'
        result['reports'].append({'family': family, 'exit': code, 'optimizer_updates': complete['optimizer_updates'],
            'classical_fits_completed': complete.get('classical_fits_completed', 0), 'summary': complete['evaluations'],
            'rows': rows, 'aggregate_people': people, 'evidence': evidence, 'npz_sessions': len(shards),
            'complete_file_sha256': sha(run / 'complete.json')})
    result.update(status='PASS', elapsed_seconds=round(time.time()-started, 3),
                  product_sha256={str(p.relative_to(ROOT)): sha(p) for p in [ROOT/'compmi/worker.py', ROOT/'compmi/classical.py', ROOT/'compmi/analysis.py']})
    (out / 'integration_report.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'report': str(out/'integration_report.json'),
                      'optimizer_updates': [r['optimizer_updates'] for r in result['reports']],
                      'elapsed_seconds': result['elapsed_seconds']}, sort_keys=True))

if __name__ == '__main__':
    main()
