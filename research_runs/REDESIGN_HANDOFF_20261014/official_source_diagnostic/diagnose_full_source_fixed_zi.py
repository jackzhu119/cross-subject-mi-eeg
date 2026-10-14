"""One full-source diagnostic, immutable originals and references, never training."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HELPER_SHA='18c51bbe10d4113c2ad92a6d7dad332590ae2941aeb15a0a70012f09a2527014'
DESIGN_SHA='e6aaad1be0e30496c809bb5dfe795f0ce81055adf5e7bdef5e1382b177348c44'
SIX_REPORT_SHA='88e5b75d18e913640988419d9f693e9650116a13049e5b8e683a9a74ee8073e3'
ORIGINAL_REPORT_SHA='a481ee98d6a1184dd6a696754b8c47a9a3bcfc6b92941393a90e7dcecbbd0a2b'


def checked(path,sha):
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise ValueError('fixed_evidence_or_helper_changed:'+path.name)


def worker(a):
    import numpy as np
    import scipy
    import pandas
    from scipy.signal import sosfilt_zi
    if (np.__version__,scipy.__version__,pandas.__version__)!=('2.3.5','1.17.0','2.2.3'):
        raise ValueError('exact_diagnostic_runtime_required')
    sys.path.insert(0,str(a.checkout/'research_runs/REDESIGN_CLOUD_20261013/scripts'))
    from reconstruct_source_readonly import verify_science
    identities=verify_science()
    sys.path.insert(0,str(a.checkout/'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
    import core_source_inputs as c
    sys.path.insert(0,str(a.checkout/'src'))
    from mi_eeg.data.q15_context import _validated_bnci_runs,BNCI_CHANNELS
    spec=importlib.util.spec_from_file_location('fixed_diagnostic_helper',a.helper)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    design=json.loads(a.design.read_text());six=json.loads(a.six_report.read_text());old=json.loads(a.original_report.read_text())
    six_rows={r['sample_id']:r for r in six['results']}
    receipt_path=a.checkout/'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json'
    frozen=json.loads(receipt_path.read_text()); expected=frozen['source_file_provenance']
    csvpath=receipt_path.with_name('source_exact_input_fingerprints.csv')
    if c.file_hash(csvpath)!=frozen['reference_sha256']:raise ValueError('frozen_CSV_changed')
    with csvpath.open() as f:refs=list(csv.DictReader(f))
    fingerprints={r['source_sample_id']:r for r in refs}
    if len(refs)!=2592 or len(fingerprints)!=2592:raise ValueError('frozen_ID_inventory_changed')
    config=json.loads((a.checkout/'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    arrays,rows,audit=c.load_source19(a.data_dir/'bnci',config)
    if audit['array_hashes']!=old['actual_array_hashes']:raise ValueError('native_full_array_environment_drift')
    for key in ('source_labels_sha256','source_metadata_sha256','source_sample_ids_sha256'):
        if audit[key]!=expected[key]:raise ValueError('native_identity_changed:'+key)
    native_mismatches={band:[r['sample_id'] for r,x in zip(rows,values) if c.array_hash(x)!=fingerprints[r['sample_id']][band+'_sha256']] for band,values in arrays.items()}
    for band,ids in native_mismatches.items():
        if ids!=old['per_trial_mismatches'][band]['first_sample_ids'] or len(ids)!=old['per_trial_mismatches'][band]['count']:
            raise ValueError('native_full_mismatch_inventory_drift')
    with (a.output_dir/'native_audit.json').open('x') as f:json.dump(audit,f,indent=2)
    sos=c.butter(4,[8,13],btype='bandpass',fs=250,output='sos')
    zi=sosfilt_zi(sos)
    alternate=np.array([[float.fromhex(x) for x in r] for r in design['observed_skylakex_zi_hex']],dtype=np.float64)
    if c.array_hash(sos)!=design['mu_sos_sha256'] or c.array_hash(zi)!=design['native_haswell_zi_sha256'] or c.array_hash(alternate)!=design['observed_skylakex_zi_sha256']:
        raise ValueError('fixed_filter_coefficient_identity_drift')
    alt=np.empty_like(arrays['mu'])
    original_files={r['filename']:r for r in expected['raw_files_verified']}
    index=0;changed=[];alt_mismatch=[];seen_six=[]
    with (a.output_dir/'trial_hash_comparison.csv').open('x',newline='') as out:
        writer=csv.writer(out);writer.writerow(['sample_id','native_mu_sha256','fixed_zi_mu_sha256','frozen_mu_sha256','changed_elements','fixed_zi_matches'])
        for subject in range(1,10):
            for suffix,session in (('T','0train'),('E','1test')):
                path=a.data_dir/'bnci'/f'A{subject:02d}{suffix}.mat';raw=original_files[path.name]
                if path.is_symlink() or path.stat().st_size!=raw['bytes'] or c.file_hash(path)!=raw['sha256']:
                    raise ValueError('source_changed_between_passes')
                for ri,run in enumerate(_validated_bnci_runs(path)):
                    signal=c.ordered_channels19(run['X'][:,:22].T,BNCI_CHANNELS)
                    for ti,(start,label) in enumerate(zip(run['trial'],run['y']),1):
                        if int(label) not in (1,2):continue
                        sid=f's{subject:02d}_{session}_r{ri}_t{ti:02d}'
                        if index>=2592 or rows[index]['sample_id']!=sid:raise ValueError('diagnostic_order_changed')
                        cue=int(start)-1+500
                        context=np.array(signal[:,cue-375:cue+1125],dtype=np.float64,copy=True)
                        context-=context.mean(axis=0,keepdims=True)
                        nfilter=helper.fixed_filter(context,sos,zi)
                        production=c.sosfiltfilt(sos,context,axis=-1,padtype='odd',padlen=27)
                        if c.array_hash(nfilter)!=c.array_hash(production):raise ValueError('diagnostic_filter_not_production_equivalent')
                        ncommon=c.resample_poly(nfilter,16,25,axis=-1,window=('kaiser',5.0),padtype='constant',cval=0.0)
                        native=np.ascontiguousarray(ncommon[:,320:640],dtype=np.float32)
                        nhash=c.array_hash(native)
                        if nhash!=c.array_hash(arrays['mu'][index]):raise ValueError('native_calibration_failed')
                        afilter=helper.fixed_filter(context,sos,alternate)
                        common=c.resample_poly(afilter,16,25,axis=-1,window=('kaiser',5.0),padtype='constant',cval=0.0)
                        output=np.ascontiguousarray(common[:,320:640],dtype=np.float32)
                        ahash=c.array_hash(output);target=fingerprints[sid]['mu_sha256'];diff=int(np.count_nonzero(output.view(np.uint32)!=native.view(np.uint32)))
                        if sid in six_rows:
                            stages={'filtered_float64':c.array_hash(afilter),'resampled_float64':c.array_hash(common),'crop_float64':c.array_hash(common[:,320:640]),'final_float32':ahash}
                            if stages!=six_rows[sid]['branches']['fixed_zi_counterfactual']['stages']:raise ValueError('six_trial_counterfactual_stage_drift')
                            seen_six.append(sid)
                        alt[index]=output
                        if diff:changed.append({'sample_id':sid,'elements':diff})
                        if ahash!=target:alt_mismatch.append(sid)
                        writer.writerow([sid,nhash,ahash,target,diff,ahash==target]);index+=1
                out.flush()
    if index!=2592 or set(seen_six)!=set(six_rows):raise ValueError('full_trial_or_anchor_inventory_incomplete')
    diagnostic_hashes={**audit['array_hashes'],'mu':c.array_hash(alt)}
    matched=diagnostic_hashes==expected['array_hashes'] and not alt_mismatch
    report={'status':'FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED' if matched else 'FULL_DIAGNOSTIC_MISMATCH_BLOCKED',
            'trials':index,'raw_files':18,'frozen_file_identities':identities,'native_array_hashes':audit['array_hashes'],
            'diagnostic_bundle_array_hashes':diagnostic_hashes,'frozen_array_hashes':expected['array_hashes'],
            'bundle_definition':'Native unchanged broad/beta plus independent fixed-zi mu; no arrays serialized',
            'native_per_trial_mismatches':native_mismatches,'fixed_zi_mu_mismatches':alt_mismatch,'changed_from_native':changed,
            'identity_hashes_match':True,'six_trial_stage_anchors_match':True,'new_fits':0,'target_EEG_read':False,
            'scientific_arrays_saved_or_replaced':False,'production_native_pipeline_passed':False,'training_authorization':False,
            'historical_generator_OpenBLAS_identity_established':False}
    with (a.output_dir/'report.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    if not matched:raise SystemExit(2)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('checkout','data-dir','helper','design','six-report','original-report','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--worker',action='store_true');a=p.parse_args()
    for path,sha in ((a.helper,HELPER_SHA),(a.design,DESIGN_SHA),(a.six_report,SIX_REPORT_SHA),(a.original_report,ORIGINAL_REPORT_SHA)):checked(path,sha)
    if a.output_dir.resolve().is_relative_to(a.checkout.resolve()) or a.output_dir.resolve().is_relative_to(a.data_dir.resolve()):raise ValueError('diagnostic_output_must_be_separate')
    if a.data_dir.resolve().is_relative_to(a.checkout.resolve()):raise ValueError('raw_cache_outside_checkout_required')
    if os.environ.get('NPY_DISABLE_CPU_FEATURES') or os.environ.get('OPENBLAS_CORETYPE'):raise ValueError('no_new_numeric_overrides_allowed')
    if a.worker:worker(a);return
    a.output_dir.mkdir(parents=False,exist_ok=False)
    with (a.output_dir/'worker.log').open('x') as log:
        try:
            r=subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--worker'],stdout=log,stderr=subprocess.STDOUT,timeout=300)
            status={'exit_code':r.returncode,'timeout':False}
        except subprocess.TimeoutExpired:status={'exit_code':None,'timeout':True}
    status.update({'new_fits':0,'training_authorization':False})
    with (a.output_dir/'supervision.json').open('x') as f:json.dump(status,f,indent=2)
    raise SystemExit(0 if status['exit_code']==0 else 2)


if __name__=='__main__':main()
