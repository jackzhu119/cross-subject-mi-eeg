"""One fixed six-trial diagnostic crossover. Never saves or replaces EEG arrays."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

FROZEN = 'eae194514def23e5d1ec6cbb117d4f84fc6f067f'
SELECTED = ('s02_1test_r2_t36', 's03_1test_r0_t06', 's07_0train_r0_t06')


def fixed_filter(context, sos, zi):
    """SciPy 1.17 pad27 forward/reverse equations, with an explicit diagnostic zi."""
    import numpy as np
    from scipy.signal import sosfilt
    from scipy.signal._signaltools import _validate_pad
    edge, ext = _validate_pad('odd', 27, context, -1, ntaps=9)
    state = zi.reshape(sos.shape[0], 1, 2)
    y, _ = sosfilt(sos, ext, axis=-1, zi=state * ext[..., :1])
    y, _ = sosfilt(sos, y[..., ::-1], axis=-1, zi=state * y[..., -1:])
    y = y[..., ::-1]
    return y[..., edge:-edge] if edge else y


def worker(a):
    import numpy as np
    import scipy
    from scipy.signal import sosfilt_zi, firwin
    if (np.__version__, scipy.__version__) != ('2.3.5', '1.17.0'):
        raise ValueError('exact_runtime_required')
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_CLOUD_20261013/scripts'))
    from reconstruct_source_readonly import verify_science
    identities = verify_science()
    sys.path.insert(0, str(a.checkout / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
    import core_source_inputs as c
    sys.path.insert(0, str(a.checkout / 'src'))
    from mi_eeg.data.q15_context import _validated_bnci_runs, BNCI_CHANNELS
    evidence = json.loads(a.design.read_text())
    if hashlib.sha256(a.design.read_bytes()).hexdigest() != DESIGN_SHA:
        raise ValueError('fixed_design_changed')
    old_path = a.prior_native
    if c.file_hash(old_path) != evidence['prior_native_sha256']:
        raise ValueError('exact_prior_native_required')
    prior = {r['sample_id']: r for r in json.loads(old_path.read_text())['results']}
    receipt = json.loads((a.checkout / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json').read_text())
    csvpath = a.checkout / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints.csv'
    if c.file_hash(csvpath) != receipt['reference_sha256']:
        raise ValueError('frozen_fingerprint_changed')
    with csvpath.open() as f:
        rows = list(csv.DictReader(f))
    fingerprints = {r['source_sample_id']: r for r in rows}
    if len(rows) != 2592 or len(fingerprints) != 2592:
        raise ValueError('frozen_ID_inventory_changed')
    config = json.loads((a.checkout / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    c.check_processing(config)
    originals = {r['filename']: r for r in receipt['source_file_provenance']['raw_files_verified']}
    sos = c.butter(4, [8,13], btype='bandpass', fs=250, output='sos')
    actual_zi = sosfilt_zi(sos)
    native_zi = np.array([[float.fromhex(x) for x in r] for r in evidence['native_haswell_zi_hex']], dtype=np.float64)
    alternate_zi = np.array([[float.fromhex(x) for x in r] for r in evidence['observed_skylakex_zi_hex']], dtype=np.float64)
    if c.array_hash(sos) != evidence['mu_sos_sha256'] or c.array_hash(actual_zi) != evidence['native_haswell_zi_sha256']:
        raise ValueError('native_coefficient_environment_drift')
    if c.array_hash(native_zi) != c.array_hash(actual_zi) or c.array_hash(alternate_zi) != evidence['observed_skylakex_zi_sha256']:
        raise ValueError('fixed_coefficient_hex_identity_failed')
    results = []
    for sample in SELECTED:
        subject, session, runpart, trialpart = sample.split('_')
        filename = 'A'+subject[1:]+('E' if session=='1test' else 'T')+'.mat'
        path = a.data_dir/'bnci'/filename; expected = originals[filename]
        if path.is_symlink() or path.stat().st_size != expected['bytes'] or c.file_hash(path) != expected['sha256']:
            raise ValueError('original_file_identity_changed')
        ri, ti = int(runpart[1:]), int(trialpart[1:])-1
        run = _validated_bnci_runs(path)[ri]
        signal = c.ordered_channels19(run['X'][:,:22].T, BNCI_CHANNELS)
        control = max(i for i in range(ti) if int(run['y'][i]) in (1,2))
        for index,role in ((ti,'mismatch'),(control,'preceding_binary_control')):
            sid = f'{subject}_{session}_r{ri}_t{index+1:02d}'
            if sid not in prior or sid not in fingerprints or int(run['y'][index]) not in (1,2):
                raise ValueError('fixed_six_trial_identity_changed')
            cue = int(run['trial'][index])-1+500
            context = np.array(signal[:,cue-375:cue+1125], dtype=np.float64, copy=True)
            if c.array_hash(context) != prior[sid]['stages']['native_context']:
                raise ValueError('native_context_drift')
            context -= context.mean(axis=0, keepdims=True)
            if c.array_hash(context) != prior[sid]['stages']['CAR19']:
                raise ValueError('CAR19_drift')
            # Native reconstruction is a calibration control, not a replacement loader.
            native_filter = fixed_filter(context, sos, native_zi)
            production_filter = c.sosfiltfilt(sos, context, axis=-1, padtype='odd', padlen=27)
            if c.array_hash(native_filter) != c.array_hash(production_filter):
                raise ValueError('diagnostic_filter_not_identical_to_production')
            branches = {}
            for label,zi in (('native_calibration',native_zi),('fixed_zi_counterfactual',alternate_zi)):
                filtered = native_filter if label=='native_calibration' else fixed_filter(context,sos,zi)
                common = c.resample_poly(filtered,16,25,axis=-1,window=('kaiser',5.0),padtype='constant',cval=0.0)
                crop = common[:,320:640]
                output = np.ascontiguousarray(crop,dtype=np.float32)
                stage = {'filtered_float64':c.array_hash(filtered),'resampled_float64':c.array_hash(common),
                         'crop_float64':c.array_hash(crop),'final_float32':c.array_hash(output)}
                if label=='native_calibration':
                    if any(stage[k]!=prior[sid]['stages']['mu'][k] for k in stage):
                        raise ValueError('native_stages_do_not_reproduce_prior')
                    native_output = output
                branches[label] = {'stages':stage, 'matches_frozen_mu':stage['final_float32']==fingerprints[sid]['mu_sha256'],
                                   'elements_changed_from_native':int(np.count_nonzero(output.view(np.uint32)!=native_output.view(np.uint32)))}
            results.append({'sample_id':sid,'role':role,'branches':branches,'expected_mu_sha256':fingerprints[sid]['mu_sha256']})
            # Progress is a new diagnostic JSON only. No EEG arrays are serialized.
            with (a.output_dir/(sid+'.json')).open('x') as f:
                json.dump(results[-1],f,indent=2)
    report = {'status':'FIXED_ZI_MEDIATION_DIAGNOSTIC_ONLY_TRAINING_BLOCKED','results':results,
              'design_sha256':DESIGN_SHA,'frozen_file_identities':identities,'raw_files_read':3,'trials':6,
              'intervention':'Only explicit initial filter state in independent diagnostic calculation; no monkeypatch or loader change',
              'mu_fir_sha256':c.array_hash(firwin(501,1/25,window=('kaiser',5.0))),
              'new_fits':0,'target_EEG_read':False,'scientific_arrays_saved_or_replaced':False,
              'historical_generator_OpenBLAS_identity_established':False,'training_authorization':False}
    with (a.output_dir/'report.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout',type=Path,required=True)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--prior-native',type=Path,required=True)
    p.add_argument('--design',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--worker',action='store_true')
    a=p.parse_args()
    if a.output_dir.resolve().is_relative_to(a.checkout.resolve()) or a.output_dir.resolve().is_relative_to(a.data_dir.resolve()):
        raise ValueError('diagnostic_output_outside_checkout_and_raw_cache_required')
    if hashlib.sha256(a.design.read_bytes()).hexdigest()!=DESIGN_SHA:
        raise ValueError('fixed_design_changed')
    if a.worker:
        worker(a);return
    if os.environ.get('NPY_DISABLE_CPU_FEATURES') or os.environ.get('OPENBLAS_CORETYPE'):
        raise ValueError('no_new_CPU_or_OpenBLAS_override_allowed')
    a.output_dir.mkdir(parents=False,exist_ok=False)
    with (a.output_dir/'worker.log').open('x') as log:
        try:
            r=subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--worker'],stdout=log,stderr=subprocess.STDOUT,timeout=180)
            status={'exit_code':r.returncode,'timeout':False}
        except subprocess.TimeoutExpired:
            status={'exit_code':None,'timeout':True}
    status.update({'new_fits':0,'training_authorization':False})
    with (a.output_dir/'supervision.json').open('x') as f:json.dump(status,f,indent=2)
    raise SystemExit(0 if status['exit_code']==0 else 2)


DESIGN_SHA = 'e6aaad1be0e30496c809bb5dfe795f0ce81055adf5e7bdef5e1382b177348c44'
if __name__=='__main__':main()
