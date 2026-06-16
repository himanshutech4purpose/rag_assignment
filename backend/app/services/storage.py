"""MinIO object storage service."""

import asyncio
from io import BytesIO

from minio import Minio

from app.config import Settings
from app.exceptions import StorageError
from app.logging_config import get_logger

logger = get_logger(__name__)


class StorageService:
    """Async-friendly wrapper around the MinIO client."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )

    async def ensure_bucket(self) -> None:
        """Create the configured bucket if it does not exist."""
        try:
            exists = await asyncio.to_thread(
                self._client.bucket_exists, self._settings.minio_bucket_name
            )
            if not exists:
                await asyncio.to_thread(
                    self._client.make_bucket, self._settings.minio_bucket_name
                )
                logger.info("Created MinIO bucket: %s", self._settings.minio_bucket_name)
        except Exception as exc:
            logger.exception("Failed to ensure MinIO bucket")
            raise StorageError(f"Bucket initialization failed: {exc}") from exc

    async def upload(self, object_name: str, data: bytes) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                self._settings.minio_bucket_name,
                object_name,
                BytesIO(data),
                len(data),
            )
            logger.debug("Uploaded object: %s", object_name)
        except Exception as exc:
            logger.exception("Failed to upload object: %s", object_name)
            raise StorageError(f"Upload failed: {exc}") from exc

    async def delete(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.remove_object,
                self._settings.minio_bucket_name,
                object_name,
            )
            logger.debug("Deleted object: %s", object_name)
        except Exception as exc:
            logger.exception("Failed to delete object: %s", object_name)
            raise StorageError(f"Delete failed: {exc}") from exc
