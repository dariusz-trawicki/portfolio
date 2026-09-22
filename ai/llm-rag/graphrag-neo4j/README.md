# GraphRAG with Neo4j

A minimal, runnable example of **GraphRAG**: extracting a knowledge graph
from unstructured text with an LLM, storing it in [Neo4j](https://neo4j.com/),
and answering questions using vector-similarity retrieval over the graph
combined with an LLM for generation.

Built on the official [`neo4j-graphrag`](https://neo4j.com/docs/neo4j-graphrag-python/current/)
library and the Anthropic API.

## How it works

```
free text
   │
   ▼
SimpleKGPipeline  ──► LLM extracts entities & relationships (constrained schema)
   │
   ▼
Neo4j knowledge graph  (Person / Company / Project nodes + typed relationships)
   │
   ▼
VectorRetriever  ──► embeds text chunks, finds semantically similar chunks to a question
   │
   ▼
GraphRAG (retriever + LLM)  ──► generates a grounded answer
```

Unlike a plain vector-RAG setup, the retrieval step here is backed by a
graph: the extraction stage enforces a **closed schema** (a fixed list of
node labels and relationship types), which keeps the graph consistent and
prevents the LLM from inventing synonymous relationship names for the same
fact across separate extraction calls.

## Requirements

- [uv](https://docs.astral.sh/uv/) — used to run the script and manage dependencies
- [Docker](https://www.docker.com/) — to run Neo4j locally
- An [Anthropic API key](https://console.anthropic.com/)

## Setup

### 1. Start Neo4j with the APOC plugin

APOC is required by the knowledge-graph pipeline for entity resolution.

```bash
docker run \
  --name neo4j-graphrag \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/<your-neo4j-password> \
  -e NEO4JLABS_PLUGINS='["apoc"]' \
  -d \
  neo4j:5
```

Check it started correctly:

```bash
docker logs neo4j-graphrag | grep -i apoc
```

Neo4j Browser is available at http://localhost:7474 (same credentials as above).

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your Anthropic API key and NEO4J password:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

### 3. Run

NOTE: Dependencies are declared inline in the script — `uv run` installs
them automatically, no separate install step needed.

```bash
uv run graphrag_library_example.py
```

First run downloads the local embedding model (`all-MiniLM-L6-v2`, ~80 MB) from Hugging Face, so it may take a moment.

## Project structure

```
.
├── graphrag_library_example.py   # main script
├── .env.example                     # environment variable template
└── README.md
```

## Design notes

- **Embeddings run locally** (`SentenceTransformerEmbeddings`) rather than
  through an API — no second API key required, and text never leaves the
  machine at the embedding step. Trade-off: lower retrieval quality than a
  hosted embedding model at scale.
- **Constrained extraction schema** (`NODE_TYPES`, `RELATIONSHIP_TYPES`,
  `ALLOWED_PATTERNS`) is the main lever for graph consistency. Without it,
  LLM-based extraction tends to produce near-duplicate relationship types
  for the same underlying fact.
- **`GraphRAGService`** creates the embedder, LLM client, and Neo4j driver
  once and reuses them across ingestion and query calls, instead of
  re-instantiating them per call.

## Cleanup

```bash
docker rm -f neo4j-graphrag
```

This removes the container along with its data (no named volume was used in the setup above). If you want data to survive container removal, add `-v neo4j-data:/data` when starting the container, and clean it up separately with `docker volume rm neo4j-data`.

## License

MIT
