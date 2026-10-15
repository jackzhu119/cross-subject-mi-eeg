"""Synthetic donor trees; no GPU import, fit or actual donor acceptance."""
import csv
import importlib.metadata
import importlib.util
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("donor_inventory", HERE / "donor_gpu_inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def distribution(site, name, version, *, requirements=(), tops=None, extras=()):
    name = name.replace("-", "_")
    tops = tops or (["nvidia"] if name.startswith("nvidia_") else [name])
    info = site / f"{name}-{version}.dist-info"
    info.mkdir(parents=True)
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    metadata += "".join(f"Requires-Dist: {r}\n" for r in requirements)
    (info / "METADATA").write_text(metadata)
    files = []
    for top in tops:
        path = site / top / "__init__.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text("# Synthetic GPU fixture; not executable implementation.\n")
        files.append((path.relative_to(site).as_posix(), "", str(path.stat().st_size)))
    files.extend([(str(info.relative_to(site) / "METADATA"), "", str(len(metadata))),
        (str(info.relative_to(site) / "RECORD"), "", "")])
    files.extend(extras)
    with (info / "RECORD").open("w", newline="") as stream:
        csv.writer(stream).writerows(files)
    return importlib.metadata.Distribution.at(info)


@pytest.fixture
def donor(tmp_path, monkeypatch):
    site = tmp_path / "site-packages"
    site.mkdir()
    rows = [distribution(site, "torch", "2.8.0+cu128", requirements=(
        "triton==3.4.0; platform_system == 'Linux'", "nvidia-cuda-runtime-cu12==12.8.90"),
        tops=["torch", "torchgen", "functorch"], extras=[("../../../bin/torchfrtrace", "", "10")]),
        distribution(site, "torchaudio", "2.8.0+cu128", requirements=("torch==2.8.0",), tops=["torchaudio", "torio"]),
        distribution(site, "triton", "3.4.0"),
        distribution(site, "nvidia-cuda-runtime-cu12", "12.8.90"),
        distribution(site, "numpy", "2.2.6"), distribution(site, "scipy", "1.15.3")]
    monkeypatch.setattr(inventory.metadata, "distributions", lambda: iter(rows))
    monkeypatch.setattr(inventory.platform, "system", lambda: "Linux")
    monkeypatch.setattr(inventory.platform, "machine", lambda: "x86_64")
    # Synthetic trees are outside the real test interpreter. Approval is only
    # patched in the fixture, never exposed as a production CLI bypass.
    monkeypatch.setattr(inventory, "approved_site", lambda path: True)
    return site, rows


def test_exact_metadata_does_not_authorize_training(donor):
    before = set(sys.modules)
    report = inventory.inspect_donor()
    assert report["status"] == "GPU_DONOR_METADATA_EXACT_NOT_IMPORT_VERIFIED"
    assert report["training_authorization"] is False
    assert report["training_consumer_imports_verified"] is False
    assert report["CUDA_operation_performed"] is False
    assert report["gpu_payload_exhaustively_hashed"] is False
    assert report["numerical_donor_observation_not_reused"]["numpy"][0]["version"] == "2.2.6"
    assert "torch" not in set(sys.modules) - before
    components = {r["name"] for r in report["components"]}
    assert {"torch", "torchgen", "functorch", "torchaudio", "torio", "triton", "nvidia"} <= components
    assert "torchfrtrace" not in components
    assert not {"numpy", "scipy"} & components


@pytest.mark.parametrize("name", ["torch", "torchaudio"])
def test_cpu_pair_cannot_be_cuda_donor(donor, name):
    site, rows = donor
    for dist in rows:
        if inventory.normalized(dist.metadata["Name"]) == name:
            path = Path(dist._path) / "METADATA"
            path.write_text(path.read_text().replace("2.8.0+cu128", "2.8.0+cpu"))
    with pytest.raises(ValueError, match="donor_exact_gpu_pair_metadata_required:" + name):
        inventory.inspect_donor()


def test_cuda_dependency_mismatch_blocks(donor):
    _, rows = donor
    dist = next(d for d in rows if inventory.normalized(d.metadata["Name"]) == "triton")
    path = Path(dist._path) / "METADATA"
    path.write_text(path.read_text().replace("3.4.0", "3.5.0"))
    with pytest.raises(ValueError, match="donor_gpu_dependency_metadata_mismatch:triton"):
        inventory.inspect_donor()


def test_unrelated_nvml_package_not_borrowed(donor):
    site, rows = donor
    rows.append(distribution(site, "nvidia-ml-py", "13.0.0", tops=["pynvml"]))
    report = inventory.inspect_donor()
    assert "nvidia-ml-py" not in report["distributions"]
    assert "pynvml" not in {row["name"] for row in report["components"]}


def test_other_cuda_major_namespace_blocks(donor):
    site, rows = donor
    rows.append(distribution(site, "nvidia-cuda-runtime-cu13", "13.0.0"))
    with pytest.raises(ValueError, match="donor_other_cuda_major_present:nvidia-cuda-runtime-cu13"):
        inventory.inspect_donor()


def test_multiple_distribution_origins_block(donor, tmp_path):
    _, rows = donor
    rows.append(distribution(tmp_path / "different-site", "torch", "2.8.0+cu128"))
    with pytest.raises(ValueError, match="multiple_gpu_distribution_origins:torch"):
        inventory.inspect_donor()


@pytest.mark.parametrize("extra", ["../../../unsafe/payload", "/tmp/payload", "numpy/__init__.py", "torch/../payload"])
def test_unallowlisted_record_components_or_paths_block(donor, extra):
    _, rows = donor
    record = Path(rows[0]._path) / "RECORD"
    with record.open("a") as stream:
        csv.writer(stream).writerow((extra, "", "1"))
    with pytest.raises(ValueError, match="donor_record_"):
        inventory.inspect_donor()


def test_top_level_symlink_blocked(donor, tmp_path):
    site, _ = donor
    (site / "torch" / "__init__.py").unlink()
    (site / "torch").rmdir()
    target = tmp_path / "different-torch"
    target.mkdir()
    (site / "torch").symlink_to(target)
    with pytest.raises(ValueError, match="donor_component_path_unsafe:torch"):
        inventory.inspect_donor()


def test_metadata_symlink_blocked(donor, tmp_path):
    _, rows = donor
    path = Path(rows[0]._path) / "METADATA"
    target = tmp_path / "foreign-metadata"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ValueError, match="donor_metadata_or_record_missing:torch"):
        inventory.inspect_donor()


