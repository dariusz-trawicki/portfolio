"""Entry point: runs the full S3 -> partition -> chunk -> embed -> Qdrant pipeline."""

import logging
import tempfile
import time
from pathlib import Path

from rag_pipeline.config import Settings
from rag_pipeline.embedder import Embedder
from rag_pipeline.processing import chunk_elements, partition_file
from rag_pipeline.qdrant_sink import QdrantSink
from rag_pipeline.s3_source import S3Source

log = logging.getLogger("rag_pipeline")


def run(settings: Settings) -> None:
    source = S3Source(settings.s3_bucket, settings.s3_prefix)
    embedder = Embedder(settings.embed_model)
    sink = QdrantSink(settings.qdrant_url, settings.collection, settings.qdrant_api_key)
    sink.ensure_collection(embedder.dimension)

    processed, failed, total_chunks = 0, 0, 0
    started = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp:
        for key in source.list_keys():
            try:
                doc = source.download(key, Path(tmp))
                elements = partition_file(doc.local_path, settings.partition_strategy)
                chunks = chunk_elements(elements, settings)
                if not chunks:
                    log.warning("No text extracted from %s", doc.uri)
                    continue

                vectors = embedder.embed([c.text for c in chunks])
                count = sink.replace_document(doc.uri, chunks, vectors)

                log.info("%-45s %3d elements -> %3d chunks", key, len(elements), count)
                processed += 1
                total_chunks += count
            except Exception:
                # One broken file shouldn't stop the whole batch.
                log.exception("Failed to process %s", key)
                failed += 1

    log.info(
        "Done in %.1fs: %d documents, %d chunks, %d failed",
        time.perf_counter() - started,
        processed,
        total_chunks,
        failed,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    # Unstructured and HTTP libraries are noisy at INFO level.
    for noisy in ("httpx", "botocore", "unstructured", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    run(Settings.from_env())


if __name__ == "__main__":
    main()
