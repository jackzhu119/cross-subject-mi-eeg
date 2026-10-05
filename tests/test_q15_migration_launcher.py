"""Run the migration launcher in Bash with synthetic, offline child programs.

No SDK installation, GPU work, network request, model fit, or Pod action occurs.
Only explicit fake credentials are supplied; child observations record names
and equality checks, never their values. The detached child keeps the actual
Bash lock descriptor open so duplicate prevention is tested across processes.
"""

import errno
import hashlib
import json
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "research_runs/Q15-MIGRATION-20261004/Q15_MIGRATE_ON_RUNPOD.sh"
HELPERS = (
    "q15_migration_bundle.py",
    "q15_migration_transport.py",
    "q15_continue_validated.py",
    "q15_migration_supervisor.py",
    "q15_restore_from_r2.py",
    "requirements-migration.txt",
)
R2_NAMES = (
    "R2_BUCKET",
    "R2_ENDPOINT",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)
REQUIRED_NAMES = (*R2_NAMES, "GH_TOKEN", "RUNPOD_API_KEY")
AUTH_NAMES = ("GH_TOKEN", "RUNPOD_API_KEY")
SECRET_NAMES = (*REQUIRED_NAMES, "GITHUB_TOKEN")
FAKES = {name: "FAKE_TEST_ONLY_" + name + "_abcdefghijklmnop" for name in SECRET_NAMES}


def _wait_file(path, timeout=4):
    deadline = time.monotonic() + timeout
    while not path.is_file():
        if time.monotonic() > deadline:
            pytest.fail("Offline child did not publish its test observation")
        time.sleep(0.01)
    return json.loads(path.read_text())


