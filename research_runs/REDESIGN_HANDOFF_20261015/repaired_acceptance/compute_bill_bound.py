"""Decimal arithmetic for the 04:49–04:51 UTC account observation, not a budget gate.

No network, provider, Pod, imports, package installation, EEG, or receipt writes.
Account aggregation is a conditional upper-bound proposal, not task attribution.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json

OLD_ORIGIN = '2026-10-14T07:07:45.290107+00:00'
CUTOFF = '2026-10-15T04:51:00+00:00'

def number(value):
    # Reject floats so binary rounding cannot silently enter the proposal.
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('exact_decimal_input_required')
    value = Decimal(value)
    if not value.is_finite() or value < 0:
        raise ValueError('nonnegative_finite_decimal_required')
    return value

def hours(start, end):
    start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if (start.tzinfo is None or end.tzinfo is None or
            start.utcoffset() != timezone.utc.utcoffset(start) or
            end.utcoffset() != timezone.utc.utcoffset(end) or end < start):
        raise ValueError('ordered_explicit_utc_required')
    delta = end - start
    micros = delta.days * 86400_000000 + delta.seconds * 1_000000 + delta.microseconds
    return Decimal(micros) / Decimal(3600_000000)

def conditional_bound(prior_day_total, missing_interval_hours, interval_rate_ceiling,
                      future_hours, future_rate_ceiling, uncertainty_allowance):
    values = tuple(number(v) for v in (prior_day_total, missing_interval_hours,
                   interval_rate_ceiling, future_hours, future_rate_ceiling,
                   uncertainty_allowance))
    prior, elapsed, rate, future, future_rate, uncertainty = values
    interval = elapsed * rate
    future_increment = future * future_rate
    before = prior + interval + uncertainty
    reserve = Decimal('2')
    total = before + future_increment + reserve
    return {
        'status': 'ARITHMETIC_ONLY_CONDITIONS_NOT_CERTIFIED',
        'prior_day_account_total_usd': str(prior),
        'missing_interval_hours': str(elapsed),
        'assumed_interval_rate_ceiling_usd_per_hour': str(rate),
        'conditional_missing_interval_usd': str(interval),
        'uncertainty_allowance_usd': str(uncertainty),
        'conditional_cost_bound_before_window_usd': str(before),
        'future_window_hours': str(future),
        'future_increment_usd': str(future_increment),
        'protected_reserve_usd': str(reserve),
        'conditional_total_with_window_and_reserve_usd': str(total),
        'arithmetic_within_10_usd': total <= Decimal('10'),
        'actual_paper1_spend_usd': None,
        'actual_cumulative_gpu_hours': None,
        'budget_gate_passed': False,
        'new_gpu_hours_approved': False,
        'training_authorization': False,
        'provider_balance_or_funding_verified': False,
    }

def proposal():
    elapsed = hours('2026-10-15T00:00:00+00:00', CUTOFF)
    common = ('4.268', elapsed)
    return {
        'schema_version': 1,
        'status': 'DRAFT_CONSERVATIVE_RECOVERY_ACCOUNTING_REQUIRES_REVIEW',
        'observation_cutoff_utc': CUTOFF,
        'observation_is_user_supplied_transcription_not_new_provider_query': True,
        'source': 'User-provided dot official RunPod read-only observation, 2026-10-15 04:49–04:51 UTC; no screenshot or provider export independently fetched in this task.',
        'account_observation': {
            'pod_id': '52ivinpjwv947i', 'pod_name': 'bright_ivory_bear',
            'gpu': 'RTX A4500 x1', 'uptime_display': '19h29m',
            'current_rate_usd_per_hour': '0.257',
            'gpu_rate_component_usd_per_hour': '0.25',
            'disk_rate_component_usd_per_hour': '0.007', 'disk_gb': 50,
            'balance_display_usd': '1.27', 'estimated_time_left_display': '5hours',
            'auto_pay_display': 'Disabled',
            'billing_visible_range_utc': ['2026-10-01', '2026-10-14'],
            'billing_lag_display_hours': 1,
            '2026_10_14_account_total_usd': '4.268',
            '2026_10_14_gpu_usd': '4.169', '2026_10_14_storage_usd': '0.099',
            '2026_10_14_gpu_type_breakdown_rounded_usd': {
                'RTX A4500': '3.802', 'RTX 2000 Ada': '0.366', 'RTX 4000 Ada': '0'},
            '2026_10_15_total_visible': False,
            'other_history_not_attributed_to_paper1_usd': {
                '2026-10-05': '2.824', '2026-10-02': '0.613'},
        },
        'original_controls_preserved': {
            'job_id': '20261014T071918Z-exploratory-89b0c07d',
            'old_budget_origin_utc': OLD_ORIGIN,
            'maximum_total_usd': '10', 'protected_reserve_usd': '2',
            'maximum_cumulative_gpu_hours': '8', 'maximum_neural_fits': 26,
            'maximum_optimizer_updates': 34440,
            'calendar_deadline_utc': '2026-10-16T09:54:00+00:00',
            'actual_cost_usd': None, 'remaining_budget_usd': None,
            'actual_cumulative_allocated_gpu_hours': None,
            'actual_fit_gpu_hours': None, 'latest_checkpoint': None,
            'counters_reset': False, 'authorization_reset_or_expanded': False,
        },
        'minimal_proposed_recovery_window_not_approved': {
            'scope': 'One CPU-only import/source acceptance attempt on the already allocated Pod; no fit, GPU computation, purchase, or target EEG.',
            'maximum_wall_minutes': 30,
            'maximum_increment_if_all_inclusive_rate_ceiling_0_257_verified_usd': '0.1285',
            'requires_new_author_approved_explicit_allocation_hour_exception_or_amendment': True,
            'requires_complete_dollar_upper_bound_and_parent_review': True,
            'requires_new_dot_slot_and_actual_resource_preflight': True,
            'does_not_satisfy_old_8_hour_gate': True,
            'author_approval_record_present': False,
            'production_gate_bypass_authorized': False,
            'required_parent_review_bindings': {
                'bounded_cpu_recovery_exception_authorized': False,
                'covered_dollar_upper_bound_reviewed': False,
                'cpu_recovery_grant_sha256': None,
                'cpu_recovery_window_start_utc': None,
                'cpu_recovery_window_end_utc': None,
                'both_operations_use_same_actual_grant_and_absolute_window': True,
            },
        },
        'calendar_hours_since_old_origin': str(hours(OLD_ORIGIN, CUTOFF)),
        'current_pod_uptime_display_hours': str(Decimal(19) + Decimal(29) / 60),
        'current_rate_conditional_scenario': conditional_bound(
            *common, '0.257', '0.5', '0.257', '0'),
        'old_max_rate_conditional_scenario': conditional_bound(
            *common, '0.75', '0.5', '0.257', '0'),
        'old_max_rate_shorter_window_conditional_scenario': {
            'status': 'ARITHMETIC_ONLY_CONDITIONS_NOT_CERTIFIED',
            'maximum_future_minutes': 10,
            'future_increment_usd_rounded_up_to_six_places': str(
                (Decimal('0.257') / 6).quantize(Decimal('0.000001'), rounding=ROUND_CEILING)),
            'conditional_total_with_window_and_reserve_usd_rounded_up': str(
                Decimal('7.9055') + Decimal('2') +
                (Decimal('0.257') / 6).quantize(Decimal('0.000001'), rounding=ROUND_CEILING)),
            'largest_zero_uncertainty_future_minutes_at_evidence_cutoff': str(
                (Decimal('10') - Decimal('2') - Decimal('7.9055')) / Decimal('0.257') * 60),
            'uncertainty_headroom_after_rounded_ten_minute_window_usd': '0.051666',
            'budget_gate_passed': False, 'training_authorization': False,
        },
        'displayed_balance_nominal_hours_at_current_rate': str(Decimal('1.27') / Decimal('0.257')),
        'rounding_late_ledger_uncovered_resource_allowance_known': False,
        'production_budget_validator_modified': False,
    }

if __name__ == '__main__':
    print(json.dumps(proposal(), indent=2, ensure_ascii=False))
