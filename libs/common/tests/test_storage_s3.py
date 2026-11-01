import io

import pytest
from botocore.exceptions import ClientError

from common.errors import ObjectNotFoundError, StorageError
from common.settings import Settings
from common.storage.s3 import S3ObjectStore


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code}}, "op")


class FakeS3Client:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise _client_error("404")

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        client = self

        class Paginator:
            def paginate(self, Bucket, Prefix):  # noqa: N803
                keys = [k for k in client.objects if k.startswith(Prefix)]
                yield {"Contents": [{"Key": k} for k in keys[:1]]}
                yield {"Contents": [{"Key": k} for k in keys[1:]]}

        return Paginator()


def test_roundtrip_through_fake_client():
    store = S3ObjectStore(FakeS3Client(), "bucket")
    store.put("tenants/uni-a/x", b"1", "text/plain")
    store.put("tenants/uni-a/y", b"2", "text/plain")
    assert store.get("tenants/uni-a/x") == b"1"
    assert store.exists("tenants/uni-a/y")
    assert store.list("tenants/uni-a/") == ["tenants/uni-a/x", "tenants/uni-a/y"]
    store.delete("tenants/uni-a/x")
    assert not store.exists("tenants/uni-a/x")


def test_missing_key_maps_to_not_found():
    store = S3ObjectStore(FakeS3Client(), "bucket")
    with pytest.raises(ObjectNotFoundError):
        store.get("nope")


def test_other_client_errors_map_to_storage_error():
    class DenyingClient(FakeS3Client):
        def get_object(self, Bucket, Key):  # noqa: N803
            raise _client_error("AccessDenied")

    with pytest.raises(StorageError) as info:
        S3ObjectStore(DenyingClient(), "bucket").get("k")
    assert not isinstance(info.value, ObjectNotFoundError)


def test_from_settings_uses_bucket():
    store = S3ObjectStore.from_settings(Settings(s3_bucket="docs"))
    assert store.bucket == "docs"
