"""Lazily created, shared resources: the embedding model and the Qdrant client.

LiveKit runs each call in its own worker process, and embedded Qdrant locks
its data directory. Opening the database at import time would also open it in
the parent process and risk lock conflicts, so everything here is created on
first use instead.
"""

from __future__ import annotations

import atexit
from functools import lru_cache
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def open_qdrant() -> QdrantClient:
    """A new client – a Qdrant server if QDRANT_URL is set, otherwise embedded."""
    from qdrant_client import QdrantClient

    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    return QdrantClient(path=settings.qdrant_path)


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    client = open_qdrant()
    atexit.register(client.close)  # release the embedded-DB lock cleanly on exit
    if not client.collection_exists(settings.collection_name):
        raise RuntimeError(
            f"Qdrant collection '{settings.collection_name}' not found. "
            "Run `python ingest.py` first."
        )
    count = client.get_collection(settings.collection_name).points_count
    print(f"[OK] Knowledge base '{settings.collection_name}': {count} chunks")
    return client
