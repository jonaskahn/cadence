"""Async S3/MinIO client.

Wraps aioboto3 to provide async S3 operations compatible with both
AWS S3 and MinIO (via endpoint_url override).
"""

import logging
from typing import List, Optional

import aioboto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Client:
    """Async S3/MinIO client.

    Provides async operations for plugin object storage. Supports both
    AWS S3 (endpoint_url=None) and MinIO (endpoint_url set).

    Attributes:
        endpoint_url: S3 endpoint URL (None for AWS, set for MinIO)
        access_key_id: AWS/MinIO access key ID
        secret_access_key: AWS/MinIO secret access key
        bucket_name: Target bucket name
        region: AWS region (ignored by MinIO)
    """

    def __init__(
        self,
        endpoint_url: Optional[str],
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region: str = "us-east-1",
    ):
        """Initialize S3 client.

        Args:
            endpoint_url: S3 endpoint URL (None for AWS S3, set for MinIO)
            access_key_id: Access key ID
            secret_access_key: Secret access key
            bucket_name: Target bucket name
            region: AWS region
        """
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.region = region
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict:
        """Build aioboto3 client keyword arguments."""
        kwargs = {
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    async def upload_file(self, key: str, data: bytes) -> None:
        """Upload bytes to S3/MinIO.

        Args:
            key: Object key (path within bucket)
            data: Raw bytes to upload
        """
        async with self._session.client("s3", **self._client_kwargs()) as client:
            await client.put_object(Bucket=self.bucket_name, Key=key, Body=data)
            logger.debug(f"Uploaded {len(data)} bytes to s3://{self.bucket_name}/{key}")

    async def download_file(self, key: str) -> bytes:
        """Download object from S3/MinIO.

        Args:
            key: Object key (path within bucket)

        Returns:
            Raw bytes of the object

        Raises:
            FileNotFoundError: If object does not exist
        """
        async with self._session.client("s3", **self._client_kwargs()) as client:
            try:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                async with response["Body"] as stream:
                    data = await stream.read()
                logger.debug(
                    f"Downloaded {len(data)} bytes from s3://{self.bucket_name}/{key}"
                )
                return data
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    raise FileNotFoundError(
                        f"Object not found: s3://{self.bucket_name}/{key}"
                    ) from e
                raise

    async def object_exists(self, key: str) -> bool:
        """Check if an object exists in S3/MinIO.

        Args:
            key: Object key

        Returns:
            True if object exists, False otherwise
        """
        async with self._session.client("s3", **self._client_kwargs()) as client:
            try:
                await client.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404", "403"):
                    return False
                raise

    async def list_objects(self, prefix: str) -> List[str]:
        """List object keys under a prefix.

        Args:
            prefix: Key prefix to list under

        Returns:
            List of object keys matching the prefix
        """
        keys = []
        async with self._session.client("s3", **self._client_kwargs()) as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.bucket_name, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
        return keys

    async def ensure_bucket(self) -> None:
        """Create bucket if it does not exist.

        Safe to call even if bucket already exists.
        """
        async with self._session.client("s3", **self._client_kwargs()) as client:
            try:
                await client.head_bucket(Bucket=self.bucket_name)
                logger.debug(f"Bucket '{self.bucket_name}' already exists")
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchBucket", "404"):
                    if self.region == "us-east-1":
                        await client.create_bucket(Bucket=self.bucket_name)
                    else:
                        await client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.region
                            },
                        )
                    logger.info(f"Created bucket '{self.bucket_name}'")
                else:
                    raise
