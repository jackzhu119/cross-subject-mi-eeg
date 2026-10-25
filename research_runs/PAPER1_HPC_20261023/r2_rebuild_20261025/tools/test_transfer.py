"""Small offline checks of transfer gating, receipts, cleanup, and resumption."""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import transfer as t


BODY = b"synthetic owned archive bytes; no EEG\n"
SHA = hashlib.sha256(BODY).hexdigest()


def entry():
    return {"dataset": "bnci", "path_under_raw": "bnci/synthetic.mat",
            "native_bytes": str(len(BODY)), "sha256": SHA, "crc32": "",
            "download_entry": "https://official.example/synthetic.mat"}


class Acquire:
    def __init__(self, root):
        self.VENDOR = root / "vendor"
        (self.VENDOR / "config").mkdir(parents=True)
        self.pin = {"path": "synthetic.mat", "size": len(BODY), "sha256": SHA}
        for dataset in ("bnci", "dreyer"):
            (self.VENDOR / "config" / (dataset + "_manifest.json")).write_text(
                json.dumps({"files": [self.pin] if dataset == "bnci" else []}))
        self.downloads = 0

    @contextlib.contextmanager
    def open_object(self, row, offset=0, **kwargs):
        yield io.BytesIO(BODY[offset:])

    def yang_pins(self):
        return {}, []

    def configure_download_trust(self):
        return None

    def safe_child(self, root, relative):
        return root / relative

    def transfer_object(self, root, row, **kwargs):
        self.downloads += 1
        with self.open_object(row) as stream:
            (root / row["path"]).write_bytes(stream.read())
        return SHA


class Adapter:
    def __init__(self, probe_ok=True):
        self.probe_ok = probe_ok
        self.remote = {}
        self.uploads = self.verifications = 0

    def probe(self, *args, **kwargs):
        return {"status": "probe_verified" if self.probe_ok else "probe_failed"}

    def archive_file(self, client, bucket, path, key, **kwargs):
        body = path.read_bytes()
        if len(body) != kwargs["expected_size"] or hashlib.sha256(body).hexdigest() != kwargs["expected_sha256"]:
            raise AssertionError("fake detected altered local data")
        self.uploads += 1
        self.remote[key] = body
        for stage in ("local_verification", "upload", "readback"):
            kwargs["progress"](stage, len(body))
        digest = {"bytes": len(body), "sha256": SHA, "crc32": "12345678"}
        return {"status": "archive_verified", "safe_to_remove_local": True,
                "stream_readback_verified": True, "local": digest, "remote": digest,
                "completed_at_utc": t.utc_now()}

    def verify_remote(self, client, bucket, key, **kwargs):
        self.verifications += 1
        body = self.remote.get(key)
        if body is None:
            return {"status": "remote_verification_failed", "error": {"http_status": 404}}
        if hashlib.sha256(body).hexdigest() != kwargs["expected_sha256"]:
            return {"status": "remote_verification_failed", "error": {"category": "mismatch"}}
        kwargs["progress"](len(body))
        return {"status": "remote_verified", "stream_readback_verified": True,
                "completed_at_utc": t.utc_now(), "remote": {"bytes": len(body), "sha256": SHA}}


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.acquire = Acquire(self.root)
        self.adapter = Adapter()

    def tearDown(self):
        self.directory.cleanup()

    def runner(self):
        return t.Transfer(self.root / "state", [entry()], self.acquire, self.adapter, None, None)

    def run_quiet(self, runner):
        with contextlib.redirect_stdout(io.StringIO()):
            runner.run()

    def test_failed_probe_prevents_source_download(self):
        self.adapter.probe_ok = False
        runner = self.runner()
        with self.assertRaises(t.TransferError):
            self.run_quiet(runner)
        self.assertEqual(self.acquire.downloads, 0)
        self.assertEqual(self.adapter.uploads, 0)
        self.assertEqual(json.loads((runner.state / "summary.json").read_text())["completed_count"], 0)

    def test_success_records_readback_and_cleans_owned_local_file(self):
        runner = self.runner()
        self.run_quiet(runner)
        self.assertEqual(self.acquire.downloads, 1)
        self.assertEqual(self.adapter.uploads, 1)
        self.assertFalse((runner.raw / "bnci/synthetic.mat").exists())
        self.assertEqual(runner.records["bnci/synthetic.mat"]["actual_sha256"], SHA)
        self.assertTrue(runner.records["bnci/synthetic.mat"]["stream_readback_verified"])
        self.assertEqual(runner.progress.row["source_bytes_received_run"], len(BODY))

    def test_resume_requires_full_remote_verification_without_redownload(self):
        self.run_quiet(self.runner())
        self.run_quiet(self.runner())
        self.assertEqual(self.acquire.downloads, 1)
        self.assertEqual(self.adapter.uploads, 1)
        self.assertEqual(self.adapter.verifications, 1)

    def test_remote_mismatch_is_failure_not_skip_or_redownload(self):
        self.run_quiet(self.runner())
        self.adapter.remote[t.PREFIX + "/bnci/synthetic.mat"] = b"wrong"
        with self.assertRaises(t.TransferError):
            self.run_quiet(self.runner())
        self.assertEqual(self.acquire.downloads, 1)
        self.assertEqual(self.adapter.uploads, 1)

    def test_resume_rejects_wrong_key_or_actual_frozen_sha(self):
        self.run_quiet(self.runner())
        runner = self.runner()
        row = runner.records["bnci/synthetic.mat"]
        original_key = row["key"]
        row["key"] = "different-prefix/bnci/synthetic.mat"
        self.assertFalse(runner.resume_remote(entry()))
        row["key"] = original_key
        row["actual_sha256"] = "0" * 64
        self.assertFalse(runner.resume_remote(entry()))
        self.assertEqual(self.adapter.verifications, 0)

    def test_resume_rejects_wrong_actual_frozen_crc(self):
        self.run_quiet(self.runner())
        runner = self.runner()
        pinned = entry()
        pinned["crc32"] = "12345678"
        row = runner.records["bnci/synthetic.mat"]
        row["expected_crc32"] = pinned["crc32"]
        row["actual_crc32"] = "00000000"
        self.assertFalse(runner.resume_remote(pinned))
        self.assertEqual(self.adapter.verifications, 0)

    def test_manifest_includes_pending_rows(self):
        runner = self.runner()
        with (runner.state / "manifest.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(rows[0]["expected_sha256"], SHA)

    def test_error_strings_are_never_serialized(self):
        original = RuntimeError("https://private.invalid/?signature=SECRET")
        self.assertNotIn("SECRET", json.dumps(t.safe_failure(original)))

    def test_safe_cause_status_and_failed_run_status_are_preserved(self):
        original = RuntimeError("private URL")
        cause = RuntimeError("https://private.invalid/?signature=SECRET")
        cause.http_status = 403
        original.__cause__ = cause
        self.assertIn(403, set(t.statuses(t.safe_failure(original))))
        self.assertNotIn("SECRET", json.dumps(t.safe_failure(original)))
        self.adapter.probe_ok = False
        runner = self.runner()
        with self.assertRaises(t.TransferError):
            self.run_quiet(runner)
        self.assertEqual(json.loads((runner.state / "status.json").read_text())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
