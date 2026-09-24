"""Destination connector: stores chunk vectors and metadata in Qdrant."""

import logging
import uuid
from dataclasses import asdict

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from rag_pipeline.processing import Chunk

log = logging.getLogger(__name__)


class QdrantSink:
    def __init__(self, url: str, collection: str, api_key: str | None = None):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection = collection

    def ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        # Index "source" so per-document deletes and filtered searches stay fast.
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        log.info("Created collection '%s' (dim=%d)", self.collection, vector_size)

    def replace_document(self, source: str, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """Replace all points of a document, making re-runs idempotent."""
        # Deleting first handles documents that shrank since the last ingest.
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source))]
            ),
        )

        points = [
            PointStruct(
                # Deterministic ID: the same chunk always maps to the same point.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}#{i}")),
                vector=vector,
                payload={"source": source, "chunk_index": i, **asdict(chunk)},
            )
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)
