"""Real Bash signal tests for the one-job wrapper; no Slurm/GPU/EEG needed."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = '''import json,os,signal,sys,time
from pathlib import Path
root=Path(os.environ["TEST_ROOT"])
state={"signal":None}
def receive(sig,frame):
    state["signal"]=sig
signal.signal(signal.SIGUSR1,receive)
signal.signal(signal.SIGTERM,receive)
signal.signal(signal.SIGINT,receive)
(root/"visible.json").write_text(json.dumps({"cuda":os.environ.get("CUDA_VISIBLE_DEVICES"),"threads":os.environ.get("OPENBLAS_NUM_THREADS"),"argv":sys.argv}))
(root/"ready").write_text(str(os.getpid()))
if os.environ.get("RUNNER_FAIL"):
    sys.exit(7)
while state["signal"] is None:
    time.sleep(.01)
(root/"saving").write_text("yes")
time.sleep(.15)
(root/"checkpoint").write_text("saved")
sys.exit(75 if state["signal"]==signal.SIGUSR1 else 143)
'''


class SingleJobShellTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        package = self.folder / "hpcmi"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "single_job.py").write_text(RUNNER)
        binary = self.folder / "bin"
        binary.mkdir()
        control = binary / "scontrol"
        control.write_text('#!/usr/bin/env bash\n[ -f "$TEST_ROOT/checkpoint" ] || exit 97\nprintf "%s\\n" "$*" >> "$TEST_ROOT/requeue"\nexit "${REQUEUE_EXIT:-0}"\n')
        control.chmod(0o755)
        # A worker must never submit a replacement or array itself.
        submit = binary / "sbatch"
        submit.write_text('#!/usr/bin/env bash\ntouch "$TEST_ROOT/unexpected_sbatch"\nexit 98\n')
        submit.chmod(0o755)
        self.env = dict(os.environ, TEST_ROOT=str(self.folder), PATH=str(binary) + ":" + os.environ["PATH"],
                        SLURM_JOB_ID="770700", CUDA_VISIBLE_DEVICES="GPU-assigned-first,GPU-assigned-second")
        self.process = None

    def tearDown(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.communicate(timeout=5)
        self.temporary.cleanup()

    def wait_file(self, name):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if (self.folder / name).exists():
                return
            if self.process.poll() is not None:
                self.fail("runner exited before " + name + ": " + str(self.process.communicate()))
            time.sleep(.01)
        self.fail("runner failed to produce " + name)

    def start(self):
        self.process = subprocess.Popen(["bash", str(ROOT / "slurm/single_job.sh"), str(self.folder),
                                         sys.executable, str(self.folder)], env=self.env, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_file("ready")

    def finish(self):
        out, err = self.process.communicate(timeout=5)
        self.assertIn("SINGLE_JOB_BATCH_START", out)
        self.assertIn("SINGLE_JOB_RUNNER_EXIT", out)
        self.assertFalse((self.folder / "unexpected_sbatch").exists())
        visible = json.loads((self.folder / "visible.json").read_text())
        self.assertEqual(visible["cuda"], self.env["CUDA_VISIBLE_DEVICES"])
        self.assertEqual(visible["threads"], "1")
        self.assertEqual(visible["argv"][1:], ["--project", str(self.folder)])
        return self.process.returncode, out, err

    def test_usr1_waits_for_save_then_requeues_only_current_job_once(self):
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        code, out, err = self.finish()
        self.assertEqual(code, 75, out + err)
        self.assertEqual((self.folder / "checkpoint").read_text(), "saved")
        self.assertEqual((self.folder / "requeue").read_text(), "requeue 770700\n")

    def test_term_checkpoints_without_requeue(self):
        self.start()
        os.kill(self.process.pid, signal.SIGTERM)
        code, out, err = self.finish()
        self.assertEqual(code, 143, out + err)
        self.assertTrue((self.folder / "checkpoint").exists())
        self.assertFalse((self.folder / "requeue").exists())

    def test_cancel_during_save_overrides_usr1_requeue(self):
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        self.wait_file("saving")
        os.kill(self.process.pid, signal.SIGTERM)
        code, out, err = self.finish()
        self.assertEqual(code, 143, out + err)
        self.assertFalse((self.folder / "requeue").exists())

    def test_denied_requeue_keeps_checkpoint_and_returns_75(self):
        self.env["REQUEUE_EXIT"] = "1"
        self.start()
        os.kill(self.process.pid, signal.SIGUSR1)
        code, out, err = self.finish()
        self.assertEqual(code, 75, out + err)
        self.assertEqual((self.folder / "requeue").read_text().count("requeue"), 1)
        self.assertIn("REQUEUE_UNAVAILABLE", err)

    def test_actual_supervisor_error_is_preserved(self):
        self.env["RUNNER_FAIL"] = "1"
        self.start()
        code, out, err = self.finish()
        self.assertEqual(code, 7, out + err)
        self.assertFalse((self.folder / "requeue").exists())


if __name__ == "__main__":
    unittest.main()
