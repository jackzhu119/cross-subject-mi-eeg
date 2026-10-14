#!/usr/bin/env python3
"""Private credential handling and verified publication; no training or Pod API.

GitHub receives explicitly selected small evidence artifacts, completed source
checkpoints and narrowly typed target-logit output files. Raw EEG, cached model
inputs, in-flight training state and credential files never enter a Git tree.
Checkpoint backup to R2 is optional and is verified by complete byte readback,
not by accepting an upload or trusting object metadata.
"""
from __future__ import annotations

import argparse
import ast
import base64
import getpass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
import time
import warnings
import zipfile
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


REPO = "jackzhu119/cross-subject-mi-eeg"
JOB_PREFIX = "research_runs/REDESIGN_CLOUD_20261013/jobs"
R2_NAMES = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
MAX_GITHUB_BYTES = 50 * 1024 * 1024
MAX_GITHUB_TOTAL_BYTES = 200 * 1024 * 1024
ALLOWED_SUFFIXES = {".json", ".md", ".csv", ".tsv", ".txt", ".log", ".yaml", ".yml", ".sha256", ".png", ".svg", ".pdf"}
RAW_SUFFIXES = {".edf", ".bdf", ".gdf", ".mat", ".fif", ".npz", ".npy", ".h5", ".hdf5"}
R2_ALLOWED_SUFFIXES = ALLOWED_SUFFIXES | {".pt", ".pth", ".ckpt", ".joblib"}
SECRET_BASENAME = re.compile(r"(?:^|[._-])(?:credentials?|secrets?|tokens?|env)(?:[._-]|$)", re.I)
CHECKPOINT_PATH = re.compile(r"source/(?:inner|final)/(?:[A-Za-z0-9_.-]+/)+checkpoint\.pt\Z")
TARGET_CELL_PATH = re.compile(r"target/cells/[A-Za-z0-9_.-]+\.npz\Z")


