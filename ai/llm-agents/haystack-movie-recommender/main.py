"""
Movie recommendation assistant: Haystack + Qdrant sparse search + LLM agent.

The agent turns a natural-language request into a single tool call that mixes:
  - metadata filters  (genre, language, min_rating, top_k)  -> exact criteria
  - sparse search     (plot_query)                          -> what the movie is ABOUT
"""
import os
import sys
from typing import Annotated

from dotenv import load_dotenv
from haystack import Document, Pipeline
from haystack.components.agents import Agent
from haystack.components.writers import DocumentWriter
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from haystack_integrations.components.generators.anthropic import AnthropicChatGenerator
from haystack_integrations.components.embedders.fastembed import (
    FastembedSparseDocumentEmbedder,
    FastembedSparseTextEmbedder,
)
from haystack_integrations.components.retrievers.qdrant import QdrantSparseEmbeddingRetriever
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore

load_dotenv()

SPARSE_MODEL = "prithivida/Splade_PP_en_v1"
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")

# Ratings are approximate, for demo purposes only.
MOVIES = [
    ("Baby Driver", 2017, "Action", "English", 7.5,
     "A young getaway driver with tinnitus relies on music to be the best car racer in the heist game."),
    ("The Fast and the Furious", 2001, "Action", "English", 6.8,
     "An undercover cop infiltrates the world of illegal street car racing in Los Angeles."),
    ("Rush", 2013, "Drama", "English", 8.1,
     "The rivalry between Formula 1 drivers James Hunt and Niki Lauda during the 1976 racing season."),
    ("Ford v Ferrari", 2019, "Drama", "English", 8.1,
     "Engineers build a race car for Ford to beat Ferrari at the 24 Hours of Le Mans."),
    ("Mad Max: Fury Road", 2015, "Action", "English", 8.1,
     "In a desert wasteland, a woman rebels against a tyrant and flees with a drifter in a war rig."),
    ("Seven Samurai", 1954, "Action", "Japanese", 8.6,
     "Farmers hire seven samurai to defend their village from bandits."),
    ("Cure", 1997, "Thriller", "Japanese", 7.4,
     "A detective investigates murders committed by people who cannot explain why they killed."),
    ("Confessions", 2010, "Thriller", "Japanese", 7.7,
     "A teacher takes revenge on the students she believes killed her daughter."),
    ("Audition", 1999, "Thriller", "Japanese", 7.1,
     "A widower holds a fake casting call to find a new wife, with disturbing consequences."),
    ("Parasite", 2019, "Thriller", "Korean", 8.5,
     "A poor family schemes to become employed by a wealthy household."),
    ("Oldboy", 2003, "Thriller", "Korean", 8.3,
     "A man imprisoned for fifteen years without explanation seeks revenge after his release."),
    ("Spirited Away", 2001, "Animation", "Japanese", 8.6,
     "A girl wanders into a world of spirits and must work in a bathhouse to save her parents."),
    ("Inception", 2010, "Sci-Fi", "English", 8.8,
     "A thief steals secrets by entering people's dreams and must plant an idea in a subconscious mind."),
    ("Amelie", 2001, "Comedy", "French", 8.3,
     "A shy waitress in Paris secretly improves the lives of the people around her."),
]


# ---------------------------------------------------------------------------
# 1. Document store + indexing pipeline
# ---------------------------------------------------------------------------
document_store = QdrantDocumentStore(
    ":memory:",                 # swap for url=... / api_key=... to use Qdrant Cloud
    use_sparse_embeddings=True,
    recreate_index=True,
)


def index_movies() -> None:
    docs = [
        Document(
            content=plot,
            meta={"title": title, "year": year, "genre": genre,
                  "language": language, "rating": rating},
        )
        for title, year, genre, language, rating, plot in MOVIES
    ]
    indexing = Pipeline()
    indexing.add_component("embedder", FastembedSparseDocumentEmbedder(
        model=SPARSE_MODEL, meta_fields_to_embed=["title"], progress_bar=False))
    indexing.add_component("writer", DocumentWriter(document_store=document_store))
    indexing.connect("embedder.documents", "writer.documents")
    indexing.run({"embedder": {"documents": docs}})
    print(f"Indexed {document_store.count_documents()} movies.\n")


