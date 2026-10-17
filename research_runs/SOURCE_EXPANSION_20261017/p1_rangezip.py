"""Read pinned public ZIP members using HTTP Range, with no full-archive claim.

The Yang v5 archive is public and supports byte ranges. Its complete size and
central-directory SHA-256 are pinned. Each extracted member is checked against
the directory CRC32 and its own SHA-256 is recorded. Selective downloading does
not verify the published MD5 of the complete 65.6 GB archive.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import time
import urllib.error
import urllib.request
import zipfile
import zlib


YANG_URL = "https://ndownloader.figshare.com/files/51001884"
YANG_BYTES = 65_630_556_299
YANG_ARCHIVE_MD5 = "e5384a58ac51b0d0c78a28a500185479"
YANG_CENTRAL_SHA256 = "cecd7ea0895da6ef85f01405960f4844c42d788ad33186b1f3fca91744d6874a"
YANG_PREFIX = "WBCIC_SHU Motor Imagery dataset/"
YANG_METADATA = (
    "CHANGES", "README.md", "dataset_description.json", "participants.json",
    "participants_2C.tsv", "participants_3C.tsv",
)


class HTTPRangeReader(io.RawIOBase):
    """Seekable remote reader; every GET must have the exact requested range.

    Small reads are bounded and larger reads are split into 8 MiB requests.
    ``max_total_bytes`` is useful for metadata-only inspection. No credentials
    are used, and signed redirect URLs are never emitted into logs.
    """

    def __init__(self, url, expected_size, *, timeout=30, retries=4,
                 chunk_bytes=8 * 1024 * 1024, max_total_bytes=None):
        super().__init__()
        self.url = url
        self.size = int(expected_size)
        self.timeout = timeout
        self.retries = retries
        self.chunk_bytes = int(chunk_bytes)
        self.max_total_bytes = max_total_bytes
        self.pos = 0
        self.bytes_received = 0
        self.request_count = 0
        self._active_url = None
        self._cache = []
        self._resolve()

    def _resolve(self):
        req = urllib.request.Request(
            self.url, method="HEAD", headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Archive HEAD returned {response.status}")
            size = int(response.headers.get("Content-Length", "-1"))
            if size != self.size:
                raise RuntimeError(f"Archive length changed: {size} != {self.size}")
            self._active_url = response.geturl()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            new_pos = offset
        elif whence == os.SEEK_CUR:
            new_pos = self.pos + offset
        elif whence == os.SEEK_END:
            new_pos = self.size + offset
        else:
            raise ValueError("Invalid seek mode")
        if new_pos < 0:
            raise ValueError("Cannot seek before the archive")
        self.pos = int(new_pos)
        return self.pos

    def _get_range(self, start, count):
        end = start + count - 1
        for cached_start, cached_bytes in self._cache:
            if cached_start <= start and end < cached_start + len(cached_bytes):
                lo = start - cached_start
                return cached_bytes[lo:lo + count]
        if (self.max_total_bytes is not None and
                self.bytes_received + count > self.max_total_bytes):
            raise RuntimeError("Metadata-only network byte limit exceeded")
        expected_range = f"bytes {start}-{end}/{self.size}"
        error = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(
                    self._active_url,
                    headers={"Range": f"bytes={start}-{end}",
                             "Accept-Encoding": "identity"})
                self.request_count += 1
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if response.status != 206:
                        raise RuntimeError("Server ignored HTTP Range; aborting")
                    if response.headers.get("Content-Range") != expected_range:
                        raise RuntimeError("Unexpected Content-Range; aborting")
                    data = response.read(count + 1)
                if len(data) != count:
                    raise RuntimeError("Truncated or oversized range response")
                self.bytes_received += len(data)
                if count <= 1_048_576:
                    self._cache.append((start, data))
                    self._cache = self._cache[-16:]
                return data
            except (OSError, urllib.error.URLError, http.client.HTTPException, RuntimeError) as exc:
                error = exc
                if attempt >= self.retries:
                    break
                if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
                    self._resolve()  # Refresh an expired public signed redirect.
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"Range read failed after {self.retries + 1} attempts") from error

    def read(self, count=-1):
        if count is None or count < 0:
            count = max(0, self.size - self.pos)
        count = min(int(count), max(0, self.size - self.pos))
        if count == 0:
            return b""
        parts = []
        remaining = count
        while remaining:
            step = min(remaining, self.chunk_bytes)
            parts.append(self._get_range(self.pos, step))
            self.pos += step
            remaining -= step
        return b"".join(parts)


def zip_directory_attestation(reader):
    """Inspect ZIP / ZIP64 end records and hash the exact central directory."""
    tail_size = min(reader.size, 65_557)
    reader.seek(-tail_size, os.SEEK_END)
    tail = reader.read(tail_size)
    position = tail.rfind(b"PK\x05\x06")
    while position >= 0:
        if position + 22 <= len(tail):
            end_record = struct.unpack_from("<4s4H2LH", tail, position)
            if position + 22 + end_record[-1] == len(tail):
                break
        position = tail.rfind(b"PK\x05\x06", 0, position)
    if position < 0:
        raise RuntimeError("Valid ZIP end-of-central-directory record not found")
    _, disk, start_disk, entries_disk, entries, cd_bytes, cd_offset, _ = end_record
    if disk != 0 or start_disk != 0:
        raise RuntimeError("Multi-disk archives are not supported")
    eocd_offset = reader.size - tail_size + position
    if entries == 65_535 or cd_bytes == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF:
        reader.seek(eocd_offset - 20)
        sig, zip64_disk, zip64_offset, disk_count = struct.unpack("<4sLQL", reader.read(20))
        if sig != b"PK\x06\x07" or zip64_disk != 0 or disk_count != 1:
            raise RuntimeError("Invalid ZIP64 locator")
        reader.seek(zip64_offset)
        z64 = struct.unpack("<4sQ2H2L4Q", reader.read(56))
        if z64[0] != b"PK\x06\x06" or z64[1] < 44 or z64[4:6] != (0, 0):
            raise RuntimeError("Invalid ZIP64 directory record")
        entries_disk, entries, cd_bytes, cd_offset = z64[6:10]
    if entries_disk != entries or cd_offset + cd_bytes > eocd_offset:
        raise RuntimeError("Inconsistent central directory bounds")
    if cd_bytes > 8 * 1024 * 1024:
        raise RuntimeError("Unexpectedly large directory; check archive version")
    reader.seek(cd_offset)
    directory = reader.read(cd_bytes)
    return {
        "archive_url": reader.url,
        "archive_bytes": reader.size,
        "central_directory_offset": cd_offset,
        "central_directory_bytes": cd_bytes,
        "central_directory_sha256": hashlib.sha256(directory).hexdigest(),
        "member_count": entries,
        "eocd_offset": eocd_offset,
    }, directory


def open_yang_archive(*, verify_pin=True, max_total_bytes=None):
    reader = HTTPRangeReader(YANG_URL, YANG_BYTES, max_total_bytes=max_total_bytes)
    attestation, directory = zip_directory_attestation(reader)
    if verify_pin and attestation["central_directory_sha256"] != YANG_CENTRAL_SHA256:
        reader.close()
        raise RuntimeError("Yang archive central-directory SHA-256 does not match the pin")
    zf = zipfile.ZipFile(reader)
    items = zf.infolist()
    if len(items) != attestation["member_count"]:
        raise RuntimeError("ZIP member count disagrees with its directory")
    if len({x.filename for x in items}) != len(items):
        raise RuntimeError("Duplicate archive member paths are not accepted")
    return reader, zf, attestation, directory


def selected_yang_members(zf):
    """Exactly 153 two-class sessions, each with raw data and event files."""
    names = set(zf.namelist())
    expected = [
        YANG_PREFIX + f"sourcedata/2C dataset/sub-{sub:03d}/ses-{ses:02d}/eeg/{kind}.bdf"
        for sub in range(1, 52) for ses in range(1, 4) for kind in ("data", "evt")
    ]
    expected += [YANG_PREFIX + name for name in YANG_METADATA]
    missing = [name for name in expected if name not in names]
    if missing:
        raise RuntimeError(f"Pinned Yang archive is missing expected files: {missing[:5]}")
    real_pairs = {
        name for name in names if re.fullmatch(
            re.escape(YANG_PREFIX) + r"sourcedata/2C dataset/sub-\d{3}/ses-\d{2}/eeg/(data|evt)\.bdf", name)
    }
    if real_pairs != set(expected[:306]):
        raise RuntimeError("Unexpected two-class subject/session inventory")
    return [zf.getinfo(name) for name in expected]


def member_record(info):
    return {
        "path": info.filename, "bytes": info.file_size,
        "compressed_bytes": info.compress_size,
        "crc32": f"{info.CRC:08x}", "header_offset": info.header_offset,
        "compression": info.compress_type,
    }


def _hash_file(path):
    digest = hashlib.sha256()
    crc = 0
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
            crc = zlib.crc32(block, crc)
            size += len(block)
    return size, crc & 0xFFFFFFFF, digest.hexdigest()


def _write_json_atomic(path, content):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def download_yang_v5(output_root, *, progress=print, reserve_bytes=15 * 1024**3):
    """Download only two-class raw EEG/event members and six source metadata files.

    Returns the receipt dict. The BIDS root is ``receipt['bids_root']``. Existing
    complete members are rehashed before reuse. Interrupted individual members
    restart from their beginning; successfully verified members are retained.
    """
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    receipt_path = output_root / "yang_v5_download_receipt.json"
    reader, zf, attestation, _ = open_yang_archive()
    selected = selected_yang_members(zf)
    # A selective transfer stores extracted members, not a second full ZIP.
    # Previously completed files consume existing disk space and need no new
    # allocation. Every such file is still checked below before it is reused.
    remaining_bytes = 0
    for info in selected:
        existing = output_root / info.filename
        if existing.exists():
            if not existing.is_file() or existing.stat().st_size != info.file_size:
                zf.close()
                reader.close()
                raise RuntimeError(f"Existing file has unexpected size; preserved: {existing}")
        else:
            remaining_bytes += info.file_size
    available_bytes = shutil.disk_usage(output_root).free
    required_bytes = remaining_bytes + int(reserve_bytes)
    if available_bytes < required_bytes:
        zf.close()
        reader.close()
        raise RuntimeError(
            f"Insufficient free disk: {available_bytes} bytes available, "
            f"{required_bytes} required ({remaining_bytes} remaining plus reserve).")
    receipt = {
        "schema_version": 1, "dataset": "Yang2025-2C", "status": "running",
        "article_doi": "10.1038/s41597-025-04826-y",
        "data_doi": "10.25452/figshare.plus.22671172.v5", "license": "CC BY 4.0",
        "download_mode": "selected_zip_members_http_range",
        "archive": attestation, "published_whole_archive_md5": YANG_ARCHIVE_MD5,
        "whole_archive_md5_verified": False,
        "integrity_scope": "pinned directory + member CRC32 + recorded member SHA256",
        "bids_root": str(output_root / YANG_PREFIX.rstrip("/")),
        "expected_subjects": 51, "expected_sessions": 153,
        "expected_raw_event_files": 306, "expected_metadata_files": 6,
        "selected_uncompressed_bytes": sum(x.file_size for x in selected),
        "selected_compressed_bytes": sum(x.compress_size for x in selected),
        "disk_preflight": {"remaining_uncompressed_bytes": remaining_bytes,
                           "reserve_bytes": int(reserve_bytes),
                           "free_bytes": available_bytes},
        "metadata_caveat": "Archive README and participant count fields are stale; fixed two-class raw inventory governs inclusion.",
        "files": [],
    }
    try:
        for number, info in enumerate(selected, 1):
            parts = PurePosixPath(info.filename).parts
            if not parts or any(p in ("..", ".") for p in parts) or info.filename.startswith("/"):
                raise RuntimeError("Unsafe ZIP member path")
            target = output_root.joinpath(*parts)
            if output_root not in target.resolve().parents:
                raise RuntimeError("ZIP member escapes output directory")
            if info.flag_bits & 1:
                raise RuntimeError("Encrypted files are not accepted")
            reused = False
            if target.is_file():
                size, crc, sha = _hash_file(target)
                reused = size == info.file_size and crc == info.CRC
                if not reused:
                    raise RuntimeError(f"Existing file failed CRC; preserved: {target}")
            if not reused:
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_name(target.name + ".part")
                digest = hashlib.sha256()
                crc = 0
                size = 0
                with zf.open(info) as source, partial.open("wb") as destination:
                    while block := source.read(8 * 1024 * 1024):
                        destination.write(block)
                        digest.update(block)
                        crc = zlib.crc32(block, crc)
                        size += len(block)
                    destination.flush()
                    os.fsync(destination.fileno())
                crc &= 0xFFFFFFFF
                sha = digest.hexdigest()
                if size != info.file_size or crc != info.CRC:
                    raise RuntimeError(f"Member size or CRC mismatch: {info.filename}")
                partial.replace(target)
            receipt["files"].append({**member_record(info), "sha256": sha, "reused": reused})
            receipt["network_bytes_received_this_run"] = reader.bytes_received
            receipt["http_range_requests_this_run"] = reader.request_count
            _write_json_atomic(receipt_path, receipt)
            if progress:
                progress(f"Yang {number}/{len(selected)} verified {info.filename}")
        receipt["status"] = "complete"
        _write_json_atomic(receipt_path, receipt)
        return receipt
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error_type"] = type(exc).__name__
        _write_json_atomic(receipt_path, receipt)
        raise
    finally:
        zf.close()
        reader.close()
