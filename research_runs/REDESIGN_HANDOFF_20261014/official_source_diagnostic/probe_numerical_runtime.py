"""Offline synthetic parity probe. Reads no EEG and changes no frozen inputs."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink() or a.output.resolve().is_relative_to(a.checkout.resolve()):
        raise ValueError('new_output_outside_checkout_required')
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_CLOUD_20261013/scripts'))
    from reconstruct_source_readonly import verify_science
    identities = verify_science()
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
    import core_source_inputs as c
    import numpy as np
    import scipy
    from scipy.signal import sosfilt_zi, firwin
    if (np.__version__, scipy.__version__, importlib.metadata.version('pandas')) != ('2.3.5', '1.17.0', '2.2.3'):
        raise ValueError('exact_diagnostic_numerical_runtime_required')
    config = json.loads((a.checkout / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    signal = ((np.arange(19 * 2000, dtype=np.int64).reshape(19, 2000) * 37) % 257 - 128).astype(np.float64)
    outputs = c.transform_context19(signal, 250, 500, config)
    numeric = {}
    for band, limits in c.BANDS.items():
        sos = c.butter(4, limits, btype='bandpass', fs=250, output='sos')
        zi = sosfilt_zi(sos)
        numeric[band] = {'sos': sos.tolist(), 'sos_sha256': c.array_hash(sos),
                         'zi': zi.tolist(), 'zi_sha256': c.array_hash(zi),
                         'synthetic_final_sha256': c.array_hash(outputs[band])}
    build = io.StringIO()
    with contextlib.redirect_stdout(build):
        np.show_config()
        scipy.show_config()
    files = {}
    for package in (np, scipy):
        root = Path(package.__file__).parent
        candidates = list(root.rglob('*.so')) + list(root.rglob('*.pyd'))
        libdir = root.parent / (package.__name__ + '.libs')
        if libdir.is_dir():
            candidates += [f for f in libdir.iterdir() if f.is_file()]
        for f in sorted(set(candidates)):
            files[str(f.relative_to(root.parent))] = hashlib.sha256(f.read_bytes()).hexdigest()
    report = {'status': 'SYNTHETIC_RUNTIME_PROBE_ONLY', 'python': sys.version, 'machine': platform.machine(),
              'versions': {k: importlib.metadata.version(k) for k in ('numpy', 'scipy', 'pandas')},
              'numerical_environment': {k: os.environ.get(k) for k in ('NPY_DISABLE_CPU_FEATURES', 'OPENBLAS_CORETYPE', 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'SCIPY_ARRAY_API')},
              'cpu_features': getattr(np._core._multiarray_umath, '__cpu_features__', {}),
              'build_config': build.getvalue(), 'compiled_file_sha256': files,
              'frozen_file_identities': identities, 'bands': numeric,
              'resample_unscaled_fir_sha256': c.array_hash(firwin(501, 1.0 / 25, window=('kaiser', 5.0))),
              'EEG_files_read': 0, 'new_fits': 0, 'historical_root_cause_established': False}
    with a.output.open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'status': report['status'], 'output': str(a.output), 'EEG_files_read': 0}))


if __name__ == '__main__':
    main()
