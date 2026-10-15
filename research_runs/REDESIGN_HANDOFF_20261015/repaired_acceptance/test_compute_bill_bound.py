import importlib.util
from pathlib import Path
from decimal import Decimal
import pytest

_spec = importlib.util.spec_from_file_location('paper1_bill_math', Path(__file__).with_name('compute_bill_bound.py'))
bill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bill)

def test_current_rate_conditional_arithmetic():
    r = bill.conditional_bound('4.268', '4.85', '0.257', '0.5', '0.257', '0')
    assert Decimal(r['conditional_missing_interval_usd']) == Decimal('1.24645')
    assert Decimal(r['conditional_cost_bound_before_window_usd']) == Decimal('5.51445')
    assert Decimal(r['future_increment_usd']) == Decimal('0.1285')
    assert Decimal(r['conditional_total_with_window_and_reserve_usd']) == Decimal('7.64295')
    assert r['arithmetic_within_10_usd'] is True
    assert r['budget_gate_passed'] is False
    assert r['training_authorization'] is False
    assert r['actual_paper1_spend_usd'] is None

def test_old_rate_ceiling_does_not_finance_half_hour_and_reserve():
    r = bill.conditional_bound('4.268', '4.85', '0.75', '0.5', '0.257', '0')
    assert Decimal(r['conditional_missing_interval_usd']) == Decimal('3.6375')
    assert Decimal(r['conditional_cost_bound_before_window_usd']) == Decimal('7.9055')
    assert Decimal(r['conditional_total_with_window_and_reserve_usd']) == Decimal('10.0340')
    assert r['arithmetic_within_10_usd'] is False

def test_ten_minute_alternative_rounds_cost_up_not_down():
    r = bill.proposal()['old_max_rate_shorter_window_conditional_scenario']
    assert r['future_increment_usd_rounded_up_to_six_places'] == '0.042834'
    assert r['conditional_total_with_window_and_reserve_usd_rounded_up'] == '9.948334'
    assert Decimal(r['largest_zero_uncertainty_future_minutes_at_evidence_cutoff']) < Decimal('22.063')
    assert r['budget_gate_passed'] is False

def test_uncertainty_is_additive_not_implicitly_zero_actual_cost():
    r = bill.conditional_bound('4.268', '4.85', '0.257', '0.5', '0.257', '2.36')
    assert Decimal(r['conditional_total_with_window_and_reserve_usd']) == Decimal('10.00295')
    assert r['arithmetic_within_10_usd'] is False
    assert r['actual_paper1_spend_usd'] is None
    assert r['actual_cumulative_gpu_hours'] is None

@pytest.mark.parametrize('invalid', [0.257, True, '-1', 'NaN', 'Infinity'])
def test_rejects_imprecise_or_invalid_money(invalid):
    with pytest.raises(ValueError):
        bill.number(invalid)

def test_utc_calendar_upper_bound_is_not_asserted_as_gpu_accounting():
    p = bill.proposal()
    assert Decimal(p['calendar_hours_since_old_origin']) > 21
    assert Decimal(p['current_pod_uptime_display_hours']) > 8
    assert p['current_rate_conditional_scenario']['actual_cumulative_gpu_hours'] is None
    assert p['production_budget_validator_modified'] is False

@pytest.mark.parametrize('start,end', [
    ('2026-10-15T00:00:00', bill.CUTOFF),
    ('2026-10-15T00:00:00-07:00', bill.CUTOFF),
    (bill.CUTOFF, '2026-10-15T00:00:00+00:00'),
])
def test_invalid_time_does_not_create_bound(start, end):
    with pytest.raises(ValueError):
        bill.hours(start, end)
