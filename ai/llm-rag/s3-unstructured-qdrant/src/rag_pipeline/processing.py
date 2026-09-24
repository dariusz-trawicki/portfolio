"""Partition and chunk documents with Unstructured."""

from dataclasses import dataclass, field
from pathlib import Path

from unstructured.chunking.title import chunk_by_title
from unstructured.partition.auto import partition

from rag_pipeline.config import Settings


@dataclass(frozen=True)
class Chunk:
    text: str
    element_type: str
    metadata: dict = field(default_factory=dict)


def partition_file(path: Path, strategy: str = "auto") -> list:
    """Split a file into typed elements (Title, NarrativeText, Table, ListItem, ...)."""
    # "auto" picks the fast text extractor for digital PDFs and falls back to OCR for scans.
    return partition(filename=str(path), strategy=strategy)


def chunk_elements(elements: list, settings: Settings) -> list[Chunk]:
    """Group elements into retrieval-sized chunks that respect section boundaries."""
    raw_chunks = chunk_by_title(
        elements,
        max_characters=settings.chunk_max_chars,
        new_after_n_chars=settings.chunk_soft_max_chars,
        overlap=settings.chunk_overlap,
        # Merge tiny sections (e.g. a lone heading) into the next one.
        combine_text_under_n_chars=200,
    )

    chunks = []
    for c in raw_chunks:
        text = c.text.strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                text=text,
                element_type=type(c).__name__,  # CompositeElement, Table or TableChunk
                metadata={"page_number": c.metadata.page_number},
            )
        )
    return chunks
