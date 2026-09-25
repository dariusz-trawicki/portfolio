# Movie Recommendation Agent: Haystack + Qdrant Sparse Search

An LLM agent that turns natural-language requests into **one structured search**: metadata filters for exact criteria and sparse vector search for what the movie is *about*.

## How a query is decomposed

| User request | Tool call made by the agent |
|---|---|
| *"Find me a highly-rated action movie about car racing"* | `plot_query="car racing", genre="Action", min_rating=7.5` |
| *"Recommend five Japanese thrillers"* | `language="Japanese", genre="Thriller", top_k=5` (no topic, so filters only) |
| *"Any film about dreams and the subconscious?"* | `plot_query="dreams subconscious"` (no filters) |


## Stack

- **Haystack**: indexing and query pipelines, `Agent` with tool calling
- **Qdrant** (in-memory): sparse vectors + payload filtering
- **FastEmbed SPLADE** (`prithivida/Splade_PP_en_v1`): local sparse embeddings, no API needed
- **Anthropic Claude** (`claude-haiku-4-5-20251001` by default, via `anthropic-haystack`): the agent's LLM

## Quick start

```bash
cp .env.example .env   # add ANTHROPIC_API_KEY
uv sync
uv run main.py
```

The first run downloads the `SPLADE` model (~500 MB) from `Hugging Face`.

## How it works

1. **Indexing pipeline**: `FastembedSparseDocumentEmbedder → DocumentWriter`. Plot goes into the content; title, year, genre, language and rating go into metadata.
2. **Search pipeline**: `FastembedSparseTextEmbedder → QdrantSparseEmbeddingRetriever`, with Haystack filters passed at runtime.
3. **Tool** `search_movies`: if `plot_query` is set, it runs sparse search restricted by filters; otherwise it runs a metadata-only query sorted by rating. Parameter descriptions (`Annotated`) become the JSON schema the LLM sees.
4. **Agent**: calls the tool, reads the results and answers. Tool calls are printed, so you can see how each request was interpreted.

## Notes

- **Why sparse?** SPLADE vectors act like a learned BM25: strong on exact terms ("racing", "samurai") with some term expansion. For a hybrid setup, add a dense embedder and use `QdrantHybridRetriever`.
- **Qdrant Cloud**: replace `":memory:"` with `url=...` and `api_key=Secret.from_env_var("QDRANT_API_KEY")`. For large collections, create payload indexes on filtered fields.
- This pattern (LLM → structured filters + semantic query) is known as *self-querying retrieval*. It applies directly to e-commerce ("black running shoes under $100") and enterprise document search.
