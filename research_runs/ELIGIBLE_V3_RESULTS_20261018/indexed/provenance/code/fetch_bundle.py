"""Install the pinned public Paper1 code bundle; never start experiments."""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

SOURCE = "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/{revision}/research_runs/SOURCE_EXPANSION_20261017/"
MANIFEST = "BUNDLE_MANIFEST.json"
LOCK = ".fetch_bundle.lock"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Bundle source redirected; refusing a different URL")


OPENER = urllib.request.build_opener(NoRedirect())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def get(url, limit):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "Paper1-bundle-installer/1"})
            with OPENER.open(request, timeout=30) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError("Unexpected bundle source response")
                content = response.read(limit + 1)
            if len(content) > limit:
                raise ValueError("Bundle object exceeds its declared size limit")
            return content
        except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
            if attempt == 3:
                raise RuntimeError("Public bundle download failed after four attempts") from error
            time.sleep(2 ** attempt)


def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Existing symlink is not allowed: {path}")


def reuse(path, size, sha):
    no_links(path)
    if not path.exists():
        return False
    if not path.is_file() or path.stat().st_size != size or digest(path.read_bytes()) != sha:
        raise ValueError(f"Existing different object was preserved: {path}")
    return True


def publish(path, content, sha):
    if reuse(path, len(content), sha):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    no_links(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".bundle-", suffix=".part", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        # Atomic publication that refuses to replace a concurrently created file.
        os.link(temporary, path, follow_symlinks=False)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install(revision, manifest_sha256, destination):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision) or not re.fullmatch(r"[0-9a-fA-F]{64}", manifest_sha256):
        raise ValueError("A full 40-hex commit and 64-hex manifest SHA256 are required")
    base = SOURCE.format(revision=revision.lower())
    manifest_sha256 = manifest_sha256.lower()
    root = Path(destination).absolute()
    no_links(root)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    no_links(root / LOCK)
    with os.fdopen(os.open(root / LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another bundle installer is using this destination") from error
        content = get(base + MANIFEST, 4 * 1024**2)
        if digest(content) != manifest_sha256:
            raise ValueError("Pinned bundle manifest SHA256 mismatch")
        reuse(root / MANIFEST, len(content), manifest_sha256)
        manifest = json.loads(content)
        if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
                or manifest["schema_version"] != 1 or not isinstance(manifest.get("protocol_id"), str)
                or not manifest["protocol_id"] or not isinstance(manifest.get("files"), list) or not manifest["files"]):
            raise ValueError("Unsupported bundle manifest schema")
        entries = {}
        for row in manifest["files"]:
            path = row.get("path") if isinstance(row, dict) else None
            if not isinstance(path, str) or not path or "\\" in path or any(ord(c) < 32 for c in path):
                raise ValueError("Manifest paths must be nonempty POSIX relative paths")
            p = PurePosixPath(path)
            if (p.is_absolute() or path != p.as_posix() or path == "." or ".." in p.parts
                    or p.parts[0] in (MANIFEST, LOCK) or path in entries):
                raise ValueError(f"Unsafe, reserved, or duplicate manifest path: {path}")
            size, sha = row.get("bytes"), row.get("sha256")
            if type(size) is not int or size < 0 or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
                raise ValueError(f"Invalid file size or SHA256: {path}")
            no_links(root / path)
            entries[path] = (size, sha.lower())
        if any(parent.as_posix() in entries for path in entries for parent in PurePosixPath(path).parents):
            raise ValueError("A manifest file is also used as a directory")
        for path, (size, sha) in entries.items():
            target = root / path
            if not reuse(target, size, sha):
                data = get(base + urllib.parse.quote(path, safe="/"), size)
                if len(data) != size or digest(data) != sha:
                    raise ValueError(f"Pinned file length or SHA256 mismatch: {path}")
                publish(target, data, sha)
        publish(root / MANIFEST, content, manifest_sha256)
    return root, len(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    try:
        root, count = install(args.revision, args.manifest_sha256, args.destination)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Bundle installation stopped: {error}\n")
    print(f"Verified {count} files and the pinned manifest in {root}. No experiment was started.")
