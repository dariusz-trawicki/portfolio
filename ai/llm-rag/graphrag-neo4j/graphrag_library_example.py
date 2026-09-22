# /// script
# dependencies = [
#     "neo4j-graphrag[anthropic,sentence-transformers]",
#     "python-dotenv>=1.0",
# ]
# ///

"""GraphRAG pipeline built on Neo4j and the official `neo4j-graphrag` library.

Ingests free text into a Neo4j knowledge graph (via an LLM-driven extraction
pipeline) and answers questions using vector-similarity retrieval over the
resulting graph, combined with an LLM for answer generation.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from types import TracebackType

from dotenv import load_dotenv

load_dotenv()

import neo4j
from neo4j_graphrag.embeddings.sentence_transformers import SentenceTransformerEmbeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.llm import AnthropicLLM
from neo4j_graphrag.retrievers import VectorRetriever


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

VECTOR_INDEX_NAME = "chunk_embeddings"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384  # must match EMBEDDING_MODEL's output size
LLM_MODEL = "claude-sonnet-4-6"

# Closed vocabulary passed to SimpleKGPipeline as `schema`. Constraining the
# extraction to a fixed set of labels/relationship types prevents the LLM
# from inventing synonymous variants of the same fact (e.g. COOPERATES_WITH
# vs. COLLABORATES_WITH) across separate extraction calls.
NODE_TYPES = ["Person", "Company", "Project"]
RELATIONSHIP_TYPES = ["WORKS_AT", "WORKED_AT", "PARTNERS_WITH", "WORKS_ON"]
ALLOWED_PATTERNS = [
    ("Person", "WORKS_AT", "Company"),
    ("Person", "WORKED_AT", "Company"),
    ("Company", "PARTNERS_WITH", "Company"),
    ("Company", "WORKS_ON", "Project"),
    ("Person", "WORKS_ON", "Project"),
]


@dataclass
class Neo4jSettings:
    """Connection settings, read from environment variables with local defaults."""

    uri: str = field(default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD", "password"))


# --------------------------------------------------------------------------- #
# GraphRAG service
# --------------------------------------------------------------------------- #

class GraphRAGService:
    """Encapsulates knowledge-graph ingestion and question answering over Neo4j.

    The embedder and LLM clients are created once and reused across calls,
    which avoids the cost of reloading the local embedding model on every
    ingest/query.
    """

    def __init__(self, settings: Neo4jSettings | None = None) -> None:
        self.settings = settings or Neo4jSettings()
        self.driver = neo4j.GraphDatabase.driver(
            self.settings.uri, auth=(self.settings.user, self.settings.password)
        )
        self.embedder = SentenceTransformerEmbeddings(model=EMBEDDING_MODEL)
        self.llm = AnthropicLLM(model_name=LLM_MODEL, model_params={"max_tokens": 2000})

        self._ensure_vector_index()
        self._kg_builder = SimpleKGPipeline(
            llm=self.llm,
            driver=self.driver,
            embedder=self.embedder,
            schema={
                "node_types": NODE_TYPES,
                "relationship_types": RELATIONSHIP_TYPES,
                "patterns": ALLOWED_PATTERNS,
            },
            on_error="IGNORE",
            from_file=False,
        )
        self._retriever = VectorRetriever(self.driver, VECTOR_INDEX_NAME, self.embedder)
        self._rag = GraphRAG(retriever=self._retriever, llm=self.llm)

    def _ensure_vector_index(self) -> None:
        """Create the vector index on Chunk nodes if it doesn't already exist.

        Requires the Neo4j APOC plugin to be installed (used internally by
        the KG-building pipeline for entity resolution).
        """
        create_vector_index(
            self.driver,
            VECTOR_INDEX_NAME,
            label="Chunk",
            embedding_property="embedding",
            dimensions=EMBEDDING_DIMENSIONS,
            similarity_fn="cosine",
        )

    async def ingest(self, text: str) -> None:
        """Extract entities/relationships from `text` and merge them into the graph."""
        await self._kg_builder.run_async(text=text)

    def ask(self, question: str, top_k: int = 5) -> str:
        """Answer `question` using vector retrieval over the graph plus the LLM."""
        response = self._rag.search(query_text=question, retriever_config={"top_k": top_k})
        return response.answer

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> "GraphRAGService":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #

SAMPLE_TEXT = """
Anna Kowalska is the CEO of TechNova. TechNova partners with DataSoft on a
data analytics project. Piotr Nowak works at DataSoft as a Lead Engineer and
previously worked at TechNova.
"""

SAMPLE_QUESTION = "What connections exist between TechNova and DataSoft?"


async def main() -> None:
    with GraphRAGService() as service:
        await service.ingest(SAMPLE_TEXT)
        answer = service.ask(SAMPLE_QUESTION)

        print(f"\nQUESTION: {SAMPLE_QUESTION}")
        print(f"ANSWER: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
