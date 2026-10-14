"""Two bounded coefficient-only subprocesses; no EEG, rounding search or training."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def worker(a):
    import numpy as np
    import scipy
    from scipy import linalg
    from scipy.signal import butter, sosfilt_zi, lfilter_zi
    import scipy.signal._signaltools as signaltools
    import numpy.linalg._umath_linalg as uml
    if (np.__version__, scipy.__version__) != ('2.3.5', '1.17.0'):
        raise ValueError('exact_numerical_versions_required')
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_CLOUD_20261013/scripts'))
    from reconstruct_source_readonly import verify_science
    identities = verify_science()
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
    import core_source_inputs as c
    # Initializes exactly the NumPy solve path used by scipy.signal.lfilter_zi.
    np.linalg.solve(np.eye(2), np.ones(2))
    libs = list((Path(np.__file__).parent.parent / 'numpy.libs').glob('*openblas*.so'))
    if len(libs) != 1:
        raise ValueError('one_identifiable_numpy_OpenBLAS_library_required')
    lib = ctypes.CDLL(str(libs[0]))
    info = {}
    for key, symbol in [('corename', 'scipy_openblas_get_corename64_'), ('config', 'scipy_openblas_get_config64_')]:
        function = getattr(lib, symbol)
        function.restype = ctypes.c_char_p
        info[key] = function().decode()
    if a.worker == 'haswell' and info['corename'].lower() != 'haswell':
        raise ValueError('requested_OpenBLAS_control_not_effective')
    files = [libs[0], Path(uml.__file__), Path(signaltools.__file__)]
    identity = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    bands = {}
    for band, limits in c.BANDS.items():
        sos = butter(4, limits, btype='bandpass', fs=250, output='sos')
        sections = []
        for row in sos:
            b, den = row[:3], row[3:]
            matrix = np.eye(2) - linalg.companion(den).T
            rhs = b[1:] - den[1:] * b[0]
            solution = np.linalg.solve(matrix, rhs)
            public = lfilter_zi(b, den)
            if c.array_hash(solution) != c.array_hash(public):
                raise ValueError('explicit_solve_not_same_as_SciPy_lfilter_zi')
            sections.append({'matrix_sha256': c.array_hash(matrix), 'rhs_sha256': c.array_hash(rhs),
                             'solution_sha256': c.array_hash(solution),
                             'matrix_hex': [[float(v).hex() for v in r] for r in matrix],
                             'rhs_hex': [float(v).hex() for v in rhs],
                             'solution_hex': [float(v).hex() for v in solution]})
        zi = sosfilt_zi(sos)
        bands[band] = {'sos_sha256': c.array_hash(sos), 'zi_sha256': c.array_hash(zi),
                       'zi_hex': [[float(v).hex() for v in r] for r in zi], 'sections': sections}
    report = {'status': 'COEFFICIENT_ONLY_NOT_ARRAY_REPAIR_OR_TRAINING', 'mode': a.worker,
              'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
              'cpu_features': sorted(k for k,v in np._core._multiarray_umath.__cpu_features__.items() if v),
              'openblas': info, 'binary_and_source_sha256': identity, 'frozen_file_identities': identities,
              'numerical_environment': {k: os.environ.get(k) for k in ('OPENBLAS_CORETYPE', 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NPY_DISABLE_CPU_FEATURES')},
              'bands': bands, 'EEG_read': False, 'new_fits': 0, 'training_authorization': False}
    with (a.output_dir / (a.worker + '.json')).open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--worker', choices=['native', 'haswell'])
    a = p.parse_args()
    if a.output_dir.resolve().is_relative_to(a.checkout.resolve()):
        raise ValueError('new_output_outside_checkout_required')
    if a.worker:
        worker(a)
        return
    if os.environ.get('OPENBLAS_CORETYPE') or os.environ.get('NPY_DISABLE_CPU_FEATURES'):
        raise ValueError('existing_numerical_override_requires_review')
    a.output_dir.mkdir(parents=False, exist_ok=False)
    for mode in ['native', 'haswell']:
        env = os.environ.copy()
        if mode == 'haswell':
            native = json.loads((a.output_dir / 'native.json').read_text())
            if not {'AVX2', 'FMA3'}.issubset(native['cpu_features']):
                raise ValueError('Haswell_control_requires_native_AVX2_and_FMA3')
            env['OPENBLAS_CORETYPE'] = 'Haswell'
        with (a.output_dir / (mode + '.log')).open('x') as log:
            try:
                r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--checkout', str(a.checkout),
                                    '--output-dir', str(a.output_dir), '--worker', mode],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, timeout=30)
                status = {'mode': mode, 'exit_code': r.returncode, 'timeout': False}
            except subprocess.TimeoutExpired:
                status = {'mode': mode, 'exit_code': None, 'timeout': True}
        with (a.output_dir / (mode + '-supervision.json')).open('x') as f:
            json.dump(status, f, indent=2)
        if status['exit_code'] != 0:
            raise SystemExit(2)
    native = json.loads((a.output_dir / 'native.json').read_text())
    control = json.loads((a.output_dir / 'haswell.json').read_text())
    comparison = {'same_binary_and_source': native['binary_and_source_sha256'] == control['binary_and_source_sha256'],
                  'native_core': native['openblas']['corename'], 'control_core': control['openblas']['corename'],
                  'bands': {}, 'root_cause_of_all_historical_array_differences_proven': False,
                  'EEG_read': False, 'training_authorization': False}
    if not comparison['same_binary_and_source']:
        raise ValueError('binary_changed_between_control_processes')
    for band in native['bands']:
        n, h = native['bands'][band], control['bands'][band]
        comparison['bands'][band] = {'same_sos': n['sos_sha256'] == h['sos_sha256'],
                                     'same_zi': n['zi_sha256'] == h['zi_sha256'],
                                     'sections': [{'same_matrix': x['matrix_sha256']==y['matrix_sha256'],
                                                   'same_rhs': x['rhs_sha256']==y['rhs_sha256'],
                                                   'same_solution': x['solution_sha256']==y['solution_sha256']}
                                                  for x,y in zip(n['sections'],h['sections'])]}
    with (a.output_dir / 'comparison.json').open('x') as f:
        json.dump(comparison, f, indent=2); f.write('\n')


if __name__ == '__main__':
    main()