def test_expected_interpreter_lexical_path_enforced(donor):
    with pytest.raises(ValueError, match="donor_interpreter_path_mismatch"):
        inventory.inspect_donor("/not/the/donor/bin/python")


def test_unsupported_abi_and_platform_block(donor, monkeypatch):
    monkeypatch.setattr(inventory.platform, "machine", lambda: "aarch64")
    with pytest.raises(ValueError, match="donor_platform_not_supported"):
        inventory.inspect_donor()


def test_torch_without_cuda_dependency_pins_blocked(donor):
    _, rows = donor
    path = Path(rows[0]._path) / "METADATA"
    path.write_text("\n".join(line for line in path.read_text().splitlines()
        if not line.startswith("Requires-Dist:")) + "\n")
    with pytest.raises(ValueError, match="donor_torch_cuda_dependency_pins_missing"):
        inventory.inspect_donor()


def test_missing_primary_package_blocked(donor):
    _, rows = donor
    record = Path(rows[1]._path) / "RECORD"
    record.write_text("\n".join(line for line in record.read_text().splitlines()
        if not line.startswith("torchaudio/")) + "\n")
    with pytest.raises(ValueError, match="donor_required_component_missing:torchaudio"):
        inventory.inspect_donor()


def test_arbitrary_third_site_origin_blocked(donor, monkeypatch):
    monkeypatch.setattr(inventory, "approved_site", lambda path: False)
    with pytest.raises(ValueError, match="donor_gpu_site_outside_measured_prefixes:torch"):
        inventory.inspect_donor()


def test_default_site_approval_requires_measured_prefix_and_site_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(inventory.sys, "prefix", str(tmp_path / "child"))
    monkeypatch.setattr(inventory.sys, "base_prefix", str(tmp_path / "base"))
    assert inventory.approved_site(tmp_path / "child/lib/python3.12/site-packages")
    assert inventory.approved_site(tmp_path / "base/lib/python3.12/dist-packages")
    assert not inventory.approved_site(tmp_path / "unrelated/lib/python3.12/site-packages")
    assert not inventory.approved_site(tmp_path / "base/foreign-directory")


def test_distro_usr_prefix_accepts_current_minor_local_dist_packages_and_generic_python3(monkeypatch):
    monkeypatch.setattr(inventory.sys, "prefix", "/usr")
    monkeypatch.setattr(inventory.sys, "base_prefix", "/usr")
    monkeypatch.setattr(inventory.sys, "version_info", (3, 12, 3))
    assert inventory.approved_site("/usr/local/lib/python3.12/dist-packages")
    assert inventory.approved_site("/usr/lib/python3/dist-packages")
    assert not inventory.approved_site("/workspace/.venvs/paper2-gpu/lib/python3.11/site-packages")


@pytest.mark.parametrize("foreign_minor", ["python3.11", "python3.13", "python2.7"])
def test_same_measured_prefix_does_not_authorize_foreign_explicit_python_minor(monkeypatch, foreign_minor):
    monkeypatch.setattr(inventory.sys, "prefix", "/usr")
    monkeypatch.setattr(inventory.sys, "base_prefix", "/usr")
    monkeypatch.setattr(inventory.sys, "version_info", (3, 12, 3))
    assert not inventory.approved_site(f"/usr/local/lib/{foreign_minor}/dist-packages")
    assert not inventory.approved_site(f"/usr/lib/{foreign_minor}/site-packages")


def test_version_like_name_of_measured_prefix_is_not_mistaken_for_site_abi(tmp_path, monkeypatch):
    prefix = tmp_path / "python3.11"
    monkeypatch.setattr(inventory.sys, "prefix", str(prefix))
    monkeypatch.setattr(inventory.sys, "base_prefix", "/usr")
    monkeypatch.setattr(inventory.sys, "version_info", (3, 12, 3))
    assert inventory.approved_site(prefix / "lib/python3.12/site-packages")


@pytest.mark.parametrize("name", ["torch", "torchaudio", "triton"])
def test_missing_critical_package_entrypoint_cannot_be_omitted_from_binding(donor, name):
    site, _ = donor
    (site / name / "__init__.py").unlink()
    with pytest.raises(ValueError, match="donor_critical_module_path_unsafe:" + name):
        inventory.inspect_donor()


@pytest.mark.parametrize("name", ["torch", "torchaudio", "triton"])
def test_broken_critical_version_symlink_is_not_silently_omitted(donor, name):
    site, _ = donor
    (site / name / "version.py").symlink_to(site / "does-not-exist.py")
    with pytest.raises(ValueError, match="donor_critical_module_path_unsafe:" + name):
        inventory.inspect_donor()
