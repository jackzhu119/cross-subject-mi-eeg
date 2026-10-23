#!/usr/bin/env python3
"""Build a code + optional CPU-wheel archive, excluding credentials/data/results."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from hpcmi.prep_runtime import WHEELS, download_wheels, verify_wheel


SOURCE_ROOT = Path(__file__).resolve().parent
ALLOWED_DIRS = {"hpcmi", "config", "slurm", "tests", "vendor", "evidence"}
ALLOWED_SUFFIXES = {".py", ".sh", ".json", ".md", ".yml", ".yaml", ".txt", ".csv", ".toml", ".sbatch", ".bib"}
EXCLUDED_NAMES = {".git", ".venvs", "__pycache__", "outputs", "data", "state", "logs", "credentials", "token", "tokens"}


def build(output, source_root=SOURCE_ROOT, wheelhouse=None, include_wheels=True, fetch=False, revision=None):
    source_root, output = Path(source_root), Path(output)
    members = {}
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file() or path.suffix not in ALLOWED_SUFFIXES:
            continue
        if len(relative.parts) > 1 and relative.parts[0] not in ALLOWED_DIRS:
            continue
        if any(word in path.name.lower() for word in ("credential", "token", "secret")):
            continue
        members[relative.as_posix()] = path.read_bytes()
    if include_wheels:
        wheelhouse = Path(wheelhouse) if wheelhouse is not None else source_root / "wheelhouse"
        if fetch:
            download_wheels(wheelhouse)
        for wheel in WHEELS:
            path = wheelhouse / wheel["filename"]
            verify_wheel(path, wheel)
            members["wheelhouse/" + wheel["filename"]] = path.read_bytes()
        members["wheelhouse/WHEEL_MANIFEST.json"] = (json.dumps({
            "schema_version": 1, "source": "Official PyPI release metadata",
            "abi": "cp312", "architecture": "x86_64", "glibc_minimum": "2.17", "wheels": WHEELS},
            indent=2, sort_keys=True) + "\n").encode()
    manifest = {"schema_version": 1, "archive_root": "PAPER1_HPC_20261023", "revision": revision,
                "contains_credentials": False, "contains_eeg_or_results": False,
                "payloads": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                             for name, data in sorted(members.items())]}
    members["OFFLINE_MANIFEST.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name, data in sorted(members.items()):
                    info = tarfile.TarInfo("PAPER1_HPC_20261023/" + name)
                    info.size, info.mode, info.mtime = len(data), (0o755 if name.endswith(".sh") else 0o644), 0
                    archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + ".sha256").write_text(digest + "  " + output.name + "\n")
    return {"archive": str(output), "sha256": digest, "bytes": output.stat().st_size,
            "payload_count": len(manifest["payloads"]), "includes_pinned_cpu_wheels": include_wheels}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--code-only", action="store_true")
    parser.add_argument("--download-wheels", action="store_true")
    parser.add_argument("--revision")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output, wheelhouse=args.wheelhouse, include_wheels=not args.code_only,
                           fetch=args.download_wheels, revision=args.revision), indent=2))


if __name__ == "__main__":
    main()
