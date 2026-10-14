"""Synthetic checks only; can run directly without installing pytest."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from scipy.signal import butter, sosfiltfilt, sosfilt_zi

HERE=Path(__file__).parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('probe',HERE/'probe_fixed_zi_mediation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path.insert(0,str(ROOT/'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
import core_source_inputs as c


def run():
    for order in ['C','F']:
        x=np.array(((np.arange(19*1500).reshape(19,1500)*37)%257-128).astype(float),order=order)
        original=x.copy()
        for band in [[8,30],[8,13],[13,30]]:
            sos=butter(4,band,btype='bandpass',fs=250,output='sos')
            zi=sosfilt_zi(sos); before=zi.copy()
            assert c.array_hash(m.fixed_filter(x,sos,zi))==c.array_hash(sosfiltfilt(sos,x,axis=-1,padtype='odd',padlen=27))
            assert np.array_equal(x,original) and np.array_equal(zi,before)
    design=HERE/'fixed_zi_mediation_design.json'
    with tempfile.TemporaryDirectory() as d:
        base=Path(d)
        cmd=[sys.executable,str(HERE/'probe_fixed_zi_mediation.py'),'--checkout',str(ROOT),'--data-dir',str(base/'data'),
             '--prior-native',str(base/'unused.json'),'--design',str(design),'--output-dir',d]
        r=subprocess.run(cmd,capture_output=True,text=True)
        assert r.returncode!=0 and 'FileExistsError' in r.stderr and not list(base.iterdir())
        cmd[-1]=str(base/'not-created')
        env=os.environ.copy();env['OPENBLAS_CORETYPE']='Haswell'
        r=subprocess.run(cmd,env=env,capture_output=True,text=True)
        assert r.returncode!=0 and 'no_new_CPU_or_OpenBLAS_override_allowed' in r.stderr and not (base/'not-created').exists()
        altered=base/'changed-design.json';altered.write_bytes(design.read_bytes()+b' ')
        cmd[cmd.index('--design')+1]=str(altered)
        r=subprocess.run(cmd,capture_output=True,text=True)
        assert r.returncode!=0 and 'fixed_design_changed' in r.stderr and not (base/'not-created').exists()
    print('PASS 6 synthetic calibration/input-preservation cases and 3 pre-execution guards; zero EEG read')


if __name__=='__main__':run()
