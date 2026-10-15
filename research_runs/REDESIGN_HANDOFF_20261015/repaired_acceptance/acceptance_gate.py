"""Read-only new-operation review/slot gate; no installation or fit authority.

The source_raw_restore operation is a new, explicit operational amendment.
It does not reinterpret any expired metadata/preparation/source slot.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

BASE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
REPAIR_ARCHIVE_SHA = '7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1'
REPAIR_RECEIPT_SHA = '0e487c7c8dcc83006681c8bdb066254da4184d49ab9f6ce96a07ad53d7cf092b'
REPAIR_ENDED = datetime(2026, 10, 15, 4, 26, 22, 935336, tzinfo=timezone.utc)
DEADLINE = datetime(2026, 10, 16, 9, 54, tzinfo=timezone.utc)
OPERATIONS = {'source_raw_restore': 1200, 'source_cpu_acceptance': 300}
GIB = 1024**3
TRUE_REVIEW = ('repair_evidence_independently_reviewed', 'paper2_absolute_priority',
    'paper2_noninterference_reviewed', 'preserved_old_failure_and_repair_identity',
    'unknown_accounting_retained', 'operation_scope_reviewed',
    'bounded_cpu_recovery_exception_authorized', 'covered_dollar_upper_bound_reviewed')
FALSE_REVIEW = ('training_authorization', 'fit_authorized', 'GPU_computation_authorized',
    'target_EEG_read_authorized', 'automatic_retry_authorized', 'pod_control_authorized',
    'numerical_thread_changes_authorized', 'budget_reset_authorized', 'budget_expansion_authorized')
TRUE_SLOT = ('paper2_absolute_priority', 'paper2_no_impact_checked_by_dot')
FALSE_SLOT = ('paper1_gpu_authorized', 'paper1_fit_authorized',
    'paper2_preemption_authorized', 'training_authorization',
    'numerical_thread_changes_authorized', 'budget_reset_authorized', 'pod_control_authorized')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('explicit_UTC_timestamp_required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError('explicit_UTC_timestamp_required')
    return result


def no_symlink(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('authorization_path_symlink_forbidden')
    return path


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate_authorization_JSON_key')
        result[k] = v
    return result


def read_record(path):
    path = no_symlink(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 16384:
            raise ValueError('bounded_regular_authorization_required')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            raw = f.read(16385)
        after = os.fstat(fd)
        if ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError('authorization_changed_while_reading')
        value = json.loads(raw, object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_authorization_JSON')))
        return value, hashlib.sha256(raw).hexdigest(), (info.st_dev, info.st_ino)
    finally:
        os.close(fd)


def validate(review, slot, operation, revision, script_sha, gate_sha, current):
    if operation not in OPERATIONS or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('fixed_delivery_and_exact_operation_required')
    bindings = {'schema_version': 1, 'status': 'DOT_PARENT_REPAIRED_SOURCE_OPERATION_APPROVED',
        'issuer': 'dot_parent', 'operation': operation, 'base_revision': BASE_REVISION,
        'delivery_revision': revision, 'operation_script_sha256': script_sha,
        'gate_sha256': gate_sha, 'repair_archive_sha256': REPAIR_ARCHIVE_SHA,
        'repair_receipt_sha256': REPAIR_RECEIPT_SHA}
    keys = set(bindings) | set(TRUE_REVIEW) | set(FALSE_REVIEW) | {
        'reviewed_at_utc', 'expires_at_utc', 'maximum_wall_seconds', 'review_notes',
        'cpu_recovery_grant_sha256', 'cpu_recovery_window_start_utc', 'cpu_recovery_window_end_utc',
        'source_restore_receipt_sha256'}
    if not isinstance(review, dict) or set(review) != keys:
        raise ValueError('exact_new_parent_review_schema_required')
    if type(review['schema_version']) is not int or any(review[k] != v for k, v in bindings.items()):
        raise ValueError('new_parent_review_binding_mismatch')
    if any(review[k] is not True for k in TRUE_REVIEW) or any(review[k] is not False for k in FALSE_REVIEW):
        raise ValueError('review_must_preserve_scientific_and_budget_gates')
    source_sha = review['source_restore_receipt_sha256']
    if ((operation == 'source_raw_restore' and source_sha is not None) or
            (operation == 'source_cpu_acceptance' and
             (not isinstance(source_sha, str) or not re.fullmatch('[0-9a-f]{64}', source_sha)))):
        raise ValueError('operation_specific_source_restore_receipt_binding_required')
    reviewed, review_end = map(timestamp, (review['reviewed_at_utc'], review['expires_at_utc']))
    window_start, window_end = map(timestamp, (review['cpu_recovery_window_start_utc'],
                                              review['cpu_recovery_window_end_utc']))
    if (not isinstance(review['cpu_recovery_grant_sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', review['cpu_recovery_grant_sha256'])
            or not window_start <= reviewed <= current < review_end <= window_end <= DEADLINE
            or not timedelta(0) < window_end - window_start <= timedelta(minutes=30)):
        raise ValueError('separately_authorized_at_most30minute_CPU_recovery_window_required')
    wall = review['maximum_wall_seconds']
    if (not REPAIR_ENDED < reviewed <= current < review_end <= DEADLINE
            or type(wall) is not int or not 1 <= wall <= OPERATIONS[operation]
            or not isinstance(review['review_notes'], str) or not review['review_notes'].strip()):
        raise ValueError('new_review_after_actual_repair_with_bounded_wall_required')
    slot_bindings = {'schema_version': 1, 'status': 'DOT_OPERATION_SLOT_GRANTED',
        'issuer': 'dot', 'pod_id': '52ivinpjwv947i', 'container_id': 'a7d3f0e408a4',
        'operation': operation}
    slot_keys = set(slot_bindings) | set(TRUE_SLOT) | set(FALSE_SLOT) | {
        'issued_at_utc', 'not_before_utc', 'expires_at_utc', 'max_new_bytes',
        'min_free_bytes', 'paper2_reserve_bytes', 'slot_rationale'}
    if not isinstance(slot, dict) or set(slot) != slot_keys:
        raise ValueError('exact_new_operation_slot_schema_required')
    if type(slot['schema_version']) is not int or any(slot[k] != v for k, v in slot_bindings.items()):
        raise ValueError('new_slot_operation_or_identity_mismatch')
    if any(slot[k] is not True for k in TRUE_SLOT) or any(slot[k] is not False for k in FALSE_SLOT):
        raise ValueError('new_slot_must_preserve_paper2_and_no_fit_authority')
    issued, start, end = map(timestamp, (slot['issued_at_utc'], slot['not_before_utc'], slot['expires_at_utc']))
    if not (reviewed <= issued <= start <= current < end <= review_end
            and end - issued <= timedelta(minutes=30)):
        raise ValueError('fresh_post_review_slot_active_within_30_minutes_required')
    for name, low, high in [('max_new_bytes', 1, 3*GIB), ('min_free_bytes', 10*GIB, 2**63-1),
                            ('paper2_reserve_bytes', 5*GIB, 2**63-1)]:
        if type(slot[name]) is not int or not low <= slot[name] <= high:
            raise ValueError('slot_total_cap_free_floor_and_actual_paper2_reserve_required')
    if not isinstance(slot['slot_rationale'], str) or not slot['slot_rationale'].strip():
        raise ValueError('actual_dot_slot_rationale_required')
    return wall, end


class Gate:
    def __init__(self, review_path, slot_path, operation, revision, code_sha256):
        self.review_path, self.slot_path = map(no_symlink, (review_path, slot_path))
        self.operation, self.revision, self.script_sha = operation, revision, code_sha256
        self.gate_sha = digest(__file__)
        self.review, self.review_sha256, self.review_identity = read_record(self.review_path)
        self.slot, self.slot_sha256, self.slot_identity = read_record(self.slot_path)
        self.max_wall_seconds, self.end = validate(self.review, self.slot, operation,
            revision, code_sha256, self.gate_sha, datetime.now(timezone.utc))
        self.reserve_bytes = self.slot['paper2_reserve_bytes']
        self.max_new_bytes = self.slot['max_new_bytes']
        self.min_free_bytes = self.slot['min_free_bytes']
        self.started = time.monotonic()

    def remaining_seconds(self):
        return min((self.end - datetime.now(timezone.utc)).total_seconds(),
            self.max_wall_seconds - (time.monotonic() - self.started))

    def check(self):
        for path, digest_value, identity in [(self.review_path, self.review_sha256, self.review_identity),
                                           (self.slot_path, self.slot_sha256, self.slot_identity)]:
            _, current_sha, current_identity = read_record(path)
            if current_sha != digest_value or current_identity != identity:
                raise ValueError('review_or_slot_revoked_replaced_or_changed')
        if digest(__file__) != self.gate_sha:
            raise ValueError('operation_gate_source_changed')
        validate(self.review, self.slot, self.operation, self.revision, self.script_sha,
            self.gate_sha, datetime.now(timezone.utc))
        if self.remaining_seconds() <= 0:
            raise TimeoutError('operation_wall_or_slot_expired')
