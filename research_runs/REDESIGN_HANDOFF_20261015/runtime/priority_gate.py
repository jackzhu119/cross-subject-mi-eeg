"""Read-only, expiring dot operation-slot guard; never grants scientific authority.

A fresh receipt is issued by dot only after checking paper2 has priority. This
module does not observe the Pod, verify paper2 results, renew accounting, write a
receipt, or authorize a paper1 fit. Separate operations require separate grants.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Mapping

POD_ID = '52ivinpjwv947i'
CONTAINER_ID = 'a7d3f0e408a4'
AUTHORIZATION_DEADLINE = datetime(2026, 10, 16, 9, 54, tzinfo=timezone.utc)
MAX_SLOT = timedelta(minutes=30)
MAX_NEW_BYTES = 3 * 1024**3
MIN_FREE_BYTES = 10 * 1024**3
MAX_RECEIPT_BYTES = 16384
OPERATIONS = frozenset(('metadata', 'runtime_preparation', 'source_cpu_acceptance'))
STATUS = 'DOT_OPERATION_SLOT_GRANTED'

_TRUE_FIELDS = ('paper2_absolute_priority', 'paper2_no_impact_checked_by_dot')
_FALSE_FIELDS = ('paper1_gpu_authorized', 'paper1_fit_authorized',
                 'paper2_preemption_authorized', 'training_authorization',
                 'numerical_thread_changes_authorized', 'budget_reset_authorized',
                 'pod_control_authorized')
_KEYS = frozenset(('schema_version', 'status', 'issuer', 'pod_id', 'container_id',
    'operation', 'issued_at_utc', 'not_before_utc', 'expires_at_utc',
    'max_new_bytes', 'min_free_bytes', 'paper2_reserve_bytes',
    'slot_rationale') + _TRUE_FIELDS + _FALSE_FIELDS)


def _clock(current=None):
    value = datetime.now(timezone.utc) if current is None else current
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('priority_clock_requires_aware_datetime')
    return value.astimezone(timezone.utc)


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('priority_timestamp_required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('priority_timestamp_invalid') from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError('priority_timestamp_must_be_explicit_utc')
    return result


def _operation(value):
    # CLI spelling retained for the existing isolated-runtime builder.
    return 'runtime_preparation' if value == 'prepare_runtime' else value


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('priority_duplicate_json_key')
        result[key] = value
    return result


def _read(path):
    path = Path(path).absolute()
    # Refuse symlink redirection of either the file or its containing path.
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('priority_receipt_symlink_forbidden')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError('priority_receipt_unavailable_or_revoked') from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECEIPT_BYTES:
            raise ValueError('priority_receipt_regular_bounded_file_required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_RECEIPT_BYTES + 1)
        after = os.fstat(fd)
        if len(raw) > MAX_RECEIPT_BYTES or (info.st_ino, info.st_dev, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns) != (after.st_ino, after.st_dev,
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('priority_receipt_changed_while_reading')
        return path, raw, (info.st_dev, info.st_ino)
    finally:
        os.close(fd)


def _validate(raw, operation, current):
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError('priority_nonfinite_json')))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('priority_receipt_invalid_json') from exc
    if not isinstance(data, dict) or set(data) != _KEYS:
        raise ValueError('priority_receipt_schema_keys_mismatch')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('priority_receipt_schema_version')
    if data['status'] != STATUS or data['issuer'] != 'dot':
        raise ValueError('priority_slot_not_granted_by_dot')
    if data['pod_id'] != POD_ID or data['container_id'] != CONTAINER_ID:
        raise ValueError('priority_pod_or_container_mismatch')
    if not isinstance(data['operation'], str) or data['operation'] not in OPERATIONS:
        raise ValueError('priority_exact_one_operation_required')
    if operation not in OPERATIONS or data['operation'] != operation:
        raise ValueError('priority_operation_mismatch')
    if any(data[key] is not True for key in _TRUE_FIELDS):
        raise ValueError('priority_paper2_priority_or_no_impact_not_confirmed')
    if any(data[key] is not False for key in _FALSE_FIELDS):
        raise ValueError('priority_forbidden_authority_or_numerical_change')
    issued, start, end = (_timestamp(data[key]) for key in
                        ('issued_at_utc', 'not_before_utc', 'expires_at_utc'))
    if not issued <= start < end or end - issued > MAX_SLOT:
        raise ValueError('priority_slot_must_be_bounded_to_30_minutes')
    if end > AUTHORIZATION_DEADLINE:
        raise ValueError('priority_slot_exceeds_existing_authorization_deadline')
    if not issued <= start <= current < end:
        raise ValueError('priority_slot_not_active_or_expired')
    if current - issued > MAX_SLOT:
        raise ValueError('priority_receipt_not_fresh')
    if any(type(data[key]) is not int for key in
           ('max_new_bytes', 'min_free_bytes', 'paper2_reserve_bytes')):
        raise ValueError('priority_disk_fields_require_integers_not_booleans')
    if not 0 <= data['max_new_bytes'] <= MAX_NEW_BYTES:
        raise ValueError('priority_new_storage_exceeds_3_gib_cap')
    if data['min_free_bytes'] < MIN_FREE_BYTES or data['paper2_reserve_bytes'] < 0:
        raise ValueError('priority_free_space_floor_or_paper2_reserve_invalid')
    if not isinstance(data['slot_rationale'], str) or not data['slot_rationale'].strip():
        raise ValueError('priority_dot_slot_rationale_required')
    return data


@dataclass(frozen=True)
class PriorityPermit:
    """Immutable receipt snapshot; re-read before each bounded own operation.

    Revocation, replacement (even identical bytes), byte drift or expiry fails
    closed. Callers still enforce storage thresholds and every scientific gate.
    """
    path: Path
    raw: bytes
    file_identity: tuple[int, int]
    operation: str
    receipt: Mapping

    @property
    def receipt_sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def max_new_bytes(self):
        return self.receipt['max_new_bytes']

    @property
    def min_free_bytes(self):
        return self.receipt['min_free_bytes']

    @property
    def paper2_reserve_bytes(self):
        return self.receipt['paper2_reserve_bytes']

    @property
    def required_free_bytes(self):
        return self.min_free_bytes + self.paper2_reserve_bytes

    def assert_active(self, current=None):
        path, raw, identity = _read(self.path)
        if path != self.path or raw != self.raw or identity != self.file_identity:
            raise ValueError('priority_receipt_revoked_replaced_or_changed')
        _validate(raw, self.operation, _clock(current))
        return self


def validate_receipt(path, expected_operation='prepare_runtime', current=None):
    """Read and validate a dot-issued slot; PLAN_ONLY templates always fail."""
    path, raw, identity = _read(path)
    operation = _operation(expected_operation)
    data = _validate(raw, operation, _clock(current))
    return PriorityPermit(path, raw, identity, operation, MappingProxyType(data))


validate_priority_receipt = validate_receipt
