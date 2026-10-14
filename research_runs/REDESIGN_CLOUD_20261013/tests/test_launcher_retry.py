"""Execute real shell control flow with stub commands; never access a GPU/network."""
from pathlib import Path
import os,subprocess
import pytest
LAUNCH=Path(__file__).resolve().parents[1]/'LAUNCH_ON_GPU.sh'

def launcher_fixture(tmp_path):
 base=tmp_path/'work';bin_dir=tmp_path/'bin';bin_dir.mkdir();script=tmp_path/'launch.sh';script.write_text(LAUNCH.read_text().replace("BASE='/workspace/mi-eeg-cloud'",'BASE='+repr(str(base))))
 python=bin_dir/'python';python.write_text('''#!/bin/bash
if [[ "$1" == '-m' ]]; then
 d="${@: -1}";mkdir -p "$d/bin"
 cat > "$d/bin/python" <<'STUB'
#!/bin/bash
if [[ "$1" == '-m' ]]; then
 echo attempt >> "$TEST_ROOT/pip-attempts.txt"
 if [[ "$(wc -l < "$TEST_ROOT/pip-attempts.txt")" == 1 ]]; then exit 1; fi
 exit 0
fi
echo synthetic_control_fixture_worker_not_scientific_execution
STUB
 chmod +x "$d/bin/python";exit 0
fi
if [[ "$#" == 3 ]];then echo "$3";fi
''');python.chmod(0o755)
 git=bin_dir/'git';git.write_text('''#!/bin/bash
if [[ "$1" == 'clone' ]]; then mkdir -p "${@: -1}/.git";fi
if [[ "$3" == 'rev-parse' ]]; then printf '%s\\n' "$TEST_HEAD";fi
''');git.chmod(0o755)
 env={**os.environ,'PATH':str(bin_dir)+':'+os.environ['PATH'],'TEST_ROOT':str(tmp_path),'TEST_HEAD':'b'*40}
 return script,base,env

def test_failed_install_retries_without_recreating_runtime(tmp_path):
 script,base,env=launcher_fixture(tmp_path);args=['bash',str(script),'--revision','b'*40]
 first=subprocess.run(args,env=env,capture_output=True,text=True);assert first.returncode==1 and 'Dependency installation failed' in first.stdout
 assert (base/('runtime-'+'b'*40)/'bin/python').exists() and not (base/('runtime-'+'b'*40)/'.requirements-installed').exists()
 second=subprocess.run(args,env=env,capture_output=True,text=True);assert second.returncode==0 and 'synthetic_control_fixture' in second.stdout
 assert (tmp_path/'pip-attempts.txt').read_text().count('attempt')==2
 assert (base/('runtime-'+'b'*40)/'.requirements-installed').exists()
 third=subprocess.run(args,env=env,capture_output=True,text=True);assert third.returncode==0 and (tmp_path/'pip-attempts.txt').read_text().count('attempt')==2

def test_wrong_immutable_checkout_blocks_before_install(tmp_path):
 script,base,env=launcher_fixture(tmp_path);env['TEST_HEAD']='c'*40
 r=subprocess.run(['bash',str(script),'--revision','b'*40],env=env,capture_output=True,text=True)
 assert r.returncode==2 and 'Code revision mismatch' in r.stdout and not (tmp_path/'pip-attempts.txt').exists()

def test_malformed_revision_never_accesses_commands(tmp_path):
 script,base,env=launcher_fixture(tmp_path)
 r=subprocess.run(['bash',str(script),'--revision','not-a-commit'],env=env,capture_output=True,text=True)
 assert r.returncode==2 and not base.exists()
