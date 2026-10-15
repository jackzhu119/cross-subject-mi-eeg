"""Review-only arithmetic; never a budget receipt or a production gate."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import re


IDENTITY = {
    'schema_version': 1,
    'record_kind': 'BOUNDED_RECOVERY_ARITHMETIC_PROPOSAL_NOT_AUTHORIZATION',
    'old_job_id': '20261014T071918Z-exploratory-89b0c07d',
    'old_code_revision': '05e683e91e2bb39b977970d04402221761e575d2',
    'original_authorized_at_utc': '2026-10-14T07:07:45.290107+00:00',
    'deadline_utc': '2026-10-16T09:54:00+00:00',
    'training_authorization': False,
    'production_budget_gate_passed': False,
}
DECIMALS = (
    'historical_attributed_cost_upper_usd',
    'historical_attributed_gpu_hours_upper',
    'current_total_hourly_rate_upper_usd',
    'proposed_additional_gpu_hours',
    'proposed_extra_cost_upper_usd',
)
COUNTS = (
    'source_fits_started', 'source_fits_completed', 'optimizer_updates',
    'proposed_additional_source_fits', 'proposed_additional_optimizer_updates',
)
OTHER = ('review_cutoff_utc', 'authentic_evidence_index_path',
         'authentic_evidence_index_sha256')


def decimal(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('nonnegative_decimal_required:' + name)
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('nonnegative_decimal_required:' + name) from exc
    if (not result.is_finite() or result < 0
            or result.as_tuple().exponent < -12 or result.adjusted() > 12):
        raise ValueError('nonnegative_decimal_required:' + name)
    return result


def utc(value, name):
    if not isinstance(value, str):
        raise ValueError('timezone_aware_timestamp_required:' + name)
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('timezone_aware_timestamp_required:' + name) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('timezone_aware_timestamp_required:' + name)
    return result.astimezone(timezone.utc)


def evaluate(proposal):
    if not isinstance(proposal, dict) or set(proposal) != set(IDENTITY) | set(DECIMALS + COUNTS + OTHER):
        raise ValueError('exact_review_proposal_schema_required')
    if any(type(proposal[k]) is not type(v) or proposal[k] != v for k, v in IDENTITY.items()):
        raise ValueError('original_identity_or_non_authorization_boundary_changed')
    report = {
        'status': 'ACCOUNTING_UNKNOWN_REVIEW_BLOCKED',
        'training_authorization': False,
        'production_budget_gate_passed': False,
        'provider_evidence_authenticity_verified': False,
        'checkpoint_or_backup_verified': False,
        'budget_or_counter_reset': False,
        'network_requests': 0,
        'files_written': False,
        'missing': [k for k in DECIMALS + COUNTS + OTHER if proposal[k] is None],
        'violations': [],
        'scope': 'Arithmetic at the supplied cutoff only; not current execution authority.',
    }
    # Validate supplied values even when another required value is missing.
    numbers = {k: decimal(proposal[k], k) for k in DECIMALS if proposal[k] is not None}
    for k in COUNTS:
        if proposal[k] is not None and (type(proposal[k]) is not int or proposal[k] < 0):
            raise ValueError('nonnegative_integer_required:' + k)
    if proposal['review_cutoff_utc'] is not None:
        cutoff = utc(proposal['review_cutoff_utc'], 'review_cutoff_utc')
        if cutoff < utc(IDENTITY['original_authorized_at_utc'], 'origin'):
            raise ValueError('cutoff_precedes_original_origin')
    if proposal['authentic_evidence_index_sha256'] is not None and (
            not isinstance(proposal['authentic_evidence_index_sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', proposal['authentic_evidence_index_sha256'])):
        raise ValueError('evidence_index_sha256_required')
    if proposal['authentic_evidence_index_path'] is not None and (
            not isinstance(proposal['authentic_evidence_index_path'], str)
            or not proposal['authentic_evidence_index_path'].strip()):
        raise ValueError('evidence_index_path_required')
    if report['missing']:
        return report
    past = numbers['historical_attributed_cost_upper_usd']
    hours = numbers['historical_attributed_gpu_hours_upper']
    rate = numbers['current_total_hourly_rate_upper_usd']
    increment = numbers['proposed_additional_gpu_hours']
    extra = numbers['proposed_extra_cost_upper_usd']
    # Inputs allow at most 12 fractional places and 13 integer places. Eighty
    # digits keeps products and sums exact rather than rounding down a ceiling.
    with localcontext() as context:
        context.prec = 80
        total = past + rate * increment + extra + Decimal('2')
        total_hours = hours + increment
    total_fits = proposal['source_fits_started'] + proposal['proposed_additional_source_fits']
    total_updates = proposal['optimizer_updates'] + proposal['proposed_additional_optimizer_updates']
    deadline = utc(IDENTITY['deadline_utc'], 'deadline')
    remaining_seconds = Decimal(str((deadline - cutoff).total_seconds()))
    with localcontext() as context:
        context.prec = 80
        interval_seconds = increment * 3600
    checks = {
        'total_usd_including_full_unchanged_reserve_exceeds_10': total > 10,
        'cumulative_gpu_hours_exceed_8': total_hours > 8,
        'source_fits_started_exceed_26': total_fits > 26,
        'optimizer_updates_exceed_34440': total_updates > 34440,
        'completed_fits_exceed_started': proposal['source_fits_completed'] > proposal['source_fits_started'],
        'total_hourly_rate_not_in_0_to_0_75': not 0 < rate <= Decimal('.75'),
        'positive_increment_required': increment <= 0,
        'calendar_deadline_would_be_exceeded': interval_seconds > remaining_seconds,
    }
    report['violations'] = [key for key, bad in checks.items() if bad]
    report['arithmetic'] = {
        'total_usd_upper_including_unchanged_2_usd_reserve': str(total),
        'total_cumulative_gpu_hours_upper': str(total_hours),
        'total_source_fits_started': total_fits,
        'total_optimizer_updates': total_updates,
        'calendar_seconds_available_at_supplied_cutoff': str(remaining_seconds),
    }
    report['status'] = ('ARITHMETIC_BOUND_EXCEEDED_EXECUTION_BLOCKED' if report['violations']
                        else 'ARITHMETIC_ONLY_FEASIBLE_ALL_EVIDENCE_AND_EXECUTION_GATES_PENDING')
    return report


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key:' + key)
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', required=True)
    args = parser.parse_args()
    path = Path(args.proposal)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('small_regular_proposal_required')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object,
                       parse_float=Decimal)
    result = evaluate(value)
    print(json.dumps(result, sort_keys=True, indent=2))
    # No output from this calculator is executable authority, including feasibility.
    raise SystemExit(3)


if __name__ == '__main__':
    main()
