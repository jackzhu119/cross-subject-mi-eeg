import importlib.util
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('mu_probe', HERE / 'probe_mu_three_trials.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'))
import core_source_inputs as c


def test_trace_matches_production_synthetic():
    import json
    config = json.loads((ROOT / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    signal = ((np.arange(19*2000).reshape(19, 2000)*37)%257-128).astype(np.float64)
    for order in ['C', 'F']:
        stages, outputs, crops = probe.trace(np.array(signal, order=order), 500, config, c)
        assert outputs['mu'].shape == (19, 320)
        assert stages['mu']['final_float32'] == c.array_hash(outputs['mu'])
        assert crops['mu'].dtype == np.float64


def test_adjacent_candidate_exact_reference_without_mutating():
    for value, direction in [(1.0, np.inf), (-1.0, -np.inf)]:
        output = np.full((19, 320), np.float32(2.0))
        output[0, 0] = np.float32(value)
        adjacent = np.nextafter(output[0,0], np.float32(direction))
        crop = output.astype(np.float64)
        crop[0,0] = (float(output[0,0])+float(adjacent))/2
        base = crop.astype(np.float32)
        other = base.copy()
        other[0,0] = adjacent if base[0,0] != adjacent else np.float32(value)
        before = crop.copy()
        result = probe.candidate_rounding(crop, c.array_hash(other), c.array_hash)
        assert len(result['exact_reference_matches']) == 1
        assert result['exact_reference_matches'][0]['changed_elements'] == 1
        assert np.array_equal(crop, before)


def test_no_candidate_match_is_inconclusive():
    crop = np.ones((19, 320), dtype=np.float64)
    altered = crop.astype(np.float32); altered[0,0] = 7
    result = probe.candidate_rounding(crop, c.array_hash(altered), c.array_hash)
    assert result['exact_reference_matches'] == []
    assert result['candidates_checked'] == 64


def test_already_matches_no_candidate_search():
    crop = np.ones((19, 320), dtype=np.float64)
    result = probe.candidate_rounding(crop, c.array_hash(crop.astype(np.float32)), c.array_hash)
    assert result['already_matches'] and result['candidates_checked'] == 0
