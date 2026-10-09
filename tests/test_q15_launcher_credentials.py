"""Exercise the real credential shell block without installation or training.

Every credential used here is an explicit fake. Terminal tests use a real
controlling PTY, including the case where standard input is redirected.
"""
import errno
import json
import os
import pty
import select
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "research_runs/Q15-EXECUTION-20261003/LAUNCH_Q15_ON_RUNPOD.sh"
FAKE_GH = "FAKEGH_TEST_ONLY_Q15_abcdefghijklmnop"
FAKE_RUNPOD = "FAKERUNPOD_TEST_ONLY_Q15_zyxwvutsrqponmlk"


@pytest.fixture
def credential_program():
    text = LAUNCHER.read_text()
    begin = "# Q15_CREDENTIALS_BEGIN"
    end = "# Q15_CREDENTIALS_END"
    assert text.count(begin) == text.count(end) == 1
    block = text.split(begin, 1)[1].split(end, 1)[0]
    return "\n".join([
        "set -euo pipefail",
        'Q15_RESET_CREDENTIALS="${Q15_TEST_RESET:-0}"',
        block,
        # Disable tracing for the test-only equality checker as well.
        "set +x",
        "python3 -c 'import json, os; print(json.dumps({",
        '"test_credentials_match": os.environ.get("GH_TOKEN") == os.environ["Q15_TEST_EXPECT_GH"]',
        'and os.environ.get("RUNPOD_API_KEY") == os.environ["Q15_TEST_EXPECT_RUNPOD"],',
        '"test_gh_length": len(os.environ.get("GH_TOKEN", "")),',
        '"test_runpod_length": len(os.environ.get("RUNPOD_API_KEY", ""))}))\'',
    ])


def _environment(credentials=None, reset=False):
    # No real credential or shell initialization environment is inherited.
    return {
        "PATH": os.environ["PATH"],
        "LC_ALL": "C",
        "TERM": "dumb",
        "Q15_TEST_RESET": "1" if reset else "0",
        "Q15_TEST_EXPECT_GH": FAKE_GH,
        "Q15_TEST_EXPECT_RUNPOD": FAKE_RUNPOD,
        **(credentials or {}),
    }


