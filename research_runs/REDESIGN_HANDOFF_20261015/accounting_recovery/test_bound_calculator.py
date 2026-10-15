import copy
import importlib.util
import json
from pathlib import Path
import pytest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('paper1_review_bound', HERE / 'bound_calculator.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TEMPLATE = json.loads((HERE / 'bounded_recovery.PLAN_ONLY.json').read_text())


def example():
    value = copy.deepcopy(TEMPLATE)
    value.update({
        'review_cutoff_utc': '2026-10-15T03:30:00+00:00',
        'historical_attributed_cost_upper_usd': '1.20',
        'historical_attributed_gpu_hours_upper': '2',
        'source_fits_started': 0, 'source_fits_completed': 0, 'optimizer_updates': 0,
        'current_total_hourly_rate_upper_usd': '.34',
        'proposed_additional_gpu_hours': '.25',
        'proposed_extra_cost_upper_usd': '.01',
        'proposed_additional_source_fits': 0,
        'proposed_additional_optimizer_updates': 0,
        'authentic_evidence_index_path': '/synthetic/evidence-index.json',
        'authentic_evidence_index_sha256': 'a' * 64,
    })
    return value


def test_unknowns_preserved():
    result = mod.evaluate(TEMPLATE)
    assert result['status'] == 'ACCOUNTING_UNKNOWN_REVIEW_BLOCKED'
    assert 'historical_attributed_cost_upper_usd' in result['missing']
    assert not result['training_authorization']
    assert 'arithmetic' not in result


def test_decimal_calculation_never_authorizes():
    result = mod.evaluate(example())
    assert result['arithmetic']['total_usd_upper_including_unchanged_2_usd_reserve'] == '3.2950'
    assert result['arithmetic']['total_cumulative_gpu_hours_upper'] == '2.25'
    assert not result['training_authorization']
    assert not result['production_budget_gate_passed']
    assert not result['provider_evidence_authenticity_verified']


@pytest.mark.parametrize('key,value,violation', [
    ('historical_attributed_cost_upper_usd', '8', 'total_usd_including_full_unchanged_reserve_exceeds_10'),
    ('historical_attributed_gpu_hours_upper', '8', 'cumulative_gpu_hours_exceed_8'),
    ('source_fits_started', 27, 'source_fits_started_exceed_26'),
    ('optimizer_updates', 34441, 'optimizer_updates_exceed_34440'),
    ('source_fits_completed', 1, 'completed_fits_exceed_started'),
    ('current_total_hourly_rate_upper_usd', '.751', 'total_hourly_rate_not_in_0_to_0_75'),
    ('current_total_hourly_rate_upper_usd', '0', 'total_hourly_rate_not_in_0_to_0_75'),
    ('proposed_additional_gpu_hours', '0', 'positive_increment_required'),
    ('review_cutoff_utc', '2026-10-16T09:53:00+00:00', 'calendar_deadline_would_be_exceeded'),
])
def test_bounds(key, value, violation):
    data = example()
    data[key] = value
    result = mod.evaluate(data)
    assert violation in result['violations']
    assert not result['training_authorization']


@pytest.mark.parametrize('key,value', [
    ('training_authorization', True), ('production_budget_gate_passed', True),
    ('old_job_id', 'new-job'), ('old_code_revision', '0' * 40),
    ('original_authorized_at_utc', '2026-10-15T03:30:00+00:00'),
    ('deadline_utc', '2026-10-17T09:54:00+00:00'), ('schema_version', True),
])
def test_frozen_identity_and_non_authorization(key, value):
    data = example()
    data[key] = value
    with pytest.raises(ValueError, match='original_identity'):
        mod.evaluate(data)


@pytest.mark.parametrize('bad', [True, '-.1', 'NaN', 'Infinity', {}, [], '1e1000000', '1e-13'])
def test_invalid_nonnegative_cost(bad):
    data = example()
    data['historical_attributed_cost_upper_usd'] = bad
    with pytest.raises(ValueError, match='nonnegative_decimal'):
        mod.evaluate(data)


@pytest.mark.parametrize('bad', [True, -1, .1, '0'])
def test_invalid_counters(bad):
    data = example()
    data['optimizer_updates'] = bad
    with pytest.raises(ValueError, match='nonnegative_integer'):
        mod.evaluate(data)


def test_even_partial_supplied_bad_values_fail():
    data = copy.deepcopy(TEMPLATE)
    data['source_fits_started'] = True
    with pytest.raises(ValueError, match='nonnegative_integer'):
        mod.evaluate(data)


def test_schema_and_duplicate_json_keys():
    data = example()
    data['new_budget_usd'] = 10
    with pytest.raises(ValueError, match='exact_review_proposal_schema'):
        mod.evaluate(data)
    with pytest.raises(ValueError, match='duplicate_json_key'):
        mod.unique_object([('x', 1), ('x', 2)])


@pytest.mark.parametrize('bad', ['2026-10-15T03:30:00', 'invalid', 0])
def test_utc_required(bad):
    data = example()
    data['review_cutoff_utc'] = bad
    with pytest.raises(ValueError, match='timezone_aware'):
        mod.evaluate(data)


def test_cutoff_cannot_precede_origin():
    data = example()
    data['review_cutoff_utc'] = '2026-10-14T07:00:00+00:00'
    with pytest.raises(ValueError, match='cutoff_precedes'):
        mod.evaluate(data)


@pytest.mark.parametrize('bad', [1, True, 'z' * 64, 'a' * 63])
def test_digest_required(bad):
    data = example()
    data['authentic_evidence_index_sha256'] = bad
    with pytest.raises(ValueError, match='evidence_index_sha256'):
        mod.evaluate(data)


def test_a_tiny_excess_is_not_rounded_away():
    data = example()
    data['historical_attributed_cost_upper_usd'] = '7.914999999999'
    data['proposed_extra_cost_upper_usd'] = '.000000000002'
    result = mod.evaluate(data)
    assert 'total_usd_including_full_unchanged_reserve_exceeds_10' in result['violations']
