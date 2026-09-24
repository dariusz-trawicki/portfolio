"""Application settings loaded from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # S3 source
    s3_bucket: str
    s3_prefix: str

    # Qdrant destination
    qdrant_url: str
    qdrant_api_key: str | None
    collection: str

    # Processing
    embed_model: str
    partition_strategy: str
    chunk_max_chars: int
    chunk_soft_max_chars: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "Settings":
        # Populates os.environ, so boto3 also picks up AWS_ENDPOINT_URL and credentials.
        load_dotenv()
        return cls(
            s3_bucket=os.getenv("S3_BUCKET", "documents"),
            s3_prefix=os.getenv("S3_PREFIX", ""),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            collection=os.getenv("QDRANT_COLLECTION", "documents"),
            embed_model=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            partition_strategy=os.getenv("PARTITION_STRATEGY", "auto"),
            chunk_max_chars=int(os.getenv("CHUNK_MAX_CHARS", "1000")),
            chunk_soft_max_chars=int(os.getenv("CHUNK_SOFT_MAX_CHARS", "800")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
        )
