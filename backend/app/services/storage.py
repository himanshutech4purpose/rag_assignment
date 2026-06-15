from io import BytesIO

from minio import Minio

from app.config import settings

client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_use_ssl,
)


def ensure_bucket():
    if not client.bucket_exists(settings.minio_bucket_name):
        client.make_bucket(settings.minio_bucket_name)


def upload_file(object_name: str, data: bytes, length: int):
    client.put_object(settings.minio_bucket_name, object_name, BytesIO(data), length)


def delete_file(object_name: str):
    client.remove_object(settings.minio_bucket_name, object_name)
