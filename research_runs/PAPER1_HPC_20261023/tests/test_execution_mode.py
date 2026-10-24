import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest import mock

from hpcmi import cli
from hpcmi.github_sync import collect_progress


class ExecutionModeTests(unittest.TestCase):
    def test_single_job_marker_prevents_legacy_array_submission(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "config").mkdir()
            (project / "config/execution_mode.json").write_text('{"mode":"single_job"}')
            with mock.patch("hpcmi.slurm.submit_task_array", side_effect=AssertionError("legacy array")):
                value = cli.controller_tick(project)
            self.assertEqual(value["stage"], "single_job_managed")
            self.assertFalse(value["legacy_array_submission"])

    def test_only_exact_project_monitor_commands_are_stopped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            proc = root / "proc"
            commands = {
                101: ["python", "-u", "-m", "hpcmi.cli", "controller", "--project", str(project)],
                102: ["python", "-m", "hpcmi.github_sync", "--project", str(project)],
                103: ["python", "-m", "hpcmi.worker", "--project", str(project)],
                104: ["python", "-m", "hpcmi.cli", "controller", "--project", str(root / "other")],
            }
            for pid, command in commands.items():
                (proc / str(pid)).mkdir(parents=True)
                (proc / str(pid) / "cmdline").write_bytes("\0".join(command).encode() + b"\0")
            stopped = []
            def send(pid, sig):
                if sig == signal.SIGTERM:
                    stopped.append(pid)
                elif sig == 0 and pid in stopped:
                    raise ProcessLookupError()
                else:
                    raise AssertionError((pid, sig))
            with mock.patch.object(cli.os, "kill", side_effect=send):
                result = cli.stop_legacy_controller(project, proc)
            self.assertEqual(set(result), {101, 102})
            self.assertEqual(set(stopped), {101, 102})

    def test_login_reporter_is_preserved_while_old_controller_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, proc = root / "project", root / "proc"
            commands = {
                201: ["python", "-m", "hpcmi.cli", "controller", "--project", str(project)],
                202: ["python", "-m", "hpcmi.github_sync", "--project", str(project)],
                203: ["python", "-m", "hpcmi.worker", "--project", str(project)],
            }
            for pid, command in commands.items():
                (proc / str(pid)).mkdir(parents=True)
                (proc / str(pid) / "cmdline").write_bytes("\0".join(command).encode() + b"\0")
            stopped = []
            def send(pid, sig):
                self.assertEqual(pid, 201, "A current login reporter or worker was signalled")
                if sig == signal.SIGTERM:
                    stopped.append(pid)
                elif sig == 0:
                    raise ProcessLookupError()
                else:
                    raise AssertionError((pid, sig))
            with mock.patch.object(cli.os, "kill", side_effect=send):
                self.assertEqual(cli.stop_legacy_controller(project, proc, include_sync=False), [201])
            self.assertEqual(stopped, [201])

    def test_single_job_phase_and_updates_are_reported_without_process_details(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "state").mkdir()
            (project / "state/single_job_status.json").write_text(json.dumps({
                "stage": "raw_download", "max_concurrent_fits": 2,
                "active_children": [{"pid": 1234, "task_id": "dev-f00-erm-s1", "optimizer_updates": 12}],
                "secret": "not-reportable"}))
            result = collect_progress(project)
            self.assertEqual(result["execution"]["stage"], "raw_download")
            self.assertEqual(result["execution"]["active_children"][0]["optimizer_updates"], 12)
            self.assertNotIn("pid", result["execution"]["active_children"][0])
            self.assertNotIn("secret", result["execution"])


if __name__ == "__main__":
    unittest.main()
