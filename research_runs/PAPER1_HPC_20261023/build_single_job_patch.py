#!/usr/bin/env python3
"""Small operations-only overlay; never bundle EEG or scientific model files."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
MEMBERS = [
    "LAUNCH.sh", "hpcmi/acquire.py", "hpcmi/cli.py", "hpcmi/github_sync.py",
    "hpcmi/single_job.py", "hpcmi/submit_single.py", "hpcmi/login_pipeline.py", "slurm/single_job.sh", "SINGLE_JOB.md",
]


def build(destination):
    destination = Path(destination)
    payloads = {name: (ROOT / name).read_bytes() for name in MEMBERS}
    manifest = {"schema_version": 1, "operation": "login-transfer-offline-single-job-20261024",
                "source_base_commit": "27094e7e89ecdc9a1477ede5f399e03f4469d70a",
                "science_model_or_input_files_included": False,
                "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(payloads.items())]}
    payloads["OPERATIONS_MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(payloads.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mtime, info.mode = len(data), 0, 0o755 if name.endswith(".sh") else 0o644
                    archive.addfile(info, io.BytesIO(data))
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_name(destination.name + ".sha256").write_text(sha + "  " + destination.name + "\n")
    return {"file": str(destination), "bytes": destination.stat().st_size, "sha256": sha,
            "payloads": len(MEMBERS)}


if __name__ == "__main__":
    print(json.dumps(build(ROOT / "dist/paper1-single-job-operations.tar.gz"), indent=2))
