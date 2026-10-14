"""Preflight checks without raw EEG or scientific execution."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def run():
    evidence={'--helper':HERE/'probe_fixed_zi_mediation.py','--design':HERE/'fixed_zi_mediation_design.json',
              '--six-report':HERE/'fixed_zi_result_20261014T1200Z/report.json',
              '--original-report':HERE/'v2_result_20261014T111526Z/new-host-source-report.json'}
    with tempfile.TemporaryDirectory() as d:
        base=Path(d)
        cmd=[sys.executable,str(HERE/'diagnose_full_source_fixed_zi.py'),'--checkout',str(ROOT),'--data-dir',str(base/'data')]
        for key,path in evidence.items():cmd.extend([key,str(path)])
        cmd.extend(['--output-dir',str(base)])
        r=subprocess.run(cmd,capture_output=True,text=True)
        assert r.returncode!=0 and 'FileExistsError' in r.stderr and not list(base.iterdir())
        print('PASS existing output refuses without worker')
        cmd[-1]=str(base/'not-created')
        env=os.environ.copy();env['OPENBLAS_CORETYPE']='Haswell'
        r=subprocess.run(cmd,env=env,capture_output=True,text=True)
        assert r.returncode!=0 and 'no_new_numeric_overrides_allowed' in r.stderr and not (base/'not-created').exists()
        print('PASS existing numeric override refuses')
        for key,path in evidence.items():
            altered=base/(path.name+'.altered');altered.write_bytes(path.read_bytes()+b' ')
            changed=cmd.copy();changed[changed.index(key)+1]=str(altered)
            r=subprocess.run(changed,capture_output=True,text=True)
            assert r.returncode!=0 and 'fixed_evidence_or_helper_changed' in r.stderr and not (base/'not-created').exists()
            print('PASS changed evidence rejects',key)
    print('6 guard scenarios PASS; full 2592-trial execution not run locally')
if __name__=='__main__':run()
