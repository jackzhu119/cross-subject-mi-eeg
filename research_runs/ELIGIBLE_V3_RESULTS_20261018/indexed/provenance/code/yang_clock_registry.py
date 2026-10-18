"""Fixed-version, full-pair identity validation for author's single-file TAL timing."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ARCHIVE_URL = 'https://ndownloader.figshare.com/files/51001884'
ARCHIVE_BYTES = 65630556299
CENTRAL_SHA256 = 'cecd7ea0895da6ef85f01405960f4844c42d788ad33186b1f3fca91744d6874a'
AUTHOR_READER_SHA256 = 'dd6acba71429ba029dd6d6fe29e9eaf1a9d51233fc484dbca87e63bd624dd18f'
PREFIX = 'WBCIC_SHU Motor Imagery dataset/sourcedata/2C dataset'


def clock(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}\.\d{2}\.\d{2}\d{2}\.\d{2}\.\d{2}', value):
        raise ValueError('invalid recording clock syntax')
    return datetime.strptime(value, '%d.%m.%y%H.%M.%S')


class ClockRegistry:
    def __init__(self, path, expected_sha256, inventory):
        raw = Path(path).read_bytes()
        if not re.fullmatch('[a-f0-9]{64}', expected_sha256) or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('clock registry SHA256 differs from reviewed evidence')
        registry = json.loads(raw)
        for key, expected in [('schema_version', 1), ('archive_url', ARCHIVE_URL),
                              ('archive_bytes', ARCHIVE_BYTES), ('central_directory_sha256', CENTRAL_SHA256),
                              ('author_reader_sha256', AUTHOR_READER_SHA256)]:
            if registry.get(key) != expected:
                raise ValueError('clock registry provenance mismatch: ' + key)
        self.sha256 = expected_sha256
        self.pairs = {}
        sizes = {r['path']: r['bytes'] for r in inventory['members']}
        if inventory.get('central_directory_sha256') != CENTRAL_SHA256:
            raise ValueError('frozen inventory provenance mismatch')
        identities = set()
        for pair in registry['pairs']:
            subject, session = pair['subject'], pair['session']
            if type(subject) is not int or type(session) is not int or not 1 <= subject <= 51 or not 1 <= session <= 3:
                raise ValueError('unexpected source person/session')
            key = (subject, session)
            if key in self.pairs:
                raise ValueError('duplicate source pair')
            for role, filename in [('signal', 'data.bdf'), ('event', 'evt.bdf')]:
                row = pair[role]
                expected_path = f'{PREFIX}/sub-{subject:03d}/ses-{session:02d}/eeg/{filename}'
                if row['path'] != expected_path or row['bytes'] != sizes.get(expected_path):
                    raise ValueError('pair path/length differs from fixed v5 inventory')
                if not isinstance(row['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
                    raise ValueError('complete file SHA256 required')
                if row['sha256'] in identities:
                    raise ValueError('duplicate raw file identity')
                identities.add(row['sha256'])
                if not re.fullmatch('[a-f0-9]{64}', row['header_sha256']):
                    raise ValueError('header SHA256 required separately from content SHA256')
                clock(row['start_date_time'])
            if clock(pair['signal']['start_date_time']).date() != clock(pair['event']['start_date_time']).date():
                raise ValueError('paired recording dates differ')
            self.pairs[key] = pair
        if set(self.pairs) != {(s, d) for s in range(1, 52) for d in range(1, 4)}:
            raise ValueError('complete 153-session registry required')

    def validate(self, subject, session, signal_clock, event_clock, signal_record, event_record, signal_header_sha256, event_header_sha256):
        pair = self.pairs.get((subject, session))
        if pair is None:
            raise ValueError('unknown Yang source pair')
        for role, current_clock, record, header_sha in [('signal', signal_clock, signal_record, signal_header_sha256), ('event', event_clock, event_record, event_header_sha256)]:
            expected = pair[role]
            actual = {'path': record['path'], 'bytes': record['size'],
                      'sha256': record['sha256'], 'start_date_time': current_clock, 'header_sha256': header_sha}
            if any(actual[k] != expected[k] for k in actual):
                raise ValueError('Yang file identity/clock differs from reviewed fixed-v5 pair: ' + role)
        difference = (clock(signal_clock) - clock(event_clock)).total_seconds()
        return {'policy': 'author_neuracle_single_data_file_TAL_offsets',
                'registry_sha256': self.sha256, 'subject': subject, 'session': session,
                'signal': pair['signal'], 'event': pair['event'],
                'author_reader_sha256': AUTHOR_READER_SHA256,
                'header_clock_difference_seconds_signal_minus_event': difference,
                'event_shift_seconds': 0.0,
                'limitation': 'author_import_convention_not_independent_acquisition_synchronization'}
