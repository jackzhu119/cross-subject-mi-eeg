"""Installer checks use mock public HTTP responses, without external writes."""
import fcntl
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fetch_bundle as fetch


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class BundleInstallerTests(unittest.TestCase):
    revision = "a" * 40

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p1-fetch-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "installed code"
        self.base = fetch.SOURCE.format(revision=self.revision)
        self.files = {"bootstrap.sh": b"echo ready\n", "sub/module.py": b"VALUE = 1\n"}
        self.calls = []

    def manifest(self, entries=None):
        rows = entries if entries is not None else [
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in self.files.items()]
        self.raw_manifest = json.dumps({"schema_version": 1, "protocol_id": "fixture-v1", "files": rows}).encode()
        return hashlib.sha256(self.raw_manifest).hexdigest()

    def open(self, request, timeout):
        url = request.full_url
        self.assertTrue(url.startswith(self.base))
        self.assertEqual(timeout, 30)
        self.calls.append(url)
        name = url[len(self.base):]
        return Response(self.raw_manifest if name == fetch.MANIFEST else self.files[name], url)

    def run_install(self, sha):
        with patch.object(fetch.OPENER, "open", side_effect=self.open):
            return fetch.install(self.revision, sha, self.root)

    def test_first_install_then_verified_reuse(self):
        sha = self.manifest()
        root, count = self.run_install(sha)
        self.assertEqual((root, count), (self.root, 2))
        for name, content in self.files.items():
            self.assertEqual((root / name).read_bytes(), content)
        self.assertEqual((root / fetch.MANIFEST).read_bytes(), self.raw_manifest)
        self.calls.clear()
        self.run_install(sha)
        self.assertEqual(self.calls, [self.base + fetch.MANIFEST])
        self.assertFalse(list(root.rglob("*.part")))

    def test_existing_different_file_is_preserved(self):
        sha = self.manifest()
        self.root.mkdir()
        target = self.root / "bootstrap.sh"
        target.write_bytes(b"user-owned content")
        with self.assertRaisesRegex(ValueError, "preserved"):
            self.run_install(sha)
        self.assertEqual(target.read_bytes(), b"user-owned content")

    def test_existing_different_manifest_is_preserved(self):
        sha = self.manifest()
        self.root.mkdir()
        path = self.root / fetch.MANIFEST
        path.write_bytes(b"old manifest")
        with self.assertRaisesRegex(ValueError, "preserved"):
            self.run_install(sha)
        self.assertEqual(path.read_bytes(), b"old manifest")
        self.assertEqual(self.calls, [self.base + fetch.MANIFEST])

    def test_invalid_paths_and_duplicates_are_rejected_before_files(self):
        row = {"path": "good.py", "bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}
        for path in ("../outside.py", "/tmp/outside.py", "a/../outside.py", "a//b.py", "a\\b.py", fetch.MANIFEST):
            with self.subTest(path=path):
                sha = self.manifest([{**row, "path": path}])
                self.calls.clear()
                with self.assertRaises(ValueError):
                    self.run_install(sha)
                self.assertEqual(self.calls, [self.base + fetch.MANIFEST])
        sha = self.manifest([row, row])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_install(sha)

    def test_symlink_target_and_parent_are_rejected(self):
        sha = self.manifest()
        self.root.mkdir()
        outside = Path(self.temporary.name) / "outside"
        outside.write_bytes(b"outside untouched")
        (self.root / "bootstrap.sh").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_install(sha)
        self.assertEqual(outside.read_bytes(), b"outside untouched")
        (self.root / "bootstrap.sh").unlink()
        (self.root / "sub").symlink_to(self.temporary.name, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_install(sha)

    def test_bad_manifest_or_file_hash_never_published(self):
        sha = self.manifest()
        with self.assertRaisesRegex(ValueError, "manifest SHA256"):
            self.run_install("0" * 64)
        self.files["bootstrap.sh"] = b"echo WRONG\n"  # Same length, wrong bytes.
        with self.assertRaisesRegex(ValueError, "length or SHA256"):
            self.run_install(sha)
        self.assertFalse((self.root / "bootstrap.sh").exists())
        self.assertFalse((self.root / fetch.MANIFEST).exists())

    def test_destination_flock_excludes_another_installer(self):
        sha = self.manifest()
        self.root.mkdir()
        with (self.root / fetch.LOCK).open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "Another bundle installer"):
                self.run_install(sha)
        self.assertEqual(self.calls, [])

    def test_transient_network_retry_is_bounded(self):
        self.manifest()
        with patch.object(fetch.OPENER, "open", side_effect=OSError("temporary")) as request, patch.object(fetch.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "four attempts"):
                fetch.get(self.base + fetch.MANIFEST, 100)
        self.assertEqual(request.call_count, 4)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [1, 2, 4])

    def test_redirected_source_is_rejected(self):
        self.manifest()
        with patch.object(fetch.OPENER, "open", return_value=Response(self.raw_manifest, "https://example.com/code")):
            with self.assertRaisesRegex(ValueError, "source response"):
                fetch.get(self.base + fetch.MANIFEST, 10000)


if __name__ == "__main__":
    unittest.main()
