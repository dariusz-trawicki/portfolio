# Multimodal Search with jina-embeddings-v4 + Qdrant

A demo of **cross-modal retrieval**: text and images are embedded into a single vector space, stored in **one** Qdrant collection, and searched in every direction with the same query pipeline.

## What it demonstrates

| # | Query | Searches in | Expected top hit |
|---|---|---|---|
| 1 | Text: *"How do I run containers on many servers?"* | text | Kubernetes passage |
| 2 | Text: *"chart showing revenue per quarter"* | images | `revenue_bar_chart.png` |
| 3 | Image: `market_share_pie.png` | text | Market share passage |
| 4 | Image: `query_sales_line_chart.png` (not indexed) | images | `revenue_bar_chart.png` |
| 5 | Text: *"How much does a GPU server cost per hour?"* | everything | GPU passage **and** `ec2_pricing_table.png` |

Query 1 contains no keyword from the matching document, so retrieval is semantic rather than lexical. Query 5 returns text and images from one collection with a single query.

## Stack

- **jina-embeddings-v4** (Jina AI API): 3.8B-parameter multimodal embedding model based on `Qwen2.5-VL`
- **Qdrant**: vector database, run in-memory (`:memory:`), no server needed
- **matplotlib**: generates sample images (charts, table, diagram) locally, no downloads

## Quick start

```bash
cp .env.example .env    # add your key from https://jina.ai/embeddings (10M free tokens)
uv sync
uv run main.py
```

A full run uses roughly tens of thousands of tokens, well within the free tier.

## How it works

1. **Generate data**: 4 images for the index and 1 query-only image, plus 6 short text passages (one deliberately off-topic).
2. **Embed**: texts (`{"text": ...}`) and images (`{"image": <base64>}`) are sent to the same model in one batch request.
   - Documents use `task="retrieval.passage"` and queries use `task="retrieval.query"` (asymmetric retrieval).
   - `dimensions=1024` truncates the default 2048-d vectors.
3. **Index**: all vectors go into one collection (cosine distance). The payload stores `type` (`text` / `image`) and the content or file name.
4. **Search**: `query_points` with an optional payload filter on `type` to force a direction (e.g. text → images only).

Images themselves are **not** stored in Qdrant. The payload holds only the file name, which points to `images/`. This mirrors the production pattern of keeping blobs in object storage (S3/GCS) and references in the vector DB.

## Notes

- **Modality gap**: text↔image similarity scores are typically lower than text↔text. In mixed results (query 5), compare the ranking within each modality rather than raw scores across modalities, or add a reranker.
- **Production**: swap `QdrantClient(":memory:")` for `QdrantClient(url=...)`; nothing else changes.
- **License**: jina-embeddings-v4 weights are CC BY-NC 4.0, which is fine for learning and portfolio use. Commercial use requires an agreement with Jina AI. Newer `jina-embeddings-v5-omni-*` models also cover audio, video and PDF and use far fewer tokens per image.

## Project structure

```
.
├── main.py           # generate images → embed → index → search
├── pyproject.toml
├── .env.example
└── images/           # created at runtime
```
