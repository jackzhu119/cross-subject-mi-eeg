"""Package the real research project for Linux CUDA execution without raw EEG data."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "Q5_EEGNet_Cloud_Ready.zip"
FILES = (
    ".gitignore",
    "README.md",
    "README_CLOUD.md",
    "ROADMAP.md",
    "pyproject.toml",
    "uv.lock",
    "requirements-cloud.txt",
    "check_gpu.py",
    "setup_gpu.sh",
    "run_gpu.sh",
    "docs",
    "configs",
    "experiments",
    "logs",
    "notebooks",
    "paper",
    "references",
    "scripts",
    "src",
    "tests",
    "outputs",
    "results",
    "data/README.md",
)
EXCLUDED_PARTS = {
    ".venv", ".venv-cloud", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".git", "raw", "node_modules",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included_files() -> list[Path]:
    files = []
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            continue
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        files.extend(
            candidate
            for candidate in candidates
            if not EXCLUDED_PARTS.intersection(candidate.relative_to(ROOT).parts)
            and candidate.suffix not in {".pyc", ".pyo"}
        )
    unique = sorted(set(files))
    if not (ROOT / "results/Q5-E001/config.json").is_file():
        raise FileNotFoundError("Missing the current Q5 experiment record")
    if not (ROOT / "outputs/Q4-E001/trial_metadata.csv").is_file():
        raise FileNotFoundError("Missing the Q4 comparator metadata required by Q5 validation")
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ARCHIVE_NAME)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = included_files()
    manifest = {
        "archive": ARCHIVE_NAME,
        "project_root_in_archive": ".",
        "included_file_count": len(entries),
        "excluded": ["data/raw/ (download on cloud on first run)", ".venv*", "Python caches", "sources/"],
        "files": [
            {
                "path": item.relative_to(ROOT).as_posix(),
                "bytes": item.stat().st_size,
                "sha256": sha256_file(item),
            }
            for item in entries
        ],
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in entries:
            name = Path("Q5_EEGNet_Cloud_Ready") / item.relative_to(ROOT)
            archive.write(item, name.as_posix())
        archive.writestr(
            "Q5_EEGNet_Cloud_Ready/CLOUD_BUNDLE_MANIFEST.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )
    print(
        json.dumps(
            {"archive": str(destination), "included_files": len(entries),
             "bytes": destination.stat().st_size, "manifest": "CLOUD_BUNDLE_MANIFEST.json"},
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
