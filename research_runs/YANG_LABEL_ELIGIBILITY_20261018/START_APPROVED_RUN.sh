#!/usr/bin/env bash
# Only the sole on-site operator dispatches this after source acceptance. No archive/credential access.
set -Eeuo pipefail
P1_ROOT=/workspace/paper1_expansion
P1_CODE="$P1_ROOT/code_eligible_v3_20261018"
P1_PYTHON="$P1_ROOT/venv/bin/python"
"$P1_PYTHON" - "$P1_ROOT" "$P1_CODE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root,code=map(Path,sys.argv[1:])
m=json.loads((code/'BUNDLE_MANIFEST.json').read_text())
assert m.get('eligibility_parent_manifest_sha256'), 'not the approved isolated revision'
for row in m['files']:
    raw=(code/row['path']).read_bytes()
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'], row['path']
cache=root/'data/processed18_eligible_v3_20261018'
a=json.loads((cache/'cache_reuse_receipt.json').read_text())
b=json.loads((cache/'affected_people_acceptance.json').read_text())
assert a['status']=='PASS_31_COMPATIBLE_CACHES' and len(a['files'])==31
assert b['status']=='PASS_REAL_FOUR_AFFECTED_PEOPLE' and [r['n_trials'] for r in b['subjects']]==[599,594,599,599]
assert all(r['compatibility']['current_data_module_sha256']==hashlib.sha256((code/'p1_data.py').read_bytes()).hexdigest() for r in a['files'])
for row in a['files']:
    assert hashlib.sha256(Path(row['destination']).read_bytes()).hexdigest()==row['npz_sha256']
for row in b['subjects']:
    path=cache/'yang'/f"sub-{row['subject']:03d}.npz"
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['npz_sha256']
print('Acceptance and copied cache hashes match; dispatch permitted.')
PY
if ! flock -n "$P1_ROOT/launch.lock" true; then
  echo 'An existing worker holds launch.lock; no new worker dispatched.' >&2
  exit 2
fi
export PYTHONUNBUFFERED=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8
nohup flock -n "$P1_ROOT/launch.lock" "$P1_PYTHON" -u "$P1_CODE/p1_runner.py" \
  --root "$P1_ROOT" --run-name expansion18_eligible_v3_20261018 \
  >> "$P1_ROOT/run_eligible_v3_20261018.log" 2>&1 < /dev/null &
echo "Dispatch PID $!; inspect new log and runs/expansion18_eligible_v3_20261018/status.json."
echo 'Dispatch is not proof of GPU fitting or backup completion.'
