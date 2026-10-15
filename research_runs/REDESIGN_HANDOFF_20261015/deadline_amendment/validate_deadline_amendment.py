"""Read bounded, immutable deadline/old-budget JSON only; never execute a job.

No network, EEG, subprocess, Torch, package mutation or record writes. A valid
operational amendment is not a current machine budget or execution permission.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_JOB = '20261014T071918Z-exploratory-89b0c07d'
OLD_REVISION = '05e683e91e2bb39b977970d04402221761e575d2'
OLD_RECEIPT_SHA = 'fcb8de686bf53a419beccd00d833f0e253ff922824b3227683e9c1ae2c93e790'
RECORD_SHA = '9a9fbbb6b73bb021867f3410510fef92561592858b8d518cf7b992444c568e0f'
OLD_STARTED = '2026-10-14T07:07:45.290107+00:00'
OLD_DEADLINE = '2026-10-14T15:07:45.290107+00:00'
NEW_DEADLINE = '2026-10-16T09:54:00+00:00'
CAPS = {
    'maximum_total_usd': 10, 'non_gpu_reserved_usd': 2,
    'maximum_gpu_hours': 8, 'maximum_neural_fits': 26,
    'maximum_optimizer_updates': 34440,
    'maximum_gpu_hourly_rate_usd': 0.75,
    'target_fits_authorized': False, 'optional_grouping_authorized': False,
}
PENDING = [
    'actual_training_runtime_and_source_strict_hash_acceptance',
    'old_task_accounting_and_unchanged_fit_update_counters',
    'cumulative_spend_and_remaining_budget_evidence',
    'cumulative_gpu_hour_allowance_evidence',
    'current_machine_and_current_total_hourly_quote_review',
    'checkpoint_and_remote_backup_identity',
    'complete_frozen_dreyer_mapping_license_and_restore_gates',
    'reviewed_execution_transition_without_ledger_reset',
    'paper2_priority_and_operator_scheduling_release',
]


def require(condition, code):
    if not condition:
        raise ValueError(code)


def strict_equal(actual, expected):
    """JSON bools are not accepted as integer ceilings, or vice versa."""
    return type(actual) is type(expected) and actual == expected


def read_json(path, expected_sha, expected_bytes=None):
    path = Path(path).absolute()
    require(not any(x.is_symlink() for x in (path, *path.parents)), 'symlink_rejected')
    require(path.is_file() and path.stat().st_size <= 65536, 'bounded_regular_json_required')
    blob = path.read_bytes()
    require(len(blob) <= 65536 and (expected_bytes is None or len(blob) == expected_bytes),
            'metadata_size_mismatch')
    digest = hashlib.sha256(blob).hexdigest()
    require(digest == expected_sha, 'metadata_sha256_mismatch')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite_json_rejected')
    result = json.loads(blob, object_pairs_hook=unique, parse_constant=invalid)
    require(isinstance(result, dict), 'json_object_required')
    return result, digest


def validate_record(record, old):
    require(record.get('record_kind') == 'SOURCED_DEADLINE_ONLY_OPERATIONAL_AMENDMENT_NOT_EXECUTION_RECEIPT'
            and record.get('status') == 'DEADLINE_ONLY_AMENDMENT_RECORDED_EXECUTION_BLOCKED',
            'execution_receipt_not_allowed')
    require(record.get('old_job_id') == OLD_JOB and record.get('old_code_revision') == OLD_REVISION,
            'old_job_identity_mismatch')
    anchor = record.get('original_budget_authorization', {})
    require(anchor.get('sha256') == OLD_RECEIPT_SHA and anchor.get('bytes') == 890
            and anchor.get('authorized_at_utc') == OLD_STARTED
            and anchor.get('expires_at_utc') == OLD_DEADLINE
            and anchor.get('original_receipt_modified') is False, 'old_budget_anchor_changed')
    require(old.get('authorized_at_utc') == OLD_STARTED and old.get('expires_at_utc') == OLD_DEADLINE,
            'old_budget_origin_or_deadline_changed')
    require(record.get('amended_execution_deadline_utc') == NEW_DEADLINE, 'deadline_changed')
    caps = record.get('unchanged_ceiling_constraints', {})
    require(set(caps) == set(CAPS) and all(strict_equal(caps[k], v) for k, v in CAPS.items()),
            'unchanged_ceiling_changed')
    for key in set(CAPS) - {'maximum_gpu_hourly_rate_usd'}:
        require(strict_equal(old.get(key), CAPS[key]), 'old_budget_ceiling_changed')
    require(strict_equal(old.get('approved_hourly_rate_usd'), 0.34), 'historical_quote_changed')
    permissions = record.get('permissions', {})
    require(set(permissions) == {
        'training_authorization', 'new_budget_authorization', 'create_or_replace_budget_receipt',
        'automatic_resume', 'Pod_operations', 'package_installation', 'target_EEG_read',
        'credentials_or_security_changes'}, 'permissions_schema')
    require(all(value is False for value in permissions.values()), 'execution_permission_not_allowed')
    preservation = record.get('preservation_requirements', {})
    require(len(preservation) == 10 and all(value is True for value in preservation.values()),
            'preservation_requirement_changed')
    state = record.get('observed_accounting_state', {})
    require(set(state) == {'actual_spend_usd', 'remaining_budget_usd', 'actual_cumulative_gpu_hours',
            'current_machine_authorization', 'current_account_identity', 'restored_checkpoint_identity',
            'zero_new_fits_proves_zero_cost'}, 'accounting_schema')
    require(state['zero_new_fits_proves_zero_cost'] is False
            and all(value is None for key, value in state.items() if key != 'zero_new_fits_proves_zero_cost'),
            'accounting_not_independently_observed')
    require(record.get('pending_before_execution') == PENDING, 'pending_gates_changed')
    source = record.get('authorization_source', {})
    require(source.get('source_kind') == 'CURRENT_AUTHOR_MESSAGE_WITH_SUPPLIED_TRANSCRIPT'
            and source.get('independently_retrieved_conversation') is False, 'transcript_scope_changed')
    transcript = source.get('supplied_transcript', [])
    require(len(transcript) == 3 and transcript[0].get('at_utc') is None
            and transcript[1].get('text') == '继续任务，赶紧训练'
            and transcript[1].get('at_utc') == '2026-10-15T00:01:00+00:00'
            and transcript[1].get('timestamp_precision') == 'minute_as_supplied'
            and transcript[2].get('text') == '尽快开始论文2，在不影响论文2训练的前提下再并行论文1'
            and transcript[2].get('at_utc') == '2026-10-15T00:48:15+00:00',
            'supplied_transcript_changed')


def audit(record_path=HERE / 'deadline_only_amendment.json',
          old_budget_path=HERE / 'historical_budget_authorization_d612f0cc.json', at_utc=None):
    record, digest = read_json(record_path, RECORD_SHA)
    old, old_digest = read_json(old_budget_path, OLD_RECEIPT_SHA, 890)
    validate_record(record, old)
    current = datetime.now(timezone.utc) if at_utc is None else datetime.fromisoformat(at_utc)
    require(current.tzinfo is not None, 'aware_UTC_time_required')
    deadline = datetime.fromisoformat(NEW_DEADLINE)
    return {
        'status': 'SOURCED_DEADLINE_ONLY_RECORD_VALID_EXECUTION_STILL_BLOCKED',
        'old_job_id': OLD_JOB, 'record_sha256': digest,
        'original_budget_authorization_sha256': old_digest,
        'amended_execution_deadline_utc': NEW_DEADLINE,
        'deadline_not_yet_expired_at_validation': current < deadline,
        'validation_at_utc': current.astimezone(timezone.utc).isoformat(),
        'historical_receipt_source': 'PREVIOUS_PUBLIC_READBACK_BYTE_IDENTICAL_SNAPSHOT',
        'fresh_remote_readback_performed': False,
        'production_budget_gate_changed': False,
        'original_budget_or_registration_written': False,
        'actual_spend_usd': None, 'remaining_budget_usd': None,
        'current_machine_identity_verified': False,
        'new_budget_authorization': False, 'training_authorization': False,
        'pending_before_execution': PENDING,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=HERE / 'deadline_only_amendment.json')
    parser.add_argument('--old-budget', type=Path, default=HERE / 'historical_budget_authorization_d612f0cc.json')
    parser.add_argument('--at-utc', help='Optional aware timestamp for deterministic metadata verification')
    args = parser.parse_args()
    try:
        result = audit(args.record, args.old_budget, args.at_utc)
    except (ValueError, OSError, TypeError, KeyError):
        print(json.dumps({'status': 'DEADLINE_AMENDMENT_INVALID_EXECUTION_BLOCKED',
                          'training_authorization': False, 'new_budget_authorization': False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
