"""No real credentials or network calls; exercise the independent uploader."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import urllib.error

from hpcmi import github_sync as sync


class GitHubSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.token_path = self.root / "private" / "token"
        self.token = "unit-test-not-a-real-token"
        self.repo = "example/research"
        self.project_id = "paper1-risk-v1"
        self.branch = "hpc/" + self.project_id
        self.remote = "hpc_status/" + self.project_id + "/status.json"
        self.sha = "a" * 40

    def write_json(self, relative, value):
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def confirm(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = sync.confirm_credentials(self.repo, self.project_id, self.token_path)
        self.assertNotIn(self.token, output.getvalue())
        return result

    def test_initial_hidden_prompt_and_actual_write_then_reuse(self):
        with mock.patch.object(sync.getpass, "getpass", return_value=self.token) as prompt, \
             mock.patch.object(sync, "_ensure_branch") as branch, \
             mock.patch.object(sync, "_put_json", return_value=self.sha) as put:
            self.assertEqual(self.confirm(), self.token_path)
            self.assertEqual(self.confirm(), self.token_path)
        prompt.assert_called_once()
        branch.assert_called_once_with(self.repo, self.branch, self.token)
        self.assertEqual(put.call_args.args[2], "hpc_status/paper1-risk-v1/connection.json")
        self.assertEqual(stat.S_IMODE(self.token_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.token_path.parent.stat().st_mode), 0o700)
        self.assertFalse(any(self.project.rglob("*")))

    def test_new_project_prompts_even_when_token_is_cached(self):
        sync._write_token(self.token_path, self.token)
        with mock.patch.object(sync.getpass, "getpass", return_value="") as prompt, \
             mock.patch.object(sync, "_ensure_branch"), \
             mock.patch.object(sync, "_put_json", return_value=self.sha):
            self.confirm()
        prompt.assert_called_once()

    def test_initial_permission_denial_blocks_submission_and_is_not_approved(self):
        for status in (401, 403):
            with self.subTest(status=status), \
                 mock.patch.object(sync.getpass, "getpass", return_value=self.token), \
                 mock.patch.object(sync, "_ensure_branch", side_effect=sync.GitHubError(
                     "github_http_" + str(status), status, permanent=True)):
                with self.assertRaises(sync.CredentialError):
                    self.confirm()
                self.assertFalse((self.token_path.parent / "project_authorizations.json").exists())

    def test_initial_network_outage_keeps_token_and_defers_upload(self):
        with mock.patch.object(sync.getpass, "getpass", return_value=self.token), \
             mock.patch.object(sync, "_ensure_branch", side_effect=sync.GitHubError("github_network_unavailable")):
            self.confirm()
        record = json.loads((self.token_path.parent / "project_authorizations.json").read_text())
        self.assertEqual(record["projects"][self.repo + ":" + self.project_id]["status"], "INITIAL_WRITE_PENDING")
        self.assertEqual(sync._read_token(self.token_path), self.token)

    def test_missing_and_symlink_credentials_are_not_accepted(self):
        with mock.patch.object(sync.getpass, "getpass", return_value=""):
            with self.assertRaises(sync.CredentialError):
                self.confirm()
        actual = self.root / "real-token"
        actual.write_text(self.token)
        actual.chmod(0o600)
        self.token_path.parent.mkdir()
        self.token_path.symlink_to(actual)
        with self.assertRaises(sync.CredentialError):
            self.confirm()

    def test_api_token_only_header_and_redirects_disabled(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok": true}'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(sync.urllib.request, "build_opener", return_value=opener) as factory:
            self.assertEqual(sync._api("GET", "/repos/example/research", self.token), {"ok": True})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/example/research")
        self.assertNotIn(self.token, request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer " + self.token)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 15)
        self.assertIsInstance(factory.call_args.args[0], sync._NoRedirect)
        self.assertIsNone(factory.call_args.args[0].redirect_request(None, None, 302, "", {}, "https://bad.example"))

    def test_http_errors_are_sanitized_and_rate_limits_retry(self):
        for status, headers, permanent in (
                (401, {}, True), (403, {}, True), (429, {"Retry-After": "230"}, False),
                (403, {"X-RateLimit-Remaining": "0"}, False), (503, {}, False)):
            error = urllib.error.HTTPError("https://api.github.com/repos/example/research", status,
                                           self.token, headers, io.BytesIO(self.token.encode()))
            opener = mock.Mock()
            opener.open.side_effect = error
            with self.subTest(status=status, headers=headers), \
                 mock.patch.object(sync.urllib.request, "build_opener", return_value=opener):
                with self.assertRaises(sync.GitHubError) as caught:
                    sync._api("GET", "/repos/example/research", self.token)
                self.assertNotIn(self.token, str(caught.exception))
                self.assertEqual(caught.exception.permanent, permanent)
                if status == 429:
                    self.assertEqual(caught.exception.retry_after, 230)
                self.assertEqual(error.fp.tell(), 0)

    def test_summary_contains_steps_and_stats_but_no_private_data(self):
        self.write_json("tasks.json", [{"id": "a"}, {"id": "b"}])
        self.write_json("outputs/runs/a/status.json", {
            "status": "RUNNING", "epoch": 3, "global_step": 100, "samples_seen": 400,
            "traceback": "private full traceback", "token": self.token,
            "checkpoint_path": "/private/checkpoint", "eeg": [[1, 2, 3]],
            "validation": {"balanced_accuracy": 0.64, "labels": [0, 1]}})
        self.write_json("outputs/runs/a/complete.json", {"status": "IN_PROGRESS"})
        self.write_json("outputs/runs/b/status.json", {"status": "COMPLETED", "global_step": 200})
        self.write_json("outputs/runs/b/complete.json", {"status": "COMPLETE", "balanced_accuracy": 0.7})
        self.write_json("outputs/analysis/summary.json", {"by_method": {"erm": {
            "mean": 0.7, "ci_low": 0.6, "ci_high": 0.8, "subject_ids": ["private"]}}})
        report = sync.collect_progress(self.project)
        self.assertEqual(report["counts"], {"planned": 2, "observed": 2, "completed": 1, "failed": 0})
        self.assertEqual(report["tasks"][0]["global_step"], 100)
        self.assertEqual(report["tasks"][0]["validation"]["balanced_accuracy"], 0.64)
        self.assertEqual(report["completed_statistics"]["by_method"]["erm"]["mean"], 0.7)
        serialized = json.dumps(report)
        for forbidden in (self.token, "private", "traceback", "checkpoint_path", "subject_ids", '"eeg"'):
            self.assertNotIn(forbidden, serialized)

    def test_sync_error_is_local_status_not_training_failure(self):
        sync._write_token(self.token_path, self.token)
        with mock.patch.object(sync, "_ensure_branch", side_effect=sync.GitHubError("github_network_unavailable")):
            state = sync.sync_once(self.project, self.repo, self.branch, self.remote, self.token_path)
        self.assertEqual(state["status"], "RETRY_PENDING")
        self.assertFalse(state["training_blocked"])
        self.assertEqual(json.loads((self.project / "state/github_sync_status.json").read_text()), state)

    def test_actual_analysis_schema_keeps_adverse_and_null_statistics(self):
        self.write_json("outputs/analysis/summary.json", {"status": "partially_complete", "domains": {
            "nested_outer": {"status": "complete", "n_participants": 9,
                             "method_means": [{"method": "erm", "metric": "min_recall", "mean_percent": 60.0}],
                             "comparisons": [{"contrast": "tail_consistency-minus-erm-min_recall", "family": "primary",
                                              "effect_pp": -0.2, "ci95_low_pp": -1.0, "ci95_high_pp": 1.2,
                                              "p_raw": 0.8, "p_holm": 1.0, "improved": 4, "declined": 5}],
                             "independent_external_confirmation": False}}})
        result = sync.collect_progress(self.project)["completed_statistics"]["domains"]["nested_outer"]
        self.assertEqual(result["comparisons"][0]["effect_pp"], -0.2)
        self.assertEqual(result["comparisons"][0]["p_raw"], 0.8)
        self.assertFalse(result["independent_external_confirmation"])
        self.assertEqual(result["method_means"][0]["mean_percent"], 60.0)

    def test_contents_write_uses_sha_and_conflict_defers_to_next_cycle(self):
        with mock.patch.object(sync, "_api", side_effect=[{"sha": "b" * 40}, {"commit": {"sha": self.sha}}]) as api:
            self.assertEqual(sync._put_json(self.repo, self.branch, self.remote, self.token, {"step": 10}), self.sha)
        payload = api.call_args.args[3]
        self.assertEqual(payload["sha"], "b" * 40)
        self.assertEqual(payload["branch"], self.branch)
        self.assertEqual(json.loads(base64.b64decode(payload["content"])), {"step": 10})
        sync._write_token(self.token_path, self.token)
        with mock.patch.object(sync, "_ensure_branch"), \
             mock.patch.object(sync, "_api", side_effect=[{"sha": "b" * 40}, sync.GitHubError("github_conflict_retry_next_cycle", 409)]) as api:
            state = sync.sync_once(self.project, self.repo, self.branch, self.remote, self.token_path)
        self.assertEqual(state["status"], "RETRY_PENDING")
        self.assertEqual(api.call_count, 2)

    def test_main_or_other_project_destination_rejected(self):
        for branch, path in (("main", self.remote), (self.branch, "manuscript.json")):
            with self.subTest(branch=branch, path=path), self.assertRaises(ValueError):
                sync._validate_destination(self.repo, self.project_id, branch, path)


if __name__ == "__main__":
    unittest.main()
