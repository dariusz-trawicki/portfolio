"""Entry point: semantic search over the ingested documents."""

import argparse
import textwrap

from rag_pipeline.config import Settings
from rag_pipeline.embedder import Embedder
from rag_pipeline.qdrant_sink import QdrantSink


def search(query: str, top_k: int, settings: Settings) -> list:
    # The query must be embedded with the same model that was used during ingestion.
    embedder = Embedder(settings.embed_model)
    sink = QdrantSink(settings.qdrant_url, settings.collection, settings.qdrant_api_key)
    return sink.client.query_points(
        collection_name=settings.collection,
        query=embedder.embed([query])[0],
        limit=top_k,
        with_payload=True,
    ).points


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic search over ingested documents.")
    parser.add_argument("query", help="Natural-language question")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="Number of results (default: 3)")
    args = parser.parse_args()

    hits = search(args.query, args.top_k, Settings.from_env())
    if not hits:
        print("No results. Did you run `uv run rag-ingest` first?")
        return

    for rank, hit in enumerate(hits, start=1):
        p = hit.payload
        page = f", page {p['metadata']['page_number']}" if p["metadata"].get("page_number") else ""
        print(f"\n#{rank}  score={hit.score:.3f}  {p['source']}{page}  [{p['element_type']}]")
        print(textwrap.indent(textwrap.shorten(p["text"], width=400, placeholder=" ..."), "    "))


if __name__ == "__main__":
    main()
