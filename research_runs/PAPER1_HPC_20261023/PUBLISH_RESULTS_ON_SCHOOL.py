#!/usr/bin/env python3
"""Read-only, stdlib-only export of completed Paper 1 result evidence."""
from pathlib import Path, PurePosixPath
import gzip
import hashlib
import io
import itertools
import json
import os
import re
import stat
import tarfile
import tempfile
import zipfile

_METHODS = ('erm', 'groupdro', 'tail', 'consistency', 'tail_consistency')
_DOMAINS = ('nested_outer', 'external_fixed40', 'external_source_selected')
_MAX_BUNDLE = 64 * 1024 * 1024
_HEX64 = re.compile(r'[0-9a-f]{64}')


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _stat_id(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _inside(project, relative):
    relative = str(relative)
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or '..' in parts.parts or '\\' in relative:
        raise ValueError('Result path escapes its selected project')
    path = project.joinpath(*parts.parts)
    if not path.resolve().is_relative_to(project):
        raise ValueError('Result symlink escapes its selected project')
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Required result file is missing: ' + relative)
    return path


def _json_result(project, relative):
    path = _inside(project, relative)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Oversized result JSON: ' + str(relative))
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def _file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _worker_fingerprint(study, task, data_fingerprint):
    defaults = {'science_version': 'paper1_hpc_subject_class_v1', 'input_shape': [3,18,320],
        'epochs': 40, 'updates_per_epoch': 128, 'subjects_per_batch': 8, 'trials_per_class': 8,
        'learning_rate': 0.001, 'weight_decay': 0.0, 'amp': False, 'architecture': {}, 'objective': {}}
    scientific = {key: study.get(key, value) for key, value in defaults.items()}
    fields = {key: task.get(key) for key in ('id', 'phase', 'method', 'seed', 'fold', 'train_ids',
                                          'validation_ids', 'test_ids', 'selected_epoch')}
    return _canonical({'science': scientific, 'task': fields, 'data': data_fingerprint})


def _atomic_evidence(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Existing export evidence differs; retained: ' + path.name)
        return
    descriptor, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class _LimitedWriter:
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
    def write(self, data):
        if self.stream.tell() + len(data) > self.limit:
            raise ValueError('Compressed result export exceeds 64 MiB; partial retained')
        return self.stream.write(data)
    def tell(self):
        return self.stream.tell()
    def flush(self):
        return self.stream.flush()


def build_bundle(project: Path, destination: Path, progress=None) -> dict:
    """Export saved results only; never execute training, inference or statistics.

    The archive preserves byte identities, not a new independent numerical audit.
    Source files remain read-only. Failed output partials are retained.
    """
    project = Path(project).expanduser().resolve()
    if progress:
        progress('checking_saved_results', completed_tasks=0, total_tasks=90,
                 selected_evaluation_summaries=0, prediction_shards=0)
    if not project.is_dir():
        raise ValueError('Result project directory is missing')
    destination = Path(destination).expanduser().absolute()
    validated_stats = {}
    def read_json(relative):
        path = _inside(project, relative)
        before = _stat_id(path)
        value = _json_result(project, relative)
        if before != _stat_id(path):
            raise ValueError('Saved JSON changed during validation; retry only the export')
        prior = validated_stats.setdefault(str(relative), before)
        if prior != before:
            raise ValueError('Saved JSON changed between validation reads')
        return value
    study = read_json('config/study.json')
    tasks = read_json('tasks.json')
    plan = read_json('state/plan.json')
    selection = read_json('state/selection.json')
    analysis = read_json('outputs/analysis/summary.json')
    if (tuple(study.get('methods', ())) != _METHODS or study.get('epochs') != 40
            or study.get('updates_per_epoch') != 128 or study.get('source_folds') != 5
            or plan.get('development_task_count') != 75 or plan.get('final_task_count') != 15):
        raise ValueError('Saved study/plan differs from the complete 75+15 frozen design')
    if not isinstance(tasks, list) or len(tasks) != 90:
        raise ValueError('The complete 90 saved task definitions are required')
    ids = [t.get('id') for t in tasks]
    if len(set(ids)) != 90 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', x) for x in ids):
        raise ValueError('Saved task identities are not unique or safe')
    dev = [t for t in tasks if t.get('phase') == 'development']
    final = [t for t in tasks if t.get('phase') == 'final']
    validation_seeds, final_seeds = study.get('validation_seeds', []), study.get('final_seeds', [])
    if (len(validation_seeds) != 3 or len(set(validation_seeds)) != 3
            or len(final_seeds) != 3 or len(set(final_seeds)) != 3
            or set(validation_seeds) & set(final_seeds)
            or len(dev) != 75 or len(final) != 15
            or {(t.get('fold'),t.get('seed'),t.get('method')) for t in dev}
                != set(itertools.product(range(5), validation_seeds, _METHODS))
            or {(t.get('seed'),t.get('method')) for t in final}
                != set(itertools.product(final_seeds, _METHODS))):
        raise ValueError('Saved development/final combinations differ from the fixed plan')
    fingerprint = plan.get('fingerprint')
    data_fingerprint = plan.get('identity', {}).get('data_fingerprint')
    if not _HEX64.fullmatch(str(fingerprint)) or not _HEX64.fullmatch(str(data_fingerprint)):
        raise ValueError('Saved plan/data fingerprints are missing')
    if (plan.get('development_tasks_sha256') != _canonical(dev)
            or selection.get('plan_fingerprint') != fingerprint
            or analysis.get('plan_fingerprint') != fingerprint
            or analysis.get('status') != 'complete'
            or set(analysis.get('domains', {})) != set(_DOMAINS)
            or any(analysis['domains'][d].get('status') != 'complete' for d in _DOMAINS)):
        raise ValueError('Saved plan, selection or complete analysis identity differs')
    selected = {'config/study.json', 'tasks.json', 'state/plan.json', 'state/selection.json',
                'outputs/analysis/summary.json'}
    for domain in _DOMAINS:
        relative = 'outputs/analysis/' + domain + '.json'
        domain_summary = read_json(relative)
        read_json('outputs/analysis/' + domain + '_participants.json')
        if domain_summary.get('status') != 'complete' or domain_summary.get('domain') != domain:
            raise ValueError('A saved statistical domain is incomplete or mismatched')
        selected.update((relative, 'outputs/analysis/' + domain + '_participants.json'))
    complete_records, evaluations, shard_count = {}, 0, 0
    for task_index, task in enumerate(tasks, 1):
        task_id = task['id']
        run_relative = 'outputs/runs/' + task_id
        relative = run_relative + '/complete.json'
        complete = read_json(relative)
        if (complete.get('status') != 'complete' or complete.get('task_id') != task_id
                or any(complete.get(k) != task.get(k) for k in ('phase','method','seed','fold','selected_epoch'))
                or complete.get('epochs_completed') != 40 or complete.get('global_step') != 5120
                or complete.get('optimizer_updates') != 5120
                or complete.get('fingerprint') != _worker_fingerprint(study,task,data_fingerprint)):
            raise ValueError('A task completion identity/40-epoch trajectory differs: ' + task_id)
        complete_records[task_id] = complete
        selected.add(relative)
        expected = {'outer_best'} if task['phase'] == 'development' else {'fixed40','source_selected'}
        if not isinstance(complete.get('evaluations'),dict) or set(complete['evaluations']) != expected:
            raise ValueError('A complete task lacks its required saved evaluation variants')
        for variant, evaluation_relative in complete['evaluations'].items():
            parts = PurePosixPath(str(evaluation_relative))
            if (len(parts.parts) != 4 or parts.parts[0] != 'evaluations' or parts.parts[1] != variant
                    or not re.fullmatch('[0-9a-f]{20}', parts.parts[2]) or parts.parts[3] != 'summary.json'):
                raise ValueError('Evaluation reference is outside its exact selected variant')
            relative = run_relative + '/' + parts.as_posix()
            summary = read_json(relative)
            digest = summary.get('model_sha256')
            if (summary.get('variant') != variant or not _HEX64.fullmatch(str(digest))
                    or digest[:20] != parts.parts[2] or not isinstance(summary.get('people'), list)
                    or not summary['people']):
                raise ValueError('Saved evaluation model/variant/people identity differs')
            people = [row.get('person_id') for row in summary['people']]
            if len(people) != len(set(people)) or set(people) != set(task.get('test_ids', [])):
                raise ValueError('Saved evaluation people differ from the fixed task')
            folder = _inside(project, relative).parent
            shards = sorted(folder.glob('*.npz'))
            if not shards:
                raise ValueError('Selected evaluation prediction shards are missing')
            selected.add(relative)
            evaluations += 1
            for shard in shards:
                if not re.fullmatch('[0-9a-f]{24}\\.npz', shard.name):
                    raise ValueError('Unexpected selected prediction filename')
                shard_relative = str(shard.relative_to(project)).replace(os.sep, '/')
                shard = _inside(project, shard_relative)
                with zipfile.ZipFile(shard) as archive:
                    names = archive.namelist()
                    if len(names) != 4 or set(names) != {'logits.npy','y.npy','trial_ids.npy','identity.npy'}:
                        raise ValueError('Prediction archive contains unexpected arrays; no EEG/input upload')
                selected.add(shard_relative)
                shard_count += 1
                if progress:
                    progress('checking_saved_results', completed_tasks=task_index-1, total_tasks=90,
                             selected_evaluation_summaries=evaluations, prediction_shards=shard_count)
        if progress:
            progress('checking_saved_results', completed_tasks=task_index, total_tasks=90,
                     selected_evaluation_summaries=evaluations, prediction_shards=shard_count)
    if evaluations != 105:
        raise ValueError('The complete 105 selected evaluation summaries are required')
    records = selection.get('source_records')
    if not isinstance(records,list) or len(records) != 75:
        raise ValueError('Complete source-selection evidence is missing')
    by_record = {row.get('task_id'):row for row in records}
    if set(by_record) != {t['id'] for t in dev}:
        raise ValueError('Source-selection task evidence differs')
    for task in dev:
        record, complete = by_record[task['id']], complete_records[task['id']]
        if record.get('best_epoch') != complete.get('best_epoch') or record.get('complete_sha256') != _canonical(complete):
            raise ValueError('Saved selection does not bind the actual completed source task')
    snapshots, files = {}, []
    hashed_bytes = 0
    if progress:
        progress('hashing_result_files', completed_files=0, total_files=len(selected), processed_bytes=0)
    for file_index, relative in enumerate(sorted(selected), 1):
        path = _inside(project, relative)
        before = _stat_id(path)
        if relative in validated_stats and before != validated_stats[relative]:
            raise ValueError('Validated result JSON changed before hashing')
        digest = _file_sha(path)
        if before != _stat_id(path):
            raise ValueError('A saved result changed during hashing; retry only the export')
        snapshots[relative] = before
        files.append({'path':relative, 'bytes':path.stat().st_size, 'sha256':digest})
        hashed_bytes += files[-1]['bytes']
        if progress:
            progress('hashing_result_files', completed_files=file_index, total_files=len(selected),
                     processed_bytes=hashed_bytes)
    manifest = {'schema_version':1, 'project_id':project.name, 'plan_fingerprint':fingerprint,
        'scope':'saved statistics, selection, task completions and selected held-out predictions',
        'development_completed':75, 'final_completed':15, 'selected_evaluation_summaries':105,
        'prediction_shards':shard_count, 'selected_file_count':len(files), 'selected_files':files,
        'new_model_fits':0, 'new_model_inference':0, 'statistics_recomputed':False,
        'array_numeric_audit_performed':False, 'model_checkpoint_backup':False,
        'raw_or_prepared_eeg_included':False, 'training_inner_epoch_shards_included':False}
    manifest_bytes = (json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    destination.mkdir(parents=True,exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix='paper1-results.',suffix='.tar.gz.partial',dir=destination)
    temporary = Path(temporary_name)
    packed_bytes = 0
    if progress:
        progress('packing_result_files', completed_files=0, total_files=len(files),
                 processed_bytes=0, total_bytes=hashed_bytes)
    with os.fdopen(descriptor,'wb') as raw:
        with gzip.GzipFile(fileobj=_LimitedWriter(raw,_MAX_BUNDLE), mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as archive:
                for file_index, row in enumerate(files, 1):
                    relative = row['path']
                    path = _inside(project,relative)
                    if snapshots[relative] != _stat_id(path):
                        raise ValueError('Saved result changed before packing; partial retained')
                    data = path.read_bytes()
                    if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                        raise ValueError('Saved result changed while packing; partial retained')
                    info = tarfile.TarInfo(relative)
                    info.size, info.mtime, info.mode = len(data), 0, 0o644
                    archive.addfile(info,io.BytesIO(data))
                    packed_bytes += len(data)
                    if progress:
                        progress('packing_result_files', completed_files=file_index, total_files=len(files),
                                 processed_bytes=packed_bytes, total_bytes=hashed_bytes)
                info = tarfile.TarInfo('EXPORT_MANIFEST.json')
                info.size, info.mtime, info.mode = len(manifest_bytes), 0, 0o644
                archive.addfile(info,io.BytesIO(manifest_bytes))
        raw.flush()
        os.fsync(raw.fileno())
    if any(snapshots[r['path']] != _stat_id(_inside(project,r['path'])) for r in files):
        raise ValueError('Saved result changed during export; partial retained')
    digest = _file_sha(temporary)
    archive_path = destination / ('paper1-results-' + digest[:16] + '.tar.gz')
    if archive_path.exists():
        if _file_sha(archive_path) != digest:
            raise ValueError('Existing export archive differs; old and partial retained')
        temporary.unlink()
    else:
        os.replace(temporary,archive_path)
    manifest_path = destination / (archive_path.name + '.manifest.json')
    _atomic_evidence(manifest_path,manifest_bytes)
    if progress:
        progress('result_evidence_exported', archive_bytes=archive_path.stat().st_size,
                 sha256=digest, completed_files=len(files), total_files=len(files))
    return {'archive':archive_path, 'manifest':manifest, 'manifest_path':manifest_path,
            'sha256':digest, 'bytes':archive_path.stat().st_size}

# GitHub publication is independent of training and the existing progress writer.
import argparse
import base64
import fcntl
import getpass
import signal
import sys
import threading
import time
import re
import stat
import subprocess
import tempfile
import urllib.parse
from datetime import datetime, timezone

REPOSITORY = 'jackzhu119/cross-subject-mi-eeg'
RESULT_BRANCH = 'hpc-results/paper1-risk-v1'
RESULT_DIRECTORY = 'research_runs/PAPER1_HPC_RESULTS_20261027'


class UploadError(RuntimeError):
    def __init__(self, message, status=None, retryable=False, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable or status in {408, 409, 429, 500, 502, 503, 504}
        self.retry_after = retry_after


def _git_blob_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


class GitHubPublisher:
    def __init__(self, token, repository):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Invalid repository name')
        self.token, self.prefix = token, '/repos/'+repository

    def request(self, method, endpoint, payload=None, *, raw_path=None, expected_bytes=None):
        if not endpoint.startswith(self.prefix+'/') or '://' in endpoint or '\n' in endpoint:
            raise ValueError('Unexpected GitHub API path')
        config = ['header = '+json.dumps('Authorization: Bearer '+self.token),
                  'header = '+json.dumps('Accept: '+('application/vnd.github.raw+json' if raw_path else 'application/vnd.github+json')),
                  'header = "X-GitHub-Api-Version: 2022-11-28"',
                  'header = "Content-Type: application/json"']
        payload_path = None
        header_fd,header_path=tempfile.mkstemp(prefix='paper1-results-http-',suffix='.headers')
        os.close(header_fd)
        try:
            command = ['curl','-q','-4','--silent','--show-error','--config','-',
                       '--connect-timeout','8','--max-time','300','--request',method,
                       '--max-filesize',str(expected_bytes+1 if raw_path else 3*1024*1024),
                       '--dump-header',header_path]
            if payload is not None:
                fd,payload_path = tempfile.mkstemp(prefix='paper1-github-payload-',suffix='.json')
                with os.fdopen(fd,'w') as stream:
                    json.dump(payload,stream,allow_nan=False,separators=(',',':'))
                command += ['--data-binary','@'+payload_path]
            if raw_path is not None:
                command += ['--output',str(raw_path)]
            command += ['--write-out','\n%{http_code}','https://api.github.com'+endpoint]
            try:
                response = subprocess.run(command,input=('\n'.join(config)+'\n').encode(),
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=320)
            except subprocess.TimeoutExpired:
                raise UploadError('GitHub connection failed; local evidence retained', retryable=True) from None
            except OSError:
                raise UploadError('System curl could not start; local evidence retained') from None
            if response.returncode:
                raise UploadError('GitHub transfer failed (curl exit %d); evidence retained'%response.returncode,
                                  retryable=response.returncode in {5, 6, 7, 18, 28, 35, 52, 55, 56, 92})
            body,separator,code = response.stdout.rpartition(b'\n')
            if not separator or not re.fullmatch(rb'[1-5][0-9]{2}',code):
                raise UploadError('Invalid GitHub response status')
            status=int(code)
            if not 200 <= status < 300:
                headers={}
                with open(header_path,'rb') as stream:
                    for line in stream.read(65536).decode('iso-8859-1').splitlines():
                        if line.startswith('HTTP/'):
                            headers={}
                        elif ':' in line:
                            key,value=line.split(':',1)
                            if key.lower() in {'retry-after','x-ratelimit-remaining','x-ratelimit-reset'}:
                                headers[key.lower()]=value.strip()
                limited=status==429 or (status==403 and (headers.get('x-ratelimit-remaining')=='0' or 'retry-after' in headers))
                wait=None
                if limited:
                    try:
                        wait=min(900,max(1,float(headers['retry-after']) if 'retry-after' in headers
                                         else float(headers['x-ratelimit-reset'])-time.time()))
                    except (ValueError,KeyError):
                        pass
                raise UploadError('GitHub HTTP %d; no training or source files changed'%status,status,
                                  retryable=limited,retry_after=wait)
            if raw_path is not None:
                return None
            try:
                return json.loads(body)
            except ValueError:
                raise UploadError('Invalid GitHub JSON response') from None
        finally:
            if payload_path is not None:
                Path(payload_path).unlink(missing_ok=True)
            Path(header_path).unlink(missing_ok=True)

    def optional(self, endpoint):
        try:
            return self.request('GET',endpoint)
        except UploadError as error:
            if error.status == 404:
                return None
            raise


def _token_path(project):
    path=Path.home()/'.config/mi-eeg/paper1-hpc-20261023/token'
    sync=project/'config/sync.json'
    if sync.is_file():
        value=json.loads(sync.read_text())
        if value.get('token_file'):
            path=Path(value['token_file']).expanduser()
    return path


def _token(project, reauthorize=False, interactive=True):
    path=_token_path(project)
    if not reauthorize and path.exists():
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077:
            raise ValueError('Existing token must be a regular private file (chmod 600); its contents were not displayed')
        token=path.read_text().strip()
    else:
        if not interactive:
            raise UploadError('Private token missing; restart with --reauthorize in an interactive terminal',status=401)
        token=getpass.getpass('GitHub Contents-write token (hidden): ').strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError('A nonempty GitHub token is required in the hidden terminal prompt')
    return token


def publish_bundle(project, bundle, token, repository=REPOSITORY, progress=None):
    if progress:
        progress('verifying_local_result_bundle', archive_bytes=bundle['bytes'])
    archive=Path(bundle['archive'])
    data=archive.read_bytes()
    if hashlib.sha256(data).hexdigest()!=bundle['sha256']:
        raise UploadError('Local bundle changed before upload')
    manifest_bytes=Path(bundle['manifest_path']).read_bytes()
    if json.loads(manifest_bytes)!=bundle['manifest']:
        raise UploadError('Local export manifest changed before upload')
    selected={row['path']:row for row in bundle['manifest']['selected_files']}
    readable={}
    for relative in ['outputs/analysis/summary.json','outputs/analysis/nested_outer.json',
                     'outputs/analysis/nested_outer_participants.json','outputs/analysis/external_fixed40.json',
                     'outputs/analysis/external_fixed40_participants.json','outputs/analysis/external_source_selected.json',
                     'outputs/analysis/external_source_selected_participants.json']:
        content=(project/relative).read_bytes()
        expected=selected[relative]
        if len(content)!=expected['bytes'] or hashlib.sha256(content).hexdigest()!=expected['sha256']:
            raise UploadError('Readable result changed after export; retain the source and rerun export')
        readable[relative]=content.decode('utf-8')
    api=GitHubPublisher(token,repository)
    base=api.prefix
    branch=RESULT_BRANCH
    branch_path=urllib.parse.quote(branch,safe='/')
    if progress:
        progress('preparing_result_branch', archive_bytes=len(data))
    reference=api.optional(base+'/git/ref/heads/'+branch_path)
    if reference is None:
        main=api.request('GET',base+'/git/ref/heads/main')
        reference=api.request('POST',base+'/git/refs',{'ref':'refs/heads/'+branch,'sha':main['object']['sha']})
    head=reference['object']['sha']
    parent=api.request('GET',base+'/git/commits/'+head)
    print(json.dumps({'stage':'uploading_result_bundle','archive_bytes':len(data),
                      'sha256':bundle['sha256'],'new_model_fits':0}),flush=True)
    if progress:
        progress('uploading_result_bundle', archive_bytes=len(data), sha256=bundle['sha256'])
    blob=api.request('POST',base+'/git/blobs',{'encoding':'base64','content':base64.b64encode(data).decode('ascii')})
    expected_blob=_git_blob_sha(data)
    if blob.get('sha')!=expected_blob:
        raise UploadError('Uploaded Git blob identity differs')
    remote=RESULT_DIRECTORY+'/'+bundle['sha256'][:16]
    name=archive.name
    entries=[{'path':remote+'/'+name,'mode':'100644','type':'blob','sha':expected_blob}]
    readme=(
        '# Paper 1: completed school HPC result evidence\n\n'
        '90 fits: 75 development and 15 final. Three saved statistical domains are complete.\n\n'
        'This export contains original completion records, exact referenced evaluation summaries, '
        'held-out prediction shards, plan/selection records and full analysis JSON. '
        'It preserves all comparison directions. It does not rerun fitting, inference or statistics.\n\n'
        'Raw EEG, prepared EEG arrays, optimizer/model checkpoints and training-time inner-epoch '
        'prediction caches are not included. Keep the original school project and weights. '
        'Archive integrity is verified by SHA256 and remote readback; independent scientific '
        'verification of the result contents remains a separate task.\n\n'
        'Download '+name+' and verify:\n\n```bash\nsha256sum -c '+name+'.sha256\n'
        'tar -xzf '+name+'\n```\n\n'
        'The full member inventory and scope are in EXPORT_MANIFEST.json. '
        'Readable original statistics are also copied to outputs/analysis/ below.\n')
    text_files={'EXPORT_MANIFEST.json':manifest_bytes.decode(),
                name+'.sha256':bundle['sha256']+'  '+name+'\n','README.md':readme}
    text_files.update(readable)
    for relative,content in sorted(text_files.items()):
        entries.append({'path':remote+'/'+relative,'mode':'100644','type':'blob','content':content})
    if progress:
        progress('committing_result_evidence', archive_bytes=len(data))
    tree=api.request('POST',base+'/git/trees',{'base_tree':parent['tree']['sha'],'tree':entries})
    commit=head
    if tree['sha']!=parent['tree']['sha']:
        commit=api.request('POST',base+'/git/commits',{
            'message':'Publish completed Paper 1 HPC result evidence '+bundle['sha256'][:16],
            'tree':tree['sha'],'parents':[head]})['sha']
        # No force: another writer's result is retained if the branch advanced.
        api.request('PATCH',base+'/git/refs/heads/'+branch_path,{'sha':commit,'force':False})
    written=api.request('GET',base+'/git/commits/'+commit)
    if written.get('tree',{}).get('sha')!=tree['sha']:
        raise UploadError('Published result tree could not be verified')
    # Read by immutable commit, verify that its archive entry is the uploaded blob.
    endpoint=base+'/contents/'+urllib.parse.quote(remote+'/'+name,safe='/')+'?'+urllib.parse.urlencode({'ref':commit})
    record=api.request('GET',endpoint)
    if record.get('sha')!=expected_blob or record.get('size')!=len(data):
        raise UploadError('Published archive entry differs from local evidence')
    verify=archive.with_name(archive.name+'.github-readback.part')
    if progress:
        progress('reading_back_result_bundle', archive_bytes=len(data))
    api.request('GET',base+'/git/blobs/'+expected_blob,raw_path=verify,expected_bytes=len(data))
    if verify.stat().st_size!=len(data) or hashlib.sha256(verify.read_bytes()).hexdigest()!=bundle['sha256']:
        raise UploadError('GitHub full archive readback SHA256 differs; original bundle retained')
    verify.unlink()
    receipt={'status':'RESULT_BUNDLE_PUBLISHED_AND_READBACK_VERIFIED','updated_at_utc':datetime.now(timezone.utc).isoformat(),
             'repository':repository,'branch':branch,'commit':commit,'directory':remote,
             'archive_sha256':bundle['sha256'],'archive_bytes':len(data),'full_archive_readback_verified':True,
             'complete_fits':90,'new_model_fits':0,'model_checkpoint_backup':False,
             'url':'https://github.com/'+repository+'/tree/'+branch+'/'+remote}
    local=archive.parent/'github-publication.json'
    local.write_text(json.dumps(receipt,indent=2)+'\n')
    if progress:
        progress('result_bundle_readback_verified', archive_bytes=len(data),
                 sha256=bundle['sha256'], commit=commit)
    print(json.dumps(receipt,indent=2),flush=True)
    return receipt


def _status_file(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,indent=2,allow_nan=False)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class UploadProgress:
    """A real phase/counter snapshot plus a periodic liveness message."""
    def __init__(self,project,interval=30):
        self.path=project/'state/results_upload_status.json'
        self.interval=interval;self.lock=threading.Lock();self.stop=threading.Event()
        self.started=time.monotonic();self.last=0
        self.data={'status':'RUNNING','stage':'starting','pid':os.getpid(),'new_model_fits':0}
        self.thread=threading.Thread(target=self._heartbeat,daemon=True)
        self.thread.start()

    def _write(self):
        row={**self.data,'updated_at_utc':datetime.now(timezone.utc).isoformat(),
             'elapsed_seconds':round(time.monotonic()-self.started,1)}
        try:
            _status_file(self.path,row)
        except OSError as error:
            row['monitor_write_error']=type(error).__name__
        print(json.dumps(row,allow_nan=False),flush=True)
        self.last=time.monotonic()

    def __call__(self,stage,**details):
        with self.lock:
            changed=stage!=self.data['stage']
            if changed:
                self.data={k:v for k,v in self.data.items() if k in {'status','pid','new_model_fits'}}
                if stage!='network_retry_wait':
                    self.data['status']='RUNNING'
            self.data.update(stage=stage,**details)
            if changed or time.monotonic()-self.last>=self.interval:
                self._write()

    def finish(self,status,stage,**details):
        with self.lock:
            self.data={'status':status,'stage':stage,'pid':os.getpid(),'new_model_fits':0,**details}
            self._write()

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            with self.lock:
                self._write()

    def close(self):
        self.stop.set();self.thread.join(timeout=1)


class UploadCancelled(Exception):
    pass


def _run_upload(project,publish=True,background=False,retry_seconds=60):
    destination=project/'exports/github-results'
    destination.mkdir(parents=True,exist_ok=True)
    progress=UploadProgress(project)
    def cancel(number,frame):
        raise UploadCancelled()
    previous={number:signal.signal(number,cancel) for number in (signal.SIGTERM,signal.SIGINT)}
    try:
        with (destination/'.export.lock').open('a+') as lock:
            while True:
                try:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    progress('waiting_existing_export',message='Existing foreground/background export retained; no duplicate packing')
                    time.sleep(3)
            bundle=build_bundle(project,destination,progress=progress)
            if not publish:
                progress.finish('EXPORTED','RESULT_EVIDENCE_EXPORTED',archive=str(bundle['archive']),sha256=bundle['sha256'])
                return 0
            attempts=0
            while True:
                attempts+=1
                try:
                    token=_token(project,interactive=not background)
                    receipt=publish_bundle(project,bundle,token,progress=progress)
                    progress.finish('COMPLETE','RESULT_BUNDLE_PUBLISHED_AND_READBACK_VERIFIED',
                                    commit=receipt['commit'],url=receipt['url'],sha256=bundle['sha256'])
                    return 0
                except UploadError as error:
                    if error.status in {401,403} and not error.retryable:
                        progress.finish('AUTH_ACTION_REQUIRED','upload_stopped',http_status=error.status,
                                        reason='Restart interactively with --background --publish --reauthorize')
                        return 3
                    if not error.retryable:
                        raise
                    delay=min(900,max(error.retry_after or 0,retry_seconds*2**min(attempts-1,4)))
                    progress('network_retry_wait',status='RETRY_PENDING',attempt=attempts,
                             retry_after_seconds=delay,http_status=error.status,
                             archive_retained=True,repacking_required=False)
                    time.sleep(delay)
    except (UploadCancelled,KeyboardInterrupt):
        progress.finish('CANCELLED','upload_cancelled',source_results_retained=True)
        return 130
    except Exception as error:
        reason=str(error) if isinstance(error,(ValueError,UploadError)) else type(error).__name__
        progress.finish('FAILED','export_or_upload_failed',error_class=type(error).__name__,
                        reason=reason,source_results_retained=True)
        return 1
    finally:
        progress.close()
        for number,handler in previous.items():
            signal.signal(number,handler)


def _live_background(project):
    try:
        marker=json.loads((project/'state/results_upload_daemon.json').read_text())
        pid=marker['pid'];proc=Path('/proc')/str(pid)
        if type(pid) is not int or pid<2 or proc.stat().st_uid!=os.getuid():
            return None
        args=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
        if ('--background-worker' not in args or '--project' not in args
                or Path(args[args.index('--project')+1]).resolve()!=project
                or str(Path(marker['script']).resolve()) not in args):
            return None
        return marker
    except (OSError,ValueError,KeyError,IndexError,UnicodeError):
        return None


def _prepare_private_token(project,reauthorize=False):
    token=_token(project,reauthorize)
    path=_token_path(project)
    if reauthorize or not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,temporary=tempfile.mkstemp(prefix='.token-',dir=path.parent)
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),0o600)
            stream.write(token+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)


def _export_lock_holders(project,proc_root=Path('/proc')):
    path=project/'exports/github-results/.export.lock'
    info=path.stat()
    identity=(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
    holders=set()
    for line in (proc_root/'locks').read_text().splitlines():
        fields=line.split()
        if ('->' in fields or len(fields)<8 or fields[1] not in {'FLOCK','POSIX'}
                or fields[2:4]!=['ADVISORY','WRITE'] or fields[6:8]!=['0','EOF']):
            continue
        try:
            major,minor,inode=fields[5].split(':')
            observed=(int(major,16),int(minor,16),int(inode,10))
            pid=int(fields[4])
        except ValueError:
            continue
        if observed==identity and pid>1:
            holders.add(pid)
    return holders,info


def _foreground_export_identity(project,pid,lock_info,proc_root=Path('/proc')):
    proc=proc_root/str(pid)
    if pid==os.getpid() or proc.stat().st_uid!=os.getuid():
        raise ValueError('Export lock owner is not an eligible process of this user; retained')
    args=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
    if (not args or not re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?',Path(args[0]).name)
            or '-m' in args or '-c' in args or '--background-worker' in args or '--background' in args
            or '--publish' not in args or args.count('--project')!=1):
        raise ValueError('Export lock owner is not the known foreground publisher; retained')
    position=args.index('--project')
    if position+1>=len(args) or Path(args[position+1]).resolve()!=project:
        raise ValueError('Export owner belongs to a different project; retained')
    names={'paper1-publish-results.py','paper1-upload-bg.py','PUBLISH_RESULTS_ON_SCHOOL.py'}
    scripts=[Path(x) for x in args[1:position] if Path(x).name in names]
    if len(scripts)!=1 or not scripts[0].is_file():
        raise ValueError('Foreground publisher script identity is not observed; retained')
    script=scripts[0].resolve()
    digest=_file_sha(script)
    known={'98bf8fe313a111c0bf84cc04a06ea1e7e0ec451d217c84d92faa075fbe0d833d',
           'ef1a6c67463c5c642c1c85e2c6bfd7378f8f9c39fc680e6c78bdd32d33ed5ef4',
           _file_sha(Path(__file__).resolve())}
    if digest not in known:
        raise ValueError('Foreground publisher source is not a delivered version; retained')
    has_descriptor=False
    for descriptor in (proc/'fd').iterdir():
        try:
            observed=descriptor.stat()
            if (observed.st_dev,observed.st_ino)==(lock_info.st_dev,lock_info.st_ino):
                has_descriptor=True
                break
        except OSError:
            continue
    if not has_descriptor:
        raise ValueError('Foreground publisher no longer has the exact export lock open; retained')
    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'start_ticks':fields[19],'script':str(script),'script_sha256':digest}


def _handoff_foreground(project,proc_root=Path('/proc'),timeout=12):
    """Interrupt only a verified old publisher, never a training/Slurm process."""
    lock_path=project/'exports/github-results/.export.lock'
    if not lock_path.exists():
        print(json.dumps({'status':'NO_OLD_EXPORT_LOCK_OBSERVED','new_model_fits':0}),flush=True)
        return
    holders,info=_export_lock_holders(project,proc_root)
    background=_live_background(project)
    if background and holders=={background['pid']}:
        print(json.dumps({'status':'BACKGROUND_ALREADY_OWNS_EXPORT','pid':background['pid']}),flush=True)
        return
    if not holders:
        # A remote NFS owner may not appear locally. Test availability, never
        # infer a stale inode and never remove or replace the lock file.
        with lock_path.open('a+') as probe:
            try:
                fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Export lock is busy but its local owner is not observable; no process signalled') from None
        print(json.dumps({'status':'OLD_EXPORT_LOCK_ALREADY_RELEASED','new_model_fits':0}),flush=True)
        return
    if len(holders)!=1:
        raise ValueError('Export lock has ambiguous owners; all processes retained')
    pid=next(iter(holders))
    identity=_foreground_export_identity(project,pid,info,proc_root)
    # Recheck owner, inode, process start and exact argv immediately before SIGINT.
    current,current_info=_export_lock_holders(project,proc_root)
    if (current!={pid} or (current_info.st_dev,current_info.st_ino)!=(info.st_dev,info.st_ino)
            or _foreground_export_identity(project,pid,info,proc_root)!=identity):
        raise ValueError('Foreground export identity changed before handoff; no process signalled')
    record={'observed_at_utc':datetime.now(timezone.utc).isoformat(),**identity,
            'signal':'SIGINT','source_results_retained':True,'lock_file_retained':True,
            'new_model_fits':0}
    receipt=project/'state/results-upload-handoffs'/('%d-%d.json'%(time.time_ns(),pid))
    _status_file(receipt,record)
    print(json.dumps({'status':'VERIFIED_OLD_FOREGROUND_EXPORT','pid':pid,'signal':'SIGINT'}),flush=True)
    try:
        os.kill(pid,signal.SIGINT)
    except ProcessLookupError:
        pass
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        owners,_=_export_lock_holders(project,proc_root)
        if pid not in owners:
            background=_live_background(project)
            if owners and (not background or owners!={background['pid']}):
                raise ValueError('Old publisher released the lock but a different owner appeared; retained')
            record.update(status='OLD_FOREGROUND_EXPORT_RELEASED',
                          released_at_utc=datetime.now(timezone.utc).isoformat())
            _status_file(receipt,record)
            print(json.dumps({'status':record['status'],'old_pid':pid,
                              'background_pid':background['pid'] if background else None}),flush=True)
            return
        time.sleep(.2)
    record.update(status='OLD_FOREGROUND_NOT_RELEASED_NO_ESCALATION')
    _status_file(receipt,record)
    raise ValueError('Verified foreground publisher has not released the lock; no forced kill or lock deletion performed')


def _start_background(project,reauthorize=False):
    if os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Start this network uploader on login1, outside a compute allocation')
    state=project/'state';state.mkdir(parents=True,exist_ok=True)
    with (state/'results_upload_start.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        existing=_live_background(project)
        if existing:
            print(json.dumps({'status':'EXISTING_BACKGROUND_UPLOAD_REUSED',**existing}),flush=True)
            return 0
        # Complete any interactive token input before disconnecting stdin.
        _prepare_private_token(project,reauthorize)
        log=project/'logs/results-upload.log';log.parent.mkdir(parents=True,exist_ok=True)
        script=str(Path(__file__).resolve())
        with log.open('ab',buffering=0) as output:
            child=subprocess.Popen([sys.executable,'-B','-u',script,'--project',str(project),
                                    '--publish','--background-worker'],stdin=subprocess.DEVNULL,
                                   stdout=output,stderr=subprocess.STDOUT,start_new_session=True,
                                   close_fds=True,env={**os.environ,'PYTHONUNBUFFERED':'1'})
        marker={'pid':child.pid,'project':str(project),'script':script,'log':str(log),
                'status_file':str(state/'results_upload_status.json')}
        _status_file(state/'results_upload_daemon.json',marker)
        # Observe the actual detached worker's first status, without waiting for packing.
        for _ in range(20):
            if child.poll() is not None:
                break
            try:
                observed=json.loads((state/'results_upload_status.json').read_text())
                if observed.get('pid')==child.pid:
                    break
            except (OSError,ValueError):
                pass
            time.sleep(.1)
        code=child.poll()
        if code not in (None,0):
            print(json.dumps({'status':'BACKGROUND_UPLOAD_STOPPED','exit_code':code,**marker}),flush=True)
            return code
        print(json.dumps({'status':'BACKGROUND_UPLOAD_STARTED' if code is None else 'BACKGROUND_UPLOAD_FINISHED',
                          'new_model_fits':0,**marker}),flush=True)
        return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path('/public/home/zhuziyuan/projects/paper1-risk-v1'))
    parser.add_argument('--publish',action='store_true',help='Upload the completed evidence to its separate result branch')
    parser.add_argument('--reauthorize',action='store_true',help='Ask for a fresh token using hidden terminal input')
    parser.add_argument('--background',action='store_true',help='Detach a login-side upload with logs, heartbeat and retry')
    parser.add_argument('--handoff-foreground',action='store_true',help='Release only the verified old foreground publisher and reuse the background worker')
    parser.add_argument('--background-worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    project=args.project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError('Existing result project directory is missing')
    if args.handoff_foreground:
        if os.environ.get('SLURM_JOB_ID'):
            raise ValueError('Use the foreground upload handoff on login1')
        state=project/'state';state.mkdir(parents=True,exist_ok=True)
        with (state/'results_upload_start.lock').open('a+') as handoff_lock:
            fcntl.flock(handoff_lock,fcntl.LOCK_EX)
            _handoff_foreground(project)
        if not args.background:
            return 0
    if args.background:
        if not args.publish:
            parser.error('--background requires --publish')
        return _start_background(project,args.reauthorize)
    if args.publish and not args.background_worker:
        _prepare_private_token(project,args.reauthorize)
    return _run_upload(project,publish=args.publish,background=args.background_worker)


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Do not render arbitrary remote bodies, token values or signed URLs.
        message=str(error) if isinstance(error,(ValueError,UploadError)) else type(error).__name__
        print(json.dumps({'status':'EXPORT_OR_UPLOAD_INCOMPLETE','reason':message,
                          'source_results_retained':True,'new_model_fits':0}),flush=True)
        raise SystemExit(1)
