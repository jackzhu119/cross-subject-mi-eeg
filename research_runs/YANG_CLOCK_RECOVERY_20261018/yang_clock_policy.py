"""Production entry point: all 153 pairs require reviewed full-file identities."""
from functools import lru_cache
from pathlib import Path
import json
import hashlib
from yang_clock_registry import ClockRegistry

REGISTRY_SHA256 = 'aa0c90e91e6a1dd876673db7319a067646d8604536d879b58b09b739d344f89f'

@lru_cache(maxsize=1)
def registry():
    root = Path(__file__).resolve().parent
    inventory = root / 'evidence/yang_v5_selected_inventory.json'
    if not inventory.exists():
        inventory = root.parent / 'SOURCE_EXPANSION_20261017/evidence/yang_v5_selected_inventory.json'
    raw = inventory.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '7d9967fbab680128208c420ec85334ec06ea9f9903c4fb48da20f856b3fc9cba':
        raise ValueError('frozen ZIP member inventory changed')
    evidence = root / 'config/yang_clock_registry_v5.json'
    if not evidence.exists():
        evidence = root / 'yang_clock_registry_v5.json'
    return ClockRegistry(evidence, REGISTRY_SHA256, json.loads(raw))


def validate_yang_clock(subject, session, signal_clock, event_clock,
                        signal_record, event_record, signal_header_sha256, event_header_sha256):
    return registry().validate(subject, session, signal_clock, event_clock,
                               signal_record, event_record, signal_header_sha256, event_header_sha256)
