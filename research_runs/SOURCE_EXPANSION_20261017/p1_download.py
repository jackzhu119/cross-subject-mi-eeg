"""Download only pinned, public source objects; resume and hash before use."""
from __future__ import annotations

import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from p1_common import atomic_json, log, read_json, safe_child, sha256_file, utc_now

CONFIG = Path(__file__).resolve().parent / "config"


def download_file(url, path, size, sha256, retries=6):
    """Resume a partial HTTP transfer. A completed file must match its pin."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.stat().st_size != size or sha256_file(path) != sha256:
            raise RuntimeError(f"Existing raw file differs from pinned data: {path}")
        return False
    partial = path.with_name(path.name + ".part")
    error = None
    for attempt in range(retries):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                raise ValueError(f"Oversized partial file: {partial}")
            if offset < size:
                headers = {"User-Agent": "Paper1-source-expansion/1.0", "Accept-Encoding": "identity"}
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status == 206:
                        expected = f"bytes {offset}-{size-1}/{size}"
                        if response.headers.get("Content-Range") != expected:
                            raise ValueError("Unexpected Content-Range for a pinned raw object")
                        mode = "ab" if offset else "wb"
                    elif response.status == 200:
                        # Servers without Range support restart this one incomplete file.
                        mode = "wb"
                        offset = 0
                    else:
                        raise ValueError(f"Unexpected HTTP status {response.status}")
                    length = response.headers.get("Content-Length")
                    if length is not None and int(length) != size - offset:
                        raise ValueError("Unexpected Content-Length for a pinned raw object")
                    with partial.open(mode) as f:
                        while True:
                            block = response.read(4 * 1024 * 1024)
                            if not block:
                                break
                            f.write(block)
                            if f.tell() > size:
                                raise ValueError("Server returned more than the declared file length")
                        f.flush()
                        os.fsync(f.fileno())
            if partial.stat().st_size != size:
                raise OSError("Incomplete raw object; resuming")
            if sha256_file(partial) != sha256:
                raise ValueError(f"SHA-256 mismatch, raw object retained for diagnosis: {partial}")
            os.replace(partial, path)
            return True
        except (OSError, urllib.error.URLError) as exc:
            error = exc
            if attempt + 1 == retries:
                break
            log(f"Transfer interrupted, retry {attempt+1}/{retries}: {path.name}")
            time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"Could not download {path.name}; the partial file can be resumed") from error


def download_pinned_dataset(dataset, root):
    if dataset not in {"bnci", "dreyer"}:
        raise ValueError(dataset)
    root = Path(root)
    manifest = read_json(CONFIG / f"{dataset}_manifest.json")
    files = manifest["files"]
    expected_count = 18 if dataset == "bnci" else 174
    if len(files) != expected_count or len({r["path"] for r in files}) != expected_count:
        raise ValueError("Unexpected pinned raw inventory")
    completed = []
    for i, row in enumerate(files, 1):
        path = safe_child(root, row["path"])
        log(f"{dataset}: verify/download raw file {i}/{len(files)} {path.name}")
        download_file(row["url"], path, row["size"], row["sha256"])
        completed.append({"path": row["path"], "size": row["size"], "sha256": row["sha256"], "url": row["url"]})
    stable = {**manifest, "files": completed, "integrity": "all_files_match_pinned_SHA256"}
    atomic_json(root / "_download_manifest.json", stable)
    receipt = {"status": "ALL_PINNED_SHA256_VERIFIED", "verified_utc": utc_now(),
               "manifest_sha256": sha256_file(root / "_download_manifest.json"), "file_count": len(completed)}
    atomic_json(root / "_verification_receipt.json", receipt)
    return receipt


def download_sources(raw_root):
    from p1_rangezip import download_yang_v5
    raw_root = Path(raw_root)
    download_pinned_dataset("bnci", raw_root / "bnci")
    receipt = download_yang_v5(raw_root / "yang", progress=log)
    # Progress, reuse flags and disk space must not change processed-input identity.
    stable = {"dataset": "Yang2025-2C", "data_doi": receipt["data_doi"], "archive": receipt["archive"],
              "license": receipt["license"], "integrity_scope": receipt["integrity_scope"],
              "whole_archive_md5_verified": False,
              "files": [{"path": x["path"], "size": x["bytes"], "sha256": x["sha256"], "crc32": x["crc32"]}
                        for x in receipt["files"]]}
    atomic_json(raw_root / "yang" / "_download_manifest.json", stable)


def download_external(raw_root):
    return download_pinned_dataset("dreyer", Path(raw_root) / "dreyer")
