"""Orchestration checks use synthetic receipts and APIs; no EEG fitting or network."""
from __future__ import annotations

import builtins
import importlib.util
import json
import os
import sys
import types
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research_runs/Q15-MIGRATION-20261004/q15_migration_supervisor.py"
FAKE_SECRETS = {
    "R2_BUCKET": "FAKER2_BUCKET_TEST_ONLY",
    "R2_ENDPOINT": "FAKER2_ENDPOINT_TEST_ONLY",
    "R2_ACCESS_KEY_ID": "FAKER2_ACCESS_TEST_ONLY",
    "R2_SECRET_ACCESS_KEY": "FAKER2_SECRET_TEST_ONLY",
    "GH_TOKEN": "FAKEGH_TEST_ONLY_MIGRATION",
    "GITHUB_TOKEN": "FAKEGH_ALIAS_TEST_ONLY_MIGRATION",
    "RUNPOD_API_KEY": "FAKERUNPOD_TEST_ONLY_MIGRATION",
}


@pytest.fixture
def supervisor(monkeypatch):
    spec = importlib.util.spec_from_file_location("q15_test_migration_supervisor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in FAKE_SECRETS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("RUNPOD_POD_ID", "new_fake_test_pod")
    return module


@pytest.fixture
def sandbox(supervisor, monkeypatch, tmp_path):
    """Translate only fixed workspace paths; actual server paths are never touched."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def mapped_path(value):
        value = os.fspath(value)
        if value == "/workspace" or value.startswith("/workspace/"):
            return workspace / value.removeprefix("/workspace").lstrip("/")
        return Path(value)

    monkeypatch.setattr(supervisor, "Path", mapped_path)
    monkeypatch.setattr(supervisor, "check_cuda_template", lambda: None)
    monkeypatch.setattr(supervisor, "existing_ready_restore", lambda *_: False)
    return workspace


def launch_args(tmp_path, mode="restore", **kwargs):
    args = [mode, "--job-directory", str(tmp_path / "job"), "--job-id", "new-test-job",
            "--private-log", str(tmp_path / "private-dependencies.log")]
    if mode == "restore":
        args += ["--object-key", kwargs.get("object_key", "q15/migrations/fake/archive.tar"),
                 "--archive-sha256", kwargs.get("archive_sha256", "a" * 64)]
    return args


def install_transport(monkeypatch, callback):
    monkeypatch.setitem(sys.modules, "q15_migration_transport", types.SimpleNamespace(main=callback))


def progress(tmp_path):
    return json.loads((tmp_path / "job/migration_status.json").read_text())


def ready_receipt(workspace, **changes):
    receipt = {"schema_version": 1,
               "kind": "q15_validated_source_and_epochs_restore",
               "origin_job_id": "20261004T005335Z-9b3bce30277a",
               "source_fit_count": 15, "new_source_fits": 0, "target_fits": 0,
               "ready_for_continuation": True, **changes}
    path = workspace / "q15-migration/restore_receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt))
    return receipt


@pytest.mark.parametrize("pod", ["", "hvjo2yy3m3wamh", "bad/pod", "a" * 65])
def test_destination_preflight_rejects_missing_origin_or_unsafe_identity(supervisor, monkeypatch, pod):
    monkeypatch.setenv("RUNPOD_POD_ID", pod)
    monkeypatch.setattr(supervisor, "read_api", lambda *_: pytest.fail("API must not be called"))
    with pytest.raises(supervisor.MigrationError, match="new_destination_pod_required"):
        supervisor.check_destination_identity()


@pytest.mark.parametrize("missing", ["GH_TOKEN", "RUNPOD_API_KEY"])
def test_destination_requires_both_account_credentials_before_api(supervisor, monkeypatch, missing):
    monkeypatch.delenv(missing)
    monkeypatch.setattr(supervisor, "read_api", lambda *_: pytest.fail("API must not be called"))
    with pytest.raises(supervisor.MigrationError, match="required_credential_missing:" + missing):
        supervisor.check_destination_identity()


@pytest.mark.parametrize("pod_response,repo_response,error", [
    ({"id": "wrong_fake_test_pod"}, None, "destination_account_pod_identity_unverified"),
    ({"id": "new_fake_test_pod"}, {"full_name": "other/repo", "permissions": {"push": True}},
     "github_publication_access_unverified"),
    ({"id": "new_fake_test_pod"}, {"full_name": "jackzhu119/cross-subject-mi-eeg",
                                  "permissions": {"push": False}},
     "github_publication_access_unverified"),
])
def test_wrong_account_or_github_permission_fails(supervisor, monkeypatch,
                                                 pod_response, repo_response, error):
    replies = iter([pod_response, repo_response])
    monkeypatch.setattr(supervisor, "read_api", lambda *_: next(replies))
    with pytest.raises(supervisor.MigrationError, match=error):
        supervisor.check_destination_identity()


def test_destination_account_queries_use_matching_tokens(supervisor, monkeypatch):
    calls = []

    def read(url, token):
        calls.append((url, token))
        if "rest.runpod.io" in url:
            return {"id": "new_fake_test_pod"}
        return {"full_name": "jackzhu119/cross-subject-mi-eeg", "permissions": {"push": True}}

    monkeypatch.setattr(supervisor, "read_api", read)
    assert supervisor.check_destination_identity() == "new_fake_test_pod"
    assert calls == [
        ("https://rest.runpod.io/v1/pods/new_fake_test_pod", FAKE_SECRETS["RUNPOD_API_KEY"]),
        ("https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg", FAKE_SECRETS["GH_TOKEN"]),
    ]


@pytest.mark.parametrize("host,provider", [("rest.runpod.io", "runpod"),
                                         ("api.github.com", "github")])
@pytest.mark.parametrize("error_kind,suffix", [("http", "http_403"),
                                             ("network", "unreachable")])
def test_read_api_sanitizes_provider_specific_errors(supervisor, monkeypatch, host, provider,
                                                     error_kind, suffix):
    sensitive = FAKE_SECRETS["RUNPOD_API_KEY"]

    def failing(*_, **__):
        if error_kind == "http":
            raise urllib.error.HTTPError("https://fake.invalid/" + sensitive, 403,
                                         "body contains " + sensitive, {}, None)
        raise RuntimeError("network diagnostic contains " + sensitive)

    monkeypatch.setattr(supervisor.urllib.request, "urlopen", failing)
    with pytest.raises(supervisor.MigrationError) as caught:
        supervisor.read_api("https://" + host + "/fake-test", sensitive)
    assert str(caught.value) == provider + "_account_api_" + suffix
    assert sensitive not in str(caught.value)


def fake_account_queries(supervisor, monkeypatch, rejected_provider=None, github_push=True):
    """Fake both account endpoints without exposing even synthetic tokens."""
    calls = []

    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, limit):
            assert limit == 2 * 1024**2
            return json.dumps(self.body).encode()

    def read(request, **kwargs):
        assert kwargs["timeout"] == 30
        if request.full_url == "https://rest.runpod.io/v1/pods/new_fake_test_pod":
            provider = "runpod"
            secret = FAKE_SECRETS["RUNPOD_API_KEY"]
            body = {"id": "new_fake_test_pod"}
        elif request.full_url == "https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg":
            provider = "github"
            secret = FAKE_SECRETS["GH_TOKEN"]
            body = {"full_name": "jackzhu119/cross-subject-mi-eeg",
                    "permissions": {"push": github_push}}
        else:
            pytest.fail("Only the two read-only account endpoints are allowed")
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bearer " + secret
        calls.append(provider)
        if provider == rejected_provider:
            raise urllib.error.HTTPError("https://fake.invalid/" + secret, 403,
                                         "private diagnostic " + secret, {}, None)
        return Response(body)

    monkeypatch.setattr(supervisor.urllib.request, "urlopen", read)
    return calls


def prohibit_scientific_and_cloud_actions(supervisor, monkeypatch):
    def prohibited(*_, **__):
        pytest.fail("Account preflight must not execute scientific or cloud actions")

    monkeypatch.setattr(supervisor, "check_cuda_template", prohibited)
    monkeypatch.setattr(supervisor, "install_scientific_runtime", prohibited)
    monkeypatch.setattr(supervisor, "existing_ready_restore", prohibited)
    monkeypatch.setattr(supervisor.subprocess, "run", prohibited)
    install_transport(monkeypatch, prohibited)
    monkeypatch.setitem(sys.modules, "q15_restore_from_r2", types.SimpleNamespace(
        restore_from_r2=prohibited))


@pytest.mark.parametrize("mode", ["restore", "from-r2"])
@pytest.mark.parametrize("provider,expected_calls", [("runpod", ["runpod"]),
                                                   ("github", ["runpod", "github"])])
def test_account_provider_http_failure_blocks_all_migration_actions(supervisor, sandbox,
                                                                   monkeypatch, tmp_path,
                                                                   capsys, mode, provider,
                                                                   expected_calls):
    prohibit_scientific_and_cloud_actions(supervisor, monkeypatch)
    calls = fake_account_queries(supervisor, monkeypatch, provider)
    assert supervisor.main(launch_args(tmp_path, mode)) == 1
    report = progress(tmp_path)
    assert report["stage"] == "failed_or_blocked"
    assert report["error_code"] == provider + "_account_api_http_403"
    assert report["new_source_fits"] == report["target_fits"] == 0
    assert report["automatic_pod_stop_requested_by_migration_supervisor"] is False
    assert calls == expected_calls
    output = capsys.readouterr().out + json.dumps(report)
    assert all(secret not in output for secret in FAKE_SECRETS.values())


@pytest.mark.parametrize("provider,expected_calls", [(None, ["runpod", "github"]),
                                                   ("runpod", ["runpod"]),
                                                   ("github", ["runpod", "github"])])
def test_check_accounts_is_read_only_without_job_arguments(supervisor, monkeypatch, tmp_path,
                                                          capsys, provider, expected_calls):
    monkeypatch.chdir(tmp_path)
    prohibit_scientific_and_cloud_actions(supervisor, monkeypatch)
    calls = fake_account_queries(supervisor, monkeypatch, provider)
    original_import = builtins.__import__

    def safe_import(name, *args, **kwargs):
        assert name not in {"q15_migration_transport", "q15_restore_from_r2", "torch", "boto3"}
        return original_import(name, *args, **kwargs)

    def no_file_change(*_, **__):
        pytest.fail("check-accounts must not create directories or write status files")

    monkeypatch.setattr(builtins, "__import__", safe_import)
    monkeypatch.setattr(Path, "mkdir", no_file_change)
    monkeypatch.setattr(Path, "write_text", no_file_change)
    monkeypatch.setattr(Path, "replace", no_file_change)
    assert supervisor.main(["check-accounts"]) == (1 if provider else 0)
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["status"] == ("accounts_preflight_failed" if provider else
                                "accounts_preflight_verified")
    assert report["new_source_fits"] == report["target_fits"] == 0
    if provider:
        assert report["error_code"] == provider + "_account_api_http_403"
    else:
        assert "error_code" not in report
    assert calls == expected_calls
    assert list(tmp_path.iterdir()) == []
    assert all(secret not in output for secret in FAKE_SECRETS.values())


def test_manual_identity_requires_no_runpod_key_and_queries_only_github(supervisor, monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY")
    calls = fake_account_queries(supervisor, monkeypatch)
    assert supervisor.check_destination_identity(manual_stop=True) == "new_fake_test_pod"
    assert calls == ["github"]


def test_manual_identity_still_requires_github_credential(supervisor, monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setattr(supervisor, "read_api", lambda *_: pytest.fail("No account API"))
    with pytest.raises(supervisor.MigrationError, match="required_credential_missing:GH_TOKEN"):
        supervisor.check_destination_identity(manual_stop=True)


@pytest.mark.parametrize("pod", ["", "hvjo2yy3m3wamh", "bad/pod", "a" * 65])
def test_manual_stop_still_rejects_missing_origin_or_unsafe_pod_environment(supervisor,
                                                                         monkeypatch, pod):
    monkeypatch.delenv("RUNPOD_API_KEY")
    monkeypatch.setenv("RUNPOD_POD_ID", pod)
    monkeypatch.setattr(supervisor, "read_api", lambda *_: pytest.fail("No account API"))
    with pytest.raises(supervisor.MigrationError, match="new_destination_pod_required"):
        supervisor.check_destination_identity(manual_stop=True)


@pytest.mark.parametrize("failure,error", [(None, None),
                                          ("http", "github_account_api_http_403"),
                                          ("permission", "github_publication_access_unverified")])
def test_manual_accounts_check_is_read_only_and_never_claims_runpod_validation(supervisor,
                                                                             monkeypatch,
                                                                             tmp_path, capsys,
                                                                             failure, error):
    monkeypatch.delenv("RUNPOD_API_KEY")
    monkeypatch.chdir(tmp_path)
    prohibit_scientific_and_cloud_actions(supervisor, monkeypatch)
    calls = fake_account_queries(supervisor, monkeypatch,
                                 "github" if failure == "http" else None,
                                 github_push=failure != "permission")
    original_import = builtins.__import__

    def safe_import(name, *args, **kwargs):
        assert name not in {"q15_migration_transport", "q15_restore_from_r2", "torch", "boto3"}
        return original_import(name, *args, **kwargs)

    def no_file_change(*_, **__):
        pytest.fail("Manual account check must not write files or create directories")

    monkeypatch.setattr(builtins, "__import__", safe_import)
    monkeypatch.setattr(Path, "mkdir", no_file_change)
    monkeypatch.setattr(Path, "write_text", no_file_change)
    monkeypatch.setattr(Path, "replace", no_file_change)
    assert supervisor.main(["check-accounts", "--manual-stop"]) == (1 if failure else 0)
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["new_source_fits"] == report["target_fits"] == 0
    if failure:
        assert report["status"] == "accounts_preflight_failed"
        assert report["error_code"] == error
    else:
        assert report["status"] == "github_preflight_verified_manual_stop"
        assert report["runpod_api_checked"] is False
        assert report["automatic_shutdown_enabled"] is False
        assert report["pod_identity_source"] == "pod_environment_only"
    assert report.get("runpod_api_checked", False) is False
    assert calls == ["github"]
    assert list(tmp_path.iterdir()) == []
    assert all(secret not in output for secret in FAKE_SECRETS.values())


@pytest.mark.parametrize("mode", ["restore", "from-r2"])
@pytest.mark.parametrize("failure,error", [("http", "github_account_api_http_403"),
                                          ("permission", "github_publication_access_unverified")])
def test_manual_github_failure_blocks_all_migration_actions(supervisor, sandbox, monkeypatch,
                                                          tmp_path, capsys, mode, failure, error):
    monkeypatch.delenv("RUNPOD_API_KEY")
    prohibit_scientific_and_cloud_actions(supervisor, monkeypatch)
    calls = fake_account_queries(supervisor, monkeypatch,
                                 "github" if failure == "http" else None,
                                 github_push=failure != "permission")
    assert supervisor.main(launch_args(tmp_path, mode) + ["--manual-stop"]) == 1
    report = progress(tmp_path)
    assert report["stage"] == "failed_or_blocked"
    assert report["error_code"] == error
    assert report["new_source_fits"] == report["target_fits"] == 0
    assert report["automatic_pod_stop_requested_by_migration_supervisor"] is False
    assert calls == ["github"]
    output = capsys.readouterr().out
    for row in (json.loads(line) for line in output.splitlines()):
        assert row["runpod_api_checked"] is False
        assert row["automatic_shutdown_enabled"] is False
        assert row["pod_identity_source"] == "pod_environment_only"
    assert all(secret not in output for secret in FAKE_SECRETS.values())


@pytest.mark.parametrize("mode", ["restore", "from-r2"])
def test_manual_stop_flag_reaches_only_verified_continuation(supervisor, sandbox, monkeypatch,
                                                           tmp_path, capsys, mode):
    monkeypatch.delenv("RUNPOD_API_KEY")
    calls = fake_account_queries(supervisor, monkeypatch)
    events = []

    def transport(args):
        assert args[0] == "restore"
        events.append("restore")
        ready_receipt(sandbox)
        return 0

    def restore_from_r2(*_, **kwargs):
        assert kwargs == {"manual_stop": True}
        events.append("restore")
        return {"ready_for_continuation": True}

    def continuation(command, **kwargs):
        assert Path(command[1]).name == "q15_continue_validated.py"
        assert command.count("--manual-stop") == 1
        assert kwargs["check"] is False
        events.append("continue")
        return types.SimpleNamespace(returncode=0)

    install_transport(monkeypatch, transport if mode == "restore" else
                      lambda *_: pytest.fail("No archive transport for from-r2"))
    monkeypatch.setitem(sys.modules, "q15_restore_from_r2", types.SimpleNamespace(
        restore_from_r2=restore_from_r2))
    monkeypatch.setattr(supervisor, "install_scientific_runtime", lambda *_: None)
    monkeypatch.setattr(supervisor.subprocess, "run", continuation)
    assert supervisor.main(launch_args(tmp_path, mode) + ["--manual-stop"]) == 0
    assert calls == ["github"]
    assert events == ["restore", "continue"]
    report = progress(tmp_path)
    assert report["scientific_completion_requires_job_report"] is True
    assert report["new_source_fits"] == report["target_fits"] == 0
    for row in (json.loads(line) for line in capsys.readouterr().out.splitlines()):
        assert row["runpod_api_checked"] is False
        assert row["automatic_shutdown_enabled"] is False
        assert row["pod_identity_source"] == "pod_environment_only"
        assert row["new_source_fits"] == row["target_fits"] == 0


@pytest.mark.parametrize("mode", ["backup", "restore", "from-r2"])
@pytest.mark.parametrize("missing", ["--job-directory", "--job-id", "--private-log"])
def test_migration_modes_still_require_all_job_arguments(supervisor, monkeypatch, tmp_path,
                                                        mode, missing):
    monkeypatch.setattr(supervisor, "check_destination_identity", lambda manual_stop=False: pytest.fail("No API"))
    args = launch_args(tmp_path, mode)
    index = args.index(missing)
    del args[index:index + 2]
    with pytest.raises(SystemExit) as caught:
        supervisor.main(args)
    assert caught.value.code == 2
    assert not (tmp_path / "job").exists()


def test_restore_account_preflight_precedes_transport(supervisor, sandbox, monkeypatch, tmp_path):
    def rejected(manual_stop=False):
        raise supervisor.MigrationError("destination_fake_rejected")

    monkeypatch.setattr(supervisor, "check_destination_identity", rejected)
    install_transport(monkeypatch, lambda *_: pytest.fail("75 GB transport must not start"))
    monkeypatch.setattr(supervisor, "install_scientific_runtime", lambda *_: pytest.fail("No install"))
    assert supervisor.main(launch_args(tmp_path)) == 1
    report = progress(tmp_path)
    assert report["error_code"] == "destination_fake_rejected"
    assert report["new_source_fits"] == report["target_fits"] == 0
    assert report["automatic_pod_stop_requested_by_migration_supervisor"] is False


def test_invalid_archive_digest_blocks_transport(supervisor, sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(supervisor, "check_destination_identity", lambda manual_stop=False: "new_fake_test_pod")
    install_transport(monkeypatch, lambda *_: pytest.fail("Unverified backup must not be downloaded"))
    assert supervisor.main(launch_args(tmp_path, archive_sha256="bad")) == 1
    assert progress(tmp_path)["error_code"] == "verified_backup_locator_required"


@pytest.mark.parametrize("transport_result,ready,error", [
    (1, True, "restore_transport_failed"),
    (0, False, "restored_originals_not_verified"),
])
def test_partial_restore_or_failed_transport_cannot_continue(supervisor, sandbox, monkeypatch,
                                                           tmp_path, transport_result, ready, error):
    monkeypatch.setattr(supervisor, "check_destination_identity", lambda manual_stop=False: "new_fake_test_pod")
    monkeypatch.setattr(supervisor, "check_cuda_template", lambda: None)

    def transport(_):
        ready_receipt(sandbox, ready_for_continuation=ready)
        return transport_result

    install_transport(monkeypatch, transport)
    monkeypatch.setattr(supervisor, "install_scientific_runtime", lambda *_: pytest.fail("No install"))
    monkeypatch.setattr(supervisor.subprocess, "run", lambda *_args, **_kw: pytest.fail("No worker"))
    assert supervisor.main(launch_args(tmp_path)) == 1
    assert progress(tmp_path)["error_code"] == error


def test_restore_launches_only_verified_continuation_after_runtime_install(supervisor, sandbox,
                                                                          monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(supervisor, "check_destination_identity",
                        lambda manual_stop=False: events.append("identity") or "new_fake_test_pod")
    monkeypatch.setattr(supervisor, "check_cuda_template", lambda: events.append("runtime_probe"))

    def transport(args):
        assert args[0] == "restore"
        events.append("restore")
        ready_receipt(sandbox)
        return 0

    def install(repo, log):
        assert repo == sandbox / "q15-execution/repo"
        assert log == tmp_path / "private-dependencies.log"
        events.append("install")

    def run(command, **kwargs):
        events.append("continue")
        assert Path(command[1]).name == "q15_continue_validated.py"
        assert "--job-id" in command and command[command.index("--job-id") + 1] == "new-test-job"
        assert "q15_full_job.py" not in command
        assert "run_source" not in " ".join(command)
        assert kwargs["check"] is False
        return types.SimpleNamespace(returncode=0)

    install_transport(monkeypatch, transport)
    monkeypatch.setattr(supervisor, "install_scientific_runtime", install)
    monkeypatch.setattr(supervisor.subprocess, "run", run)
    assert supervisor.main(launch_args(tmp_path)) == 0
    assert events.index("identity") < events.index("restore") < events.index("install") < events.index("continue")
    report = progress(tmp_path)
    assert report["stage"] == "continuation_process_returned"
    assert report["scientific_completion_requires_job_report"] is True
    assert report["new_source_fits"] == report["target_fits"] == 0


def test_verified_backup_preserves_old_job_and_does_not_stop_or_continue(supervisor, sandbox,
                                                                      monkeypatch, tmp_path):
    def transport(args):
        assert args[0] == "backup"
        assert args[args.index("--base-commit") + 1] == supervisor.BASE
        assert args[args.index("--origin-job") + 1] == supervisor.ORIGIN_JOB
        receipt_path = Path(args[args.index("--receipt") + 1])
        receipt_path.write_text(json.dumps({"readback_verified": True,
                                            "object_key": "q15/migrations/fake/archive.tar",
                                            "archive_sha256": "a" * 64}))
        return 0

    install_transport(monkeypatch, transport)
    monkeypatch.setattr(supervisor, "check_destination_identity", lambda manual_stop=False: pytest.fail("Backup uses old Pod"))
    monkeypatch.setattr(supervisor.subprocess, "run", lambda *_args, **_kw: pytest.fail("No scientific worker"))
    assert supervisor.main(launch_args(tmp_path, "backup")) == 0
    report = progress(tmp_path)
    assert report["stage"] == "backup_verified_old_pod_can_be_stopped_manually"
    assert report["origin_source_fits"] == 15
    assert report["new_source_fits"] == report["target_fits"] == 0


def test_backup_without_readback_cannot_claim_safe_stop(supervisor, sandbox, monkeypatch, tmp_path):
    def transport(args):
        Path(args[args.index("--receipt") + 1]).write_text(json.dumps({"readback_verified": False}))
        return 0

    install_transport(monkeypatch, transport)
    assert supervisor.main(launch_args(tmp_path, "backup")) == 1
    assert progress(tmp_path)["error_code"] == "backup_readback_not_verified"


@pytest.mark.parametrize("kind,expected", [("sdk", "ValueError"), ("controlled", "redacted_failure")])
def test_main_error_output_never_contains_credentials(supervisor, sandbox, monkeypatch, tmp_path,
                                                      capsys, kind, expected):
    def transport(_):
        error = "diagnostic with " + FAKE_SECRETS["R2_SECRET_ACCESS_KEY"]
        raise ValueError(error) if kind == "sdk" else supervisor.MigrationError(error)

    install_transport(monkeypatch, transport)
    assert supervisor.main(launch_args(tmp_path, "backup")) == 1
    assert progress(tmp_path)["error_code"] == expected
    output = capsys.readouterr().out + (tmp_path / "job/migration_status.json").read_text()
    assert all(value not in output for value in FAKE_SECRETS.values())


@pytest.mark.parametrize("returncode", [0, 1])
def test_dependency_install_strips_all_secrets_and_keeps_output_private(supervisor, monkeypatch,
                                                                      tmp_path, capsys, returncode):
    repo = tmp_path / "repo"
    log = tmp_path / "private-install.log"

    def run(command, **kwargs):
        assert command[:4] == [sys.executable, "-m", "pip", "install"]
        assert command[-1] == str(repo / "requirements-q15-runtime.txt")
        assert all(name not in kwargs["env"] for name in FAKE_SECRETS)
        assert kwargs["stderr"] == supervisor.subprocess.STDOUT
        kwargs["stdout"].write(b"synthetic private installation detail\n")
        return types.SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(supervisor.subprocess, "run", run)
    if returncode:
        with pytest.raises(supervisor.MigrationError, match="scientific_dependency_install_failed"):
            supervisor.install_scientific_runtime(repo, log)
    else:
        supervisor.install_scientific_runtime(repo, log)
    assert "synthetic private" in log.read_text()
    assert "synthetic private" not in capsys.readouterr().out


def test_from_r2_uses_no_archive_and_continues_only_after_ready(supervisor, sandbox, monkeypatch,
                                                              tmp_path):
    events = []
    monkeypatch.setattr(supervisor, 'check_destination_identity',
                        lambda manual_stop=False: events.append('identity') or 'new_fake_test_pod')
    monkeypatch.setattr(supervisor, 'check_cuda_template', lambda: events.append('gpu'))
    install_transport(monkeypatch, lambda *_: pytest.fail('No archive transport is needed'))

    def restore(workspace, job_id, job, log, installer):
        events.append('r2_restore')
        assert workspace == sandbox and job_id == 'new-test-job'
        assert job == tmp_path / 'job' and log == tmp_path / 'private-dependencies.log'
        assert installer is supervisor.install_scientific_runtime
        return {'ready_for_continuation': True}

    def run(command, **kwargs):
        events.append('continuation')
        assert Path(command[1]).name == 'q15_continue_validated.py'
        assert 'q15_full_job.py' not in command and kwargs['check'] is False
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setitem(sys.modules, 'q15_restore_from_r2', types.SimpleNamespace(restore_from_r2=restore))
    monkeypatch.setattr(supervisor.subprocess, 'run', run)
    assert supervisor.main(launch_args(tmp_path, 'from-r2')) == 0
    assert events == ['identity', 'gpu', 'r2_restore', 'continuation']
    assert progress(tmp_path)['scientific_completion_requires_job_report'] is True


def test_from_r2_incomplete_restore_never_starts_scientific_worker(supervisor, sandbox,
                                                                monkeypatch, tmp_path):
    monkeypatch.setattr(supervisor, 'check_destination_identity', lambda manual_stop=False: 'new_fake_test_pod')
    install_transport(monkeypatch, lambda *_: pytest.fail('No archive transport'))
    monkeypatch.setitem(sys.modules, 'q15_restore_from_r2', types.SimpleNamespace(
        restore_from_r2=lambda *_: {'ready_for_continuation': False}))
    monkeypatch.setattr(supervisor.subprocess, 'run', lambda *_a, **_k: pytest.fail('No worker'))
    assert supervisor.main(launch_args(tmp_path, 'from-r2')) == 1
    assert progress(tmp_path)['error_code'] == 'r2_restoration_not_ready'


def test_wrong_cuda_template_blocks_r2_download(supervisor, sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(supervisor, 'check_destination_identity', lambda manual_stop=False: 'new_fake_test_pod')

    def reject():
        raise supervisor.MigrationError('pinned_pytorch_cuda_template_required')

    monkeypatch.setattr(supervisor, 'check_cuda_template', reject)
    monkeypatch.setitem(sys.modules, 'q15_restore_from_r2', types.SimpleNamespace(
        restore_from_r2=lambda *_: pytest.fail('No R2 downloads')))
    install_transport(monkeypatch, lambda *_: pytest.fail('No archive'))
    assert supervisor.main(launch_args(tmp_path, 'from-r2')) == 1
    assert progress(tmp_path)['error_code'] == 'pinned_pytorch_cuda_template_required'


def test_child_inherits_existing_migration_lock_descriptor(supervisor, monkeypatch):
    monkeypatch.setattr(supervisor.os, 'fstat', lambda fd: object() if fd == 9 else pytest.fail())
    assert supervisor.continuation_descriptor_options() == {'pass_fds': (9,)}


def test_no_descriptor_is_required_for_direct_unit_orchestration(supervisor, monkeypatch):
    monkeypatch.setattr(supervisor.os, 'fstat', lambda _: (_ for _ in ()).throw(OSError()))
    assert supervisor.continuation_descriptor_options() == {}
