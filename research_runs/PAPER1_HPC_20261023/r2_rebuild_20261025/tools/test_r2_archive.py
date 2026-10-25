import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import r2_archive as archive


class ServiceError(Exception):
    def __init__(self, status):
        super().__init__("DO NOT PRINT https://private.test/?signature=secret")
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status},
                         "Error": {"Code": "Unauthorized" if status == 401 else "NoSuchKey"}}


class FakeS3:
    def __init__(self, fail=None, corrupt=False):
        self.calls = []
        self.objects = {}
        self.parts = {}
        self.fail = fail
        self.corrupt = corrupt

    def _call(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise ServiceError(401)

    def put_object(self, **kw):
        self._call("put")
        body = kw["Body"]
        self.objects[kw["Key"]] = body if isinstance(body, bytes) else body.read()
        assert len(self.objects[kw["Key"]]) == kw["ContentLength"]
        return {}

    def get_object(self, **kw):
        self._call("get")
        if kw["Key"] not in self.objects:
            raise ServiceError(404)
        data = self.objects[kw["Key"]]
        if self.corrupt:
            data = b"!" * len(data)
        return {"Body": io.BytesIO(data), "ContentLength": len(data)}

    def delete_object(self, **kw):
        self._call("delete")
        self.objects.pop(kw["Key"], None)
        return {}

    def head_object(self, **kw):
        self._call("head")
        if kw["Key"] not in self.objects:
            raise ServiceError(404)
        return {"ContentLength": len(self.objects[kw["Key"]])}

    def create_multipart_upload(self, **kw):
        self._call("create")
        return {"UploadId": "fake-private-id"}

    def upload_part(self, **kw):
        self._call("part")
        self.parts[kw["PartNumber"]] = kw["Body"]
        return {"ETag": str(kw["PartNumber"])}

    def complete_multipart_upload(self, **kw):
        self._call("complete")
        self.objects[kw["Key"]] = b"".join(self.parts[n] for n in sorted(self.parts))
        return {}

    def abort_multipart_upload(self, **kw):
        self._call("abort")
        self.parts.clear()
        return {}


class ArchiveTests(unittest.TestCase):
    def test_probe_full_order_and_cleanup(self):
        client = FakeS3()
        row = archive.probe(client, "bucket")
        self.assertEqual(row["status"], "probe_verified")
        self.assertTrue(row["cleanup_verified"])
        self.assertEqual(client.calls, ["put", "get", "delete", "head"])
        self.assertFalse(client.objects)

    def test_probe_denial_no_retry_no_false_readback(self):
        client = FakeS3(fail="put")
        row = archive.probe(client, "bucket")
        self.assertEqual(row["status"], "probe_failed")
        self.assertEqual(client.calls, ["put"])
        self.assertEqual(row["operations"][0]["http_status"], 401)
        self.assertNotIn("private.test", str(row))
        self.assertFalse(row["stream_readback_verified"])

    def test_error_headers_are_bounded_categories_and_presence_only(self):
        error = ServiceError(401)
        error.response["ResponseMetadata"]["HTTPHeaders"] = {
            "server": "envoy", "content-type": "application/xml; charset=utf-8",
            "cf-ray": "do-not-print", "x-amz-request-id": "do-not-print",
            "www-authenticate": "Bearer secret", "location": "https://private.test/?signature=secret"}
        detail = archive.safe_error(error)
        self.assertEqual(detail["server_category"], "envoy")
        self.assertEqual(detail["content_type_category"], "application/xml")
        self.assertTrue(detail["cf_ray_present"])
        self.assertTrue(detail["www_authenticate_present"])
        self.assertNotIn("do-not-print", str(detail))
        self.assertNotIn("Bearer", str(detail))
        self.assertNotIn("private.test", str(detail))

    def test_probe_readback_corruption_still_cleans_owned_object(self):
        client = FakeS3(corrupt=True)
        row = archive.probe(client, "bucket")
        self.assertEqual(row["status"], "probe_failed")
        self.assertTrue(row["cleanup_verified"])
        self.assertEqual(client.calls, ["put", "get", "delete", "head"])

    def test_local_verification_precedes_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_bytes(b"original frozen file")
            client = FakeS3()
            row = archive.archive_file(client, "bucket", path, "key", expected_size=20,
                                       expected_sha256="0" * 64)
            self.assertEqual(row["status"], "archive_failed")
            self.assertFalse(client.calls)
            self.assertTrue(path.exists())

    def test_full_archive_verifies_readback_and_retains_file(self):
        data = b"original frozen file"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_bytes(data)
            client = FakeS3()
            progress = []
            row = archive.archive_file(client, "bucket", path, "key", expected_size=len(data),
                                       expected_sha256=hashlib.sha256(data).hexdigest(),
                                       progress=lambda stage, n: progress.append((stage, n)))
            self.assertEqual(row["status"], "archive_verified")
            self.assertTrue(row["safe_to_remove_local"])
            self.assertEqual(client.calls, ["put", "get"])
            self.assertTrue(path.exists())
            self.assertIn(("readback", len(data)), progress)

    def test_archive_corrupt_remote_never_authorizes_cleanup(self):
        data = b"original frozen file"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_bytes(data)
            client = FakeS3(corrupt=True)
            row = archive.archive_file(client, "bucket", path, "key", expected_size=len(data),
                                       expected_sha256=hashlib.sha256(data).hexdigest())
            self.assertEqual(row["status"], "archive_failed")
            self.assertFalse(row["safe_to_remove_local"])
            self.assertTrue(path.exists())

    def test_multipart_denial_aborts_without_retry(self):
        data = b"original frozen file"
        with tempfile.TemporaryDirectory() as directory, patch.object(archive, "PART_BYTES", 8):
            path = Path(directory) / "file"
            path.write_bytes(data)
            client = FakeS3(fail="part")
            row = archive.archive_file(client, "bucket", path, "key", expected_size=len(data),
                                       expected_sha256=hashlib.sha256(data).hexdigest())
            self.assertEqual(row["status"], "archive_failed")
            self.assertEqual(client.calls, ["create", "part", "abort"])
            self.assertTrue(row["failure_detail"]["multipart_abort_succeeded"])
            self.assertEqual(row["failure_detail"]["http_status"], 401)
            self.assertTrue(path.exists())

    def test_multipart_success_and_remote_resume_verification(self):
        data = b"original frozen file"
        with tempfile.TemporaryDirectory() as directory, patch.object(archive, "PART_BYTES", 8):
            path = Path(directory) / "file"
            path.write_bytes(data)
            client = FakeS3()
            digest = hashlib.sha256(data).hexdigest()
            row = archive.archive_file(client, "bucket", path, "key", expected_size=len(data),
                                       expected_sha256=digest)
            self.assertEqual(row["status"], "archive_verified")
            self.assertEqual(client.calls, ["create", "part", "part", "part", "complete", "get"])
            row = archive.verify_remote(client, "bucket", "key", expected_size=len(data),
                                        expected_sha256=digest)
            self.assertEqual(row["status"], "remote_verified")
            self.assertEqual(client.calls[-1], "get")

    def test_remote_missing_is_explicit(self):
        row = archive.verify_remote(FakeS3(), "bucket", "key", expected_size=1,
                                    expected_sha256="0" * 64)
        self.assertEqual(row["status"], "remote_verification_failed")
        self.assertEqual(row["error"]["http_status"], 404)

    def test_missing_bindings_are_names_only(self):
        with patch.dict(archive.os.environ, {}, clear=True):
            with self.assertRaises(archive.ArchiveError) as context:
                archive.environment_client()
        self.assertEqual(context.exception.evidence["status"], "blocked_missing_r2_bindings")
        self.assertEqual(set(context.exception.evidence["missing_names"]), set(archive.ENV_NAMES))

    @unittest.skipUnless(importlib.util.find_spec("boto3"), "requires installed SDK; no network")
    def test_explicit_r2_session_ignores_invalid_aws_profile_without_mutating_environment(self):
        config = {"R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
                  "R2_ACCESS_KEY_ID": "unit-test-id", "R2_SECRET_ACCESS_KEY": "unit-test-secret",
                  "E2_BUCKET": "unit-test-bucket", "AWS_PROFILE": "unit-test-profile-does-not-exist"}
        with patch.dict(archive.os.environ, config):
            archive.os.environ.pop("R2_BUCKET", None)
            client, bucket = archive.environment_client()
            self.assertEqual(bucket, "unit-test-bucket")
            self.assertEqual(archive.os.environ["AWS_PROFILE"], config["AWS_PROFILE"])
            self.assertEqual(client.meta.config.retries["total_max_attempts"], 1)
            self.assertEqual(client.meta.config.s3["addressing_style"], "path")
            self.assertEqual(client.meta.config.signature_version, "s3v4")
            client.close()


if __name__ == "__main__":
    unittest.main()