class TerminalRun:
    def __init__(self, program, credentials=None, *, reset=False,
                 redirect_stdin=False, trace=False):
        self.master, slave = pty.openpty()

        args = ["bash", "-x", "-c", program] if trace else ["bash", "-c", program]
        # Establish the controlling terminal after a normal process spawn,
        # avoiding preexec_fn and its hazards in threaded pytest workers.
        controller = (
            "import fcntl, os, sys, termios; "
            "fcntl.ioctl(1, termios.TIOCSCTTY, 0); "
            "os.execvp(sys.argv[1], sys.argv[1:])"
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", controller, *args],
            stdin=subprocess.DEVNULL if redirect_stdin else slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
            env=_environment(credentials, reset),
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

    def submit(self, provider, value):
        deadline = time.monotonic() + 4
        variable = "GH_TOKEN" if provider == "GitHub" else "RUNPOD_API_KEY"
        needle = (variable + " (hidden;").encode()
        while needle not in self.output[self.cursor:]:
            if self.process.poll() is not None or time.monotonic() > deadline:
                pytest.fail("Credential prompt did not arrive")
            self._read()
        self.cursor = len(self.output)
        # Prove that hiding is active before supplying any fake credential.
        deadline = time.monotonic() + 1
        while termios.tcgetattr(self.master)[3] & termios.ECHO:
            if time.monotonic() > deadline:
                pytest.fail("Credential terminal input was not hidden")
            time.sleep(0.005)
        os.write(self.master, value.encode() + b"\n")

    def eof(self, provider):
        deadline = time.monotonic() + 4
        variable = "GH_TOKEN" if provider == "GitHub" else "RUNPOD_API_KEY"
        while (variable + " (hidden;").encode() not in self.output[self.cursor:]:
            if self.process.poll() is not None or time.monotonic() > deadline:
                pytest.fail("Credential prompt did not arrive before EOF")
            self._read()
        self.cursor = len(self.output)
        os.write(self.master, b"\x04")

    def finish(self):
        deadline = time.monotonic() + 4
        while self.process.poll() is None:
            if time.monotonic() > deadline:
                pytest.fail("Credential collection did not terminate")
            self._read()
        while self._read(0.02):
            pass
        return self.process.returncode, self.output.decode(errors="replace")

    def close(self):
        if self.closed:
            return
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        os.close(self.master)
        self.closed = True


@pytest.fixture
def terminal(credential_program):
    runs = []

    def start(credentials=None, **kwargs):
        run = TerminalRun(credential_program, credentials, **kwargs)
        runs.append(run)
        return run

    yield start
    for run in runs:
        run.close()


def _assert_success(result):
    returncode, output = result
    assert returncode == 0
    public_receipts = [json.loads(line) for line in output.splitlines()
                       if line.startswith('{"stage":"credential_input"')]
    assert public_receipts == [{"stage": "credential_input",
                               "status": "values_present_not_api_validated",
                               "present": {"GH_TOKEN": True, "RUNPOD_API_KEY": True},
                               "fits_started": 0}]
    receipts = [json.loads(line) for line in output.splitlines()
                if line.startswith('{"test_credentials_match"')]
    assert receipts == [{"test_credentials_match": True,
                         "test_gh_length": len(FAKE_GH),
                         "test_runpod_length": len(FAKE_RUNPOD)}]
    assert FAKE_GH not in output
    assert FAKE_RUNPOD not in output
    return output


def _assert_failure(result, missing, code):
    returncode, output = result
    assert returncode != 0
    receipts = [json.loads(line) for line in output.splitlines()
                if line.startswith('{"status":"NOT_STARTED"')]
    assert receipts == [{"status": "NOT_STARTED", "error_code": code + ":" + missing,
                         "fits_started": 0}]
    assert "test_credentials_match" not in output
    assert FAKE_GH not in output and FAKE_RUNPOD not in output
    return output


def test_blank_github_retries_with_inherited_runpod(terminal):
    run = terminal({"RUNPOD_API_KEY": FAKE_RUNPOD})
    run.submit("GitHub", "")
    run.submit("GitHub", FAKE_GH)
    output = _assert_success(run.finish())
    assert "RunPod" not in output


def test_both_missing_are_collected_without_echo(terminal):
    run = terminal()
    run.submit("GitHub", FAKE_GH)
    run.submit("RunPod", FAKE_RUNPOD)
    _assert_success(run.finish())


def test_whitespace_environment_is_missing(terminal):
    run = terminal({"GH_TOKEN": " \t\r\n", "RUNPOD_API_KEY": " \t "})
    run.submit("GitHub", FAKE_GH)
    run.submit("RunPod", FAKE_RUNPOD)
    _assert_success(run.finish())


def test_internal_whitespace_environment_is_rejected(terminal):
    run = terminal({"GH_TOKEN": "FAKE GITHUB VALUE", "RUNPOD_API_KEY": FAKE_RUNPOD})
    run.submit("GitHub", FAKE_GH)
    _assert_success(run.finish())


def test_internal_whitespace_input_retries(terminal):
    run = terminal({"RUNPOD_API_KEY": FAKE_RUNPOD})
    run.submit("GitHub", "FAKE GITHUB VALUE")
    run.submit("GitHub", FAKE_GH)
    output = _assert_success(run.finish())
    assert "whitespace-containing input" in output
    assert "FAKE GITHUB VALUE" not in output


@pytest.mark.parametrize("source", ["environment", "terminal"])
def test_surrounding_whitespace_is_trimmed(terminal, source):
    gh = " \t" + FAKE_GH + "\r "
    runpod = "\t " + FAKE_RUNPOD + " \r"
    run = terminal({"GH_TOKEN": gh, "RUNPOD_API_KEY": runpod}
                   if source == "environment" else None)
    if source == "terminal":
        # A literal CR is a terminal line delimiter, so use spaces and tabs.
        run.submit("GitHub", " \t" + FAKE_GH + "\t ")
        run.submit("RunPod", " \t" + FAKE_RUNPOD + "\t ")
    _assert_success(run.finish())


def test_reset_requests_both_values_even_when_environment_is_valid(terminal):
    run = terminal({"GH_TOKEN": "OLD_FAKE_GH", "RUNPOD_API_KEY": "OLD_FAKE_RUNPOD"},
                   reset=True)
    run.submit("GitHub", FAKE_GH)
    run.submit("RunPod", FAKE_RUNPOD)
    _assert_success(run.finish())


def test_redirected_stdin_uses_controlling_terminal(terminal):
    run = terminal(redirect_stdin=True)
    run.submit("GitHub", FAKE_GH)
    run.submit("RunPod", FAKE_RUNPOD)
    _assert_success(run.finish())


@pytest.mark.parametrize("trace", [False, True])
def test_existing_credentials_work_without_terminal(credential_program, trace):
    args = ["bash", "-x", "-c", credential_program] if trace else ["bash", "-c", credential_program]
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True,
                            env=_environment({"GH_TOKEN": FAKE_GH,
                                              "RUNPOD_API_KEY": FAKE_RUNPOD}), timeout=4,
                            check=False)
    _assert_success((result.returncode, result.stdout.decode()))


