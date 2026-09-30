"""Check fail-closed behavior with no credentials, network or raw data."""

import io
import json

import pytest

from scripts import q15_r2_preflight as preflight


class MemoryClient:
    def __init__(self, fail=None, corrupt=False, retain=False):
        self.fail, self.corrupt, self.retain = fail, corrupt, retain
        self.objects = {}
        self.calls = []

    def check(self, operation):
        self.calls.append(operation)
        if operation == self.fail:
            raise RuntimeError("this untrusted SDK message must never reach receipts")

    def head_bucket(self, **kwargs):
        self.check("head")

    def list_objects_v2(self, **kwargs):
        self.check("list")
        contents = [{"Key": key} for key in self.objects if key.startswith(kwargs["Prefix"])]
        return {"KeyCount": len(contents), "Contents": contents}

    def put_object(self, **kwargs):
        self.check("put")
        self.objects[kwargs["Key"]] = kwargs

    def get_object(self, **kwargs):
        self.check("get")
        obj = self.objects[kwargs["Key"]]
        return {"Body": io.BytesIO(b"changed" if self.corrupt else obj["Body"]),
                "ContentLength": len(obj["Body"]), "Metadata": obj["Metadata"]}

    def delete_object(self, **kwargs):
        self.check("delete")
        if not self.retain:
            self.objects.pop(kwargs["Key"], None)


def test_missing_configuration_does_not_create_sdk_client(monkeypatch):
    for name in preflight.REQUIRED:
        monkeypatch.delenv(name, raising=False)
    result = preflight.run_preflight()
    assert result["status"] == "blocked_missing_environment"
    assert set(result["environment_variables"].values()) == {"missing"}
    assert result["large_download_started"] is False
    assert result["fits_started"] == 0


def test_private_probe_roundtrip_and_delete():
    client = MemoryClient()
    result = preflight.probe(client, "eeg-research", "q15/manifests/.preflight/test")
    assert result["status"] == "passed"
    assert all(result["checks"].values())
    assert client.objects == {}


@pytest.mark.parametrize("operation", ["head", "list", "put", "get", "delete"])
def test_permission_and_transport_failure_remain_blocked(operation):
    client = MemoryClient(fail=operation)
    result = preflight.probe(client, "eeg-research", "q15/manifests/.preflight/test")
    assert result["status"] == "blocked"
    assert "untrusted SDK message" not in json.dumps(result)
    if operation in ("head", "list"):
        assert "put" not in client.calls
    if operation == "get":
        assert client.objects == {}


def test_corrupt_readback_is_rejected_and_cleaned():
    client = MemoryClient(corrupt=True)
    result = preflight.probe(client, "eeg-research", "q15/manifests/.preflight/test")
    assert result["status"] == "blocked"
    assert result["failed_stage"] == "read_verify"
    assert result["probe_cleanup"] == "verified_absent"


def test_delete_acknowledgement_is_not_enough():
    client = MemoryClient(retain=True)
    result = preflight.probe(client, "eeg-research", "q15/manifests/.preflight/test")
    assert result["status"] == "blocked"
    assert result["probe_cleanup"] == "unconfirmed"


def test_receipts_preserve_previous_attempt(tmp_path):
    output = tmp_path / "r2_preflight.json"
    preflight.write_receipt(output, {"status": "first"})
    preflight.write_receipt(output, {"status": "second"})
    assert json.loads(output.read_text())["status"] == "second"
    old = list(tmp_path.glob("r2_preflight.*.json"))
    assert len(old) == 1
    assert json.loads(old[0].read_text())["status"] == "first"
