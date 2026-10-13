"""Source-only fingerprints for exact data-copy checks, no model invocation."""
from pathlib import Path
import sys,json,csv,hashlib
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parents[1]
REPO=BASE.parents[1]
V1=REPO/'research_runs/REDESIGN_SOURCE_SELECTION_20261012'
def main():
    sys.path.insert(0,str(V1/'scripts'))
    from core_source_inputs import load_source19,array_hash,file_hash
    config=json.loads((V1/'config/core_experiment_v1.json').read_text())
    arrays,rows,audit=load_source19(Path('/workspace/mi-eeg-redesign-data/bnci'),config)
    out=BASE/'evidence/source_exact_input_fingerprints.csv'
    fields=['source_sample_id','subject','session','run','trial','canonical_label','broad_sha256','mu_sha256','beta_sha256']
    with out.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for i,row in enumerate(rows):
            writer.writerow(dict(zip(fields,[row['sample_id'],row['subject'],row['session'],row['run'],row['trial'],row['label'],*[array_hash(arrays[k][i]) for k in ['broad','mu','beta']]])))
    receipt={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'SOURCE_COPY_FINGERPRINTS_READY_NO_MODEL_RESULTS','source_trials':len(rows),'source_file_provenance':audit,'reference_sha256':file_hash(out),'helper_sha256':file_hash(V1/'scripts/core_source_inputs.py'),'config_sha256':file_hash(V1/'config/core_experiment_v1.json'),'new_neural_fits':0,'new_source_models_fitted':0,'target_predictions':0,'target_fits':0,'scope':'Exact transformed-window-copy reference on familiar source trials; no person identity independence proof or alternate preprocessing validation'}
    (BASE/'evidence/source_exact_input_fingerprints_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'source_trials':len(rows),'new_models':0,'target_predictions':0}))
if __name__=='__main__':main()
