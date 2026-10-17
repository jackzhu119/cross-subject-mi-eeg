#!/usr/bin/env bash
# Paper1 source expansion: verified training + isolated GitHub/R2 archive watcher.
set -Eeuo pipefail
umask 077
ROOT=/workspace/paper1_expansion
ARC="$ROOT/_archive"
CONF="$HOME/.config/paper1_archive/credentials.json"
mkdir -p "$ARC"
if [[ ! -s "$CONF" ]]; then
  echo 'Missing saved credentials. Configure them before starting; no training started.' >&2
  exit 2
fi
for cmd in python3 curl git nvidia-smi flock; do
  command -v "$cmd" >/dev/null || { echo "Missing required program: $cmd" >&2; exit 2; }
done
python3 -m venv "$ARC/venv"
"$ARC/venv/bin/python" -m pip install --disable-pip-version-check -q 'boto3==1.40.61'

cat > "$ARC/watch.py" <<'PY'
#!/usr/bin/env python3
"""Archive a completed scientific run; never mutate frozen training code."""
import csv
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.config import Config

ROOT = Path('/workspace/paper1_expansion')
ARC = ROOT / '_archive'
RUN = ROOT / 'runs/expansion18_v1'
CONF = Path.home() / '.config/paper1_archive/credentials.json'
STATUS = RUN / 'archive_status.json'
REPO = 'jackzhu119/cross-subject-mi-eeg'
BRANCH = 'results/paper1-expansion18-v1'
PREFIX = 'paper1/source-expansion/expansion18_v1'
ALLOWED = {'.json', '.csv', '.md', '.pdf', '.png'}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


def credentials():
    if CONF.is_symlink() or not CONF.is_file() or CONF.stat().st_mode & 0o077:
        raise RuntimeError('credential_file_missing_or_insecure')
    c = json.loads(CONF.read_text())
    if any(not isinstance(c.get(k), str) or not c[k].strip()
           for k in ('bucket', 'endpoint', 'access', 'secret', 'github')):
        raise RuntimeError('credential_fields_incomplete')
    if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.r2\.cloudflarestorage\.com/?', c['endpoint']):
        raise RuntimeError('r2_endpoint_invalid')
    return c


def client(c):
    return boto3.client('s3', endpoint_url=c['endpoint'],
        aws_access_key_id=c['access'], aws_secret_access_key=c['secret'], region_name='auto',
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                      connect_timeout=20, read_timeout=100,
                      retries={'max_attempts': 4, 'mode': 'standard'}))


def github_check(c):
    headers = {'Authorization': 'Bearer ' + c['github'],
               'Accept': 'application/vnd.github+json',
               'User-Agent': 'paper1-source-expansion-archive'}
    for endpoint in ('https://api.github.com/user',
                     'https://api.github.com/repos/' + REPO):
        with urllib.request.urlopen(urllib.request.Request(endpoint, headers=headers), timeout=45) as r:
            if r.status != 200:
                raise RuntimeError('github_auth_failed')


def preflight(c):
    github_check(c)
    s = client(c)
    try:
        s.list_objects_v2(Bucket=c['bucket'], Prefix=PREFIX + '/', MaxKeys=1)
    finally:
        s.close()
    print('PREFLIGHT_OK: GitHub authentication and R2 listing passed (write/readback untested).', flush=True)


