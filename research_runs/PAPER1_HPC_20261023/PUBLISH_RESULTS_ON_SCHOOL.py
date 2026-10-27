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


def build_bundle(project: Path, destination: Path) -> dict:
    """Export saved results only; never execute training, inference or statistics.

    The archive preserves byte identities, not a new independent numerical audit.
    Source files remain read-only. Failed output partials are retained.
    """
    project = Path(project).expanduser().resolve()
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
    for task in tasks:
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
    for relative in sorted(selected):
        path = _inside(project, relative)
        before = _stat_id(path)
        if relative in validated_stats and before != validated_stats[relative]:
            raise ValueError('Validated result JSON changed before hashing')
        digest = _file_sha(path)
        if before != _stat_id(path):
            raise ValueError('A saved result changed during hashing; retry only the export')
        snapshots[relative] = before
        files.append({'path':relative, 'bytes':path.stat().st_size, 'sha256':digest})
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
    with os.fdopen(descriptor,'wb') as raw:
        with gzip.GzipFile(fileobj=_LimitedWriter(raw,_MAX_BUNDLE), mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as archive:
                for row in files:
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
    return {'archive':archive_path, 'manifest':manifest, 'manifest_path':manifest_path,
            'sha256':digest, 'bytes':archive_path.stat().st_size}

# GitHub publication is independent of training and the existing progress writer.
import argparse
import base64
import fcntl
import getpass
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
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


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
        try:
            command = ['curl','-q','-4','--silent','--show-error','--config','-',
                       '--connect-timeout','8','--max-time','300','--request',method,
                       '--max-filesize',str(expected_bytes+1 if raw_path else 3*1024*1024)]
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
            except (OSError,subprocess.TimeoutExpired):
                raise UploadError('GitHub connection failed; local evidence retained; rerun the same command') from None
            if response.returncode:
                raise UploadError('GitHub transfer failed (curl exit %d); evidence retained; rerun the same command'%response.returncode)
            body,separator,code = response.stdout.rpartition(b'\n')
            if not separator or not re.fullmatch(rb'[1-5][0-9]{2}',code):
                raise UploadError('Invalid GitHub response status')
            status=int(code)
            if not 200 <= status < 300:
                raise UploadError('GitHub HTTP %d; no training or source files changed'%status,status)
            if raw_path is not None:
                return None
            try:
                return json.loads(body)
            except ValueError:
                raise UploadError('Invalid GitHub JSON response') from None
        finally:
            if payload_path is not None:
                Path(payload_path).unlink(missing_ok=True)

    def optional(self, endpoint):
        try:
            return self.request('GET',endpoint)
        except UploadError as error:
            if error.status == 404:
                return None
            raise


def _token(project, reauthorize=False):
    path=Path.home()/'.config/mi-eeg/paper1-hpc-20261023/token'
    sync=project/'config/sync.json'
    if sync.is_file():
        value=json.loads(sync.read_text())
        if value.get('token_file'):
            path=Path(value['token_file']).expanduser()
    if not reauthorize and path.exists():
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077:
            raise ValueError('Existing token must be a regular private file (chmod 600); its contents were not displayed')
        token=path.read_text().strip()
    else:
        token=getpass.getpass('GitHub Contents-write token (hidden): ').strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError('A nonempty GitHub token is required in the hidden terminal prompt')
    return token


def publish_bundle(project, bundle, token, repository=REPOSITORY):
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
    reference=api.optional(base+'/git/ref/heads/'+branch_path)
    if reference is None:
        main=api.request('GET',base+'/git/ref/heads/main')
        reference=api.request('POST',base+'/git/refs',{'ref':'refs/heads/'+branch,'sha':main['object']['sha']})
    head=reference['object']['sha']
    parent=api.request('GET',base+'/git/commits/'+head)
    print(json.dumps({'stage':'uploading_result_bundle','archive_bytes':len(data),
                      'sha256':bundle['sha256'],'new_model_fits':0}),flush=True)
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
    print(json.dumps(receipt,indent=2),flush=True)
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path('/public/home/zhuziyuan/projects/paper1-risk-v1'))
    parser.add_argument('--publish',action='store_true',help='Upload the completed evidence to its separate result branch')
    parser.add_argument('--reauthorize',action='store_true',help='Ask for a fresh token using hidden terminal input')
    args=parser.parse_args(argv)
    project=args.project.expanduser().resolve()
    destination=project/'exports/github-results'
    destination.mkdir(parents=True,exist_ok=True)
    with (destination/'.export.lock').open('a+') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another result export is active; no duplicate upload started.',flush=True)
            return 0
        bundle=build_bundle(project,destination)
        print(json.dumps({'stage':'RESULT_EVIDENCE_EXPORTED','archive':str(bundle['archive']),
                          'bytes':bundle['bytes'],'sha256':bundle['sha256'],'new_model_fits':0}),flush=True)
        if args.publish:
            publish_bundle(project,bundle,_token(project,args.reauthorize))
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Do not render arbitrary remote bodies, token values or signed URLs.
        message=str(error) if isinstance(error,(ValueError,UploadError)) else type(error).__name__
        print(json.dumps({'status':'EXPORT_OR_UPLOAD_INCOMPLETE','reason':message,
                          'source_results_retained':True,'new_model_fits':0}),flush=True)
        raise SystemExit(1)