class TransportError(RuntimeError):
    """Errors expose only a fixed code and deliberately nonsensitive details."""

    def __init__(self, code: str, *, http_status: int | None = None, partial_receipt: dict | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.partial_receipt = partial_receipt


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _is_checkpoint(name: str) -> bool:
    return bool(CHECKPOINT_PATH.fullmatch(name))


def _is_target_output(name: str) -> bool:
    return name == "target/raw_logits.npz" or bool(TARGET_CELL_PATH.fullmatch(name))


def _prediction_npz_only(data: bytes, name: str) -> None:
    """Inspect bounded NPY headers without unpickling or importing ML software."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > 40 or len({info.filename for info in infos}) != len(infos):
                raise TransportError("publication_prediction_output_schema_invalid")
            if sum(info.file_size for info in infos) > MAX_GITHUB_BYTES:
                raise TransportError("publication_prediction_output_size_limit")
            shapes, dtypes = {}, {}
            for info in infos:
                if not re.fullmatch(r"[A-Za-z0-9_:-]+\.npy", info.filename) or info.file_size < 16:
                    raise TransportError("publication_prediction_output_schema_invalid")
                with archive.open(info) as stream:
                    magic = stream.read(8)
                    if magic[:6] != b"\x93NUMPY" or magic[6:8] not in (b"\x01\x00", b"\x02\x00", b"\x03\x00"):
                        raise TransportError("publication_prediction_output_schema_invalid")
                    version = magic[6]
                    length_bytes = stream.read(2 if version == 1 else 4)
                    if len(length_bytes) != (2 if version == 1 else 4):
                        raise TransportError("publication_prediction_output_schema_invalid")
                    length = struct.unpack("<H" if version == 1 else "<I", length_bytes)[0]
                    if length > 4096:
                        raise TransportError("publication_prediction_output_schema_invalid")
                    header = ast.literal_eval(stream.read(length).decode("utf-8" if version == 3 else "latin1"))
                if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
                    raise TransportError("publication_prediction_output_schema_invalid")
                key = info.filename[:-4]
                shapes[key], dtypes[key] = header["shape"], header["descr"]
            if "event_ids" not in shapes or not isinstance(shapes["event_ids"], tuple) or len(shapes["event_ids"]) != 1 or not isinstance(shapes["event_ids"][0], int) or shapes["event_ids"][0] <= 0:
                raise TransportError("publication_prediction_output_schema_invalid")
            if not isinstance(dtypes["event_ids"], str) or not re.fullmatch(r"[<>=|][US]\d+", dtypes["event_ids"]):
                raise TransportError("publication_prediction_output_schema_invalid")
            count = shapes["event_ids"][0]
            logits = set(shapes) - {"event_ids"}
            if not logits or name != "target/raw_logits.npz" and logits != {"logits"}:
                raise TransportError("publication_prediction_output_schema_invalid")
            if any(shapes[key] != (count, 2) or dtypes[key] not in {"<f4", ">f4", "=f4", "<f8", ">f8", "=f8"} for key in logits):
                raise TransportError("publication_prediction_output_schema_invalid")
    except TransportError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile, EOFError, struct.error, SyntaxError):
        raise TransportError("publication_prediction_output_schema_invalid") from None


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise TransportError("artifact_path_invalid")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in ("..", ".", "") for part in value.split("/")):
        raise TransportError("artifact_path_invalid")
    return str(parsed)


def _ensure_private_directory(directory: Path) -> Path:
    directory = directory.absolute()
    # A RunPod network volume can return successful chmod while retaining 777.
    # Credentials must live on a private local filesystem instead.
    if directory == Path("/workspace") or Path("/workspace") in directory.parents:
        raise TransportError("credential_directory_network_volume_forbidden")
    for parent in (directory, *directory.parents):
        if parent.exists() and parent.is_symlink():
            raise TransportError("credential_directory_symlink_forbidden")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    info = directory.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
        raise TransportError("credential_directory_permissions_unsafe")
    return directory


def private_credential_root(private_root: str | Path | None = None) -> Path:
    if private_root is not None:
        return _ensure_private_directory(Path(private_root))
    candidates = [Path.home() / ".local/share/mi-eeg-cloud", Path(tempfile.gettempdir()) / f"mi-eeg-cloud-private-{os.getuid()}"]
    for candidate in candidates:
        try:
            return _ensure_private_directory(candidate)
        except (OSError, TransportError):
            continue
    raise TransportError("no_private_local_credential_directory")


def _load_private_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if path.is_symlink():
        raise TransportError("credential_cache_symlink_forbidden")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise TransportError("credential_cache_permissions_unsafe")
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise TransportError("credential_cache_unreadable") from None
    allowed = {"GH_TOKEN", *R2_NAMES}
    if not isinstance(cached, dict) or not set(cached).issubset(allowed) or any(not isinstance(x, str) for x in cached.values()):
        raise TransportError("credential_cache_schema_invalid")
    return cached


def _save_private_cache(path: Path, values: Mapping[str, str]) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    temp_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
            raise TransportError("credential_cache_permissions_unsafe")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(_canonical_json(dict(values)))
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise TransportError("credential_cache_symlink_forbidden")
        os.replace(temp_path, path)
        _load_private_cache(path)  # Verify permissions after creation, not just chmod's exit status.
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temp_path.unlink(missing_ok=True)


def secure_credentials(*, require_github: bool = True, enable_r2: bool = False, reset: bool = False,
                       private_root: str | Path | None = None, prompt: Callable[[str], str] = getpass.getpass,
                       environ: Mapping[str, str] | None = None, interactive: bool = True) -> dict[str, str]:
    """Read env/local-private-cache/hidden input, never RunPod API or workspace cache.

    Nothing is API-validated here. Returned values are private and callers must
    never serialize them into receipts, exceptions, logs or GitHub artifacts.
    """
    root = private_credential_root(private_root)
    path = root / "credentials.json"
    values = {} if reset else _load_private_cache(path)
    environment = os.environ if environ is None else environ
    names = (["GH_TOKEN"] if require_github else []) + (list(R2_NAMES) if enable_r2 else [])
    for name in names:
        value = environment.get(name, "").strip() or values.get(name, "").strip()
        if not value and interactive:
            for attempt in range(1, 4):
                try:
                    # getpass otherwise falls back to echoed stdin when it
                    # cannot disable terminal echo. Never permit that fallback.
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", getpass.GetPassWarning)
                        value = prompt(f"{name} (hidden; {attempt}/3): ").strip()
                except (EOFError, KeyboardInterrupt):
                    raise TransportError("credential_input_cancelled") from None
                except getpass.GetPassWarning:
                    raise TransportError("hidden_credential_terminal_unavailable") from None
                if value:
                    break
        if not value:
            raise TransportError(f"required_credential_not_provided:{name}")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise TransportError(f"credential_format_invalid:{name}")
        values[name] = value
    if enable_r2:
        endpoint = urlsplit(values["R2_ENDPOINT"])
        if endpoint.scheme != "https" or not endpoint.hostname or not endpoint.hostname.endswith(".r2.cloudflarestorage.com") or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise TransportError("r2_endpoint_format_invalid")
        bucket = values["R2_BUCKET"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise TransportError("r2_bucket_format_invalid")
    _save_private_cache(path, values)
    # R2 entries retained locally for reuse but do not silently enable R2 calls.
    return {name: values[name] for name in names}


class GitHubAPI:
    def __init__(self, token: str, *, opener: Callable = urlopen, sleeper: Callable[[float], None] = time.sleep, attempts: int = 4):
        self._token = token
        self._opener = opener
        self._sleeper = sleeper
        self._attempts = attempts

    def __call__(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not path.startswith("/repos/") or "?" in path and "access_token" in path or "\n" in path:
            raise TransportError("github_api_path_invalid")
        data = None if payload is None else _canonical_json(payload)
        request = Request("https://api.github.com" + path, data=data, method=method,
                          headers={"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json",
                                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "mi-eeg-verified-evidence-publisher"})
        for attempt in range(self._attempts):
            try:
                with self._opener(request, timeout=120) as response:
                    parsed = json.loads(response.read())
                if not isinstance(parsed, dict):
                    raise TransportError("github_response_schema_invalid")
                return parsed
            except HTTPError as error:
                status = error.code
                error.close()
                if status not in (408, 429, 500, 502, 503, 504) or attempt + 1 == self._attempts:
                    raise TransportError(f"github_http_{status}", http_status=status) from None
            except (URLError, TimeoutError, OSError):
                if attempt + 1 == self._attempts:
                    raise TransportError("github_network_error") from None
            except (ValueError, UnicodeError):
                raise TransportError("github_response_invalid") from None
            self._sleeper(min(2 ** attempt, 8))
        raise TransportError("github_request_unfinished")


def public_bytes(url: str, *, opener: Callable = urlopen, sleeper: Callable[[float], None] = time.sleep) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com" or parsed.query or parsed.fragment:
        raise TransportError("public_readback_url_invalid")
    for attempt in range(4):
        try:
            with opener(Request(url, headers={"User-Agent": "mi-eeg-public-byte-verification"}), timeout=120) as response:
                data = response.read(MAX_GITHUB_BYTES + 1)
            if len(data) > MAX_GITHUB_BYTES:
                raise TransportError("public_readback_size_limit")
            return data
        except HTTPError as error:
            status = error.code
            error.close()
            # An immediately created public commit can take a moment to reach raw CDN.
            if status not in (404, 408, 429, 500, 502, 503, 504) or attempt == 3:
                raise TransportError(f"public_readback_http_{status}", http_status=status) from None
        except (URLError, TimeoutError, OSError):
            if attempt == 3:
                raise TransportError("public_readback_network_error") from None
        sleeper(min(2 ** attempt, 8))
    raise TransportError("public_readback_unfinished")


class GitHubPublisher:
    def __init__(self, token: str, *, repo: str = REPO, request: Callable | None = None,
                 get_public: Callable[[str], bytes] = public_bytes, secret_values: Sequence[str] = ()):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise TransportError("github_repo_invalid")
        self.repo = repo
        self._request = request or GitHubAPI(token)
        self._get_public = get_public
        self._secret_values = tuple(x.encode() for x in (token, *secret_values) if x)

    def _api(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        return self._request(method, f"/repos/{self.repo}" + endpoint, payload)

    def _read_inventory(self, prefix: str, commit: str) -> dict:
        try:
            response = self._api("GET", f"/contents/{prefix}/publication_manifest.json?ref={commit}")
        except TransportError as error:
            if error.http_status == 404:
                return {}
            raise
        try:
            parsed = json.loads(base64.b64decode(response["content"], validate=False))
            if not isinstance(parsed, dict):
                raise TransportError("publication_inventory_invalid")
            return parsed
        except (KeyError, TypeError, ValueError):
            raise TransportError("publication_inventory_invalid") from None

    def publish_snapshot(self, *, job_id: str, base_commit: str, local_root: str | Path,
                         relative_paths: Sequence[str], message: str, verify_public: bool = True,
                         immutable_paths: Sequence[str] = ()) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,110}", job_id) or not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            raise TransportError("publication_identity_invalid")
        if not relative_paths or len(set(relative_paths)) != len(relative_paths):
            raise TransportError("publication_artifacts_empty_or_duplicate")
        if not message.strip() or len(message) > 500 or any(secret.decode() in message for secret in self._secret_values):
            raise TransportError("publication_message_invalid")
        root = Path(local_root).resolve()
        artifacts: dict[str, bytes] = {}
        records: dict[str, dict] = {}
        frozen = {_safe_relative(path) for path in immutable_paths}
        for name in relative_paths:
            name = _safe_relative(name)
            path = root / name
            if name == "publication_manifest.json" or SECRET_BASENAME.search(path.name) or any(SECRET_BASENAME.search(part) for part in PurePosixPath(name).parts):
                raise TransportError("publication_sensitive_path_forbidden")
            if path.suffix.lower() not in ALLOWED_SUFFIXES and not _is_checkpoint(name) and not _is_target_output(name):
                raise TransportError("publication_artifact_type_forbidden")
            if path.is_symlink() or root not in path.resolve().parents or not path.is_file():
                raise TransportError("publication_artifact_missing_or_symlink")
            if path.stat().st_size > MAX_GITHUB_BYTES:
                raise TransportError("publication_artifact_size_limit")
            data = path.read_bytes()
            if len(data) > MAX_GITHUB_BYTES:
                raise TransportError("publication_artifact_size_limit")
            if any(secret in data for secret in self._secret_values):
                raise TransportError("publication_secret_content_forbidden")
            if _is_checkpoint(name):
                receipt_path = path.parent / "fit_receipt.json"
                try:
                    fit_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raise TransportError("publication_checkpoint_not_completed") from None
                if not isinstance(fit_receipt, dict) or fit_receipt.get("status") != "completed" or fit_receipt.get("checkpoint_sha256") != _sha(data):
                    raise TransportError("publication_checkpoint_not_completed")
            if _is_target_output(name):
                _prediction_npz_only(data, name)
            # Common credential assignment patterns remain blocked even if the
            # supplied secret-value scan cannot recognize a different credential.
            if path.suffix.lower() not in {".png", ".pdf"} and re.search(rb'(?:GH_TOKEN|RUNPOD_API_KEY|R2_SECRET_ACCESS_KEY|R2_ACCESS_KEY_ID)\s*[=:]\s*["\']?[A-Za-z0-9_+/.-]{12,}', data):
                raise TransportError("publication_credential_pattern_forbidden")
            artifacts[name] = data
            records[name] = {"sha256": _sha(data), "size_bytes": len(data), "immutable": name in frozen}
        branch = f"redesign/run-{job_id}"
        prefix = f"{JOB_PREFIX}/{job_id}"
        ref_path = "/git/ref/heads/" + branch
        try:
            head = self._api("GET", ref_path)["object"]["sha"]
        except TransportError as error:
            if error.http_status != 404:
                raise
            self._api("GET", f"/git/commits/{base_commit}")  # Must exist before branch creation.
            try:
                self._api("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": base_commit})
                head = base_commit
            except TransportError as create_error:
                if create_error.http_status != 422:
                    raise
                head = self._api("GET", ref_path)["object"]["sha"]
        inventory = self._read_inventory(prefix, head)
        if head != base_commit and (inventory.get("job_id") != job_id or inventory.get("base_commit") != base_commit):
            raise TransportError("publication_branch_identity_mismatch")
        old_records = inventory.get("artifacts", {})
        if not isinstance(old_records, dict):
            raise TransportError("publication_inventory_invalid")
        for previous in old_records.values():
            if not isinstance(previous, dict) or not isinstance(previous.get("size_bytes"), int) or isinstance(previous.get("size_bytes"), bool) or previous["size_bytes"] < 0:
                raise TransportError("publication_inventory_invalid")
        for name, record in records.items():
            previous = old_records.get(name)
            if previous and previous.get("immutable") and previous.get("sha256") != record["sha256"]:
                raise TransportError("publication_frozen_artifact_changed")
            if previous and previous.get("immutable"):
                record["immutable"] = True
        combined = {**old_records, **records}
        if sum(record["size_bytes"] for record in combined.values()) > MAX_GITHUB_TOTAL_BYTES:
            raise TransportError("publication_aggregate_size_limit")
        # Content-addressed blobs already bound by the previous inventory need
        # no second upload. Public readback below still verifies requested bytes.
        tree_entries = []
        new_blob_count = 0
        for name, data in artifacts.items():
            previous = old_records.get(name, {})
            previous_blob = previous.get("git_blob_sha", "")
            if previous.get("sha256") == records[name]["sha256"] and isinstance(previous_blob, str) and re.fullmatch(r"[0-9a-f]{40}", previous_blob):
                records[name]["git_blob_sha"] = previous["git_blob_sha"]
            else:
                blob = self._api("POST", "/git/blobs", {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
                records[name]["git_blob_sha"] = blob["sha"]
                tree_entries.append({"path": f"{prefix}/{name}", "mode": "100644", "type": "blob", "sha": blob["sha"]})
                new_blob_count += 1
        combined = {**old_records, **records}
        checkpoint_names = [name for name in combined if _is_checkpoint(name)]
        manifest = {"schema_version": 1, "job_id": job_id, "base_commit": base_commit,
                    "branch": branch, "artifacts": combined,
                    "raw_eeg_in_github": False, "checkpoints_in_github": bool(checkpoint_names),
                    "prediction_only_npz_in_github": any(_is_target_output(name) for name in combined),
                    "credentials_in_github": False}
        artifacts["publication_manifest.json"] = _canonical_json(manifest)
        if sum(record["size_bytes"] for record in combined.values()) + len(artifacts["publication_manifest.json"]) > MAX_GITHUB_TOTAL_BYTES:
            raise TransportError("publication_aggregate_size_limit")
        records["publication_manifest.json"] = {"sha256": _sha(artifacts["publication_manifest.json"]),
                                                 "size_bytes": len(artifacts["publication_manifest.json"]), "immutable": False}
        if tree_entries or manifest != inventory:
            blob = self._api("POST", "/git/blobs", {"content": base64.b64encode(artifacts["publication_manifest.json"]).decode("ascii"), "encoding": "base64"})
            records["publication_manifest.json"]["git_blob_sha"] = blob["sha"]
            tree_entries.append({"path": f"{prefix}/publication_manifest.json", "mode": "100644", "type": "blob", "sha": blob["sha"]})
            parent = self._api("GET", f"/git/commits/{head}")
            tree = self._api("POST", "/git/trees", {"base_tree": parent["tree"]["sha"], "tree": tree_entries})
            commit = self._api("POST", "/git/commits", {"message": message, "tree": tree["sha"], "parents": [head]})["sha"]
            self._api("PATCH", "/git/refs/heads/" + branch, {"sha": commit, "force": False})
        else:
            commit = head
        receipt = {"schema_version": 1, "status": "COMMITTED_PUBLIC_READBACK_UNVERIFIED", "job_id": job_id,
                   "repository": self.repo, "branch": branch, "commit": commit, "base_commit": base_commit,
                   "github_public_readback_verified": False, "checkpoint_backup_verified": False,
                   "checkpoint_backup_scope": "all_completed_source_checkpoints_in_current_inventory",
                   "completed_checkpoint_count": len(checkpoint_names), "new_artifact_blob_count": new_blob_count,
                   "artifact_prefix": prefix, "artifacts": records}
        if verify_public:
            try:
                for name, record in records.items():
                    url = f"https://raw.githubusercontent.com/{self.repo}/{commit}/{quote(prefix + '/' + name, safe='/')}"
                    returned = self._get_public(url)
                    if len(returned) != record["size_bytes"] or _sha(returned) != record["sha256"]:
                        raise TransportError("github_public_readback_mismatch")
                # A snapshot that selects only a status update must not claim
                # checkpoint backup merely because older inventory entries exist.
                # Explicitly verify any checkpoint not selected in this call.
                for name in checkpoint_names:
                    if name not in records:
                        record = combined[name]
                        url = f"https://raw.githubusercontent.com/{self.repo}/{commit}/{quote(prefix + '/' + name, safe='/')}"
                        returned = self._get_public(url)
                        if len(returned) != record["size_bytes"] or _sha(returned) != record["sha256"]:
                            raise TransportError("github_public_checkpoint_readback_mismatch")
            except TransportError as error:
                raise TransportError(error.code, http_status=error.http_status, partial_receipt=receipt) from None
            except Exception:
                raise TransportError("github_public_readback_unexpected_error", partial_receipt=receipt) from None
            receipt["status"] = "VERIFIED_PUBLIC_GITHUB_SNAPSHOT"
            receipt["github_public_readback_verified"] = True
            receipt["checkpoint_backup_verified"] = bool(checkpoint_names)
        return receipt


class R2CheckpointBackup:
    def __init__(self, credentials: Mapping[str, str], *, client=None):
        if not all(credentials.get(name) for name in R2_NAMES):
            raise TransportError("r2_credentials_incomplete")
        self._bucket = credentials["R2_BUCKET"]
        self._secret_values = tuple(credentials[name].encode() for name in ("GH_TOKEN", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY") if credentials.get(name))
        if client is None:
            try:
                import boto3
                from botocore.config import Config
                client = boto3.client("s3", endpoint_url=credentials["R2_ENDPOINT"],
                                      aws_access_key_id=credentials["R2_ACCESS_KEY_ID"],
                                      aws_secret_access_key=credentials["R2_SECRET_ACCESS_KEY"],
                                      region_name="auto", config=Config(retries={"max_attempts": 4, "mode": "standard"}))
            except Exception:
                raise TransportError("r2_client_initialization_failed") from None
        self._client = client

    def upload_and_verify(self, files_mapping: Mapping[str, str | Path], *, key_prefix: str) -> dict:
        prefix = _safe_relative(key_prefix).rstrip("/")
        if not files_mapping:
            raise TransportError("r2_backup_artifacts_empty")
        records = []
        for name, value in files_mapping.items():
            name = _safe_relative(name)
            path = Path(value)
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in R2_ALLOWED_SUFFIXES and not _is_target_output(name) or SECRET_BASENAME.search(path.name) or any(SECRET_BASENAME.search(part) for part in PurePosixPath(name).parts):
                raise TransportError("r2_backup_artifact_forbidden")
            if _is_target_output(name):
                if path.stat().st_size > MAX_GITHUB_BYTES:
                    raise TransportError("r2_prediction_output_size_limit")
                _prediction_npz_only(path.read_bytes(), name)
            if path.suffix.lower() in {".json", ".md", ".csv", ".tsv", ".txt", ".log", ".yaml", ".yml"}:
                with path.open("rb") as stream:
                    overlap = b""
                    longest_secret = max((len(secret) for secret in self._secret_values), default=1)
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        scanned = overlap + chunk
                        if any(secret in scanned for secret in self._secret_values):
                            raise TransportError("r2_backup_secret_content_forbidden")
                        overlap = scanned[-longest_secret:]
            expected_sha = _file_sha(path)
            expected_size = path.stat().st_size
            key = f"{prefix}/{name}"
            try:
                self._client.upload_file(str(path), self._bucket, key, ExtraArgs={"Metadata": {"sha256": expected_sha}})
                header = self._client.head_object(Bucket=self._bucket, Key=key)
                if header.get("ContentLength") != expected_size:
                    raise TransportError("r2_backup_size_mismatch")
                response = self._client.get_object(Bucket=self._bucket, Key=key)
                body = response["Body"]
                digest = hashlib.sha256()
                actual_size = 0
                try:
                    for chunk in iter(lambda: body.read(1024 * 1024), b""):
                        actual_size += len(chunk)
                        if actual_size > expected_size:
                            raise TransportError("r2_backup_size_mismatch")
                        digest.update(chunk)
                finally:
                    body.close()
                if actual_size != expected_size or digest.hexdigest() != expected_sha:
                    raise TransportError("r2_backup_byte_readback_mismatch")
                if _file_sha(path) != expected_sha or path.stat().st_size != expected_size:
                    raise TransportError("r2_backup_local_file_changed")
            except TransportError:
                raise
            except Exception:
                raise TransportError("r2_backup_request_failed") from None
            records.append({"object_key": key, "sha256": expected_sha, "size_bytes": expected_size,
                            "complete_byte_readback_verified": True})
        return {"schema_version": 1, "status": "VERIFIED_R2_COMPLETE_BYTE_READBACK",
                "checkpoint_backup_verified": any(Path(name).suffix.lower() in {".pt", ".pth", ".ckpt", ".joblib"} for name in files_mapping), "objects": records}

    def backup(self, *, job_id: str, local_root: str | Path, relative_paths: Sequence[str]) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,110}", job_id):
            raise TransportError("r2_backup_job_identity_invalid")
        root = Path(local_root).resolve()
        paths = {}
        for name in relative_paths:
            name = _safe_relative(name)
            path = root / name
            if root not in path.resolve().parents:
                raise TransportError("r2_backup_artifact_forbidden")
            paths[name] = path
        return self.upload_and_verify(paths, key_prefix="redesign/" + job_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    credentials_parser = sub.add_parser("credentials", help="Save required credentials privately; no API calls.")
    credentials_parser.add_argument("--r2", action="store_true")
    credentials_parser.add_argument("--reset", action="store_true")
    credentials_parser.add_argument("--non-interactive", action="store_true")
    credentials_parser.add_argument("--private-root")
    args = parser.parse_args()
    try:
        values = secure_credentials(enable_r2=args.r2, reset=args.reset, private_root=args.private_root,
                                    interactive=not args.non_interactive)
        print(json.dumps({"status": "PRIVATE_CREDENTIALS_PRESENT_NOT_API_VALIDATED", "present": {name: bool(value) for name, value in values.items()},
                          "runpod_api_required": False, "secrets_saved_on_workspace": False}))
        return 0
    except TransportError as error:
        print(json.dumps({"status": "NOT_STARTED", "error_code": error.code, "runpod_api_required": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
