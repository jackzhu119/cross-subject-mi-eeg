"""Exact old-publisher handoff using synthetic proc metadata; no real signals."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

import test_results_publication as fixtures
b=fixtures.b


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.project=(self.root/'paper1-risk-v1').resolve();self.project.mkdir()
        self.lock=self.project/'exports/github-results/.export.lock'
        self.lock.parent.mkdir(parents=True);self.lock.write_text('')
        self.inode=self.lock.stat().st_ino
        self.proc=self.root/'proc';self.proc.mkdir();(self.proc/'locks').write_text('')
        self.pid=21001;self.background=21002
        self.script=self.root/'paper1-publish-results.py'
        self.script.write_bytes(Path(b.__file__).read_bytes())
        self.old=self.proc/str(self.pid);self.old.mkdir();(self.old/'fd').mkdir()
        (self.old/'fd/9').symlink_to(self.lock)
        args=[sys.executable,'-B','-u',str(self.script),'--project',str(self.project),'--publish']
        self.argv=args
        self.command(args)
        self.starttime('777')
        self.holders(self.pid)

    def command(self,args):
        (self.old/'cmdline').write_bytes(('\0'.join(args)+'\0').encode())

    def starttime(self,value):
        (self.old/'stat').write_text(str(self.pid)+' (old foreground uploader) S '+' '.join(['0']*18+[value]))

    def line(self,pid,kind='FLOCK',waiting=False):
        info=self.lock.stat()
        return '1: '+('-> ' if waiting else '')+kind+' ADVISORY WRITE '+str(pid)+' '+('%02x:%02x:%d'%(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino))+' 0 EOF\n'

    def holders(self,*pids):
        (self.proc/'locks').write_text(''.join(self.line(pid) for pid in pids))

    def test_hex_devices_posix_nfs_and_waiting_rows(self):
        (self.proc/'locks').write_text(self.line(self.pid,'POSIX')+self.line(self.background,waiting=True))
        holders,info=b._export_lock_holders(self.project,self.proc)
        self.assertEqual(holders,{self.pid})
        self.assertEqual(info.st_ino,self.inode)

    def test_only_verified_old_owner_interrupted_and_background_can_take_lock(self):
        marker={'pid':self.background}
        def interrupt(pid,number):
            self.assertEqual((pid,number),(self.pid,signal.SIGINT))
            self.holders(self.background)
        with mock.patch.object(b,'_live_background',return_value=marker), \
             mock.patch.object(b.os,'kill',side_effect=interrupt) as kill, \
             contextlib.redirect_stdout(io.StringIO()):
            b._handoff_foreground(self.project,self.proc,timeout=.1)
        kill.assert_called_once_with(self.pid,signal.SIGINT)
        self.assertEqual(self.lock.stat().st_ino,self.inode)
        records=list((self.project/'state/results-upload-handoffs').glob('*.json'))
        self.assertEqual(len(records),1)
        self.assertEqual(json.loads(records[0].read_text())['status'],'OLD_FOREGROUND_EXPORT_RELEASED')

    def test_existing_background_owner_is_never_signalled(self):
        self.holders(self.background)
        with mock.patch.object(b,'_live_background',return_value={'pid':self.background}), \
             mock.patch.object(b.os,'kill',side_effect=AssertionError('background must be retained')), \
             contextlib.redirect_stdout(io.StringIO()):
            b._handoff_foreground(self.project,self.proc)
        self.assertEqual(self.lock.stat().st_ino,self.inode)

    def test_training_process_and_other_project_are_retained(self):
        cases=[[sys.executable,'-m','hpcmi.worker','--project',str(self.project),'--publish'],
               [sys.executable,str(self.script),'--project',str(self.root/'other-paper'),'--publish'],
               [sys.executable,str(self.script),'--project',str(self.project),'--publish','--background-worker']]
        for args in cases:
            self.command(args)
            with self.subTest(args=args),mock.patch.object(b,'_live_background',return_value=None), \
                 mock.patch.object(b.os,'kill',side_effect=AssertionError('unrelated process retained')):
                with self.assertRaises(ValueError):b._handoff_foreground(self.project,self.proc)
        self.assertEqual(self.lock.stat().st_ino,self.inode)

    def test_reused_pid_starttime_stops_before_signal(self):
        real=b._foreground_export_identity;calls=0
        def identity(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==1:self.starttime('888')
            return result
        with mock.patch.object(b,'_live_background',return_value=None), \
             mock.patch.object(b,'_foreground_export_identity',side_effect=identity), \
             mock.patch.object(b.os,'kill',side_effect=AssertionError('reused PID retained')):
            with self.assertRaisesRegex(ValueError,'identity changed'):
                b._handoff_foreground(self.project,self.proc)

    def test_unobservable_busy_lock_is_not_deleted_or_treated_as_stale(self):
        self.holders()
        with self.lock.open('a+') as owner:
            fcntl.flock(owner,fcntl.LOCK_EX)
            with mock.patch.object(b,'_live_background',return_value=None), \
                 mock.patch.object(b.os,'kill',side_effect=AssertionError('unknown owner retained')):
                with self.assertRaisesRegex(ValueError,'not observable'):
                    b._handoff_foreground(self.project,self.proc)
        self.assertEqual(self.lock.stat().st_ino,self.inode)

    def test_released_lock_is_reused_without_deleting_inode(self):
        self.holders()
        with mock.patch.object(b,'_live_background',return_value=None), \
             mock.patch.object(b.os,'kill',side_effect=AssertionError('no owner to signal')), \
             contextlib.redirect_stdout(io.StringIO()):
            b._handoff_foreground(self.project,self.proc)
        self.assertEqual(self.lock.stat().st_ino,self.inode)

    def test_standalone_handoff_does_not_start_a_new_export(self):
        with mock.patch.object(b,'_handoff_foreground') as handoff, \
             mock.patch.object(b,'_run_upload',side_effect=AssertionError('no new foreground export')), \
             mock.patch.dict(os.environ,{},clear=True):
            self.assertEqual(b.main(['--project',str(self.project),'--handoff-foreground']),0)
        handoff.assert_called_once_with(self.project)


if __name__=='__main__':unittest.main()
