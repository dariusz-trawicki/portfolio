"""Index the PDF knowledge base into Qdrant.

Pipeline: PDF -> Docling (layout-aware parsing) -> heading-aware chunks ->
embeddings -> Qdrant.  Re-run whenever the files in docs/ change.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from config import settings

BATCH_SIZE = 64


def chunk_pdf(pdf_path: Path, converter, chunker) -> list[dict]:
    """Turn one PDF into chunks, each prefixed with its heading breadcrumb."""
    document = converter.convert(str(pdf_path)).document
    chunks = []
    for piece in chunker.chunk(document):
        content = piece.text.strip()
        if not content:
            continue
        headings = list(piece.meta.headings or [])
        breadcrumb = " > ".join(headings)
        chunks.append(
            {
                "source": pdf_path.name,
                "headings": headings,
                "content": content,
                "chunk_text": f"{breadcrumb}\n{content}" if breadcrumb else content,
            }
        )
    return chunks


def stable_id(chunk: dict) -> str:
    """Deterministic point ID, so re-indexing never creates duplicates."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk['source']}::{chunk['chunk_text']}"))


def ingest(docs_dir: str) -> int:
    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker import HierarchicalChunker
    from qdrant_client.models import Distance, PointStruct, VectorParams

    from energy_agent.resources import get_embedder, open_qdrant

    pdfs = sorted(Path(docs_dir).glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in '{docs_dir}'. Generate them with: python scripts/build_docs.py")
        return 0

    print(f"\n[1/3] Parsing {len(pdfs)} documents")
    converter = DocumentConverter()
    chunker = HierarchicalChunker()  # one chunk per document element (paragraph, table, list item)
    chunks: list[dict] = []
    failed: list[str] = []
    for pdf in pdfs:
        try:
            doc_chunks = chunk_pdf(pdf, converter, chunker)
        except Exception as exc:  # one bad file shouldn't stop the run
            print(f"  [FAIL] {pdf.name}: {exc}")
            failed.append(pdf.name)
            continue
        print(f"  [OK] {pdf.name}: {len(doc_chunks)} chunks")
        chunks.extend(doc_chunks)

    if not chunks:
        print("No chunks were produced – check the documents.")
        return 0

    print(f"\n[2/3] Embedding with {settings.embedding_model}")
    vectors = get_embedder().encode(
        [c["chunk_text"] for c in chunks],
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    print(f"\n[3/3] Writing to Qdrant collection '{settings.collection_name}'")
    client = open_qdrant()
    try:
        # recreate_collection() is deprecated in qdrant-client; drop and create explicitly.
        if client.collection_exists(settings.collection_name):
            client.delete_collection(settings.collection_name)
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(size=int(vectors.shape[1]), distance=Distance.COSINE),
        )
        points = [PointStruct(id=stable_id(c), vector=v.tolist(), payload=c) for c, v in zip(chunks, vectors, strict=True)]
        for start in range(0, len(points), BATCH_SIZE):
            client.upsert(settings.collection_name, points=points[start : start + BATCH_SIZE], wait=True)
        total = client.get_collection(settings.collection_name).points_count
    finally:
        client.close()

    print(f"\n[DONE] Indexed {total} chunks.")
    if failed:
        print(f"Skipped: {', '.join(failed)}")
    return total


if __name__ == "__main__":
    print(f"{settings.company_name} – knowledge-base ingestion")
    print(f"  Documents: {settings.docs_dir}")
    print(f"  Qdrant:    {settings.qdrant_url or settings.qdrant_path}")
    ingest(settings.docs_dir)