class OfflineLauncher:
    def __init__(self, base):
        self.base = base
        self.private_root = base / "root"
        self.workspace = base / "workspace"
        self.bin = base / "bin"
        self.payload = base / "payload"
        self.observations = base / "observations.jsonl"
        self.release = base / "release-worker"
        for folder in (self.private_root, self.workspace, self.bin, self.payload):
            folder.mkdir()
        text = LAUNCHER.read_text().replace(
            "__Q15_MIGRATION_HELPER_REVISION__", "a" * 40
        )
        # Redirect only absolute operational directories, leaving the actual
        # credential, quoting, subprocess, checksum, and lock code intact.
        text = text.replace("/root/", str(self.private_root) + "/")
        text = text.replace("/workspace/", str(self.workspace) + "/")
        self.launcher = base / "offline-launch.sh"
        self.launcher.write_text(text)
        self.processes = []
        self.terminals = []
        self._write_payload()
        self._write_children()

    def _write_payload(self):
        expected_hashes = {
            name: hashlib.sha256(value.encode()).hexdigest()
            for name, value in FAKES.items()
        }
        worker = "\n".join([
            "import fcntl, hashlib, json, os, pathlib, sys, time",
            "expected = " + repr(expected_hashes),
            "names = " + repr(SECRET_NAMES),
            "arguments = sys.argv[1:]",
            "if arguments[0] == 'check-accounts':",
            "    observations = pathlib.Path(os.environ['Q15_TEST_OBSERVATIONS'])",
            "    prior = [json.loads(line) for line in observations.read_text().splitlines()] if observations.exists() else []",
            "    attempt = sum(row['kind'] == 'accounts' for row in prior)",
            "    configured = json.loads(os.environ.get('Q15_TEST_AUTH_STATUSES', '{}'))",
            "    providers = {}",
            "    for provider in ('github', 'runpod'):",
            "        statuses = configured.get(provider, [200])",
            "        providers[provider] = statuses[min(attempt, len(statuses) - 1)]",
            "    receipt = {",
            "        'kind': 'accounts', 'arguments': arguments, 'statuses': providers,",
            "        'secret_names': [name for name in names if name in os.environ],",
            "        'trimmed_matches': {name: hashlib.sha256(os.environ.get(name, '').encode()).hexdigest() == expected[name] for name in names if name in os.environ},",
            "        'system_python': os.environ['Q15_TEST_RUNTIME_PATH'] == os.environ['Q15_TEST_SYSTEM_RUNTIME']}",
            "    with observations.open('a') as stream:",
            "        stream.write(json.dumps(receipt) + '\\n')",
            "    response = {'status': 'accounts_preflight_verified', 'pod_id': os.environ['RUNPOD_POD_ID'], 'new_source_fits': 0, 'target_fits': 0}",
            "    for provider, status in providers.items():",
            "        if status != 200:",
            "            response.update(status='accounts_preflight_failed', error_code=provider + '_account_api_http_' + str(status))",
            "            print(json.dumps(response, separators=(',', ':')))",
            "            sys.exit(1)",
            "    print(json.dumps(response, separators=(',', ':')))",
            "    sys.exit(0)",
            "directory = pathlib.Path(arguments[arguments.index('--job-directory') + 1])",
            "receipt = {",
            "'mode': arguments[0], 'arguments': arguments, 'pid': os.getpid(),",
            "'present': [name for name in names if name in os.environ],",
            "'trimmed_matches': {name: hashlib.sha256(os.environ.get(name, '').encode()).hexdigest() == expected[name] for name in names if name in os.environ},",
            "'fd9_open': fcntl.fcntl(9, fcntl.F_GETFD) >= 0}",
            "temporary = directory / 'worker_observation.tmp'",
            "temporary.write_text(json.dumps(receipt))",
            "temporary.replace(directory / 'worker_observation.json')",
            "release = pathlib.Path(os.environ['Q15_TEST_RELEASE'])",
            "deadline = time.monotonic() + 12",
            "while not release.exists() and time.monotonic() < deadline:",
            "    time.sleep(0.02)",
        ])
        for name in HELPERS:
            content = worker if name == "q15_migration_supervisor.py" else "# offline test fixture\n"
            (self.payload / name).write_text(content)
        checksums = "".join(
            hashlib.sha256((self.payload / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in HELPERS
        )
        (self.payload / "SHA256SUMS").write_text(checksums)

    def _write_children(self):
        common = "\n".join([
            "import json, os, pathlib, shutil, sys",
            "secret_names = " + repr(SECRET_NAMES),
            "def observe(kind, **other):",
            "    row = {'kind': kind, 'secret_names': [name for name in secret_names if name in os.environ], **other}",
            "    with open(os.environ['Q15_TEST_OBSERVATIONS'], 'a') as stream:",
            "        stream.write(json.dumps(row) + '\\n')",
        ])
        curl = "\n".join([
            "#!" + sys.executable,
            common,
            "arguments = sys.argv[1:]",
            "url = arguments[arguments.index('-o') - 1]",
            "name = url.rsplit('/', 1)[-1]",
            "observe('curl', name=name, url=url)",
            "source = pathlib.Path(os.environ['Q15_TEST_PAYLOAD']) / name",
            "destination = pathlib.Path(arguments[arguments.index('-o') + 1])",
            "shutil.copyfile(source, destination)",
        ])
        runtime = "\n".join([
            "#!" + sys.executable,
            common,
            "arguments = sys.argv[1:]",
            "if arguments[:2] == ['-m', 'venv']:",
            "    observe('venv')",
            "    target = pathlib.Path(arguments[-1]) / 'bin' / 'python'",
            "    target.parent.mkdir(parents=True)",
            "    shutil.copyfile(__file__, target)",
            "    target.chmod(0o700)",
            "elif arguments[:2] == ['-m', 'pip']:",
            "    observe('pip')",
            "    sys.exit(int(os.environ.get('Q15_TEST_PIP_FAIL', '0')))",
            "else:",
            "    os.environ['Q15_TEST_RUNTIME_PATH'] = str(pathlib.Path(__file__).resolve())",
            "    os.execv(sys.executable, [sys.executable, *arguments])",
        ])
        for name, content in (("curl", curl), ("python3", runtime)):
            script = self.bin / name
            script.write_text(content)
            script.chmod(0o700)

    def environment(self, credentials=None, *, pip_fail=False, auth_statuses=None):
        # Deliberately inherit no real cloud or GitHub credentials.
        return {
            "PATH": str(self.bin) + ":" + os.environ["PATH"],
            "LC_ALL": "C",
            "TERM": "dumb",
            "RUNPOD_POD_ID": "offline_test_new_pod",
            "Q15_TEST_PAYLOAD": str(self.payload),
            "Q15_TEST_OBSERVATIONS": str(self.observations),
            "Q15_TEST_RELEASE": str(self.release),
            "Q15_TEST_PIP_FAIL": "1" if pip_fail else "0",
            "Q15_TEST_AUTH_STATUSES": json.dumps(auth_statuses or {}),
            "Q15_TEST_SYSTEM_RUNTIME": str((self.bin / 'python3').resolve()),
            **(credentials or {}),
        }

    def run(self, *arguments, credentials=None, trace=False, pip_fail=False, auth_statuses=None):
        command = ["bash", *(["-x"] if trace else []), str(self.launcher), *arguments]
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=self.environment(credentials, pip_fail=pip_fail, auth_statuses=auth_statuses),
            timeout=4,
            check=False,
        )
        return result.returncode, result.stdout.decode()

    def terminal(
        self, *arguments, credentials=None, redirect_stdin=False, trace=False, auth_statuses=None
    ):
        run = TerminalRun(self, arguments, credentials, redirect_stdin, trace, auth_statuses)
        self.terminals.append(run)
        return run

    def worker(self, job_id="offline-job"):
        return _wait_file(
            self.workspace / "q15-migration/jobs" / job_id / "worker_observation.json"
        )

    def child_observations(self):
        return [json.loads(line) for line in self.observations.read_text().splitlines()]

    def assert_no_stored_credentials(self):
        for folder in (self.private_root, self.workspace):
            for path in folder.rglob("*"):
                if path.is_file():
                    content = path.read_bytes()
                    assert all(value.encode() not in content for value in FAKES.values())

    def close(self):
        self.release.touch()
        for terminal in self.terminals:
            terminal.close()
        # Give actual nohup children time to close FD 9; a bounded fallback
        # targets only PIDs whose identity came from our private test fixture.
        for path in self.workspace.rglob("worker_observation.json"):
            pid = json.loads(path.read_text())["pid"]
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            else:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


class TerminalRun:
    def __init__(self, fixture, arguments, credentials, redirect_stdin, trace, auth_statuses):
        self.master, slave = pty.openpty()
        self.return_receipt = fixture.base / "terminal-return-code.json"
        command = [
            "bash", *(["-x"] if trace else []), str(fixture.launcher), *arguments
        ]
        controller = (
            "import fcntl, json, os, pathlib, subprocess, sys, termios, time; "
            "fcntl.ioctl(1, termios.TIOCSCTTY, 0); "
            # Jupyter's existing interactive shell remains the session owner
            # after a launcher subprocess returns. Keep that terminal owner
            # alive until cleanup, rather than turning the launcher itself
            # into a session leader whose exit instantly hangs up its tty.
            "result = subprocess.run(sys.argv[1:], check=False); "
            "pathlib.Path(os.environ['Q15_TEST_TERMINAL_RECEIPT']).write_text(json.dumps(result.returncode)); "
            "release = pathlib.Path(os.environ['Q15_TEST_RELEASE']); "
            "deadline = time.monotonic() + 12; "
            "exec('while not release.exists() and time.monotonic() < deadline:\\n    time.sleep(0.02)')"
        )
        environment = fixture.environment(credentials, auth_statuses=auth_statuses)
        environment["Q15_TEST_TERMINAL_RECEIPT"] = str(self.return_receipt)
        self.process = subprocess.Popen(
            [sys.executable, "-c", controller, *command],
            stdin=subprocess.DEVNULL if redirect_stdin else slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
            env=environment,
        )
        os.close(slave)
        self.output = b""
        self.cursor = 0
        self.closed = False

    def _read(self, timeout=0.1):
        if not select.select([self.master], [], [], timeout)[0]:
            return False
        try:
            chunk = os.read(self.master, 65536)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return False
            raise
        self.output += chunk
        return bool(chunk)

    def submit(self, name, value):
        needle = (name + " (hidden;").encode()
        deadline = time.monotonic() + 4
        while needle not in self.output[self.cursor:]:
            if self.process.poll() is not None or time.monotonic() > deadline:
                pytest.fail("Hidden migration credential prompt did not arrive")
            self._read()
        self.cursor = len(self.output)
        deadline = time.monotonic() + 1
        while termios.tcgetattr(self.master)[3] & termios.ECHO:
            if time.monotonic() > deadline:
                pytest.fail("Migration credential prompt did not disable echo")
            time.sleep(0.005)
        os.write(self.master, value.encode() + b"\n")

    def finish(self):
        deadline = time.monotonic() + 4
        while not self.return_receipt.exists():
            if time.monotonic() > deadline:
                pytest.fail("Offline migration launcher did not exit")
            self._read()
        while self._read(0.02):
            pass
        return json.loads(self.return_receipt.read_text()), self.output.decode(errors="replace")

    def close(self):
        if self.closed:
            return
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        os.close(self.master)
        self.closed = True


@pytest.fixture
def offline(tmp_path):
    fixture = OfflineLauncher(tmp_path)
    yield fixture
    fixture.close()


def _assert_started(result, mode):
    code, output = result
    assert code == 0, output
    assert all(value not in output for value in FAKES.values())
    receipts = [
        json.loads(line) for line in output.splitlines()
        if line.startswith('{"status":"detached_migration')
    ]
    assert len(receipts) == 1
    assert receipts[0]["operation"] == mode
    assert receipts[0]["job_id"] == "offline-job"
    assert receipts[0]["new_source_fits"] == receipts[0]["target_fits"] == 0


def _assert_setup_children_are_private(offline, *, accounts=True):
    observations = offline.child_observations()
    checks = [row for row in observations if row["kind"] == "accounts"]
    assert bool(checks) is accounts
    for row in observations:
        if row["kind"] == "accounts":
            assert row["secret_names"] == list(AUTH_NAMES)
            assert row["arguments"] == ["check-accounts"]
            assert row["system_python"] is True
        else:
            assert row["secret_names"] == []
    return checks


@pytest.mark.parametrize("trace", [False, True])
def test_from_r2_environment_is_trimmed_and_setup_children_have_no_secrets(offline, trace):
    credentials = {name: " \t" + value + "\r " for name, value in FAKES.items()}
    _assert_started(
        offline.run("from-r2", "--job-id", "offline-job", credentials=credentials, trace=trace),
        "from-r2",
    )
    worker = offline.worker()
    assert worker["present"] == list(REQUIRED_NAMES)
    assert all(worker["trimmed_matches"].values())
    assert worker["fd9_open"] is True
    assert "--object-key" not in worker["arguments"]
    observations = offline.child_observations()
    assert [row["name"] for row in observations if row["kind"] == "curl"] == [
        *HELPERS, "SHA256SUMS"
    ]
    checks = _assert_setup_children_are_private(offline)
    assert len(checks) == 1
    assert all(checks[0]["trimmed_matches"].values())
    assert [row["kind"] for row in observations] == [
        *["curl"] * 7, "accounts", "venv", "pip"
    ]
    offline.assert_no_stored_credentials()


@pytest.mark.parametrize("redirect_stdin", [False, True])
def test_real_terminal_collects_all_six_without_echo_and_retries_blank(offline, redirect_stdin):
    run = offline.terminal(
        "from-r2", "--job-id", "offline-job", redirect_stdin=redirect_stdin, trace=True
    )
    for name in AUTH_NAMES:
        run.submit(name, " \t" + FAKES[name] + "\t ")
    run.submit("R2_BUCKET", "")
    for name in R2_NAMES:
        run.submit(name, " \t" + FAKES[name] + "\t ")
    _assert_started(run.finish(), "from-r2")
    worker = offline.worker()
    assert worker["present"] == list(REQUIRED_NAMES)
    assert all(worker["trimmed_matches"].values())
    _assert_setup_children_are_private(offline)
    offline.assert_no_stored_credentials()


def test_invalid_internal_whitespace_retries_and_is_not_printed(offline):
    credentials = {name: value for name, value in FAKES.items() if name != "GH_TOKEN"}
    credentials["GH_TOKEN"] = "FAKE BAD VALUE"
    run = offline.terminal("from-r2", "--job-id", "offline-job", credentials=credentials)
    run.submit("GH_TOKEN", "FAKE BAD INPUT")
    run.submit("GH_TOKEN", FAKES["GH_TOKEN"])
    result = run.finish()
    _assert_started(result, "from-r2")
    assert "FAKE BAD INPUT" not in result[1] and "FAKE BAD VALUE" not in result[1]
    assert offline.worker()["trimmed_matches"]["GH_TOKEN"] is True


def test_three_blank_attempts_after_public_download_do_not_install_or_start(offline):
    credentials = {name: value for name, value in FAKES.items() if name != "GH_TOKEN"}
    run = offline.terminal("from-r2", "--job-id", "offline-job", credentials=credentials)
    for value in ("", " \t ", ""):
        run.submit("GH_TOKEN", value)
    code, output = run.finish()
    assert code != 0
    assert "Missing required credential: GH_TOKEN" in output
    assert all(value not in output for value in FAKES.values())
    assert [row["kind"] for row in offline.child_observations()] == ["curl"] * 7
    assert all(row["secret_names"] == [] for row in offline.child_observations())
    assert not list(offline.workspace.rglob("worker_observation.json"))
    offline.assert_no_stored_credentials()


def test_missing_credentials_without_terminal_fail_after_public_download(offline):
    code, output = offline.run("from-r2", "--job-id", "offline-job")
    assert code != 0
    assert "interactive terminal is required" in output
    assert [row["kind"] for row in offline.child_observations()] == ["curl"] * 7
    assert all(row["secret_names"] == [] for row in offline.child_observations())
    assert not list(offline.workspace.rglob("worker_observation.json"))


@pytest.mark.parametrize("provider,name", [
    ("github", "GH_TOKEN"), ("runpod", "RUNPOD_API_KEY")
])
@pytest.mark.parametrize("status", [401, 403, 404])
def test_foreground_auth_rejection_retries_only_provider_before_any_r2_input(
    offline, provider, name, status
):
    # Neither an R2 prompt nor SDK setup may occur while account access fails.
    credentials = {key: FAKES[key] for key in AUTH_NAMES if key != name}
    run = offline.terminal(
        "from-r2", "--job-id", "offline-job", credentials=credentials, trace=True,
        auth_statuses={provider: [status]},
    )
    for _ in range(3):
        run.submit(name, FAKES[name])
    code, output = run.finish()
    assert code != 0
    assert provider + "_account_api_http_" + str(status) in output
    assert "detached_migration" not in output
    assert output.count(name + " (hidden;") == 3
    assert all(other + " (hidden;" not in output for other in SECRET_NAMES if other != name)
    assert all(value not in output for value in FAKES.values())
    checks = _assert_setup_children_are_private(offline)
    assert len(checks) == 3
    assert all(row["statuses"][provider] == status for row in checks)
    assert {row["kind"] for row in offline.child_observations()} == {"curl", "accounts"}
    assert not (offline.workspace / "q15-migration/jobs").exists()
    offline.assert_no_stored_credentials()


def test_inherited_runpod_403_reprompts_only_runpod_and_preserves_other_credentials(offline):
    rejected = "FAKE_REJECTED_INHERITED_RUNPOD_TOKEN_abcdefghijklmnop"
    credentials = {**FAKES, "RUNPOD_API_KEY": rejected}
    run = offline.terminal(
        "from-r2", "--job-id", "offline-job", credentials=credentials, trace=True,
        auth_statuses={"runpod": [403, 200]},
    )
    run.submit("RUNPOD_API_KEY", " \t" + FAKES["RUNPOD_API_KEY"] + "\r ")
    result = run.finish()
    _assert_started(result, "from-r2")
    assert rejected not in result[1]
    assert result[1].count("RUNPOD_API_KEY (hidden;") == 1
    assert all(name + " (hidden;" not in result[1] for name in SECRET_NAMES if name != "RUNPOD_API_KEY")
    checks = _assert_setup_children_are_private(offline)
    assert len(checks) == 2
    assert checks[0]["trimmed_matches"] == {"GH_TOKEN": True, "RUNPOD_API_KEY": False}
    assert all(checks[1]["trimmed_matches"].values())
    assert offline.worker()["present"] == list(REQUIRED_NAMES)
    assert all(offline.worker()["trimmed_matches"].values())
    assert [row["kind"] for row in offline.child_observations()] == [
        *["curl"] * 7, "accounts", "accounts", "venv", "pip"
    ]
    offline.assert_no_stored_credentials()


def test_inherited_rejected_token_without_terminal_does_not_install_or_detach(offline):
    code, output = offline.run(
        "from-r2", "--job-id", "offline-job", credentials=FAKES,
        auth_statuses={"runpod": [403]},
    )
    assert code != 0
    assert "runpod_account_api_http_403" in output
    assert "interactive terminal is required" in output
    assert "detached_migration" not in output
    assert len(_assert_setup_children_are_private(offline)) == 1
    assert {row["kind"] for row in offline.child_observations()} == {"curl", "accounts"}
    assert not (offline.workspace / "q15-migration/jobs").exists()


@pytest.mark.parametrize("name", REQUIRED_NAMES)
def test_reset_credential_forces_only_named_inherited_value_to_be_prompted(offline, name):
    run = offline.terminal(
        "from-r2", "--job-id", "offline-job", "--reset-credential", name,
        credentials=FAKES, trace=True,
    )
    run.submit(name, " \t" + FAKES[name] + "\t ")
    result = run.finish()
    _assert_started(result, "from-r2")
    assert result[1].count(name + " (hidden;") == 1
    assert all(other + " (hidden;" not in result[1] for other in SECRET_NAMES if other != name)
    assert all(offline.worker()["trimmed_matches"].values())
    assert len(_assert_setup_children_are_private(offline)) == 1
    offline.assert_no_stored_credentials()


def test_reset_credential_is_repeatable_and_other_inherited_values_survive(offline):
    run = offline.terminal(
        "from-r2", "--job-id", "offline-job",
        "--reset-credential", "GH_TOKEN", "--reset-credential", "RUNPOD_API_KEY",
        "--reset-credential", "R2_BUCKET", "--reset-credential", "GH_TOKEN",
        credentials=FAKES,
    )
    for name in (*AUTH_NAMES, "R2_BUCKET"):
        run.submit(name, FAKES[name])
    result = run.finish()
    _assert_started(result, "from-r2")
    for name in (*AUTH_NAMES, "R2_BUCKET"):
        assert result[1].count(name + " (hidden;") == 1
    assert all(name + " (hidden;" not in result[1] for name in SECRET_NAMES if name not in (*AUTH_NAMES, "R2_BUCKET"))
    assert all(offline.worker()["trimmed_matches"].values())
    _assert_setup_children_are_private(offline)


@pytest.mark.parametrize("name", ["GITHUB_TOKEN", "UNKNOWN", "gh_token", "GH_TOKEN=value"])
def test_reset_credential_rejects_unknown_names_before_any_child(offline, name):
    code, output = offline.run(
        "from-r2", "--job-id", "offline-job", "--reset-credential", name,
        credentials=FAKES,
    )
    assert code != 0
    assert "credential name" in output.lower()
    assert not offline.observations.exists()
    assert not (offline.workspace / "q15-migration/jobs").exists()


@pytest.mark.parametrize("with_unused_tokens", [False, True])
def test_backup_needs_only_four_r2_values_and_does_not_forward_unused_tokens(
    offline, with_unused_tokens
):
    credentials = FAKES if with_unused_tokens else {name: FAKES[name] for name in R2_NAMES}
    _assert_started(
        offline.run("backup", "--job-id", "offline-job", credentials=credentials), "backup"
    )
    worker = offline.worker()
    assert worker["present"] == list(R2_NAMES)
    assert all(worker["trimmed_matches"].values())
    _assert_setup_children_are_private(offline, accounts=False)
    offline.assert_no_stored_credentials()


def test_checksum_mismatch_prevents_sdk_install_and_worker(offline):
    (offline.payload / "q15_restore_from_r2.py").write_text("# corrupted fixture\n")
    code, output = offline.run("from-r2", "--job-id", "offline-job", credentials=FAKES)
    assert code != 0
    assert "FAILED" in output
    assert {row["kind"] for row in offline.child_observations()} == {"curl"}
    assert not list(offline.workspace.rglob("worker_observation.json"))
    offline.assert_no_stored_credentials()


def test_sdk_install_failure_prevents_worker_and_log_contains_no_secrets(offline):
    code, output = offline.run(
        "from-r2", "--job-id", "offline-job", credentials=FAKES, pip_fail=True
    )
    assert code != 0
    assert "S3 client installation failed" in output
    _assert_setup_children_are_private(offline)
    assert not list(offline.workspace.rglob("worker_observation.json"))
    offline.assert_no_stored_credentials()


@pytest.mark.parametrize("job_id", ["../outside", "bad/name", "bad\nname", "$(touch sentinel)"])
def test_invalid_job_id_is_rejected_before_any_child(offline, job_id):
    code, output = offline.run("from-r2", "--job-id", job_id, credentials=FAKES)
    assert code != 0
    assert "Invalid migration job ID" in output
    assert not offline.observations.exists()


def test_restore_object_key_is_preserved_as_one_argument_without_shell_execution(offline):
    marker = offline.base / "shell-execution-must-not-happen"
    object_key = "q15/migrations/archive;$(touch " + str(marker) + ")"
    digest = "b" * 64
    _assert_started(
        offline.run(
            "restore", "--job-id", "offline-job", "--object-key", object_key,
            "--archive-sha256", digest, credentials=FAKES,
        ),
        "restore",
    )
    arguments = offline.worker()["arguments"]
    assert arguments[arguments.index("--object-key") + 1] == object_key
    assert arguments[arguments.index("--archive-sha256") + 1] == digest
    assert not marker.exists()


@pytest.mark.parametrize("arguments", [
    ("restore",),
    ("restore", "--object-key", "q15/migrations/test", "--archive-sha256", "wrong"),
    ("restore", "--object-key", "wrong-prefix", "--archive-sha256", "b" * 64),
])
def test_restore_requires_archive_identity_before_children(offline, arguments):
    code, output = offline.run(*arguments, credentials=FAKES)
    assert code != 0
    assert "verified backup object key and SHA256" in output
    assert not offline.observations.exists()


def test_detached_worker_retains_lock_after_launcher_exit(offline):
    _assert_started(
        offline.run("from-r2", "--job-id", "offline-job", credentials=FAKES), "from-r2"
    )
    worker = offline.worker()
    assert worker["fd9_open"] is True
    original_observations = offline.observations.read_text()
    code, output = offline.run("from-r2", "--job-id", "another-job", credentials=FAKES)
    assert code != 0
    assert "migration worker is already active" in output
    assert offline.observations.read_text() == original_observations
    assert not (offline.workspace / "q15-migration/jobs/another-job").exists()
