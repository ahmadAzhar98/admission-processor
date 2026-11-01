"""S3-compatible object store (SeaweedFS, MinIO, AWS S3) backed by boto3."""

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from common.errors import ObjectNotFoundError, StorageError
from common.settings import Settings

_NOT_FOUND_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


class S3ObjectStore:
    """:class:`~common.storage.base.ObjectStore` over one S3 bucket."""

    def __init__(self, client: Any, bucket: str) -> None:
        """Wrap an existing boto3 S3 ``client`` for ``bucket``."""
        self._client = client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3ObjectStore":
        """Create a store using endpoint and credentials from ``settings``.

        Path-style addressing is forced because SeaweedFS and MinIO do not
        serve virtual-hosted bucket names in local deployments.
        """
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )
        return cls(client, settings.s3_bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        """Upload ``data`` to ``key``."""
        try:
            self._client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"put failed for {key}") from exc

    def get(self, key: str) -> bytes:
        """Download the object at ``key``."""
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body: bytes = response["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise ObjectNotFoundError(key) from exc
            raise StorageError(f"get failed for {key}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"get failed for {key}") from exc
        return body

    def exists(self, key: str) -> bool:
        """Return whether ``key`` exists, using a HEAD request."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise StorageError(f"head failed for {key}") from exc
        return True

    def delete(self, key: str) -> None:
        """Delete ``key``; S3 treats missing keys as success."""
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"delete failed for {key}") from exc

    def list(self, prefix: str) -> list[str]:
        """Return all keys under ``prefix``, following pagination."""
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"list failed for {prefix}") from exc
        return sorted(keys)
