"""Small, independent GitHub progress writer. Never imports the training runtime.

Only aggregate progress JSON is sent to api.github.com. A token is acquired with
getpass once for each project and stored outside its project tree. Training does
not call this loop or depend on upload success.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import email.utils
import fcntl
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


DEFAULT_REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
DEFAULT_PROJECT_ID = "paper1-risk-v1"
DEFAULT_TOKEN = Path.home() / ".config/mi-eeg/paper1-hpc-20261023/token"
API_ROOT = "https://api.github.com"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _atomic_json(path, value, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if private:
                os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class CredentialError(RuntimeError):
    """A user-correctable initial credential or repository configuration error."""


class GitHubError(RuntimeError):
    def __init__(self, code, status=None, retry_after=None, permanent=False):
        super().__init__(code)
        self.code, self.status = code, status
        self.retry_after, self.permanent = retry_after, permanent


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _retry_seconds(headers):
    value = headers.get("Retry-After")
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            when = email.utils.parsedate_to_datetime(value)
            seconds = when.timestamp() - time.time()
        except (ValueError, TypeError, AttributeError):
            try:
                seconds = float(headers.get("X-RateLimit-Reset", "0")) - time.time()
            except (ValueError, TypeError):
                seconds = 0
    return max(1.0, min(900.0, seconds)) if seconds > 0 else None


def _api_curl(method, endpoint, token, payload=None):
    """One IPv4 HTTPS attempt, with credentials only in curl's stdin config.

    The optional login-side transport follows the same error semantics as urllib.
    It never falls back after a write or retries a possibly committed request.
    """
    if not endpoint.startswith("/repos/") or "://" in endpoint:
        raise ValueError("Only repository API paths are supported")
    config = ["header = " + json.dumps("Authorization: Bearer " + token),
              'header = "Accept: application/vnd.github+json"',
              'header = "Content-Type: application/json"',
              'header = "X-GitHub-Api-Version: 2022-11-28"',
              'user-agent = "paper1-hpc-progress/1"']
    if payload is not None:
        config.append("data = " + json.dumps(json.dumps(payload, allow_nan=False)))
    descriptor, header_path = tempfile.mkstemp(prefix="paper1-github-headers-", suffix=".tmp")
    os.close(descriptor)  # mkstemp creates mode 0600; it never contains the token.
    try:
        # -q must be first: local .curlrc must not enable redirects or disable TLS.
        arguments = ["curl", "-q", "-4", "--silent", "--show-error", "--config", "-",
                     "--connect-timeout", "8", "--max-time", "20", "--max-filesize", "2000000",
                     "--request", method, "--dump-header", header_path,
                     "--write-out", "\n%{http_code}", API_ROOT + endpoint]
        try:
            response = subprocess.run(arguments, input=("\n".join(config) + "\n").encode(),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      timeout=25, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise GitHubError("github_network_unavailable") from None
        if response.returncode:
            if response.returncode == 63:
                raise GitHubError("github_response_too_large", permanent=True)
            # Curl stderr can contain proxies or response text; never render it.
            raise GitHubError("github_network_unavailable")
        body, separator, code = response.stdout.rpartition(b"\n")
        if not separator or not re.fullmatch(rb"[1-5][0-9][0-9]", code):
            raise GitHubError("github_invalid_http_response")
        status = int(code)
        if len(body) > 2_000_000:
            raise GitHubError("github_response_too_large", permanent=True)
        headers = {}
        selected = {"retry-after": "Retry-After", "x-ratelimit-remaining": "X-RateLimit-Remaining",
                    "x-ratelimit-reset": "X-RateLimit-Reset"}
        with open(header_path, "rb") as stream:
            raw_headers = stream.read(65537)
        if len(raw_headers) > 65536:
            raise GitHubError("github_invalid_http_response")
        for line in raw_headers.decode("iso-8859-1").splitlines():
            if line.startswith("HTTP/"):
                headers = {}  # Ignore any preceding proxy CONNECT header block.
            elif ":" in line:
                key, value = line.split(":", 1)
                if key.lower() in selected:
                    headers[selected[key.lower()]] = value.strip()
        if not 200 <= status < 300:
            limited = status == 429 or (status == 403 and
                      (headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in headers))
            if limited:
                raise GitHubError("github_rate_limited", status, _retry_seconds(headers), False)
            permanent = status in (400, 401, 403, 404) or 300 <= status < 400
            error = "github_conflict_retry_next_cycle" if status in (409, 422) else "github_http_" + str(status)
            raise GitHubError(error, status, _retry_seconds(headers), permanent)
        try:
            return json.loads(body) if body else {}
        except (ValueError, UnicodeError):
            raise GitHubError("github_invalid_json_response") from None
    finally:
        try:
            os.unlink(header_path)
        except FileNotFoundError:
            pass


def _api(method, endpoint, token, payload=None):
    """One HTTPS attempt; no redirects, secret-bearing URLs or response dumps."""
    if not endpoint.startswith("/repos/") or "://" in endpoint:
        raise ValueError("Only repository API paths are supported")
    if os.environ.get("PAPER1_GITHUB_TRANSPORT", "urllib") == "curl":
        return _api_curl(method, endpoint, token, payload)
    request = urllib.request.Request(
        API_ROOT + endpoint,
        data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
        method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "paper1-hpc-progress/1"})
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise GitHubError("github_response_too_large", permanent=True)
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        status = error.code
        limited = status == 429 or (status == 403 and
                  (error.headers.get("X-RateLimit-Remaining") == "0" or
                   error.headers.get("Retry-After") is not None))
        # Do not read or log an error response body or Location header.
        if limited:
            raise GitHubError("github_rate_limited", status,
                              _retry_seconds(error.headers), False) from None
        permanent = status in (400, 401, 403, 404) or 300 <= status < 400
        code = "github_conflict_retry_next_cycle" if status in (409, 422) else "github_http_" + str(status)
        raise GitHubError(code, status, _retry_seconds(error.headers), permanent) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GitHubError("github_network_unavailable") from None
    except (ValueError, UnicodeError):
        raise GitHubError("github_invalid_json_response") from None


def _validate_destination(repository, project_id, branch=None, remote_path=None):
    if not _REPO.fullmatch(repository) or not _ID.fullmatch(project_id):
        raise ValueError("Invalid repository or project identifier")
    branch = branch or "hpc/" + project_id
    remote_path = remote_path or "hpc_status/" + project_id + "/status.json"
    if branch != "hpc/" + project_id or remote_path != "hpc_status/" + project_id + "/status.json":
        raise ValueError("Progress must use this project's dedicated hpc branch and status path")
    return branch, remote_path


def _ensure_branch(repository, branch, token):
    base = "/repos/" + repository
    ref = "/git/ref/heads/" + urllib.parse.quote(branch, safe="")
    try:
        _api("GET", base + ref, token)
        return
    except GitHubError as error:
        if error.status != 404:
            raise
    repo = _api("GET", base, token)
    default = repo.get("default_branch")
    if not isinstance(default, str) or not default:
        raise GitHubError("github_default_branch_missing", permanent=True)
    source = _api("GET", base + "/git/ref/heads/" + urllib.parse.quote(default, safe=""), token)
    source_sha = source.get("object", {}).get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40,64}", source_sha):
        raise GitHubError("github_source_commit_missing", permanent=True)
    _api("POST", base + "/git/refs", token,
         {"ref": "refs/heads/" + branch, "sha": source_sha})


def _put_json(repository, branch, remote_path, token, value):
    endpoint = "/repos/" + repository + "/contents/" + urllib.parse.quote(remote_path, safe="/")
    current_sha = None
    try:
        existing = _api("GET", endpoint + "?" + urllib.parse.urlencode({"ref": branch}), token)
        current_sha = existing.get("sha")
    except GitHubError as error:
        if error.status != 404:
            raise
    content = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    data = {"message": "Update " + branch + " progress", "branch": branch,
            "content": base64.b64encode(content).decode("ascii")}
    if current_sha:
        data["sha"] = current_sha
    result = _api("PUT", endpoint, token, data)
    commit = result.get("commit", {}).get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise GitHubError("github_write_commit_missing")
    return commit


def _read_token(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise CredentialError("Token file must be a regular private file (chmod 600)")
    token = path.read_text(encoding="utf-8").strip()
    if not token or any(c.isspace() for c in token):
        raise CredentialError("GitHub token must be a nonempty single value")
    return token


def _write_token(path, token):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".token-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(token + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _verify_written_json(repository, remote_path, token, commit, value):
    """Read the exact written commit; compare bytes and the Git blob identity."""
    endpoint = "/repos/" + repository + "/contents/" + urllib.parse.quote(remote_path, safe="/")
    result = _api("GET", endpoint + "?" + urllib.parse.urlencode({"ref": commit}), token)
    expected = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    encoded = result.get("content")
    if (result.get("type") != "file" or result.get("encoding") != "base64"
            or not isinstance(encoded, str) or len(encoded) > 65536):
        raise GitHubError("github_write_readback_invalid", permanent=True)
    try:
        content = base64.b64decode("".join(encoded.split()), validate=True)
    except (ValueError, TypeError):
        raise GitHubError("github_write_readback_invalid", permanent=True) from None
    expected_blob = hashlib.sha1(b"blob " + str(len(expected)).encode() + b"\0" + expected).hexdigest()
    if (content != expected or result.get("size") != len(expected)
            or result.get("sha") != expected_blob):
        raise GitHubError("github_write_readback_mismatch", permanent=True)
    return hashlib.sha256(expected).hexdigest()


def confirm_credentials(repository, project_id, credential_path=None, *, force=False,
                        require_verified=False):
    """Acquire a private token, optionally requiring fresh write/readback proof.

    Normal training keeps reporting outages independent. Explicit reauthorization
    always prompts and only replaces an existing token after a successful live
    write and exact commit readback. Strict verification never accepts a pending
    or cached authorization as proof of current GitHub connectivity.
    """
    branch, _ = _validate_destination(repository, project_id)
    path = Path(credential_path or DEFAULT_TOKEN).expanduser().absolute()
    authorization_path = path.parent / "project_authorizations.json"
    try:
        records = json.loads(authorization_path.read_text())
    except FileNotFoundError:
        records = {"schema_version": 1, "projects": {}}
    key = repository + ":" + project_id
    existing = _read_token(path) if path.exists() or path.is_symlink() else None
    fingerprint = hashlib.sha256(existing.encode()).hexdigest() if existing else None
    saved = records.get("projects", {}).get(key, {})
    strict = force or require_verified
    if not strict and fingerprint and saved.get("token_sha256") == fingerprint:
        if saved.get("status") == "INITIAL_WRITE_PENDING":
            print(json.dumps({"github_authorization": "INITIAL_WRITE_PENDING", "project_id": project_id,
                              "remote_write_verified": False,
                              "training_dependency": "Cached token reused; remote upload retries independently"}), flush=True)
        return path
    if force:
        token = getpass.getpass("GitHub Contents-write token (hidden; fresh input required): ").strip()
    elif strict and existing:
        token = existing
    else:
        prompt = "GitHub Contents-write token (hidden"
        prompt += "; Enter reuses the existing private token): " if existing else "): "
        entered = getpass.getpass(prompt).strip()
        token = entered or existing
    if not token or any(c.isspace() for c in token):
        raise CredentialError("A nonempty GitHub token is required; forced reauthorization cannot reuse blank input")
    # Normal offline-tolerant startup retains its previous token acquisition
    # semantics. A forced/strict attempt leaves the working token untouched.
    if not strict:
        _write_token(path, token)
    state = {"repository": repository, "project_id": project_id,
             "authorized_at_utc": _now(), "token_sha256": hashlib.sha256(token.encode()).hexdigest()}
    remote_path = "hpc_status/" + project_id + "/connection.json"
    connection = {"schema_version": 1, "project_id": project_id,
                  "status": "CONTENTS_WRITE_VERIFIED", "observed_at_utc": _now()}
    if strict:
        connection["authorization_nonce"] = uuid.uuid4().hex
    try:
        _ensure_branch(repository, branch, token)
        commit = _put_json(repository, branch, remote_path, token, connection)
        state.update(status="CONTENTS_WRITE_VERIFIED", commit=commit)
        if strict:
            content_sha = _verify_written_json(repository, remote_path, token, commit, connection)
            state.update(status="CONTENTS_WRITE_READBACK_VERIFIED", readback_verified=True,
                         connection_sha256=content_sha)
    except GitHubError as error:
        if strict or error.permanent:
            detail = "). Existing private credentials were retained; " if strict else "). "
            raise CredentialError("GitHub authorization failed (" + error.code + detail +
                                  "Check repository Contents permission and connectivity.") from None
        state.update(status="INITIAL_WRITE_PENDING", error_code=error.code)
    if strict:
        _write_token(path, token)
    records.setdefault("projects", {})[key] = state
    _atomic_json(authorization_path, records, private=True)
    public = {"github_authorization": state["status"], "project_id": project_id,
              "remote_write_verified": state["status"] != "INITIAL_WRITE_PENDING",
              "training_dependency": "Live GitHub write/readback verified" if strict else
                                     "Token acquired; remote upload retries independently"}
    if strict:
        public.update(commit=state["commit"], readback_verified=True,
                      connection_sha256=state["connection_sha256"])
    print(json.dumps(public), flush=True)
    return path


_NUMBERS = {"epoch", "step", "global_step", "updates", "optimizer_updates", "samples_seen",
            "processed_samples", "train_loss", "loss", "best_epoch", "n", "n_trials",
            "n_subjects", "n_participants", "balanced_accuracy", "weaker_class_recall",
            "ba", "min_recall", "recall_left", "recall_right", "ce", "mean", "std",
            "difference", "difference_pp", "p_value", "p_holm", "ci_low", "ci_high",
            "seed", "fold", "selected_epoch", "completed_tasks", "total_tasks",
            "processed_evaluation_samples", "training_samples", "step_in_epoch", "resume_from_step",
            "epochs_completed", "n_seeds", "effect", "effect_pp", "ci95_low_pp", "ci95_high_pp",
            "p_raw", "improved", "declined", "numerically_unchanged", "mean_percent",
            "bootstrap_replicates", "permutation_replicates", "secondary_family_size",
            "source_equal_cohort_mean_min_recall", "completed_fits", "pending_fits",
            "max_concurrent_fits", "stop_requested_exit_code", "completed_objects", "total_objects",
            "requested_gpus"}
_STRINGS = {"status", "stage", "phase", "method", "endpoint", "metric", "variant", "task_id",
            "updated_at_utc", "started_at_utc", "completed_at_utc", "finished_at_utc",
            "domain", "contrast", "family", "aggregation", "bootstrap", "permutation", "evaluation_variant",
            "requested_memory", "slurm_job_id", "submission_status"}
_BOOLS = {"all_comparison_directions_retained", "independent_external_confirmation"}
_CONTAINERS = {"metrics", "validation", "test_metrics", "statistics", "summary", "results",
               "conditions", "comparisons", "by_method", "primary", "secondary", "evaluation",
               "fixed40", "selected", "source_selected", "outer", "development", "final",
               "domains", "nested_outer", "external_fixed40", "external_source_selected", "method_means", "active_children"}


def _safe_stats(value, depth=0):
    if depth > 5 or not isinstance(value, dict):
        return {}
    clean = {}
    for key, item in value.items():
        if key in _NUMBERS and isinstance(item, (int, float)) and not isinstance(item, bool) and (isinstance(item, int) or math.isfinite(item)):
            clean[key] = item
        elif key in _STRINGS and isinstance(item, str) and len(item) <= 80 and re.fullmatch(r"[A-Za-z0-9_.:+ /-]+", item):
            clean[key] = item
        elif key in _BOOLS and type(item) is bool:
            clean[key] = item
        elif key in _CONTAINERS:
            if isinstance(item, dict):
                nested = _safe_stats(item, depth + 1)
                # Method-name keys are allowed only inside an explicit grouping.
                if key in {"by_method", "conditions", "results"}:
                    nested.update({name: _safe_stats(body, depth + 1) for name, body in item.items()
                                   if _ID.fullmatch(str(name)) and isinstance(body, dict)})
                if nested:
                    clean[key] = nested
            elif isinstance(item, list):
                clean[key] = [_safe_stats(row, depth + 1) for row in item[:500] if isinstance(row, dict)]
    return clean


def _read_json_optional(path):
    try:
        if path.stat().st_size > 2_000_000:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, UnicodeError):
        return None


def collect_progress(project):
    project = Path(project)
    tasks = []
    for folder in sorted((project / "outputs/runs").glob("*")):
        if not folder.is_dir() or not _ID.fullmatch(folder.name):
            continue
        status = _read_json_optional(folder / "status.json")
        completed = _read_json_optional(folder / "complete.json")
        row = {"task_id": folder.name, **_safe_stats(status or {})}
        if completed:
            row["completion_record_present"] = True
            row["completed_statistics"] = _safe_stats(completed)
            row["complete"] = str(completed.get("status", "")).upper() in {"COMPLETE", "COMPLETED"} or completed.get("complete") is True
        tasks.append(row)
    plan = _read_json_optional(project / "tasks.json")
    counts = {"planned": len(plan) if isinstance(plan, list) else None,
              "observed": len(tasks), "completed": sum(row.get("complete", False) for row in tasks),
              "failed": sum("FAIL" in str(row.get("status", row.get("stage", ""))).upper() for row in tasks)}
    result = {"schema_version": 1, "project_id": project.name, "updated_at_utc": _now(),
              "counts": counts, "tasks": tasks,
              "observation_scope": "Saved task steps and summaries; not independent proof of current GPU activity"}
    execution = _read_json_optional(project / "state/single_job_status.json")
    if execution:
        result["execution"] = _safe_stats(execution)
    preparation = _read_json_optional(project / "state/login_pipeline_status.json")
    if preparation:
        result["preparation"] = _safe_stats(preparation)
        paths = _read_json_optional(project / "config/paths.json") or {}
        raw_dir = Path(paths.get("raw_dir", project / "raw"))
        transport = _read_json_optional(raw_dir / "transport_status.json")
        if transport:
            result["transport"] = _safe_stats(transport)
    analysis = _read_json_optional(project / "outputs/analysis/summary.json")
    if analysis:
        result["completed_statistics"] = _safe_stats(analysis)
    return result


@contextlib.contextmanager
def _lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def sync_once(project, repository, branch, remote_path, token_path):
    """One attempt. Return a safe status even when GitHub is unavailable."""
    project = Path(project)
    project_id = branch.removeprefix("hpc/")
    _validate_destination(repository, project_id, branch, remote_path)
    state = {"updated_at_utc": _now(), "repository": repository,
             "branch": branch, "path": remote_path, "training_blocked": False}
    try:
        with _lock(project / "state/github_sync_once.lock"):
            token = _read_token(token_path)
            _ensure_branch(repository, branch, token)
            report = collect_progress(project)
            report["project_id"] = project_id
            commit = _put_json(repository, branch, remote_path, token, report)
            state.update(status="SYNCED", commit=commit, counts=report["counts"])
    except BlockingIOError:
        return {**state, "status": "OTHER_SYNC_WRITER_ACTIVE"}
    except GitHubError as error:
        state.update(status="PAUSED_AUTH_OR_CONFIG" if error.permanent else "RETRY_PENDING",
                     error_code=error.code, http_status=error.status, retry_after_seconds=error.retry_after)
    except (CredentialError, FileNotFoundError):
        state.update(status="PAUSED_AUTH_OR_CONFIG", error_code="private_token_missing_or_invalid")
    except Exception as error:
        # Preserve only the type: arbitrary exception text can contain tokens/paths.
        state.update(status="RETRY_PENDING", error_code="sync_" + type(error).__name__)
    try:
        _atomic_json(project / "state/github_sync_status.json", state)
    except OSError:
        state["local_status_write_failed"] = True
    return state


def _token_signature(path):
    try:
        info = Path(path).stat()
        return info.st_ino, info.st_size, info.st_mtime_ns
    except OSError:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--branch", default="hpc/" + DEFAULT_PROJECT_ID)
    parser.add_argument("--path", default="hpc_status/" + DEFAULT_PROJECT_ID + "/status.json")
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=180)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.interval < 1:
        parser.error("interval must be positive")
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    failures, paused_signature, paused = 0, None, False
    try:
        with _lock(args.project / "state/github_sync_daemon.lock"):
            while running:
                signature = _token_signature(args.token_file)
                if paused and signature == paused_signature:
                    delay = args.interval
                else:
                    state = sync_once(args.project, args.repository, args.branch, args.path, args.token_file)
                    print(json.dumps(state, sort_keys=True), flush=True)
                    if args.once:
                        return 0  # Reporting failure cannot terminate model training.
                    if state["status"] == "SYNCED":
                        failures, paused_signature, paused, delay = 0, None, False, args.interval
                    elif state["status"] == "PAUSED_AUTH_OR_CONFIG":
                        paused_signature, paused, delay = signature, True, args.interval
                    else:
                        failures += 1
                        delay = min(900, max(state.get("retry_after_seconds") or 0,
                                             args.interval * 2 ** min(failures - 1, 4)))
                deadline = time.monotonic() + delay
                while running and time.monotonic() < deadline:
                    time.sleep(max(0, min(1, deadline - time.monotonic())))
    except BlockingIOError:
        print(json.dumps({"status": "SYNC_DAEMON_ALREADY_RUNNING"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
