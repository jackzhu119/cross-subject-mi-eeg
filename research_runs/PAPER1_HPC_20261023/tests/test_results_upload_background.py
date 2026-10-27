"""Detached upload tests with synthetic result files and an offline fake curl."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

import test_results_publication as fixtures
b=fixtures.b


class BackgroundUploadTests(unittest.TestCase):
    setUp=fixtures.BundleTests.setUp
    write=fixtures.BundleTests.write
    read=fixtures.BundleTests.read

    def test_temporary_network_retry_reuses_the_same_bundle(self):
        output=io.StringIO()
        receipt={'commit':'d'*40,'url':'https://github.com/example/result'}
        with mock.patch.object(b,'build_bundle',wraps=b.build_bundle) as build, \
             mock.patch.object(b,'_token',return_value='FAKE_PRIVATE_TOKEN'), \
             mock.patch.object(b,'publish_bundle',side_effect=[b.UploadError('temporary',503),receipt]) as publish, \
             contextlib.redirect_stdout(output):
            code=b._run_upload(self.project,background=True,retry_seconds=0)
        self.assertEqual(code,0)
        self.assertEqual(build.call_count,1)
        self.assertEqual(publish.call_count,2)
        self.assertIs(publish.call_args_list[0].args[1],publish.call_args_list[1].args[1])
        status=self.read('state/results_upload_status.json')
        self.assertEqual(status['status'],'COMPLETE')
        self.assertIn('network_retry_wait',output.getvalue())
        self.assertNotIn('FAKE_PRIVATE_TOKEN',output.getvalue())

    def test_auth_and_integrity_errors_do_not_retry(self):
        for error,expected in [(b.UploadError('denied',403),3),(b.UploadError('SHA mismatch'),1)]:
            with self.subTest(error=str(error)),mock.patch.object(b,'_token',return_value='FAKE_PRIVATE_TOKEN'), \
                 mock.patch.object(b,'publish_bundle',side_effect=error) as publish, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(b._run_upload(self.project,background=True,retry_seconds=0),expected)
                self.assertEqual(publish.call_count,1)
                self.assertTrue((self.project/'outputs/analysis/summary.json').exists())

    def test_progress_heartbeat_and_network_classification(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            progress=b.UploadProgress(self.project,interval=.02)
            try:
                progress('network_retry_wait',status='RETRY_PENDING')
                progress('packing_result_files',completed_files=3,total_files=9)
                time.sleep(.05)
            finally:progress.close()
        value=self.read('state/results_upload_status.json')
        self.assertEqual(value['status'],'RUNNING')
        self.assertEqual(value['completed_files'],3)
        self.assertGreaterEqual(len(output.getvalue().splitlines()),3)
        self.assertTrue(b.UploadError('temporary',503).retryable)
        self.assertFalse(b.UploadError('denied',403).retryable)
        self.assertFalse(b.UploadError('SHA mismatch').retryable)

    def test_rate_limited_403_is_retryable_while_auth_403_is_not(self):
        from types import SimpleNamespace
        def execute(command,**kwargs):
            Path(command[command.index('--dump-header')+1]).write_text(
                'HTTP/1.1 403 Forbidden\r\nX-RateLimit-Remaining: 0\r\nRetry-After: 2\r\n\r\n')
            return SimpleNamespace(returncode=0,stdout=b'{}\n403',stderr=b'')
        with mock.patch.object(b.subprocess,'run',side_effect=execute):
            with self.assertRaises(b.UploadError) as caught:
                b.GitHubPublisher('FAKE_PRIVATE_TOKEN',b.REPOSITORY).request(
                    'GET','/repos/'+b.REPOSITORY+'/git/ref/heads/main')
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.retry_after,2)

    def test_detached_worker_waits_for_old_lock_deduplicates_and_finishes(self):
        private=self.root/'private-token';private.write_text('FAKE_PRIVATE_TOKEN');private.chmod(0o600)
        self.write('config/sync.json',{'token_file':str(private)})
        binaries=self.root/'bin';binaries.mkdir()
        remote=self.root/'fake-remote';remote.mkdir()
        curl=binaries/'curl'
        curl.write_text('#!'+sys.executable+'\n'+r'''
import base64,hashlib,json,os,sys
from pathlib import Path
from urllib.parse import urlsplit
args=sys.argv[1:];config=sys.stdin.read()
assert 'Authorization: Bearer FAKE_PRIVATE_TOKEN' in config
assert not any('FAKE_PRIVATE_TOKEN' in x for x in args)
method=args[args.index('--request')+1]
url=next(x for x in args if x.startswith('https://'));path=urlsplit(url).path
payload=json.loads(Path(args[args.index('--data-binary')+1][1:]).read_text()) if '--data-binary' in args else None
state=Path(os.environ['TEST_RESULTS_REMOTE']);body={};code=200
if method=='GET' and '/git/ref/heads/' in path:body={'object':{'sha':'a'*40}}
elif method=='GET' and '/git/commits/' in path:body={'tree':{'sha':'c'*40 if path.endswith('d'*40) else 'b'*40}}
elif method=='POST' and path.endswith('/git/blobs'):
 data=base64.b64decode(payload['content']);(state/'archive').write_bytes(data)
 sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
 (state/'sha').write_text(sha);body={'sha':sha};code=201
elif method=='POST' and path.endswith('/git/trees'):body={'sha':'c'*40};code=201
elif method=='POST' and path.endswith('/git/commits'):body={'sha':'d'*40};code=201
elif method=='PATCH':assert payload['force'] is False;body={'object':{'sha':'d'*40}}
elif method=='GET' and '/contents/' in path:body={'sha':(state/'sha').read_text(),'size':(state/'archive').stat().st_size}
elif method=='GET' and '/git/blobs/' in path:
 Path(args[args.index('--output')+1]).write_bytes((state/'archive').read_bytes())
 print('\n200',end='');sys.exit(0)
else:raise AssertionError((method,path))
print(json.dumps(body)+'\n'+str(code),end='')
''')
        # raw source above contains literal \n only where the fake HTTP transport writes it.
        curl.chmod(0o755)
        env={**os.environ,'PATH':str(binaries)+os.pathsep+os.environ['PATH'],
             'TEST_RESULTS_REMOTE':str(remote),'PYTHONUNBUFFERED':'1'}
        destination=self.project/'exports/github-results';destination.mkdir(parents=True)
        old=(destination/'.export.lock').open('a+')
        self.addCleanup(old.close)
        fcntl.flock(old,fcntl.LOCK_EX)
        command=[sys.executable,'-B','-u',str(Path(b.__file__).resolve()),'--project',str(self.project),'--publish','--background']
        first=subprocess.run(command,env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        started=json.loads(first.stdout.splitlines()[-1])
        self.assertEqual(started['status'],'BACKGROUND_UPLOAD_STARTED')
        pid=started['pid']
        def stop_worker():
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
        self.addCleanup(stop_worker)
        duplicate=subprocess.run(command,env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(duplicate.returncode,0,duplicate.stdout+duplicate.stderr)
        reused=json.loads(duplicate.stdout.splitlines()[-1])
        self.assertEqual(reused['status'],'EXISTING_BACKGROUND_UPLOAD_REUSED')
        self.assertEqual(reused['pid'],pid)
        self.assertEqual(self.read('state/results_upload_status.json')['stage'],'waiting_existing_export')
        fcntl.flock(old,fcntl.LOCK_UN)
        deadline=time.monotonic()+15
        result={}
        while time.monotonic()<deadline:
            result=self.read('state/results_upload_status.json')
            if result.get('status') in {'COMPLETE','FAILED','AUTH_ACTION_REQUIRED'}:break
            time.sleep(.1)
        log=(self.project/'logs/results-upload.log').read_text()
        self.assertEqual(result.get('status'),'COMPLETE',log)
        self.assertIn('hashing_result_files',log)
        self.assertIn('reading_back_result_bundle',log)
        self.assertNotIn('FAKE_PRIVATE_TOKEN',log)
        self.assertTrue((destination/'github-publication.json').exists())
        self.assertTrue((self.project/'outputs/analysis/summary.json').exists())


if __name__=='__main__':unittest.main()
