"""Native privacy-source transport only; synthetic bytes, no network or EEG."""
from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import tempfile
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock
import urllib.error
import zlib

from hpcmi import acquire as a
from hpcmi import yang_nemar_download as n

PRIVATE = 'PRIVATE-SIGNED-QUERY-NOT-FOR-LOGS'


class Response(io.BytesIO):
    def __init__(self, body, url, status=200, headers=None):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}

    def geturl(self):
        return self.url


class NativeDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()

    def pin(self, body=b'abcdefghij', metadata=False):
        relative = 'CHANGES' if metadata else 'sourcedata/2C dataset/sub-001/ses-01/eeg/evt.bdf'
        row = {'path': n.PREFIX + relative, 'size': len(body),
               'sha256': hashlib.sha256(body).hexdigest(),
               'original_sha256': None if metadata else hashlib.sha256(b'old-identity').hexdigest()}
        if metadata:
            row['crc32'] = '%08x' % (zlib.crc32(body) & 0xffffffff)
            remote = 'sourcedata/' + relative
        else:
            row['original_zip_crc32'] = 'deadbeef'
            remote = relative
        from urllib.parse import quote
        row['url'] = n.SOURCE + quote(remote, safe='/')
        return row

    def location(self, row):
        return ('https://' + n.STORAGE + '/nm000348/objects/SHA256E-s%d--%s.bdf?signature=' %
                (row['size'], row['sha256'])) + PRIVATE

    def redirect(self, row, location=None):
        return urllib.error.HTTPError(row['url'], 302, PRIVATE,
                                      {'Location': self.location(row) if location is None else location}, None)

    def download(self, rows):
        with mock.patch.object(n, '_selected_rows', return_value=rows), redirect_stdout(self.output):
            return n.download(self.root)

    def test_exact_storage_redirect_retains_offset_and_completed_cache_skips_network_hash(self):
        body = b'abcdefghij'
        row = self.pin(body)
        target = a.safe_child(self.root, row['path'])
        target.parent.mkdir(parents=True)
        target.with_name(target.name+'.part').write_bytes(body[:4])
        url = self.location(row)
        response = Response(body[4:], url, 206, {'Content-Range': 'bytes 4-9/10'})
        with mock.patch.object(a, '_open_no_redirect', side_effect=[self.redirect(row), response]) as opener:
            self.assertEqual(self.download([row]), {row['path']: row['sha256']})
        self.assertEqual([c.args for c in opener.call_args_list], [(row['url'], 4), (url, 4)])
        self.assertEqual(target.read_bytes(), body)
        self.assertFalse(target.with_name(target.name+'.part').exists())
        with mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('network')), \
             mock.patch.object(a, 'sha256_file', side_effect=AssertionError('unnecessary rehash')):
            self.assertEqual(self.download([row]), {row['path']: row['sha256']})
        self.assertNotIn(PRIVATE, self.output.getvalue())

    def test_old_native_hash_is_not_accepted_or_overwritten(self):
        row = self.pin()
        target = a.safe_child(self.root, row['path'])
        target.parent.mkdir(parents=True)
        old = b'oldvalues!'
        self.assertEqual(len(old), row['size'])
        target.write_bytes(old)
        with mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('unexpected request')):
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                self.download([row])
        self.assertEqual(target.read_bytes(), old)

    def test_wrong_body_preserves_partial_and_never_claims_current_sha(self):
        row = self.pin()
        with mock.patch.object(a, '_open_no_redirect', return_value=Response(b'xxxxxxxxxx', row['url'])):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                self.download([row])
        target = a.safe_child(self.root, row['path'])
        self.assertFalse(target.exists())
        self.assertEqual(target.with_name(target.name+'.part').read_bytes(), b'xxxxxxxxxx')
        self.assertNotIn(PRIVATE, self.output.getvalue())

    def test_entry_or_storage_denial_is_not_retried_or_logged_with_private_url(self):
        row = self.pin()
        for storage in (False, True):
            with self.subTest(storage=storage):
                url = self.location(row) if storage else row['url']
                error = urllib.error.HTTPError(url, 403, PRIVATE, {}, None)
                events = [self.redirect(row), error] if storage else [error]
                with mock.patch.object(a, '_open_no_redirect', side_effect=events) as opener, \
                     mock.patch.object(a.time, 'sleep') as sleep:
                    with self.assertRaises(ValueError) as caught:
                        self.download([row])
                self.assertEqual(caught.exception.http_status, 403)
                self.assertEqual(opener.call_count, 2 if storage else 1)
                sleep.assert_not_called()
                self.assertNotIn(PRIVATE, self.output.getvalue())
                self.assertNotIn(PRIVATE, str(caught.exception))

    def test_storage_status_survives_redirect_context_for_pipeline_retry_classification(self):
        from hpcmi import login_pipeline
        row = self.pin()
        for status in (500, 503, 403):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(self.location(row), status, PRIVATE, {}, None)
                with mock.patch.object(a, '_open_no_redirect', side_effect=[self.redirect(row),error]):
                    with self.assertRaises(ValueError) as caught:
                        with n.official_object(row):
                            self.fail('HTTP failure yielded a native object')
                detail = a.safe_error_details(caught.exception)
                self.assertEqual(detail['http_status'], status)
                self.assertEqual(detail['category'], 'http')
                self.assertNotIn(302, [cause.get('http_status') for cause in detail['causes']])
                self.assertTrue(a._independent_network_failure(caught.exception, detail))
                self.assertEqual(login_pipeline._network_retryable({'attempt_id':'unit',**detail},'unit'), status in (500,503))
                self.assertNotIn(PRIVATE, str(detail))

    def test_unknown_host_path_or_second_redirect_never_followed(self):
        row = self.pin()
        known = self.location(row)
        for location in (known.replace(n.STORAGE, 'unknown.example'), known.replace('/nm000348/', '/nm000250/'),
                         known.replace('https:', 'http:'), known+'#fragment', known.replace('s10--', 's11--')):
            with self.subTest(location=location.split('?')[0]):
                with mock.patch.object(a, '_open_no_redirect', side_effect=self.redirect(row, location)) as opener:
                    with self.assertRaises(ValueError):
                        with n.official_object(row):
                            self.fail('Unverified storage object was yielded')
                self.assertEqual(opener.call_count, 1)
        extra = urllib.error.HTTPError(known, 302, PRIVATE, {'Location':'https://unknown.example/'+PRIVATE}, None)
        with mock.patch.object(a, '_open_no_redirect', side_effect=[self.redirect(row), extra]) as opener:
            with self.assertRaises(ValueError) as caught:
                with n.official_object(row):
                    self.fail('Additional redirect was followed')
        self.assertEqual(opener.call_count, 2)
        self.assertEqual(caught.exception.http_status, 302)
        self.assertNotIn(PRIVATE, str(caught.exception))

    def test_metadata_original_crc_is_checked_and_wrong_crc_retains_file(self):
        body = b'original metadata'
        row = self.pin(body, metadata=True)
        with mock.patch.object(a, '_open_no_redirect', return_value=Response(body, row['url'])):
            self.assertEqual(self.download([row]), {row['path']:row['sha256']})
        broken = {**row, 'crc32':'00000000'}
        with mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'original CRC differs'):
                self.download([broken])
        self.assertEqual(a.safe_child(self.root, row['path']).read_bytes(), body)

    def test_progress_counts_only_completed_current_files_and_keeps_prior_file_on_failure(self):
        first, second = self.pin(), self.pin(b'abcdefghiK')
        second = {**second, 'path':second['path'].replace('ses-01','ses-02'),
                  'url':second['url'].replace('ses-01','ses-02')}
        progress = []
        denial = urllib.error.HTTPError(second['url'],403,PRIVATE,{},None)
        with mock.patch.object(n, '_selected_rows', return_value=[first,second]), \
             mock.patch.object(a, '_open_no_redirect', side_effect=[Response(b'abcdefghij', first['url']),denial]), \
             redirect_stdout(self.output):
            with self.assertRaises(ValueError):
                n.download(self.root, lambda count,total:progress.append((count,total)))
        self.assertEqual(progress,[(0,2),(1,2)])
        self.assertTrue(a.safe_child(self.root,first['path']).is_file())
        self.assertFalse(a.safe_child(self.root,second['path']).exists())

    def test_source_url_and_original_bdf_crc_cannot_be_substituted(self):
        row = self.pin()
        for modified in ({**row,'url':row['url']+'?signature='+PRIVATE},
                         {**row,'url':row['url'].replace('/v1.0.5/','/latest/')},
                         {**row,'crc32':'deadbeef'}):
            with self.assertRaises(ValueError):
                n._source_url(modified)

    def test_inactive_profile_stops_before_any_network_or_local_publication(self):
        module = ModuleType('hpcmi.yang_privacy')
        module.is_active = mock.Mock(return_value=False)
        module.pins = mock.Mock(side_effect=AssertionError('Inactive profile loaded native pins'))
        with mock.patch.dict(sys.modules, {'hpcmi.yang_privacy':module}), \
             mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'explicit profile activation'):
                n.download(self.root)
        self.assertEqual(list(self.root.iterdir()), [])
        module.pins.assert_not_called()

    def test_remaining_native_space_guard_preserves_partial_before_network(self):
        row = self.pin()
        target = a.safe_child(self.root, row['path'])
        target.parent.mkdir(parents=True)
        partial = target.with_name(target.name + '.part')
        partial.write_bytes(b'abcd')
        required = row['size'] - 4 + 4 * 1024 ** 3
        with mock.patch.object(a.shutil, 'disk_usage', return_value=SimpleNamespace(free=required-1)), \
             mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('space checked before network')):
            with self.assertRaisesRegex(ValueError, 'remaining native bytes plus 4 GiB'):
                self.download([row])
        self.assertEqual(partial.read_bytes(), b'abcd')
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