@pytest.mark.parametrize("credentials, missing", [
    ({"RUNPOD_API_KEY": FAKE_RUNPOD}, "GH_TOKEN"),
    ({"GH_TOKEN": FAKE_GH}, "RUNPOD_API_KEY"),
    ({"GH_TOKEN": " \t ", "RUNPOD_API_KEY": FAKE_RUNPOD}, "GH_TOKEN"),
])
def test_missing_credentials_without_terminal_fail_closed(credential_program, credentials, missing):
    result = subprocess.run(["bash", "-c", credential_program], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True, env=_environment(credentials), timeout=4,
                            check=False)
    _assert_failure((result.returncode, result.stdout.decode()), missing,
                    "interactive_terminal_required")


@pytest.mark.parametrize("missing, provider, credentials", [
    ("GH_TOKEN", "GitHub", {"RUNPOD_API_KEY": FAKE_RUNPOD}),
    ("RUNPOD_API_KEY", "RunPod", {"GH_TOKEN": FAKE_GH}),
])
def test_three_blank_attempts_fail_with_missing_variable(terminal, missing, provider, credentials):
    run = terminal(credentials)
    for value in ("", " \t ", ""):
        run.submit(provider, value)
    _assert_failure(run.finish(), missing, "credential_required")


@pytest.mark.parametrize("missing, provider, credentials", [
    ("GH_TOKEN", "GitHub", {"RUNPOD_API_KEY": FAKE_RUNPOD}),
    ("RUNPOD_API_KEY", "RunPod", {"GH_TOKEN": FAKE_GH}),
])
def test_terminal_eof_fails_without_spawning_worker(terminal, missing, provider, credentials):
    run = terminal(credentials)
    run.eof(provider)
    _assert_failure(run.finish(), missing, "credential_input_interrupted")


def test_shell_xtrace_never_prints_prompted_credentials(terminal):
    run = terminal(trace=True)
    run.submit("GitHub", FAKE_GH)
    run.submit("RunPod", FAKE_RUNPOD)
    _assert_success(run.finish())


def test_missing_credentials_are_checked_before_git_and_dependencies():
    text = LAUNCHER.read_text()
    assert text.index("flock -n 9") < text.index("# Q15_CREDENTIALS_BEGIN")
    assert text.index("# Q15_CREDENTIALS_END") < text.index("git init")
    assert text.index("# Q15_CREDENTIALS_END") < text.index("-m pip install")
