"""Evidence-bound Yang single-file TAL policy; no automatic clock corrections."""

SIGNAL_SHA256 = '9c0559fc74a16249a15567046572e8de1d49f6a2ac423e45fbbc2c972e1c1361'
EVENT_SHA256 = 'bde96107208aec97eee0b2f5acb2e3f24114412f0c6fa54bfcc236e280a0184a'
AUTHOR_READER_SHA256 = 'dd6acba71429ba029dd6d6fe29e9eaf1a9d51233fc484dbca87e63bd624dd18f'


def validate_yang_clock(signal_clock, event_clock, signal_sha256, event_sha256):
    if signal_clock == event_clock:
        return {'policy': 'equal_header_clocks', 'event_shift_seconds': 0.0}
    expected = ('22.03.1915.03.13', '22.03.1915.03.12', SIGNAL_SHA256, EVENT_SHA256)
    if (signal_clock, event_clock, signal_sha256, event_sha256) != expected:
        raise ValueError('Yang signal/event recording clocks differ: unreviewed file pair; preserved and blocked')
    return {'policy': 'author_neuracle_single_data_file_TAL_offsets',
            'signal_clock': signal_clock, 'event_clock': event_clock,
            'signal_sha256': signal_sha256, 'event_sha256': event_sha256,
            'author_reader_sha256': AUTHOR_READER_SHA256,
            'header_clock_difference_seconds_signal_minus_event': 1,
            'event_shift_seconds': 0.0,
            'scope': 'exact_v5_sub001_ses02_pair_only',
            'limitation': 'author_import_convention_not_independent_acquisition_synchronization'}
