"""Bounded allocation remeasurement for one exact source-repair operation.

This measures allocated blocks only. It neither verifies EEG contents nor grants
an installation, transport, numerical-acceptance, or training authorization.
"""
from __future__ import annotations

import errno
from pathlib import Path
import re
import stat


SANCTIONED_FILENAMES = frozenset(
    f'A{subject:02d}{session}.mat' for subject in (7, 8, 9) for session in 'ET')


def owned_bytes(root, *, receipt_name, attempt, partial_rows, required_paths=(),
                on_event=None, max_scans=3):
    """Return a complete successful scan, retrying only exact publish races.

    Required paths are ordinary files under root and are checked before and
    after each complete scan. Missing directories, required files, ordinary
    MAT files, and arbitrary temporary files never receive the retry exception.
    A sanctioned vanished partial requires its exact final MAT to exist at the
    frozen byte size; full SHA verification remains the caller's separate gate.
    """
    root = Path(root).absolute()
    token = r'[A-Za-z0-9][A-Za-z0-9_.-]*'
    if (type(max_scans) is not int or not 1 <= max_scans <= 3
            or not isinstance(receipt_name, str) or not re.fullmatch(token, receipt_name)
            or not isinstance(attempt, str) or not re.fullmatch(token, attempt)
            or '..' in root.parts):
        raise ValueError('source_measurement_exact_bounded_operation_required')
    rows = list(partial_rows)
    if (len(rows) != 6 or any(not isinstance(row, dict) for row in rows)
            or {row.get('filename') for row in rows} != SANCTIONED_FILENAMES
            or any(type(row.get('bytes')) is not int or row['bytes'] <= 0 for row in rows)):
        raise ValueError('source_measurement_exact_six_partial_rows_required')
    partials = {Path('bnci') / ('.' + row['filename'] + '.' + attempt + '.partial'):
                (root / 'bnci' / row['filename'], row['bytes']) for row in rows}
    receipt_tmp = re.compile(re.escape(receipt_name) + r'\.tmp-[0-9a-f]{32}')
    required = []
    for value in required_paths:
        path = Path(value)
        if '..' in path.parts:
            raise ValueError('source_measurement_required_path_outside_root')
        path = path if path.is_absolute() else root / path
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise ValueError('source_measurement_required_path_outside_root') from None
        if relative == Path('.'):
            raise ValueError('source_measurement_required_regular_file_required')
        required.append(path)

    def relative_name(path):
        try:
            name = str(path.relative_to(root))
        except ValueError:
            return '<outside-root>'
        if len(name) > 256 or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', name):
            return '<noncanonical-member>'
        return name

    def emit(path, stage, scan, action, error=None):
        diagnostic = {'relative_filename': relative_name(path),
            'errno': errno.ENOENT if error is None else error.errno,
            'stage': stage, 'code_location': 'source_owned_measurement.py:owned_bytes'}
        if error is not None:
            error.controlled_diagnostic = diagnostic
        if on_event is not None:
            on_event(dict(diagnostic, phase='source_owned_measurement_missing_member',
                scan_index=scan, retry_index=scan - 1, action=action))

    def checked_info(path, *, stage, scan, directory=False):
        try:
            info = path.lstat()
        except FileNotFoundError as error:
            if error.errno != errno.ENOENT:
                raise
            emit(path, stage, scan, 'stop_required_or_paired_member_missing', error)
            raise
        good = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not good:
            raise ValueError('source_measurement_symlink_or_special_member_forbidden')
        return info

    def anchors(scan, stage):
        # Check ancestor directories without following links, including root.
        for path in reversed((root, *root.parents)):
            checked_info(path, stage=stage, scan=scan, directory=True)
        checked_info(root / 'bnci', stage=stage, scan=scan, directory=True)
        for path in required:
            # Required-path ancestors must not become a symlink to a file tree.
            for parent in reversed(path.parents):
                if parent == root or root in parent.parents:
                    checked_info(parent, stage=stage, scan=scan, directory=True)
            checked_info(path, stage=stage, scan=scan)

    for scan in range(1, max_scans + 1):
        anchors(scan, 'required_paths_before_scan')
        total, retry = 0, False
        for item in (root, *root.rglob('*')):
            try:
                info = item.lstat()
            except FileNotFoundError as error:
                if error.errno != errno.ENOENT:
                    raise
                relative = item.relative_to(root)
                if len(relative.parts) == 1 and receipt_tmp.fullmatch(relative.name):
                    checked_info(root / receipt_name, stage='paired_receipt_after_tmp_disappeared', scan=scan)
                elif relative in partials:
                    final, size = partials[relative]
                    if checked_info(final, stage='paired_final_after_partial_disappeared', scan=scan).st_size != size:
                        raise ValueError('source_measurement_paired_final_frozen_size_required')
                else:
                    emit(item, 'enumerated_member_lstat', scan, 'stop_unsanctioned_missing_member', error)
                    raise
                if scan == max_scans:
                    limited = FileNotFoundError(errno.ENOENT,
                        'source_measurement_transient_retry_limit', relative_name(item))
                    emit(item, 'enumerated_member_lstat', scan, 'stop_bounded_remeasurement_exhausted', limited)
                    raise limited from None
                emit(item, 'enumerated_member_lstat', scan, 'remeasure_complete_tree')
                retry = True
                break
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('source_measurement_symlink_or_special_member_forbidden')
            total += info.st_blocks * 512
        if retry:
            continue
        anchors(scan, 'required_paths_after_scan')
        return total
    raise AssertionError('source_measurement_no_successful_scan')
