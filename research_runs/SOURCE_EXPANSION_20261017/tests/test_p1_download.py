"""No-network regression checks for stable download-manifest identity."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from p1_common import atomic_json, read_json, sha256_file
import p1_download as download


class StableDownloadManifestTests(unittest.TestCase):
    def test_bnci_dynamic_verification_time_does_not_change_manifest(self):
        with tempfile.TemporaryDirectory(prefix="p1-download-test-") as folder:
            root = Path(folder)
            config = root / "config"
            rows = []
            for i in range(18):
                data = f"synthetic payload {i}".encode()
                path = f"A{i // 2 + 1:02d}{'T' if i % 2 == 0 else 'E'}.mat"
                (root / path).write_bytes(data)
                rows.append({"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                             "url": f"https://example.invalid/{path}"})
            atomic_json(config / "bnci_manifest.json", {"dataset": "bnci", "files": rows})
            with patch.object(download, "CONFIG", config), patch.object(download, "log"), \
                    patch.object(download, "utc_now", side_effect=["2026-10-17T00:00:00Z", "2026-10-18T00:00:00Z"]), \
                    patch("urllib.request.urlopen", side_effect=AssertionError("network access forbidden")):
                first = download.download_pinned_dataset("bnci", root)
                stable = (root / "_download_manifest.json").read_bytes()
                second = download.download_pinned_dataset("bnci", root)
            self.assertNotEqual(first["verified_utc"], second["verified_utc"])
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            self.assertEqual(stable, (root / "_download_manifest.json").read_bytes())
            self.assertEqual(second, read_json(root / "_verification_receipt.json"))

    def test_yang_dynamic_receipt_does_not_change_stable_manifest(self):
        receipt = {"data_doi": "synthetic-pinned-v5", "archive": {"file_id": 51001884, "bytes": 10},
                   "license": "CC BY 4.0", "integrity_scope": "synthetic_test", "free_disk_bytes": 1000,
                   "elapsed_seconds": 1, "verified_utc": "2026-10-17", "reused": False,
                   "files": [{"path": "sourcedata/synthetic/data.bdf", "bytes": 10,
                              "sha256": "a" * 64, "crc32": "12345678", "reused": False}]}
        later = deepcopy(receipt)
        later.update({"free_disk_bytes": 700, "elapsed_seconds": 2, "verified_utc": "2026-10-18", "reused": True})
        later["files"][0]["reused"] = True
        with tempfile.TemporaryDirectory(prefix="p1-yang-manifest-test-") as folder:
            root = Path(folder)
            with patch.object(download, "download_pinned_dataset") as bnci, \
                    patch("p1_rangezip.download_yang_v5", side_effect=[receipt, later]) as yang, \
                    patch("urllib.request.urlopen", side_effect=AssertionError("network access forbidden")):
                download.download_sources(root)
                stable = (root / "yang/_download_manifest.json").read_bytes()
                digest = sha256_file(root / "yang/_download_manifest.json")
                download.download_sources(root)
            self.assertEqual(bnci.call_count, 2)
            self.assertEqual(yang.call_count, 2)
            self.assertEqual(stable, (root / "yang/_download_manifest.json").read_bytes())
            self.assertEqual(digest, sha256_file(root / "yang/_download_manifest.json"))
            saved = read_json(root / "yang/_download_manifest.json")
            self.assertNotIn("verified_utc", saved)
            self.assertNotIn("reused", saved["files"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
