"""Synthetic safety tests: no environment installation, network, CUDA or EEG."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import stat
from types import SimpleNamespace
import zipfile

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("isolated_training_runtime", HERE / "isolated_training_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
# The wrapper imports its sibling by this stable module name.
sys.modules["isolated_training_runtime"] = runtime
spec = importlib.util.spec_from_file_location("isolated_acceptance_under_test", HERE / "accept_training_runtime_source.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def item(name="numpy", version="2.3.5", digest="a" * 64, url=None):
    return {"metadata": {"name": name, "version": version}, "download_info": {
        "url": url or f"https://files.pythonhosted.org/{name}-1-py3-none-any.whl",
        "archive_info": {"hashes": {"sha256": digest}},
    }}


@pytest.mark.parametrize("name", ["torch", "torchaudio", "triton", "nvidia-cublas-cu12", "nvidia_cudnn_cu12", "TORCH"])
def test_resolver_cannot_reinstall_GPU_packages(name):
    with pytest.raises(ValueError, match="protected_or_duplicate"):
        runtime.validate_plan({"install": [item(name)]}, {})


def test_every_donated_distribution_is_protected():
    with pytest.raises(ValueError, match="protected_or_duplicate"):
        runtime.validate_plan({"install": [item("unexpected_GPU_dependency")]}, {"unexpected-gpu-dependency": {}})


def test_normalized_duplicate_distribution_is_blocked():
    with pytest.raises(ValueError, match="protected_or_duplicate"):
        runtime.validate_plan({"install": [item("scikit-learn"), item("scikit_learn")]}, {})


@pytest.mark.parametrize("version", ["1;echo bad", "1\n2", "$(x)", "", "1 2"])
def test_resolver_versions_are_not_command_text(version):
    with pytest.raises(ValueError, match="unsafe_resolved_version"):
        runtime.validate_plan({"install": [item(version=version)]}, {})


@pytest.mark.parametrize("url", ["https://files.pythonhosted.org/x.tar.gz", "https://files.pythonhosted.org/x.zip"])
def test_no_source_builds_in_plan(url):
    with pytest.raises(ValueError, match="binary_wheels"):
        runtime.validate_plan({"install": [item(url=url)]}, {})


def test_plan_requires_exact_SHA256():
    with pytest.raises(ValueError, match="wheel_sha_required"):
        runtime.validate_plan({"install": [item(digest="short")]}, {})


def test_lightweight_plan_is_allowed():
    assert len(runtime.validate_plan({"install": [item()]}, {"torch": {}})) == 1


@pytest.mark.parametrize("name", ["numpy", "scipy", "sitecustomize.py", "usercustomize.py", "reuse.pth", ".hidden"])
def test_no_numerics_or_startup_hook_donor_inheritance(tmp_path, name):
    donor = tmp_path / "donor"; donor.mkdir()
    component = donor / name; component.mkdir()
    child = tmp_path / "child"; child.mkdir()
    inventory = {"site_packages": [str(donor)], "components": [{"name": name, "path": str(component)}]}
    with pytest.raises(ValueError):
        runtime.link_components(inventory, child)
    assert not list(child.iterdir())


def test_linked_donor_component_cannot_escape_site(tmp_path):
    donor = tmp_path / "donor"; donor.mkdir()
    external = tmp_path / "external"; external.mkdir()
    (donor / "torch").symlink_to(external, target_is_directory=True)
    child = tmp_path / "child"; child.mkdir()
    with pytest.raises(ValueError, match="donor_component_not_regular"):
        runtime.link_components({"site_packages": [str(donor)], "components": [
            {"name": "torch", "path": str(donor / "torch")}]}, child)


def test_safe_GPU_link_does_not_copy_or_allocate_donor(tmp_path):
    donor = tmp_path / "donor"; donor.mkdir()
    component = donor / "torch"; component.mkdir()
    (component / "large.bin").write_bytes(b"x" * 1024 * 1024)
    child = tmp_path / "child"; child.mkdir()
    before = runtime.allocated(child)
    linked = runtime.link_components({"site_packages": [str(donor)], "components": [
        {"name": "torch", "path": str(component)}]}, child)
    assert linked == {"torch": str(component)}
    assert (child / "torch").is_symlink()
    assert runtime.allocated(child) - before < 4096
    assert (component / "large.bin").stat().st_size == 1024 * 1024


def test_existing_child_component_is_never_replaced(tmp_path):
    donor = tmp_path / "donor"; donor.mkdir(); (donor / "torch").mkdir()
    child = tmp_path / "child"; child.mkdir(); (child / "torch").mkdir()
    with pytest.raises(ValueError, match="do_not_replace"):
        runtime.link_components({"site_packages": [str(donor)], "components": [
            {"name": "torch", "path": str(donor / "torch")}]}, child)


def make_wheel(folder, names=None):
    path = folder / "safe-1-py3-none-any.whl"
    entries = dict(names or {"safe/__init__.py": b"# synthetic\n"})
    entries.setdefault("safe-1.dist-info/METADATA", b"Metadata-Version: 2.1\nName: safe\nVersion: 1\n")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path, [item("safe", "1", runtime.sha(path))]


def test_bounded_wheel_budget(tmp_path):
    path, items = make_wheel(tmp_path)
    result = runtime.wheel_budget(tmp_path, items)
    assert result["wheel_compressed_bytes"] == path.stat().st_size
    assert result["estimated_peak_new_bytes"] <= runtime.MAX_NEW_BYTES


def test_actual_wheel_bytes_must_match_plan(tmp_path):
    _, items = make_wheel(tmp_path); items[0]["download_info"]["archive_info"]["hashes"]["sha256"] = "a" * 64
    with pytest.raises(ValueError, match="bytes_differ"):
        runtime.wheel_budget(tmp_path, items)


def test_unplanned_file_is_rejected(tmp_path):
    _, items = make_wheel(tmp_path); (tmp_path / "extra.txt").write_text("x")
    with pytest.raises(ValueError, match="file_count"):
        runtime.wheel_budget(tmp_path, items)


@pytest.mark.parametrize("name", ["../outside", "/outside", "safe/../../outside", "safe\\outside"])
def test_wheel_path_traversal_is_rejected(tmp_path, name):
    _, items = make_wheel(tmp_path, {name: b"x"})
    with pytest.raises(ValueError, match="unsafe_wheel_member"):
        runtime.wheel_budget(tmp_path, items)


def test_zip_expansion_budget_is_checked(tmp_path, monkeypatch):
    _, items = make_wheel(tmp_path, {"safe/file": b"x" * 100000})
    monkeypatch.setattr(runtime, "MAX_NEW_BYTES", 256 * 1024**2 + 99999)
    with pytest.raises(ValueError, match="peak_exceeds"):
        runtime.wheel_budget(tmp_path, items)


@pytest.mark.parametrize("name", [
    "torch/__init__.py", "nvidia/cuda/lib.so", "torch-2.8.0.dist-info/RECORD",
    "safe-1.data/purelib/torch/changed.py", "safe-1.data/platlib/nvidia/lib.so",
])
def test_wheel_cannot_write_through_donated_component_symlink(tmp_path, name):
    _, items = make_wheel(tmp_path, {name: b"unsafe"})
    with pytest.raises(ValueError, match="protected_gpu_component"):
        runtime.wheel_budget(tmp_path, items, protected=["torch-2.8.0.dist-info"])


@pytest.mark.parametrize("name", ["safe.pth", "sitecustomize.py", "safe-1.data/purelib/usercustomize.py"])
def test_wheel_cannot_install_startup_path_inheritance(tmp_path, name):
    _, items = make_wheel(tmp_path, {name: b"unsafe"})
    with pytest.raises(ValueError, match="foreign_startup_code"):
        runtime.wheel_budget(tmp_path, items)


@pytest.mark.parametrize('package,modified,expected_pass', [
    ('setuptools', False, True), ('setuptools', True, False), ('safe', False, False)])
def test_only_exact_reviewed_setuptools_local_distutils_hook_is_allowed(tmp_path, package, modified, expected_pass):
    hook = b"import os; var = 'SETUPTOOLS_USE_DISTUTILS'; enabled = os.environ.get(var, 'local') == 'local'; enabled and __import__('_distutils_hack').add_shim(); \n"
    if modified:
        hook += b"import sys; sys.path.append('/foreign')\n"
    wheel = tmp_path / (package + '-1-py3-none-any.whl')
    with zipfile.ZipFile(wheel, 'w') as z:
        z.writestr(package + '-1.dist-info/METADATA', f'Metadata-Version: 2.1\nName: {package}\nVersion: 1\n')
        z.writestr('distutils-precedence.pth', hook)
    plan = [item(package, '1', runtime.sha(wheel))]
    if expected_pass:
        runtime.wheel_budget(tmp_path, plan)
    else:
        with pytest.raises(ValueError, match='foreign_startup_code'):
            runtime.wheel_budget(tmp_path, plan)


@pytest.mark.parametrize("metadata", [b"Name: other\nVersion: 1\n", b"Name: safe\nVersion: 2\n"])
def test_wheel_metadata_must_match_resolver_plan(tmp_path, metadata):
    _, items = make_wheel(tmp_path, {"safe-1.dist-info/METADATA": metadata})
    with pytest.raises(ValueError, match="identity_different_from_plan"):
        runtime.wheel_budget(tmp_path, items)


def test_wheel_symlink_member_is_rejected(tmp_path):
    path = tmp_path / "safe-1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("safe-1.dist-info/METADATA", "Name: safe\nVersion: 1\n")
        member = zipfile.ZipInfo("safe/link"); member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "../../donor")
    with pytest.raises(ValueError, match="symlink_or_special"):
        runtime.wheel_budget(tmp_path, [item("safe", "1", runtime.sha(path))])


@pytest.mark.parametrize("name", ["safe-1.data/data/lib/python3.12/site-packages/torch/x.py", "safe-1.data/headers/file.h"])
def test_wheel_prefix_data_and_header_mapping_requires_separate_review(tmp_path, name):
    _, items = make_wheel(tmp_path, {name: b"unsafe"})
    with pytest.raises(ValueError, match="data_or_headers_destination"):
        runtime.wheel_budget(tmp_path, items)


def test_wheel_metadata_zip_expansion_is_bounded_before_read(tmp_path):
    _, items = make_wheel(tmp_path, {"safe-1.dist-info/METADATA": b"x" * (1024**2 + 1)})
    with pytest.raises(ValueError, match="metadata_size_cap"):
        runtime.wheel_budget(tmp_path, items)


@pytest.mark.parametrize("name", ["safe-1.data/scripts/python", "safe-1.data/scripts/pip3"])
def test_wheel_cannot_replace_child_interpreter_or_pip(tmp_path, name):
    _, items = make_wheel(tmp_path, {name: b"unsafe"})
    with pytest.raises(ValueError, match="environment_interpreter"):
        runtime.wheel_budget(tmp_path, items)


def test_log_inside_donor_is_rejected_without_write(tmp_path):
    donor = tmp_path / "donor"; donor.mkdir()
    path = donor / "installer.log"
    with pytest.raises(ValueError):
        runtime.validate_log(path, [donor], tmp_path / "new-child")
    assert not path.exists()


def test_direct_workspace_sibling_log_allowed_without_creation(tmp_path):
    path = Path("/workspace") / (tmp_path.name + "-new-installer.log")
    runtime.validate_log(path, [tmp_path / "donor"], Path("/workspace") / "new-child")
    assert not path.exists()


def test_existing_log_is_never_overwritten(tmp_path):
    path = tmp_path / "installer.log"; path.write_text("original")
    with pytest.raises(ValueError):
        runtime.validate_log(path, [], tmp_path / "new-child")
    assert path.read_text() == "original"


@pytest.mark.parametrize("reason", ["space", "allocation"])
def test_owned_installer_monitor_aborts_without_touching_other_processes(tmp_path, monkeypatch, reason):
    child = tmp_path / "new-env"; child.mkdir()
    calls = {}
    process = SimpleNamespace(pid=987654, returncode=None, poll=lambda: None)
    def start(command, **kwargs):
        calls["command"] = command; calls.update(kwargs)
        return process
    monkeypatch.setattr(runtime.subprocess, "Popen", start)
    monkeypatch.setattr(runtime, "stop_owned_child", lambda proc: calls.update(stopped=proc))
    monkeypatch.setattr(runtime.shutil, "disk_usage", lambda _: SimpleNamespace(
        free=runtime.MIN_FREE_BYTES - 1 if reason == "space" else runtime.MIN_FREE_BYTES + runtime.MAX_NEW_BYTES))
    monkeypatch.setattr(runtime, "allocated", lambda _: runtime.MAX_NEW_BYTES + 1 if reason == "allocation" else 0)
    with pytest.raises(ValueError, match="aborts_owned_installer|allocation_exceeds"):
        runtime.run_command(["synthetic-no-execution"], tmp_path / "installer.log", child)
    assert calls["stopped"] is process
    assert calls["start_new_session"] is True
    assert calls["env"]["TMPDIR"] == str(child / "bounded-temp")
    assert calls["command"] == ["synthetic-no-execution"]


def test_owned_installer_commands_use_child_TMP_and_no_site_inheritance(tmp_path, monkeypatch):
    child = tmp_path / "new-env"; child.mkdir()
    calls = {}
    process = SimpleNamespace(pid=987654, returncode=0, poll=lambda: 0)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda command, **kwargs: (calls.update(command=command, **kwargs) or process))
    monkeypatch.setenv("TMPDIR", "/foreign-paper2-cache")
    monkeypatch.setenv("PYTHONPATH", "/foreign-paper2-site")
    runtime.run_command(["synthetic-no-execution"], tmp_path / "installer.log", child)
    assert calls["env"]["TMPDIR"] == str(child / "bounded-temp")
    assert "PYTHONPATH" not in calls["env"]
    assert calls["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_environment_does_not_inherit_PYTHON_or_pip_settings(monkeypatch):
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"):
        monkeypatch.setenv(key, "untrusted")
    env = runtime.clean_env()
    assert not any(key in env for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"))
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PIP_CONFIG_FILE"] == "/dev/null"


@pytest.mark.parametrize("url", ["http://files.pythonhosted.org/x.whl", "https://other.org/x.whl", "https://user:pass@files.pythonhosted.org/x.whl"])
def test_download_origin_rejected_before_network(tmp_path, monkeypatch, url):
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("network must not run"))
    with pytest.raises(ValueError, match="unreviewed_wheel_origin"):
        runtime.download_wheels([item(url=url)], tmp_path, tmp_path)


@pytest.fixture
def import_context(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance.platform, 'python_version', lambda: '3.12.3')
    env = tmp_path / "environment"
    site = env / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    site.mkdir(parents=True)
    donor = tmp_path / "donor"; donor.mkdir()
    linked = {}
    for name in ("torch", "torchaudio"):
        root = donor / name; root.mkdir(); (root / "__init__.py").write_text("# synthetic")
        (site / name).symlink_to(root, target_is_directory=True)
        linked[name] = str(root)
    req = tmp_path / "requirements.txt"; req.write_text("numpy==2.3.5\nscipy==1.17.0\n")
    monkeypatch.setattr(runtime, "REQ", req)
    monkeypatch.setattr(sys, "prefix", str(env)); monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "base"))
    monkeypatch.setattr(sys, "path", [str(site)])
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(acceptance.sysconfig, "get_path", lambda name: str(tmp_path / "base/lib/python3.12"))
    for key in ("MPLCONFIGDIR", "XDG_CACHE_HOME", "TORCH_HOME", "HF_HOME", "NUMBA_CACHE_DIR"):
        monkeypatch.setenv(key, "original-synthetic-cache")
    versions = {"numpy": "2.3.5", "scipy": "1.17.0"}
    modules = {}
    for name in versions:
        path = site / (name + ".py"); path.write_text("# synthetic")
        modules[name] = SimpleNamespace(__file__=str(path))
    for name in ("torch", "torchaudio"):
        modules[name] = SimpleNamespace(__file__=str(donor / name / "__init__.py"), __version__="2.8.0+cu128", version=SimpleNamespace(cuda="12.8"))
        monkeypatch.setitem(sys.modules, name, modules[name])
    monkeypatch.setattr(acceptance.metadata, "version", lambda name: versions[name])
    monkeypatch.setattr(acceptance.importlib, "import_module", modules.__getitem__)
    receipt = {"environment": str(env), "linked_gpu_components": linked, "requirements_sha256": runtime.sha(req)}
    return receipt, modules, versions, site


def test_actual_import_boundary_accepts_only_child_numerics_exact_donor(import_context):
    receipt, _, _, _ = import_context
    result = acceptance.exact_imports(receipt)
    assert result["numpy"]["version"] == "2.3.5"
    assert result["torch"]["version"] == "2.8.0+cu128"


def test_donor_site_inheritance_is_rejected_before_import(import_context, monkeypatch):
    receipt, _, _, site = import_context
    monkeypatch.setattr(sys, "path", [str(site), str(site.parent / "other/site-packages")])
    with pytest.raises(ValueError, match="no_inheritance"):
        acceptance.exact_imports(receipt)


@pytest.mark.parametrize('python_version', ['3.11.16', '3.12.14', '3.13.0'])
def test_paper1_does_not_silently_change_original_python_or_reuse_paper2_ABI(import_context, monkeypatch, python_version):
    receipt, _, _, _ = import_context
    monkeypatch.setattr(acceptance.platform, 'python_version', lambda: python_version)
    with pytest.raises(ValueError, match='original_python_version_required'):
        acceptance.exact_imports(receipt)


def test_wrong_numerics_are_rejected(import_context):
    receipt, _, versions, _ = import_context
    versions["numpy"] = "2.2.6"
    with pytest.raises(ValueError, match="version_changed:numpy"):
        acceptance.exact_imports(receipt)


def test_imported_numerics_outside_child_are_rejected(import_context, tmp_path):
    receipt, modules, _, _ = import_context
    modules["numpy"].__file__ = str(tmp_path / "old-numerics.py")
    with pytest.raises(ValueError, match="outside_child:numpy"):
        acceptance.exact_imports(receipt)


def test_GPU_pair_metadata_is_not_enough_wrong_import_version_rejected(import_context):
    receipt, modules, _, _ = import_context
    modules["torch"].__version__ = "2.8.0+cpu"
    with pytest.raises(ValueError, match="gpu_pair_import_not_exact:torch"):
        acceptance.exact_imports(receipt)


def test_bytecode_write_flag_is_required(import_context, monkeypatch):
    receipt, _, _, _ = import_context
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    with pytest.raises(ValueError, match="no_inheritance"):
        acceptance.exact_imports(receipt)


def test_bound_GPU_links_cannot_be_replaced(import_context):
    receipt, _, _, site = import_context
    (site / "torch").unlink(); (site / "torch").mkdir()
    with pytest.raises(ValueError, match="component_binding_changed"):
        acceptance.exact_imports(receipt)


def test_arbitrary_non_site_sys_path_is_rejected(import_context, monkeypatch):
    receipt, _, _, site = import_context
    monkeypatch.setattr(sys, "path", [str(site), "/foreign-module-directory"])
    with pytest.raises(ValueError, match="foreign_sys_path"):
        acceptance.exact_imports(receipt)


def test_requirement_digest_change_is_rejected_before_import(import_context):
    receipt, _, _, _ = import_context
    receipt["requirements_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="requirements_changed"):
        acceptance.exact_imports(receipt)


@pytest.fixture
def wrapper_context(tmp_path, monkeypatch):
    env = tmp_path / "isolated-child"; env.mkdir()
    receipt_path = env / "runtime_preparation.json"
    revision = "a" * 40
    receipt = {"status": "ISOLATED_RUNTIME_PREPARED_IMPORT_AND_SOURCE_ACCEPTANCE_PENDING",
               "code_revision": revision, "environment": str(env),
               "donor_metadata": {"donor_python": "/synthetic/donor/python"},
               "donor_post_metadata": {"identity": "fixed"}}
    receipt_path.write_text(json.dumps(receipt))
    output = tmp_path / "source-acceptance-new"
    calls = []
    expected_package = "2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9"
    module = SimpleNamespace(FULL_PACKAGE_SHA=expected_package, result=0)
    def fake_source_acceptance(args):
        calls.append((args.runtime_role, args.diagnostic_package))
        output.mkdir(exist_ok=False)
        (output / "formal_source_acceptance.json").write_text(json.dumps({"training_authorization": False}))
        return module.result
    module.run = fake_source_acceptance
    monkeypatch.setattr(runtime, "fixed_checkout", lambda _: {})
    monkeypatch.setattr(runtime, "donor_observation", lambda _: {"identity": "fixed"})
    monkeypatch.setattr(runtime, "identity", lambda obj: obj["identity"])
    monkeypatch.setattr(acceptance, "exact_imports", lambda _: {"synthetic": "no imports"})
    monkeypatch.setattr(acceptance.subprocess, "check_output", lambda _: Path(acceptance.__file__).read_bytes())
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *args: SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None)))
    monkeypatch.setattr(importlib.util, "module_from_spec", lambda _: module)
    args = SimpleNamespace(code_revision=revision, runtime_receipt=receipt_path,
                           data_dir=tmp_path / "not-read", output_dir=output,
                           diagnostic_package=tmp_path / "not-read-private-package.tar.gz", old_work_root=None)
    return args, module, calls, receipt


def test_wrapper_invokes_exactly_one_CPU_source_acceptance_and_keeps_training_blocked(wrapper_context):
    args, module, calls, _ = wrapper_context
    acceptance.run(args)
    assert calls == [("training", args.diagnostic_package)]
    bound = json.loads((args.output_dir / "runtime_bound_acceptance.json").read_text())
    assert bound["private_full_package_sha256"] == module.FULL_PACKAGE_SHA
    assert bound["training_authorization"] is False
    assert bound["target_EEG_read"] is False and bound["new_fits"] == 0
    assert bound["old_task_transition_authorized"] is False and bound["budget_transition_authorized"] is False
    assert bound["runtime_GPU_computation_verified"] is False


def test_wrapper_does_not_retry_pending_source_or_private_package_gate(wrapper_context):
    args, module, calls, _ = wrapper_context; module.result = 3
    with pytest.raises(ValueError, match="source_or_private_package_gate_pending"):
        acceptance.run(args)
    assert len(calls) == 1
    assert not (args.output_dir / "runtime_bound_acceptance.json").exists()


@pytest.mark.parametrize("field,value", [("code_revision", "b" * 40), ("status", "diagnostic")])
def test_wrapper_rejects_wrong_preparation_revision_or_role_before_source_read(wrapper_context, field, value):
    args, _, calls, receipt = wrapper_context; receipt[field] = value
    args.runtime_receipt.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="prepared_runtime_receipt_required_same_revision"):
        acceptance.run(args)
    assert not calls


def test_wrapper_rejects_receipt_outside_prepared_child(wrapper_context, tmp_path):
    args, _, calls, receipt = wrapper_context
    external = tmp_path / "unbound-runtime.json"; external.write_text(json.dumps(receipt)); args.runtime_receipt = external
    with pytest.raises(ValueError, match="receipt_not_in_prepared_child"):
        acceptance.run(args)
    assert not calls


def test_wrapper_rejects_changed_donor_before_source_read(wrapper_context, monkeypatch):
    args, _, calls, _ = wrapper_context
    monkeypatch.setattr(runtime, "donor_observation", lambda _: {"identity": "changed"})
    with pytest.raises(ValueError, match="changed_since_runtime_preparation"):
        acceptance.run(args)
    assert not calls
