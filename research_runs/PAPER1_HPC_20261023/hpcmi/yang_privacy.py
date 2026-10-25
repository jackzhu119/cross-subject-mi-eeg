"""Explicit, versioned identities for the official privacy-corrected Yang copy.

Original vendor contracts and policy source stay untouched. This module never
changes file bytes or passes an old identity as if it belonged to a new file.
"""
from contextlib import contextmanager
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys

PROFILE = 'yang_nemar_privacy_v1'
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config'
VENDOR = ROOT / 'vendor/eligible_v3'
CONTRACT_SHA256 = '8cdf62ce36a0541b1e043e3b6c7bc973bb44669846a7f62c94c49fb4854e6a04'
ORIGINAL_CLOCK_SHA256 = 'aa0c90e91e6a1dd876673db7319a067646d8604536d879b58b09b739d344f89f'
ORIGINAL_ELIGIBILITY_SHA256 = '5291d362185a8db9bf45ddc95d9cb49d40de57893d2fd4da8681a802b5ab36f9'
INVENTORY_SHA256 = '7d9967fbab680128208c420ec85334ec06ea9f9903c4fb48da20f856b3fc9cba'
_HEX = re.compile(r'[0-9a-f]{64}')
_POLICY_SOURCE_SHA256 = {
    'eligibility_policy.py': 'b7ccb5499b56b46191b622ebec67ac8044e8f9801156e563ab53e4edbe2d9e5f',
    'yang_clock_registry.py': '634d86954e4e3f60e9af0bf0da340889b3d14b820a9245b4b82d86dd0abd2785',
    'yang_clock_policy.py': 'ce831956fb00d461f1a4026e358f82b016a5516aa9f9703a37315f1cab568ba0',
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _digest(value):
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def _json(path, expected):
    raw = Path(path).read_bytes()
    if not _digest(expected) or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Privacy route contract SHA256 differs: ' + Path(path).name)
    return json.loads(raw)


def is_active(raw_yang_root):
    path = Path(raw_yang_root) / '.source-profile.json'
    if not path.exists():
        return False
    if path.stat().st_size > 8192:
        raise ValueError('Privacy source marker is oversized')
    marker = json.loads(path.read_text())
    if not isinstance(marker, dict) or marker.get('profile') != PROFILE:
        raise ValueError('Unsupported explicit Yang source profile')
    if marker.get('contract_sha256', CONTRACT_SHA256) != CONTRACT_SHA256:
        raise ValueError('Yang source marker identifies a different contract')
    return True


def _isolated_vendor_module(filename, alias):
    expected = _POLICY_SOURCE_SHA256[filename]
    path = VENDOR / filename
    if _sha(path) != expected:
        raise ValueError('Original policy source differs: ' + filename)
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validated_contracts():
    contract = _json(CONFIG / 'yang_nemar_privacy_v1.json', CONTRACT_SHA256)
    if (contract.get('profile') != PROFILE or contract.get('schema_version') != 1
            or contract.get('original_clock_registry_sha256') != ORIGINAL_CLOCK_SHA256
            or contract.get('original_eligibility_manifest_sha256') != ORIGINAL_ELIGIBILITY_SHA256
            or contract.get('allowed_changed_header_ranges_zero_based_half_open') != [[8, 88], [88, 168]]):
        raise ValueError('Privacy source ancestry or transformation scope differs')
    old_clock = _json(VENDOR / 'config/yang_clock_registry_v5.json', ORIGINAL_CLOCK_SHA256)
    old_events = _json(VENDOR / 'config/eligibility_manifest.json', ORIGINAL_ELIGIBILITY_SHA256)
    inventory = _json(VENDOR / 'evidence/yang_v5_selected_inventory.json', INVENTORY_SHA256)
    new_clock = _json(CONFIG / 'yang_clock_registry_nemar_privacy_v1.json', contract['clock_registry_sha256'])
    new_events = _json(CONFIG / 'eligibility_manifest_nemar_privacy_v1.json', contract['eligibility_manifest_sha256'])
    if ({k: new_clock.get(k) for k in old_clock if k != 'pairs'} !=
            {k: v for k, v in old_clock.items() if k != 'pairs'}):
        raise ValueError('Privacy clock provenance or scientific fields changed')
    if ({k: new_events.get(k) for k in old_events if k != 'sessions'} !=
            {k: v for k, v in old_events.items() if k != 'sessions'}):
        raise ValueError('Privacy eligibility scientific fields changed')
    rows = contract['files']
    by_path = {row['path']: row for row in rows}
    inv_rows = {row['path']: row for row in inventory['members']}
    if len(rows) != 312 or len(by_path) != 312 or set(by_path) != set(inv_rows):
        raise ValueError('Privacy source inventory differs from the original 312 paths')
    old_native = {row['path']: row for pair in old_clock['pairs'] for row in (pair['signal'], pair['event'])}
    for path, row in by_path.items():
        original = inv_rows[path]
        if (row['size'] != original['bytes'] or row.get('original_zip_crc32') != original['crc32']
                or not _digest(row['sha256'])):
            raise ValueError('Privacy source size or recorded ancestry differs')
        if path in old_native:
            before = old_native[path]
            if (row.get('original_sha256') != before['sha256'] or 'crc32' in row
                    or not _digest(row.get('header_sha256'))
                    or row.get('start_date_time') != before['start_date_time']):
                raise ValueError('Privacy native identity or clock ancestry differs')
        elif (row.get('original_sha256') is not None or row.get('crc32') != original['crc32']):
            raise ValueError('Original metadata CRC differs')
    if len(new_clock['pairs']) != len(old_clock['pairs']):
        raise ValueError('Privacy clock pair count changed')
    for old, new in zip(old_clock['pairs'], new_clock['pairs']):
        if {k: v for k, v in new.items() if k not in ('signal', 'event')} != {k: v for k, v in old.items() if k not in ('signal', 'event')}:
            raise ValueError('Privacy clock subject/session changed')
        for role in ('signal', 'event'):
            before, after = old[role], new[role]
            if {k: v for k, v in before.items() if k not in ('sha256', 'header_sha256')} != {k: v for k, v in after.items() if k not in ('sha256', 'header_sha256')}:
                raise ValueError('Privacy clock policy or non-identity fields changed')
            row = by_path[before['path']]
            if after['sha256'] != row['sha256'] or after['header_sha256'] != row['header_sha256']:
                raise ValueError('Privacy clock identities differ from the current contract')
    if len(old_events['sessions']) != len(new_events['sessions']):
        raise ValueError('Privacy eligibility session count changed')
    for old, new in zip(old_events['sessions'], new_events['sessions']):
        if {k: v for k, v in old.items() if k != 'sha256'} != {k: v for k, v in new.items() if k != 'sha256'}:
            raise ValueError('Privacy event sequence or eligibility policy changed')
        if new['sha256'] != by_path[old['path']]['sha256']:
            raise ValueError('Privacy event identity differs from current contract')
    registry_class = _isolated_vendor_module('yang_clock_registry.py', 'hpcmi._privacy_clock_registry').ClockRegistry
    registry = registry_class(CONFIG / 'yang_clock_registry_nemar_privacy_v1.json',
                              contract['clock_registry_sha256'], inventory)
    return contract, new_events, registry


def load_contract():
    return _validated_contracts()[0]


def pins(root=None):
    if root is not None and not is_active(root):
        raise ValueError('Explicit privacy source profile is not active')
    rows = copy.deepcopy(load_contract()['files'])
    for row in rows:
        row['url'] = row['provider_url']
    return rows


def current_identity():
    contract = load_contract()
    return {'profile': PROFILE, 'contract_sha256': CONTRACT_SHA256,
            'adapter_sha256': _sha(__file__),
            'clock_registry_sha256': contract['clock_registry_sha256'],
            'eligibility_manifest_sha256': contract['eligibility_manifest_sha256'],
            'upstream_clock_registry_sha256': ORIGINAL_CLOCK_SHA256,
            'upstream_eligibility_manifest_sha256': ORIGINAL_ELIGIBILITY_SHA256}


@contextmanager
def policy_context(p1_data_module):
    """Use actual new identities with unchanged, separately hashed policy code."""
    contract, new_events, registry = _validated_contracts()
    events = _isolated_vendor_module('eligibility_policy.py', 'hpcmi._privacy_eligibility_policy')
    events.MANIFEST_SHA256 = contract['eligibility_manifest_sha256']
    session_rows = {(row['subject'], row['session']): row for row in new_events['sessions']}
    events.sessions = lambda: session_rows
    # The original data module imports this named module during each Yang call.
    clock = importlib.import_module('yang_clock_policy')
    if _sha(clock.__file__) != _POLICY_SOURCE_SHA256['yang_clock_policy.py']:
        raise ValueError('Imported original clock policy source differs')
    original_clock = clock.validate_yang_clock
    originals = {name: getattr(p1_data_module, name) for name in ('population', 'qualified_events')}

    def validate_clock(*args, **kwargs):
        result = registry.validate(*args, **kwargs)
        result.update(input_profile=PROFILE, upstream_registry_sha256=ORIGINAL_CLOCK_SHA256)
        return result

    try:
        p1_data_module.population = events.population
        p1_data_module.qualified_events = events.qualified_events
        clock.validate_yang_clock = validate_clock
        yield current_identity()
    finally:
        for name, function in originals.items():
            setattr(p1_data_module, name, function)
        clock.validate_yang_clock = original_clock
