"""Prepare the small CPU preprocessing environment once on login1.

The existing PyTorch environment is an interpreter donor only. Scientific
packages are installed into a separate venv; no torch or CUDA package is used.
Pinned official PyPI wheels target CPython 3.12 and glibc >= 2.17 on x86_64.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


# Metadata read from https://pypi.org/pypi/{name}/{version}/json on 2026-10-23.
WHEELS = [
    {"name": "numpy", "version": "2.2.6",
     "filename": "numpy-2.2.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
     "url": "https://files.pythonhosted.org/packages/8c/3d/1e1db36cfd41f895d266b103df00ca5b3cbe965184df824dec5c08c6b803/numpy-2.2.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
     "size": 16527618,
     "sha256": "fd83c01228a688733f1ded5201c678f0c53ecc1006ffbc404db9f7a899ac6249"},
    {"name": "scipy", "version": "1.15.3",
     "filename": "scipy-1.15.3-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
     "url": "https://files.pythonhosted.org/packages/0b/1f/03f52c282437a168ee2c7c14a1a0d0781a9a4a8962d84ac05c06b4c5b555/scipy-1.15.3-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
     "size": 37309455,
     "sha256": "271e3713e645149ea5ea3e97b57fdab61ce61333f97cfae392c28ba786f9bb49"},
]
LOCK_SHA256 = hashlib.sha256(json.dumps(WHEELS, sort_keys=True).encode()).hexdigest()


def _json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_wheel(path, wheel):
    path = Path(path)
    if not path.is_file() or path.stat().st_size != wheel["size"] or file_hash(path) != wheel["sha256"]:
        raise RuntimeError("Missing or mismatched pinned wheel: " + wheel["filename"])


def download_wheels(wheelhouse):
    """Login/offline packaging operation only; verified cached wheels are reused."""
    wheelhouse = Path(wheelhouse)
    wheelhouse.mkdir(parents=True, exist_ok=True)
    for wheel in WHEELS:
        target = wheelhouse / wheel["filename"]
        if target.exists():
            verify_wheel(target, wheel)
            continue
        if os.environ.get("SLURM_JOB_ID"):
            raise RuntimeError("Missing offline wheels: run dependency preparation on login1 before submitting")
        fd, temporary = tempfile.mkstemp(prefix=wheel["filename"] + ".", suffix=".part", dir=wheelhouse)
        print("Downloading official pinned preprocessing wheel: " + wheel["filename"], flush=True)
        try:
            with os.fdopen(fd, "wb") as output:
                request = urllib.request.Request(wheel["url"], headers={"User-Agent": "paper1-hpc-offline/1"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    written = 0
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        written += len(block)
                        if written > wheel["size"]:
                            raise RuntimeError("Pinned wheel exceeded its published size")
                        output.write(block)
                output.flush()
                os.fsync(output.fileno())
            verify_wheel(temporary, wheel)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    manifest = {"schema_version": 1, "lock_sha256": LOCK_SHA256,
                "abi": "cp312", "architecture": "x86_64", "glibc_minimum": "2.17",
                "source": "Official PyPI release metadata", "wheels": WHEELS}
    _json_write(wheelhouse / "WHEEL_MANIFEST.json", manifest)
    return manifest


def _probe(python, installed=False, numerical=False):
    code = (
        "import sys,sysconfig,platform,json; "
        "d={'python':list(sys.version_info[:3]),'machine':platform.machine(),"
        "'soabi':sysconfig.get_config_var('SOABI'),'libc':list(platform.libc_ver())}; "
    )
    if installed:
        code += "import importlib.metadata as m; d['packages']={n:m.version(n) for n in ('numpy','scipy')}; "
    if numerical:
        code += (
            "import numpy as np; from scipy.signal import butter,sosfiltfilt; "
            "x=np.arange(128,dtype=np.float64); y=sosfiltfilt(butter(2,[.1,.4],btype='bandpass',output='sos'),x); "
            "assert y.shape==x.shape and np.isfinite(y).all(); d['cpu_filter_smoke_passed']=True; "
        )
    code += "print(json.dumps(d))"
    result = subprocess.run([str(python), "-I", "-c", code], check=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(result.stdout)


def _check_probe(probe, installed=False):
    if probe["python"][:2] != [3, 12] or probe["machine"] != "x86_64":
        raise RuntimeError("Preprocessing wheels require CPython 3.12 on x86_64")
    if not str(probe.get("soabi", "")).startswith("cpython-312-"):
        raise RuntimeError("Unexpected Python ABI for pinned preprocessing wheels")
    if probe.get("libc", [None])[0] == "glibc":
        version = tuple(int(x) for x in probe["libc"][1].split(".")[:2])
        if version < (2, 17):
            raise RuntimeError("Pinned preprocessing wheels require glibc >= 2.17")
    if installed and probe.get("packages") != {w["name"]: w["version"] for w in WHEELS}:
        raise RuntimeError("Preprocessing package versions differ from the frozen dependency lock")


def prepare(project, base_python, wheelhouse=None):
    """Return the independent CPU venv Python; reuse a successful setup.

    Call on login1, before data preparation or submission. The source interpreter
    and its packages are never modified. First use may fetch the two pinned
    wheels on login1; with an offline wheelhouse no network is used.
    """
    project = Path(project).expanduser().absolute()
    base_python = Path(base_python).expanduser().absolute()
    runtime = project / ".venvs/preprocessing-cp312"
    python = runtime / "bin/python"
    receipt = runtime / "preprocessing_runtime.json"
    if receipt.exists() and python.exists():
        saved = json.loads(receipt.read_text())
        if saved.get("lock_sha256") != LOCK_SHA256:
            raise RuntimeError("Existing preprocessing venv uses another lock; retain it and use another project version")
        _check_probe(_probe(python, installed=True), installed=True)
        return python
    _check_probe(_probe(base_python))
    if os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Prepare the CPU environment once on login1, not inside a submitted job")
    wheelhouse = Path(wheelhouse) if wheelhouse is not None else Path(__file__).resolve().parents[1] / "wheelhouse"
    download_wheels(wheelhouse)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    if not python.exists():
        print("Preparing isolated CPU preprocessing environment (existing GPU environment unchanged).", flush=True)
        subprocess.run([str(base_python), "-I", "-m", "venv", "--copies", str(runtime)], check=True)
    log = project / "logs/preprocessing-install.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        result = subprocess.run(
            [str(python), "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-deps",
             "--no-cache-dir", "--disable-pip-version-check"] + [str(wheelhouse / w["filename"]) for w in WHEELS],
            stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError("CPU preprocessing installation failed; existing partial environment and install log retained")
    observed = _probe(python, installed=True, numerical=True)
    _check_probe(observed, installed=True)
    _json_write(receipt, {"schema_version": 1, "lock_sha256": LOCK_SHA256,
                          "python": str(python), "base_python": str(base_python),
                          "status": "CPU_PREPROCESSING_READY", "observed": observed,
                          "wheels": [{"filename": w["filename"], "sha256": w["sha256"]} for w in WHEELS],
                          "torch_imported": False, "gpu_environment_modified": False})
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--base-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--wheelhouse", type=Path, default=Path(__file__).resolve().parents[1] / "wheelhouse")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args(argv)
    if args.download_only:
        print(json.dumps(download_wheels(args.wheelhouse), indent=2))
    else:
        if args.project is None:
            parser.error("--project is required unless --download-only")
        print(prepare(args.project, args.base_python, args.wheelhouse))


if __name__ == "__main__":
    main()
