"""Downloading and uploading artifacts: file:// locally, gs:// in the cloud.

The same code runs on KIND (with fake-gcs-server via STORAGE_EMULATOR_HOST)
and on GKE (with real GCS via Workload Identity) — only the endpoint and
the authentication method differ, not the execution path.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse


def _gcs_client():
    from google.cloud import storage

    if os.getenv("STORAGE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials

        return storage.Client(credentials=AnonymousCredentials(), project="local")
    return storage.Client()


def download_dir(uri: str, dest: Path) -> Path:
    """Downloads the whole artifact directory (prefix) into dest."""
    parsed = urlparse(uri)
    dest.mkdir(parents=True, exist_ok=True)

    if parsed.scheme in ("", "file"):
        src = Path(parsed.path)
        if not src.exists():
            raise FileNotFoundError(f"Source directory not found: {src}")
        for item in src.iterdir():
            if item.is_file():
                shutil.copy(item, dest / item.name)
        return dest

    if parsed.scheme == "gs":
        client = _gcs_client()
        bucket = client.bucket(parsed.netloc)
        prefix = parsed.path.lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"
        blobs = list(client.list_blobs(bucket, prefix=prefix))
        if not blobs:
            raise FileNotFoundError(f"No objects found under {uri}")
        for blob in blobs:
            name = blob.name[len(prefix) :]
            if name:
                blob.download_to_filename(dest / name)
        return dest

    raise ValueError(f"Unsupported URI scheme: {uri}")


def upload_dir(src: Path, uri: str) -> None:
    """Uploads the contents of a local directory to the given URI — used by training."""
    parsed = urlparse(uri)

    if parsed.scheme in ("", "file"):
        dest = Path(parsed.path)
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.is_file():
                shutil.copy(item, dest / item.name)
        return

    if parsed.scheme == "gs":
        client = _gcs_client()
        bucket = client.bucket(parsed.netloc)
        prefix = parsed.path.lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"
        for item in src.iterdir():
            if item.is_file():
                bucket.blob(prefix + item.name).upload_from_filename(item)
        return

    raise ValueError(f"Unsupported URI scheme: {uri}")
