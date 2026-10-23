import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from hpcmi import prep_runtime as prep
import build_offline


class PrepRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.base = self.root / "existing-gpu-env/bin/python"
        self.probe = {"python": [3, 12, 3], "machine": "x86_64", "soabi": "cpython-312-x86_64-linux-gnu",
                      "libc": ["glibc", "2.17"]}
        self.ready = {**self.probe, "packages": {"numpy": "2.2.6", "scipy": "1.15.3"}, "cpu_filter_smoke_passed": True}

    def test_preparation_installs_only_into_isolated_cpu_env_offline(self):
        with mock.patch.object(prep, "_probe", side_effect=[self.probe, self.ready]), \
             mock.patch.object(prep, "download_wheels") as download, \
             mock.patch.object(prep.subprocess, "run", return_value=mock.Mock(returncode=0)) as run, \
             mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            python = prep.prepare(self.project, self.base, wheelhouse=self.root / "wheelhouse")
        self.assertEqual(python, self.project / ".venvs/preprocessing-cp312/bin/python")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][:4], [str(self.base), "-I", "-m", "venv"])
        self.assertIn("--copies", commands[0])
        self.assertNotIn("--system-site-packages", commands[0])
        self.assertEqual(commands[1][0], str(python))
        self.assertIn("--no-index", commands[1])
        self.assertIn("--no-deps", commands[1])
        self.assertFalse(any("torch" in arg or "nvidia" in arg for arg in commands[1]))
        download.assert_called_once_with(self.root / "wheelhouse")
        receipt = json.loads((python.parent.parent / "preprocessing_runtime.json").read_text())
        self.assertFalse(receipt["gpu_environment_modified"])
        self.assertFalse(self.base.parent.exists())

    def test_prepared_runtime_reuses_without_install_or_wheel_scan(self):
        runtime = self.project / ".venvs/preprocessing-cp312"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "bin/python").write_text("")
        (runtime / "preprocessing_runtime.json").write_text(json.dumps({"lock_sha256": prep.LOCK_SHA256}))
        with mock.patch.object(prep, "_probe", return_value=self.ready) as probe, \
             mock.patch.object(prep, "download_wheels") as download, \
             mock.patch.object(prep.subprocess, "run") as run:
            self.assertEqual(prep.prepare(self.project, self.base), runtime / "bin/python")
        probe.assert_called_once_with(runtime / "bin/python", installed=True)
        download.assert_not_called()
        run.assert_not_called()

    def test_no_install_inside_slurm_or_wrong_abi(self):
        with mock.patch.object(prep, "_probe", return_value=self.probe), \
             mock.patch.dict(os.environ, {"SLURM_JOB_ID": "123"}), \
             mock.patch.object(prep, "download_wheels") as download:
            with self.assertRaisesRegex(RuntimeError, "login1"):
                prep.prepare(self.project, self.base)
            download.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "3.12"):
            prep._check_probe({**self.probe, "python": [3, 11, 16]})
        with self.assertRaisesRegex(RuntimeError, "glibc"):
            prep._check_probe({**self.probe, "libc": ["glibc", "2.12"]})

    def test_wheel_download_exact_hash_and_completed_cache_reused(self):
        content = b"test-wheel-byte-content"
        wheel = {"filename": "example.whl", "name": "example", "version": "1.0",
                 "url": "https://files.pythonhosted.org/example.whl", "size": len(content),
                 "sha256": hashlib.sha256(content).hexdigest()}
        wheelhouse = self.root / "wheels"
        with mock.patch.object(prep, "WHEELS", [wheel]), \
             mock.patch.object(prep.urllib.request, "urlopen", return_value=io.BytesIO(content)) as urlopen, \
             mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            prep.download_wheels(wheelhouse)
            prep.download_wheels(wheelhouse)
        urlopen.assert_called_once()
        self.assertEqual((wheelhouse / "example.whl").read_bytes(), content)
        (wheelhouse / "example.whl").write_bytes(b"corrupted")
        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            prep.verify_wheel(wheelhouse / "example.whl", wheel)

    def test_failed_install_retains_partial_and_no_success_receipt(self):
        with mock.patch.object(prep, "_probe", return_value=self.probe), \
             mock.patch.object(prep, "download_wheels"), \
             mock.patch.object(prep.subprocess, "run", side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=1)]), \
             mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "partial environment"):
                prep.prepare(self.project, self.base)
        self.assertTrue((self.project / "logs/preprocessing-install.log").exists())
        self.assertFalse((self.project / ".venvs/preprocessing-cp312/preprocessing_runtime.json").exists())

    def test_offline_code_archive_excludes_tokens_data_and_runtime(self):
        source = self.root / "source"
        for name, contents in {"LAUNCH.sh": "#!/bin/bash\n", "README.md": "Instructions",
                               "hpcmi/train.py": "print('train')", "state/token.json": "SECRET",
                               "data/subject.csv": "RAW EEG", "outputs/results.json": "private results",
                               ".venvs/packages.py": "runtime", "credentials.json": "SECRET"}.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        (source / "hpcmi/escape.py").symlink_to(source / "credentials.json")
        output = self.root / "package.tar.gz"
        result = build_offline.build(output, source_root=source, include_wheels=False, revision="a" * 40)
        with tarfile.open(output) as archive:
            names = archive.getnames()
            self.assertEqual(sorted(names), ["PAPER1_HPC_20261023/LAUNCH.sh", "PAPER1_HPC_20261023/OFFLINE_MANIFEST.json",
                                             "PAPER1_HPC_20261023/README.md", "PAPER1_HPC_20261023/hpcmi/train.py"])
            manifest = json.load(archive.extractfile("PAPER1_HPC_20261023/OFFLINE_MANIFEST.json"))
            for item in manifest["payloads"]:
                data = archive.extractfile("PAPER1_HPC_20261023/" + item["path"]).read()
                self.assertEqual(len(data), item["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
        self.assertEqual(result["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
