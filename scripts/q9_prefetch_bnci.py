"""Fetch BNCI2014_001 on the cloud data disk and verify frozen Q5 MAT hashes.

This is a read-only check of historical Q5 metadata. It never changes Q4--Q8
artifacts and never uses labels to select a method. MOABB may download missing
public MAT files into --data-dir; existing files are reused when valid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from moabb.datasets import BNCI2014_001


ROOT = Path(__file__).resolve().parents[1]
Q5_SOURCE_FILES = ROOT / "results/Q5-E001/source_files.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MNE_DATASETS_BNCI_PATH"] = str(data_dir)
    expected = json.loads(Q5_SOURCE_FILES.read_text(encoding="utf-8"))
    expected_by_name = {Path(item["path"]).name: item for item in expected}
    if len(expected_by_name) != 18:
        raise AssertionError("Frozen Q5 source manifest must contain 18 distinct MAT files")

    dataset = BNCI2014_001(artifact_handling="annotate_bad")
    for subject in range(1, 10):
        print(f"Fetching/verifying S{subject}...", flush=True)
        dataset.data_path(subject, path=str(data_dir), force_update=False)

    rows = []
    for name, item in sorted(expected_by_name.items()):
        matches = list(data_dir.rglob(name))
        if len(matches) != 1:
            raise AssertionError(f"Expected one local copy of {name}, found {len(matches)}")
        path = matches[0]
        if path.stat().st_size != int(item["bytes"]):
            raise AssertionError(f"Size mismatch for {path}")
        current_hash = sha256(path)
        if current_hash != item["sha256"]:
            raise AssertionError(f"SHA256 mismatch for {path}")
        rows.append({"name": name, "path": str(path), "bytes": path.stat().st_size, "sha256": current_hash})
        print(f"Verified {name}", flush=True)

    receipt = {
        "status": "passed",
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "source_experiment": "Q5-E001",
        "source_manifest_sha256": sha256(Q5_SOURCE_FILES),
        "data_dir": str(data_dir),
        "n_files": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "files": rows,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.receipt.with_suffix(args.receipt.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.receipt)
    print(f"All 18 Q5-matched MAT files verified; receipt: {args.receipt}", flush=True)


if __name__ == "__main__":
    main()
