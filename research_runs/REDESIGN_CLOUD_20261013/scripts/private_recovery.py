"""Synchronous private recovery snapshots. No GPU, credentials persistence or migration.

One writer owns HEAD with conditional writes. An acknowledged remote intent must
precede consuming any fit ordinal or optimizer update. COMMITTED is published
only after every artifact and manifest was fully read back. Pending/uncertain
updates cannot be automatically replayed after losing the container.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from r2_only import CHUNK, RESERVE, digest, environment_client, regular_path, relative

MAX_FILE = 256 * 1024**2
MAX_SNAPSHOT = 2 * 1024**3
MAX_LOG = 64 * 1024**2
STATIC = ('launch_record.json', 'runtime_lock.json', 'budget_authorization.json',
          'code_identity.json', 'data_prepare_receipt.json', 'public_freeze.json')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def allowed(name):
    relative(name)
    if name in STATIC or name in ('numerical_execution_review.json', 'formal_source_acceptance.json',
                                  'work_root/execution_registration.json', 'work_root/budget_origin.json',
                                  'logs/supervisor.redacted.log'):
        return True
    p = Path(name)
    return (name.startswith('source/') and p.suffix in ('.json', '.csv', '.pt')
            and not any(re.search(r'credential|secret|token|\.env|raw', x, re.I) for x in p.parts))


class Store:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket
        self.verified_blobs = set()

    def get(self, key, limit=MAX_FILE):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response['Body'] as body:
                if response.get('ContentLength', limit + 1) > limit:
                    raise ValueError('recovery_object_oversize')
                data = body.read(limit + 1)
                if len(data) > limit or len(data) != response.get('ContentLength'):
                    raise ValueError('recovery_object_size_mismatch')
            return data, response.get('ETag')
        except ValueError:
            raise
        except Exception:
            raise RuntimeError('private_recovery_read_failed') from None

    def head(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, 'response', {})
            if response.get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None, None
            raise RuntimeError('private_recovery_head_unknown') from None
        with response['Body'] as body:
            data = body.read(1024**2 + 1)
        if len(data) > 1024**2 or len(data) != response.get('ContentLength'):
            raise ValueError('private_recovery_head_size_invalid')
        return data, response.get('ETag')

    def put(self, key, data, *, etag=None, new=False):
        kwargs = {'IfNoneMatch': '*'} if new else {'IfMatch': etag}
        if not new and not etag:
            raise ValueError('conditional_recovery_write_required')
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **kwargs)
        except Exception:
            # Could have succeeded before transport loss: never retry or assume absent.
            raise RuntimeError('private_recovery_write_outcome_uncertain_do_not_retry') from None
        actual, actual_etag = self.get(key, max(len(data), 1))
        if actual != data or not actual_etag:
            raise ValueError('private_recovery_full_readback_mismatch')
        return actual_etag

    def blob(self, prefix, path):
        path = Path(path)
        size = path.stat().st_size
        if size > MAX_FILE:
            raise ValueError('recovery_artifact_size_limit')
        before = digest(path)
        key = prefix + '/blobs/' + before
        if (key, size) in self.verified_blobs:
            return {'key': key, 'bytes': size, 'sha256': before}
        # Immutable content objects must never overwrite an older snapshot's blob.
        try:
            header = self.client.head_object(Bucket=self.bucket, Key=key)
            exists = True
        except Exception as exc:
            if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in ('NoSuchKey', '404'):
                raise RuntimeError('private_recovery_blob_presence_unknown') from None
            exists = False
        if not exists:
            try:
                with path.open('rb') as body:
                    self.client.put_object(Bucket=self.bucket, Key=key, Body=body, IfNoneMatch='*')
            except Exception:
                raise RuntimeError('private_recovery_blob_upload_outcome_uncertain') from None
        elif header.get('ContentLength') != size:
            raise ValueError('existing_recovery_blob_size_mismatch')
        data, _ = self.get(key, size)
        if len(data) != size or hashlib.sha256(data).hexdigest() != before or digest(path) != before:
            raise ValueError('recovery_artifact_changed_or_readback_mismatch')
        self.verified_blobs.add((key, size))
        return {'key': key, 'bytes': size, 'sha256': before}


def safe_log(source, destination, secrets):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or source.stat().st_size > MAX_LOG:
        raise ValueError('log_size_or_symlink_rejected')
    # The log writer may append; capture an explicitly bounded prefix, never claim EOF.
    size = source.stat().st_size
    with source.open('rb') as f:
        data = f.read(size)
    if len(data) != size:
        raise ValueError('log_truncated_during_snapshot')
    for secret in sorted((s.encode() for s in secrets if s), key=len, reverse=True):
        data = data.replace(secret, b'[REDACTED]')
    data = re.sub(rb'(?i)(?:authorization\s*:\s*[^\r\n]+|(?:GH_TOKEN|R2_SECRET_ACCESS_KEY|R2_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*[^\r\n]+)', b'[REDACTED_CREDENTIAL_LINE]', data)
    data = re.sub(rb'https?://[^\s]+\?[^\s]+', b'[REDACTED_URL_QUERY]', data)
    with destination.open('xb') as f:
        f.write(data)
    return size


def validate_boundary(job):
    source = Path(job) / 'source'
    receipts = [json.loads(p.read_text()) for p in source.glob('**/fit_receipt.json')]
    ledger_path = source / 'budget_ledger.json'
    if not ledger_path.exists():
        if receipts:
            raise ValueError('fit_receipts_without_ledger')
        return
    ledger = json.loads(ledger_path.read_text())
    if ledger['actual_neural_fits_started'] != len(receipts) or ledger['actual_neural_fits_completed'] != sum(r.get('status') == 'completed' for r in receipts):
        raise ValueError('snapshot_ledger_fit_counts_inconsistent')
    active = [p for p in source.glob('**/fit_receipt.json') if json.loads(p.read_text()).get('status') == 'started']
    if len(active) > 1:
        raise ValueError('multiple_active_fits')
    if active:
        import torch
        state = torch.load(active[0].parent / 'resume_state.pt', map_location='cpu', weights_only=True)
        if state['global_updates'] != ledger['optimizer_updates']:
            raise ValueError('snapshot_ledger_update_inconsistent')
        receipt = json.loads(active[0].read_text())
        if any(state['fit_identity'].get(k) != receipt.get(k) for k in ('architecture', 'seed', 'epochs', 'cell_kind')) or state['config_sha256'] != receipt['configuration_sha256']:
            raise ValueError('snapshot_active_identity_inconsistent')
        if not {'model_state', 'optimizer_state', 'rng', 'batch_offset', 'epoch', 'order'}.issubset(state):
            raise ValueError('snapshot_resume_state_incomplete')


class Recovery:
    def __init__(self, job, client, bucket, *, work_root=None, secrets=(), reserve=RESERVE):
        self.job = Path(job)
        self.root = Path(work_root) if work_root else None
        self.store = Store(client, bucket)
        self.prefix = 'redesign-private-recovery/' + relative(self.job.name)
        self.key = self.prefix + '/HEAD.json'
        self.secrets, self.reserve = secrets, reserve
        self.current, self.etag = self.store.head(self.key)
        if self.current is not None:
            head, manifest = read_committed(self.store, self.prefix, self.job.name)
            for name, row in manifest['files'].items():
                if name.startswith('logs/'):
                    continue
                p = self.local(name)
                if not p.is_file() or digest(p) != row['sha256']:
                    raise ValueError('local_recovery_state_differs_from_remote')
            self.current = encoded(head)
        elif any(self.job.glob('source/**/fit_receipt.json')):
            raise ValueError('existing_fits_without_private_recovery_head_require_review')

    def local(self, name):
        if name.startswith('work_root/'):
            if self.root is None:
                raise ValueError('work_root_required')
            return regular_path(self.root, name.split('/', 1)[1])
        return regular_path(self.job, name)

    def pointer(self, state):
        body = encoded(state)
        self.etag = self.store.put(self.key, body, etag=self.etag, new=self.current is None)
        self.current = body

    def begin(self, operation, counter):
        if self.current is None or json.loads(self.current)['state'] != 'COMMITTED':
            raise ValueError('verified_snapshot_required_before_operation')
        previous = json.loads(self.current)
        self.pointer({'state': 'PENDING', 'job_id': self.job.name, 'operation': operation,
                      'counter': counter, 'previous_manifest': previous['manifest'],
                      'reason': 'uncertain_update_must_not_be_repeated'})

    def snapshot(self, phase):
        """Call only from the training writer at a committed batch/fit boundary."""
        if shutil.disk_usage(self.job).free < self.reserve + MAX_LOG:
            raise ValueError('private_snapshot_disk_reserve_required')
        validate_boundary(self.job)
        files = {}
        for name in STATIC:
            p = self.local(name)
            if not p.is_file():
                raise ValueError('snapshot_required_record_missing:' + name)
            files[name] = p
        # Retain old snapshots as reviewable evidence; new amended executions
        # bind these mandatory-at-training records when present, without silently
        # modifying or reclassifying historical recovery manifests.
        for name in ('numerical_execution_review.json', 'formal_source_acceptance.json'):
            p = self.local(name)
            if p.is_file():
                files[name] = p
        source = self.job / 'source'
        for p in source.rglob('*') if source.exists() else []:
            if p.is_symlink():
                raise ValueError('snapshot_symlink_rejected')
            if p.is_file():
                name = p.relative_to(self.job).as_posix()
                if not allowed(name):
                    raise ValueError('unexpected_source_snapshot_artifact')
                files[name] = regular_path(self.job, name)
        if self.root:
            for name in ('execution_registration.json', 'budget_origin.json'):
                p = self.local('work_root/' + name)
                if not p.is_file():
                    raise ValueError('work_root_recovery_record_missing')
                files['work_root/' + name] = p
        if sum(p.stat().st_size for p in files.values()) > MAX_SNAPSHOT:
            raise ValueError('snapshot_total_size_limit')
        # An unresolved intent is preserved but never advertised as resumable.
        if list(source.rglob('update_intent.json')):
            raise ValueError('unresolved_update_intent_blocks_snapshot_commit')
        temp = self.job / ('.redacted-log-' + uuid.uuid4().hex)
        log_size = None
        try:
            log = self.job / 'supervisor.log'
            if log.exists():
                log_size = safe_log(log, temp, self.secrets)
                files['logs/supervisor.redacted.log'] = temp
            rows = {}
            for name, path in sorted(files.items()):
                if path.suffix in ('.json', '.csv'):
                    data = path.read_bytes()
                    if any(secret.encode() in data for secret in self.secrets if secret):
                        raise ValueError('secret_in_recovery_artifact')
                rows[name] = self.store.blob(self.prefix, path)
            manifest = {'schema_version': 1, 'job_id': self.job.name, 'phase': phase,
                        'files': rows, 'log_source_prefix_bytes': log_size,
                        'raw_data_included': False, 'automatic_cross_machine_resume': False}
            body = encoded(manifest)
            key = self.prefix + '/manifests/' + uuid.uuid4().hex + '.json'
            self.store.put(key, body, new=True)
            self.pointer({'state': 'COMMITTED', 'job_id': self.job.name,
                          'manifest': key, 'manifest_sha256': hashlib.sha256(body).hexdigest()})
            return {'state': 'COMMITTED', 'manifest': key, 'files': len(rows), 'full_readback_verified': True}
        finally:
            temp.unlink(missing_ok=True)


def read_committed(store, prefix, job_id):
    raw, _ = store.get(prefix + '/HEAD.json', 1024**2)
    head = json.loads(raw)
    if head.get('state') != 'COMMITTED' or head.get('job_id') != job_id:
        raise ValueError('remote_pending_or_wrong_job_manual_review_required')
    key = head.get('manifest', '')
    if not key.startswith(prefix + '/manifests/') or relative(key) != key:
        raise ValueError('manifest_outside_job')
    data, _ = store.get(key, 8 * 1024**2)
    if hashlib.sha256(data).hexdigest() != head.get('manifest_sha256'):
        raise ValueError('recovery_manifest_hash_mismatch')
    manifest = json.loads(data)
    if manifest.get('schema_version') != 1 or manifest.get('job_id') != job_id or not manifest.get('files'):
        raise ValueError('recovery_manifest_schema')
    rows = manifest['files']
    if not set(STATIC).issubset(rows) or len(rows) > 10000:
        raise ValueError('recovery_manifest_incomplete')
    total = 0
    for name, row in rows.items():
        if (not allowed(name) or type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= MAX_FILE
                or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                or row.get('key') != prefix + '/blobs/' + row['sha256']):
            raise ValueError('recovery_manifest_unsafe_entry')
        total += row['bytes']
    if total > MAX_SNAPSHOT + MAX_LOG or any(n.endswith('update_intent.json') for n in rows):
        raise ValueError('unsafe_recovery_manifest')
    return head, manifest


def restore_verified(client, bucket, job_id, destination, *, reserve=RESERVE):
    """Extract to NEW review directory only. Never replace active job or registration."""
    prefix = 'redesign-private-recovery/' + relative(job_id)
    if '/' in job_id:
        raise ValueError('job_id_invalid')
    store = Store(client, bucket)
    head, manifest = read_committed(store, prefix, job_id)
    dest = Path(destination)
    regular_path(dest, 'probe')
    if dest.exists():
        raise ValueError('restore_requires_new_review_directory')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(dest.parent).free < sum(x['bytes'] for x in manifest['files'].values()) + reserve:
        raise ValueError('restore_disk_reserve_required')
    dest.mkdir()
    for name, row in manifest['files'].items():
        p = regular_path(dest, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        data, _ = store.get(row['key'], row['bytes'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('restore_blob_hash_mismatch')
        with p.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    after, _ = store.get(prefix + '/HEAD.json', 1024**2)
    if after != encoded(head):
        raise ValueError('remote_head_changed_during_restore')
    receipt = {'status': 'VERIFIED_REVIEW_COPY_NOT_RESUME_AUTHORIZATION', 'head': head,
               'files': manifest['files'], 'automatic_resume': False}
    (dest / 'RESTORE_VERIFIED.json').write_bytes(encoded(receipt))
    return receipt


def from_environment(job):
    client, bucket = environment_client()
    root = os.environ.get('MI_EEG_WORK_ROOT')
    if not root:
        raise ValueError('private_recovery_work_root_required')
    secrets = tuple(os.environ.get(k, '') for k in ('GH_TOKEN', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY'))
    return Recovery(job, client, bucket, work_root=root, secrets=secrets)


def backup_terminal_log(job, client, bucket, secrets=()):
    """Independent immutable log receipt; never clear a PENDING training HEAD."""
    job = Path(job)
    temp = job / ('.redacted-terminal-' + uuid.uuid4().hex)
    try:
        captured = safe_log(job / 'supervisor.log', temp, secrets)
        store = Store(client, bucket)
        prefix = 'redesign-private-recovery/' + relative(job.name)
        blob = store.blob(prefix, temp)
        body = encoded({'schema_version': 1, 'job_id': job.name, 'log': blob,
                        'source_prefix_bytes': captured, 'resume_authorization': False})
        key = prefix + '/logs/' + uuid.uuid4().hex + '.json'
        store.put(key, body, new=True)
        return {'status': 'TERMINAL_LOG_PREFIX_VERIFIED', 'receipt_key': key,
                'sha256': hashlib.sha256(body).hexdigest(), 'source_prefix_bytes': captured}
    finally:
        temp.unlink(missing_ok=True)


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='operation', required=True)
    restore = sub.add_parser('restore-review-copy')
    restore.add_argument('--job-id', required=True)
    restore.add_argument('--destination', type=Path, required=True)
    logs = sub.add_parser('backup-stopped-worker-log')
    logs.add_argument('--job-dir', type=Path, required=True)
    a = p.parse_args()
    client, bucket = environment_client()
    if a.operation == 'restore-review-copy':
        result = restore_verified(client, bucket, a.job_id, a.destination)
        print(json.dumps({'status': result['status'], 'automatic_resume': False}))
    else:
        secrets = tuple(os.environ.get(k, '') for k in ('GH_TOKEN', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY'))
        print(json.dumps(backup_terminal_log(a.job_dir, client, bucket, secrets)))


if __name__ == '__main__':
    main()