def upload(s, c, path, key):
    expected = sha(path)
    size = path.stat().st_size
    reusable = False
    try:
        head = s.head_object(Bucket=c['bucket'], Key=key)
        reusable = head.get('ContentLength') == size and head.get('Metadata', {}).get('sha256') == expected
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in ('404', 'NotFound', 'NoSuchKey'):
            raise
    if not reusable:
        s.upload_file(str(path), c['bucket'], key, ExtraArgs={'Metadata': {'sha256': expected}})
    response = s.get_object(Bucket=c['bucket'], Key=key)
    verified = hashlib.sha256()
    remaining = size
    with response['Body'] as body:
        while remaining:
            block = body.read(min(4 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError('r2_full_readback_truncated')
            verified.update(block)
            remaining -= len(block)
    if verified.hexdigest() != expected:
        raise RuntimeError('r2_full_readback_hash_mismatch')
    return {'key': key, 'sha256': expected, 'bytes': size}


def validate_run():
    status = json.loads((RUN / 'status.json').read_text())
    if status.get('stage') != 'COMPLETE':
        raise RuntimeError('training_not_complete')
    receipt = json.loads((RUN / 'export_receipt.json').read_text())
    result_zip = RUN / 'paper1_expansion_results.zip'
    if Path(receipt['path']).resolve() != result_zip.resolve() or sha(result_zip) != receipt['sha256']:
        raise RuntimeError('export_receipt_mismatch')
    report = json.loads((RUN / 'results/report.json').read_text())
    if report.get('study_status') != 'exploratory_external' or not report.get('diagnostics', {}).get('complete_paired_grid'):
        raise RuntimeError('report_scientific_gate_not_met')
    return result_zip


def selected_checkpoints():
    files = {}
    with (RUN / 'results/final_fit_manifest.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            path = Path(row['checkpoint']).resolve()
            if not path.is_relative_to(RUN.resolve()) or sha(path) != row['checkpoint_sha256']:
                raise RuntimeError('selected_checkpoint_integrity_error')
            files[str(path)] = path
    if not files:
        raise RuntimeError('checkpoint_inventory_empty')
    return list(files.values())


def copy_github_files(destination, c):
    count = 0
    excluded = ('credential', 'secret', 'token', 'password', 'private_key')
    needles = [c[k].encode() for k in ('github', 'secret', 'access')]
    needles += [b'github_pat_', b'ghp_', b'cfut_']
    for dirname in ('results', 'provenance'):
        base = RUN / dirname
        for src in sorted(base.rglob('*')):
            if not src.is_file() or src.is_symlink() or src.suffix.lower() not in ALLOWED:
                continue
            if src.stat().st_size > 8_000_000 or any(x in src.name.lower() for x in excluded):
                continue
            raw = src.read_bytes()
            if any(needle in raw for needle in needles):
                raise RuntimeError('secret_pattern_detected_in_git_artifact')
            target = destination / dirname / src.relative_to(base)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            count += 1
    source = RUN / 'archive_manifest.json'
    dest = destination / source.name
    dest.write_bytes(source.read_bytes())
    return count + 1


def run_git(args, directory, environment, optional=False):
    p = subprocess.run(['git', '-C', str(directory), *args], env=environment,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if p.returncode and not optional:
        raise RuntimeError('github_git_operation_failed_' + args[0])
    return p


def publish_github(c):
    askpass = ARC / 'git_askpass.py'
    askpass.write_text('''#!/usr/bin/env python3
import json, sys
from pathlib import Path
c=json.loads((Path.home()/'.config/paper1_archive/credentials.json').read_text())
print('x-access-token' if 'username' in (sys.argv[1] if len(sys.argv)>1 else '').lower() else c['github'])
''')
    askpass.chmod(0o700)
    env = dict(os.environ, GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT='0')
    with tempfile.TemporaryDirectory(prefix='p1-github-', dir=ARC) as temp:
        repo = Path(temp) / 'git'
        repo.mkdir()
        run_git(['init', '-q'], repo, env)
        run_git(['remote', 'add', 'origin', 'https://github.com/' + REPO + '.git'], repo, env)
        run_git(['config', 'user.name', 'Paper1 Research Archive'], repo, env)
        run_git(['config', 'user.email', 'paper1-archive@users.noreply.github.com'], repo, env)
        run_git(['config', 'credential.helper', ''], repo, env)
        fetch = run_git(['fetch', '-q', '--depth=1', 'origin', 'refs/heads/' + BRANCH], repo, env, optional=True)
        if fetch.returncode == 0:
            run_git(['checkout', '-q', '-B', BRANCH, 'FETCH_HEAD'], repo, env)
        else:
            run_git(['checkout', '-q', '--orphan', BRANCH], repo, env)
        count = copy_github_files(repo, c)
        run_git(['add', '-A'], repo, env)
        changes = run_git(['diff', '--cached', '--quiet'], repo, env, optional=True)
        if changes.returncode:
            run_git(['commit', '-q', '-m', 'Archive verified Paper1 source-expansion results'], repo, env)
        local = run_git(['rev-parse', 'HEAD'], repo, env).stdout.strip()
        run_git(['push', '-q', 'origin', 'HEAD:refs/heads/' + BRANCH], repo, env)
        remote = run_git(['ls-remote', 'origin', 'refs/heads/' + BRANCH], repo, env).stdout.split()[0]
        if remote != local:
            raise RuntimeError('github_remote_commit_mismatch')
        return {'commit': local, 'files': count, 'branch': BRANCH}


def archive(c):
    result_zip = validate_run()
    checkpoints = selected_checkpoints()
    s = client(c)
    try:
        objects = [upload(s, c, result_zip, PREFIX + '/results/' + result_zip.name)]
        for path in checkpoints:
            objects.append(upload(s, c, path, PREFIX + '/checkpoints/' + sha(path) + path.suffix))
        manifest = {
            'protocol': 'paper1_source_expansion_18ch_dimensionless_v1_20261017',
            'status': 'completed_verified',
            'source_code_commit': '14bc7ad24c10cc72c9dc074816a63e0b246b0c68',
            'results_sha256': sha(result_zip),
            'r2_objects': objects,
            'external_evidence_role': 'exploratory'
        }
        write(RUN / 'archive_manifest.json', manifest)
        upload(s, c, RUN / 'archive_manifest.json', PREFIX + '/archive_manifest.json')
    finally:
        s.close()
    receipt = publish_github(c)
    write(STATUS, {'status': 'ARCHIVE_COMPLETE', 'github': receipt,
                   'r2_object_count': len(objects) + 1,
                   'r2_prefix': PREFIX, 'results_sha256': sha(result_zip)})
    print('ARCHIVE_COMPLETE GitHub and R2 readbacks confirmed.', flush=True)


def main():
    c = credentials()
    if '--check' in sys.argv:
        preflight(c)
        return
    RUN.mkdir(parents=True, exist_ok=True)
    with (ARC / 'monitor.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Existing archive monitor is already active.', flush=True)
            return
        while True:
            try:
                if STATUS.exists() and json.loads(STATUS.read_text()).get('status') == 'ARCHIVE_COMPLETE':
                    return
                current = RUN / 'status.json'
                if current.is_file() and json.loads(current.read_text()).get('stage') == 'COMPLETE':
                    archive(c)
                    return
            except Exception as exc:
                write(STATUS, {'status': 'ARCHIVE_RETRYING', 'error_type': type(exc).__name__,
                               'retry_seconds': 120})
                print('Archive attempt failed; retrying. Error type:', type(exc).__name__, flush=True)
            time.sleep(120)


if __name__ == '__main__':
    main()
PY
"$ARC/venv/bin/python" -m py_compile "$ARC/watch.py"
"$ARC/venv/bin/python" "$ARC/watch.py" --check
nohup "$ARC/venv/bin/python" -u "$ARC/watch.py" \
    >> "$ARC/archive.log" 2>&1 < /dev/null &
WATCH_PID=$!
if ! kill -0 "$WATCH_PID" 2>/dev/null; then
  echo 'Archive watcher did not start. Inspect archive.log' >&2
  exit 3
fi

INSTALLER=/tmp/paper1-source-expansion-verified-runpod.sh
curl --fail --silent --show-error --location --retry 4 \
 'https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5c1146b5b3749170b351c504f466247d3454a3e9/research_runs/SOURCE_EXPANSION_20261017_RUNPOD.sh' \
 -o "$INSTALLER"
bash "$INSTALLER"
echo 'INSTALLER_DISPATCHED; monitor status via /workspace/paper1_expansion/run.log'
echo 'ARCHIVE_WATCHER_RUNNING; monitor via /workspace/paper1_expansion/_archive/archive.log'
echo 'Run ends only when status.json reports COMPLETE and archive_status.json reports ARCHIVE_COMPLETE.'