# ---------------------------------------------------------------------------
# 2. Query pipeline: sparse text embedding -> filtered retrieval
# ---------------------------------------------------------------------------
search_pipeline = Pipeline()
search_pipeline.add_component("text_embedder", FastembedSparseTextEmbedder(model=SPARSE_MODEL))
search_pipeline.add_component("retriever", QdrantSparseEmbeddingRetriever(document_store=document_store))
search_pipeline.connect("text_embedder.sparse_embedding", "retriever.query_sparse_embedding")


def build_filters(genre: str | None, language: str | None, min_rating: float | None) -> dict | None:
    conditions = []
    if genre:
        conditions.append({"field": "meta.genre", "operator": "==", "value": genre})
    if language:
        conditions.append({"field": "meta.language", "operator": "==", "value": language})
    if min_rating is not None:
        conditions.append({"field": "meta.rating", "operator": ">=", "value": min_rating})
    return {"operator": "AND", "conditions": conditions} if conditions else None


# ---------------------------------------------------------------------------
# 3. The tool the agent can call
# ---------------------------------------------------------------------------
@tool
def search_movies(
    plot_query: Annotated[str, "What the movie should be ABOUT (plot, theme). "
                               "Empty string if the user gave no topic."] = "",
    genre: Annotated[str | None, "One of: Action, Drama, Thriller, Sci-Fi, Animation, Comedy"] = None,
    language: Annotated[str | None, "Original language, e.g. English, Japanese, Korean, French"] = None,
    min_rating: Annotated[float | None, "Minimum rating 0-10. 'Highly rated' means 7.5"] = None,
    top_k: Annotated[int, "How many movies to return"] = 3,
) -> str:
    """Search the movie database using plot keywords and/or metadata filters."""
    filters = build_filters(genre, language, min_rating)

    if plot_query.strip():
        # Topic given -> sparse search, restricted by filters
        result = search_pipeline.run({
            "text_embedder": {"text": plot_query},
            "retriever": {"filters": filters, "top_k": top_k},
        })
        docs = result["retriever"]["documents"]
    else:
        # No topic -> metadata only, best-rated first
        docs = document_store.filter_documents(filters=filters)
        docs = sorted(docs, key=lambda d: d.meta["rating"], reverse=True)[:top_k]

    if not docs:
        return "No movies found."
    return "\n".join(
        f"{d.meta['title']} ({d.meta['year']}) | {d.meta['genre']} | "
        f"{d.meta['language']} | rating {d.meta['rating']} | {d.content}"
        for d in docs
    )


# ---------------------------------------------------------------------------
# 4. The agent
# ---------------------------------------------------------------------------
agent = Agent(
    chat_generator=AnthropicChatGenerator(model=LLM_MODEL),
    tools=[search_movies],
    system_prompt=(
        "You are a movie recommendation assistant. Always use the search_movies tool. "
        "Put plot/theme words in plot_query and exact criteria in the other parameters. "
        "Recommend only movies returned by the tool. If fewer movies match than requested, say so."
    ),
)


def ask(question: str) -> None:
    print("=" * 80)
    print(f"USER: {question}")
    result = agent.run(messages=[ChatMessage.from_user(question)])

    for msg in result["messages"]:
        for call in msg.tool_calls:
            print(f"TOOL CALL: {call.tool_name}({call.arguments})")
    print(f"\nASSISTANT: {result['messages'][-1].text}\n")


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in .env")

    index_movies()
    ask("Find me a highly-rated action movie about car racing")
    ask("Recommend five Japanese thrillers")
    ask("Any film about dreams and the subconscious?")


if __name__ == "__main__":
    main()
