"""Publish only explicit archival code, manifests and evidence; never raw data."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote

REPO = "jackzhu119/cross-subject-mi-eeg"
FIXED = "23aec28407468b5d3d4b9b15450e84dc616bfd54"
BRANCH = "archive/paper1-frozen-inputs-20261025"
CHECKOUT = Path("/workspace/cross-subject-mi-eeg")
TOOLS = Path("/workspace/paper1-archive-tools")
STATE = Path("/workspace/paper1-archive-state")
DEST = "research_runs/PAPER1_HPC_20261023/r2_rebuild_20261025/"
sys.path.insert(0, str(CHECKOUT / "research_runs/PAPER1_HPC_20261023"))
from hpcmi.github_sync import _api, GitHubError

# Fixed allowlists avoid ever globbing raw/, secret/config files or process logs.
CODE = ("r2_archive.py", "transfer.py", "github_progress.py", "launch.py",
        "test_r2_archive.py", "test_transfer.py", "requirements.txt", "README.md")
EVIDENCE = ("initial-preflight.json", "r2-probe.json", "r2-probe-attempt2.json",
            "frozen_preflight.json", "manifest.tsv", "completion.jsonl", "status.json",
            "summary.json", "progress.json", "last_failure.json", "failures.json",
            "r2_probe.json", "yang_directory_attestation.json", "test-results.json")


def snapshot():
    files = {}
    for root, names, group in ((TOOLS, CODE, "tools/"), (STATE, EVIDENCE, "evidence/")):
        for name in names:
            path = root / name
            if path.is_file():
                if path.is_symlink() or path.stat().st_size > 1_500_000:
                    raise ValueError("invalid_report_file")
                files[DEST + group + name] = path.read_bytes()
    return files


def sync_once():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"status": "github_sync_blocked", "missing": "github_runtime_auth"}
    base = "/repos/" + REPO
    ref = base + "/git/ref/heads/" + quote(BRANCH, safe="")
    try:
        try:
            parent = _api("GET", ref, token)["object"]["sha"]
        except GitHubError as error:
            if error.status != 404:
                raise
            _api("POST", base + "/git/refs", token,
                 {"ref": "refs/heads/" + BRANCH, "sha": FIXED})
            parent = FIXED
        files = snapshot()
        fingerprint = hashlib.sha256(b"".join(
            name.encode() + b"\0" + files[name] for name in sorted(files))).hexdigest()
        previous = STATE / "github-sync.json"
        if previous.is_file():
            old = json.loads(previous.read_text())
            if old.get("fingerprint") == fingerprint and old.get("commit") == parent:
                return {**old, "status": "github_sync_unchanged"}
        parent_tree = _api("GET", base + "/git/commits/" + parent, token)["tree"]["sha"]
        tree = _api("POST", base + "/git/trees", token, {
            "base_tree": parent_tree,
            "tree": [{"path": path, "mode": "100644", "type": "blob",
                      "content": data.decode("utf-8")} for path, data in sorted(files.items())]})
        commit = _api("POST", base + "/git/commits", token, {
            "message": "Record frozen input archival tools and actual verification progress",
            "tree": tree["sha"], "parents": [parent]})["sha"]
        _api("PATCH", base + "/git/refs/heads/" + quote(BRANCH, safe=""), token,
             {"sha": commit, "force": False})
        verified = _api("GET", ref, token)["object"]["sha"] == commit
        result = {"status": "github_sync_verified" if verified else "github_sync_ref_mismatch",
                  "branch": BRANCH, "commit": commit, "files": len(files),
                  "fingerprint": fingerprint, "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    except GitHubError as error:
        result = {"status": "github_sync_failed", "http_status": error.status, "code": error.code}
    except Exception as error:
        result = {"status": "github_sync_failed", "error_class": type(error).__name__}
    path = STATE / "github-sync.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--watch", action="store_true")
    args = p.parse_args()
    while True:
        print(json.dumps(sync_once()), flush=True)
        if not args.watch:
            return
        status_path = STATE / "status.json"
        if status_path.is_file():
            status = json.loads(status_path.read_text()).get("status", "")
            if any(word in status.lower() for word in ("blocked", "failed", "complete", "interrupted", "stopped")):
                return
        time.sleep(180)


if __name__ == "__main__":
    main()
