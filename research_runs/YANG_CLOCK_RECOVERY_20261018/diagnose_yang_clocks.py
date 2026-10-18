#!/usr/bin/env python3
"""Read only clock metadata; no EEG samples, credentials, or source mutations."""
import argparse
import hashlib
import json
from pathlib import Path


def header(path):
    with path.open('rb') as stream:
        fixed = stream.read(256)
        if len(fixed) != 256:
            raise ValueError('truncated fixed header')
        size = int(fixed[184:192])
        if not 256 <= size <= 1024 * 1024:
            raise ValueError('unexpected header length')
        signal = stream.read(size - 256)
    if len(signal) != size - 256:
        raise ValueError('truncated signal headers')
    return {'bytes': path.stat().st_size,
            'header_sha256': hashlib.sha256(fixed + signal).hexdigest(),
            'start_date_hex': fixed[168:176].hex(), 'start_time_hex': fixed[176:184].hex(),
            'start_date': fixed[168:176].decode('latin1'),
            'start_time': fixed[176:184].decode('latin1'),
            'reserved': fixed[192:236].decode('latin1').strip(),
            'records': fixed[236:244].decode('ascii').strip(),
            'record_duration': fixed[244:252].decode('ascii').strip()}


def diagnose(root):
    pairs = []
    for signal in sorted(root.rglob('data.bdf')):
        event = signal.with_name('evt.bdf')
        if not event.is_file():
            continue
        a, b = header(signal), header(event)
        pairs.append({'directory': str(signal.parent.relative_to(root)),
                      'signal': a, 'event': b,
                      'clock_bytes_equal': (a['start_date_hex'], a['start_time_hex']) ==
                                           (b['start_date_hex'], b['start_time_hex'])})
    return {'scope': 'headers_only_no_content_hash_or_alignment_claim', 'pairs': pairs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('yang_root', type=Path)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.yang_root.resolve(strict=True)), indent=2))
