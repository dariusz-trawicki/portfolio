"""Source connector: lists and downloads supported documents from an S3-compatible bucket."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import boto3

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt", ".eml"}


@dataclass(frozen=True)
class S3Document:
    key: str
    uri: str
    local_path: Path


class S3Source:
    def __init__(self, bucket: str, prefix: str = ""):
        # Endpoint and credentials come from the standard AWS_* environment variables,
        # so the same code works against AWS, SeaweedFS, MinIO or moto.
        self._client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix

    def list_keys(self) -> Iterator[str]:
        # Paginate: list_objects_v2 returns at most 1000 keys per call.
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if Path(key).suffix.lower() in SUPPORTED_EXTENSIONS:
                    yield key
                else:
                    log.debug("Skipping unsupported file: %s", key)

    def download(self, key: str, dest_dir: Path) -> S3Document:
        # Flatten the key so nested "folders" don't require creating directories.
        local_path = dest_dir / key.replace("/", "__")
        self._client.download_file(self.bucket, key, str(local_path))
        return S3Document(key=key, uri=f"s3://{self.bucket}/{key}", local_path=local_path)
