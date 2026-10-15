"""Read-only metadata inventory for a possible CUDA donor; never imports torch.

Run with the candidate donor's interpreter, ``-I -B``. An exact metadata pair is
not an actual training-runtime import or a GPU/source-input acceptance. Component
paths are candidates for separately guarded, read-only reuse, not permission to
install into or alter the donor. GPU payload bytes are not exhaustively hashed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata as metadata
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys
import sysconfig


GPU_PAIR = {"torch": "2.8.0+cu128", "torchaudio": "2.8.0+cu128"}
TOP_LEVEL = {
    "torch": {"torch", "torchgen", "functorch"},
    "torchaudio": {"torchaudio", "torio"},
    "triton": {"triton"},
}


def normalized(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gpu_name(name):
    # nvidia-ml-py exposes pynvml rather than the CUDA namespace and is neither
    # a Torch-declared CUDA payload nor an eligible component to borrow.
    return name in GPU_PAIR or name == "triton" or (name.startswith("nvidia-") and re.search(r"-cu[0-9]+$", name))


def approved_site(path):
    path = Path(path).resolve()
    if path.name not in ("site-packages", "dist-packages"):
        return False
    for prefix in (sys.prefix, sys.base_prefix):
        prefix = Path(prefix).resolve()
        if not path.is_relative_to(prefix):
            continue
        # Distro Python can legitimately use /usr/local/lib/python3.12/
        # dist-packages with prefix /usr, or generic python3/dist-packages.
        # A different explicit major/minor below that measured prefix cannot
        # donate native packages merely because its directory shares /usr.
        explicit_versions = [re.fullmatch(r"python([0-9]+)\.([0-9]+)", part)
            for part in path.relative_to(prefix).parts]
        if all(match is None or tuple(map(int, match.groups())) == sys.version_info[:2]
               for match in explicit_versions):
            return True
    return False


def distribution_info(dist):
    name = normalized(dist.metadata["Name"])
    if name.startswith("nvidia-") and not name.endswith("-cu12"):
        raise ValueError("donor_other_cuda_major_present:" + name)
    root = Path(dist.locate_file("")).absolute()
    path = Path(dist._path).absolute()
    if not approved_site(root):
        raise ValueError("donor_gpu_site_outside_measured_prefixes:" + name)
    if (path.is_symlink() or not path.is_dir() or path.parent != root
            or not path.name.endswith(".dist-info")
            or path.resolve().parent != root.resolve()):
        raise ValueError("donor_dist_info_path_unsafe:" + name)
    required = (path / "METADATA", path / "RECORD")
    if any(p.is_symlink() or not p.is_file() for p in required):
        raise ValueError("donor_metadata_or_record_missing:" + name)
    allowed = {"nvidia"} if name.startswith("nvidia-") else TOP_LEVEL[name]
    tops = set()
    recorded = {}
    skipped = []
    seen = set()
    # Parse the actual RECORD bytes. importlib.metadata.files can silently drop
    # missing paths, which would hide a malformed or foreign component row.
    for row in csv.reader(io.StringIO(required[1].read_text())):
        if len(row) != 3:
            raise ValueError("donor_record_row_invalid:" + name)
        value = row[0]
        if value in seen:
            raise ValueError("donor_record_path_duplicate:" + name)
        seen.add(value)
        if "\\" in value or any(ord(ch) < 32 for ch in value):
            raise ValueError("donor_record_path_unsafe:" + name)
        parts = PurePosixPath(value).parts
        if not parts or PurePosixPath(value).is_absolute():
            raise ValueError("donor_record_path_unsafe:" + name)
        # Wheels commonly record ../../../bin/torchrun. Never reuse entrypoints
        # or any RECORD path outside the selected site-package root.
        if ".." in parts or "." in value.split("/"):
            if "bin" not in parts or parts[-1] not in {
                    "torchrun", "torchfrtrace", "convert-caffe2-to-onnx", "convert-onnx-to-caffe2",
                    "proton", "proton-viewer"}:
                raise ValueError("donor_record_outside_site_unrecognized:" + name)
            skipped.append(value)
            continue
        top = parts[0]
        if top == path.name:
            continue
        if top not in allowed:
            raise ValueError("donor_record_component_not_allowlisted:" + name + ":" + top)
        top_path = root / top
        if top_path.is_symlink() or not top_path.is_dir() or top_path.resolve().parent != root.resolve():
            raise ValueError("donor_component_path_unsafe:" + name + ":" + top)
        tops.add(top)
        # Bound disk estimates from RECORD, without traversing all CUDA binaries.
        if row[2]:
            try:
                size = int(row[2])
            except ValueError:
                raise ValueError("donor_record_size_invalid:" + name) from None
            if size < 0:
                raise ValueError("donor_record_size_invalid:" + name)
            recorded[value] = size
    primary = "nvidia" if name.startswith("nvidia-") else name
    if primary not in tops:
        raise ValueError("donor_required_component_missing:" + name)
    return {
        "name": name, "version": dist.version,
        "site_packages": str(root), "metadata_dir": str(path),
        "metadata_sha256": digest(required[0]), "record_sha256": digest(required[1]),
        "requires_dist": list(dist.requires or []),
        "component_names": sorted(tops),
        "recorded_payload_bytes": sum(recorded.values()),
        "outside_site_entrypoints_not_reused": sorted(skipped),
    }


def inspect_donor(expected_python=None):
    if expected_python is not None:
        expected = Path(expected_python).absolute()
        if expected != Path(sys.executable).absolute():
            raise ValueError("donor_interpreter_path_mismatch")
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        raise ValueError("donor_python_version_not_supported")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("donor_platform_not_supported")
    observed = {}
    numerical = {}
    for dist in metadata.distributions():
        name = normalized(dist.metadata.get("Name", ""))
        if name in ("numpy", "scipy"):
            numerical.setdefault(name, []).append({"version": dist.version,
                "metadata_dir": str(Path(dist._path).absolute())})
        if not gpu_name(name):
            continue
        info = distribution_info(dist)
        if name in observed and info["metadata_dir"] != observed[name]["metadata_dir"]:
            raise ValueError("multiple_gpu_distribution_origins:" + name)
        observed[name] = info
    for name, version in GPU_PAIR.items():
        if name not in observed or observed[name]["version"] != version:
            raise ValueError("donor_exact_gpu_pair_metadata_required:" + name)
    dependencies = {}
    for requirement in observed["torch"]["requires_dist"]:
        match = re.match(r"^(nvidia[-_][\w-]+|triton)\s*(?:\(\s*)?==\s*([\w.+-]+)", requirement)
        if match:
            dependencies[normalized(match[1])] = match[2]
    if "triton" not in dependencies or not any(n.startswith("nvidia-") for n in dependencies):
        raise ValueError("donor_torch_cuda_dependency_pins_missing")
    for name, version in dependencies.items():
        if name not in observed or observed[name]["version"] != version:
            raise ValueError("donor_gpu_dependency_metadata_mismatch:" + name)
    components = {}
    for name, info in observed.items():
        candidates = [(top, Path(info["site_packages"]) / top, True)
            for top in info["component_names"]]
        candidates.append((Path(info["metadata_dir"]).name, Path(info["metadata_dir"]), True))
        for component_name, path, directory in candidates:
            entry = {"name": component_name, "path": str(path), "is_directory": directory,
                "distribution_names": [name]}
            if component_name in components:
                previous = components[component_name]
                if previous["path"] != entry["path"]:
                    raise ValueError("donor_component_multiple_origins:" + component_name)
                previous["distribution_names"].append(name)
            else:
                components[component_name] = entry
    critical = {}
    for name in ("torch", "torchaudio", "triton"):
        info = observed[name]
        root = Path(info["site_packages"]) / name
        for filename in ("__init__.py", "version.py"):
            path = root / filename
            # These packages are regular import packages, not namespaces.
            # Missing entry modules must not silently disappear from the
            # critical-file binding. version.py remains optional.
            if filename == "__init__.py" or path.exists() or path.is_symlink():
                if path.is_symlink() or not path.is_file():
                    raise ValueError("donor_critical_module_path_unsafe:" + name)
                critical[str(path)] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return {
        "schema_version": 1, "status": "GPU_DONOR_METADATA_EXACT_NOT_IMPORT_VERIFIED",
        "inventory_implementation_sha256": digest(Path(__file__)),
        "donor_python": str(Path(sys.executable).absolute()),
        "prefix": sys.prefix, "base_prefix": sys.base_prefix,
        "base_executable": str(Path(sys._base_executable).absolute()),
        "python_version": platform.python_version(), "python_major_minor": list(sys.version_info[:2]),
        "cache_tag": sys.implementation.cache_tag,
        "SOABI": sysconfig.get_config_var("SOABI"),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "site_packages": sorted({info["site_packages"] for info in observed.values()}),
        "free_bytes": shutil.disk_usage(Path(sys.prefix)).free,
        "distributions": observed, "torch_gpu_dependency_pins": dependencies,
        "components": [components[n] for n in sorted(components)],
        "critical_module_files": critical,
        "isolated_venv_prerequisites": {
            "venv_module_available": importlib.util.find_spec('venv') is not None,
            "ensurepip_module_available": importlib.util.find_spec('ensurepip') is not None,
            "packages_installed_by_inventory": False,
        },
        "numerical_donor_observation_not_reused": numerical,
        "gpu_payload_exhaustively_hashed": False,
        "torch_imported_by_inventory": False, "CUDA_operation_performed": False,
        "training_consumer_imports_verified": False, "training_authorization": False,
        "target_EEG_read": False, "new_fits": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-python", required=True)
    args = parser.parse_args()
    if any(n == "torch" or n.startswith("torch.") for n in sys.modules):
        raise ValueError("donor_startup_already_imported_torch")
    result = inspect_donor(args.expected_python)
    if any(n == "torch" or n.startswith("torch.") for n in sys.modules):
        raise ValueError("inventory_unexpected_torch_import")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
