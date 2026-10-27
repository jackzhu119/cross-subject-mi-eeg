#!/usr/bin/env bash
# Immutable code-only bootstrap. No data, package or model downloads in Slurm.
set -euo pipefail
PROJECTS_ROOT="${PAPER1_PROJECTS_ROOT:-/public/home/zhuziyuan/projects}"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
SOURCE_REV="f79e4efb42e64a0a0dbdbf0a68043eadbd2563a7"
BUNDLE_SHA="a046529eae4f3069847488fc1a69628eb4ce5a434e4ece2194dc9dbbaf813d8e"
mkdir -p "$PROJECTS_ROOT"
PROJECTS_ROOT="$(cd "$PROJECTS_ROOT" && pwd)"
CACHE="$PROJECTS_ROOT/.paper1-composition-downloads"
CODE="$PROJECTS_ROOT/PAPER1_COMPOSITION_20261027/code-${BUNDLE_SHA:0:16}"
mkdir -p "$CACHE"
if [ ! -x "$PYTHON_BIN" ]; then printf 'Existing Python missing: %s\n' "$PYTHON_BIN" >&2; exit 2; fi
ARCHIVE="$CACHE/$BUNDLE_SHA.tar.gz"
exec 9>"$CACHE/bootstrap.lock"
flock 9
if [ ! -f "$ARCHIVE" ]; then
  curl -q -4 -f --connect-timeout 8 --max-time 90 --retry 2 \
    -H 'Accept: application/vnd.github.raw+json' \
    "https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_COMPOSITION_20261027/dist/paper1-composition-code.tar.gz?ref=$SOURCE_REV" \
    -o "$ARCHIVE.part"
  observed="$(sha256sum "$ARCHIVE.part")"
  if [ "${observed%% *}" != "$BUNDLE_SHA" ]; then printf 'Code package SHA mismatch; partial preserved.\n' >&2; exit 2; fi
  mv "$ARCHIVE.part" "$ARCHIVE"
fi
"$PYTHON_BIN" -B - "$ARCHIVE" "$CODE" "$BUNDLE_SHA" <<'INSTALL_CODE'
import hashlib,json,os,sys,tarfile,tempfile
from pathlib import Path
archive,root=map(Path,sys.argv[1:3]); expected=sys.argv[3]
if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected: raise ValueError('Code package SHA mismatch')
with tarfile.open(archive,'r:gz') as source:
    members=source.getmembers()
    if not all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members):
        raise ValueError('Invalid code package member')
    if len(members)>200 or len({m.name for m in members})!=len(members) or sum(m.size for m in members)>16*1024**2:
        raise ValueError('Invalid code package inventory')
    manifest=json.load(source.extractfile('BUNDLE_MANIFEST.json'))
    rows=manifest['files']
    if {m.name for m in members}!={r['path'] for r in rows}|{'BUNDLE_MANIFEST.json'}:
        raise ValueError('Code package inventory mismatch')
    root.mkdir(parents=True,exist_ok=True)
    for row in rows:
        data=source.extractfile(row['path']).read(); path=root/row['path']
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('Code payload SHA mismatch')
        if path.exists():
            if path.read_bytes()!=data: raise ValueError('Existing fixed code differs: '+row['path'])
            continue
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
        with os.fdopen(fd,'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,path)
print(json.dumps({'code_ready':True,'code_root':str(root),'bundle_sha256':expected,'data_downloaded':False}),flush=True)
INSTALL_CODE
flock -u 9
exec 9>&-
export PAPER1_GITHUB_TRANSPORT=curl
export PYTHONPATH="$CODE${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -B -u -m compmi.launch \
  --project "$PROJECTS_ROOT/paper1-composition-v2" \
  --base-project "$PROJECTS_ROOT/paper1-risk-v1" --python "$PYTHON_BIN" "$@"
