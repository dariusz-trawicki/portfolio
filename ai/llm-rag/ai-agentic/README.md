# RAG Examples: Classic Pipeline + Agentic RAG (LangGraph)

This demo contains two complementary examples of Retrieval-Augmented Generation (RAG):

1. **Classic RAG pipeline**: `PDF` ingestion → chunking → embeddings → vector database (ChromaDB) → retrieval → LLM answer generation (Groq via LangChain).
2. **Agentic RAG**: A simple stateful workflow built with **LangGraph**, where an agent decides whether retrieval is needed, optionally retrieves from a vector store (FAISS), and then generates an answer using an LLM (OpenAI via `LangChain`).

The goal is to demonstrate both:
- a straightforward, production-style RAG pipeline, and
- a lightweight “agentic” control flow that can branch conditionally.

---

## 1) Classic RAG Pipeline (PDF → Vector DB → Retrieval → LLM)

### Overview
The classic pipeline follows these steps:

1. **Load PDF documents** from a directory (recursively).
2. **Split** loaded pages into smaller **text chunks**.
3. **Embed** each chunk into a vector representation (SentenceTransformers).
4. **Store embeddings** and metadata in **ChromaDB** (persistent vector store).
5. **Retrieve** the most relevant chunks for a user query via vector similarity.
6. **Generate** a final answer using an LLM (Groq) grounded in retrieved context.

### Key Components

#### A. PDF Ingestion
- Uses `PyPDFLoader` (LangChain community loader) to load PDFs page-by-page.
- Adds useful metadata to each page document:
  - `source_file` (filename)
  - `file_type` (`pdf`)
  - (plus loader-provided metadata like `page`)

**Why it matters:** RAG answers are more useful when you can trace output back to sources (file + page).

#### B. Chunking / Text Splitting
- Uses `RecursiveCharacterTextSplitter` with parameters like:
  - `chunk_size=1000`
  - `chunk_overlap=200`
  - custom separators (`\n\n`, `\n`, space, fallback)

**Why it matters:** Smaller chunks improve retrieval precision and reduce irrelevant context.

#### C. Embedding Generation
- Uses `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) to generate dense vector embeddings.

**Why it matters:** Embeddings enable semantic search (meaning-based similarity), not just keyword matching.

#### D. Vector Store (ChromaDB)
- Uses `chromadb.PersistentClient` to persist vectors to disk.
- Creates or loads a collection (e.g., `"pdf_documents"`).
- Stores:
  - `documents` (chunk text)
  - `embeddings`
  - `metadatas` (source, page, content length, etc.)
  - `ids` (unique IDs per chunk)

**Why it matters:** Persistence allows reuse without re-embedding every run.

#### E. Retriever
- Embeds the query text using the same embedding model.
- Queries ChromaDB for top-k nearest neighbors.
- Converts ChromaDB cosine distance to similarity score:
  - `similarity_score = 1 - distance`
- Supports filtering by a minimum similarity threshold.

**Why it matters:** Retrieval is the core of RAG grounding—better retrieval usually means better answers.

#### F. LLM Answer Generation (Groq)
- Uses `langchain_groq.ChatGroq` (e.g., `llama-3.1-8b-instant`).
- Builds prompts that include:
  - retrieved **context**
  - the **question**
  - instructions to avoid hallucination if context is insufficient

**Why it matters:** The LLM is guided to answer based on retrieved evidence.

### “Simple” vs “Advanced” RAG functions
The example shows multiple styles:
- **`rag_simple`**: retrieve → join context → prompt LLM
- **`rag_advanced`**: adds:
  - `min_score` threshold
  - source list (file/page/score/preview)
  - confidence (e.g., max similarity score)
  - optional context return
- **`AdvancedRAGPipeline`**: demonstrates additional “features” like:
  - history tracking
  - optional summarization step
  - basic “streaming simulation” (printing prompt chunks)

> Note: The “streaming” in the example is a print-based simulation, not true token streaming from the model provider.

---

## 2) Agentic RAG with LangGraph (Decision → Optional Retrieval → Generation)

### Overview
This example uses **LangGraph** to model a small agent workflow as a **state machine**:

1. Start with a question
2. Decide if retrieval is needed
3. If needed: retrieve documents
4. Generate answer
5. End

### Key Concepts

#### A. State Definition
A typed state container (via `TypedDict`) tracks:

- `question`: user query
- `documents`: retrieved docs (if any)
- `answer`: final response
- `needs_retrieval`: decision flag

**Why it matters:** LangGraph encourages explicit state, which makes multi-step flows easier to debug and extend.

#### B. Vector Store + Retriever (FAISS)
- Uses `FAISS.from_documents(...)` to build an in-memory vector store.
- Uses `OpenAIEmbeddings()` for embeddings.
- Exposes a retriever (`k=3`).

**Why it matters:** FAISS is fast and simple for local demos; Chroma is convenient for persistence.

#### C. Agent Decision Node
`decide_retrieval` uses a simple heuristic:
- if question contains keywords like `"what"`, `"how"`, `"explain"`, etc. → retrieval

**Why it matters:** In real systems you’d replace this with:
- a classifier,
- an LLM-based router,
- or a policy based on confidence / intent.

#### D. Conditional Edges
LangGraph routes based on `should_retrieve(state)`:
- `"retrieve"` → go to retrieval node
- `"generate"` → go directly to generation node

**Why it matters:** This is the core “agentic” pattern: branching logic based on intermediate decisions.

#### E. Generation Node
`generate_answer`:
- if documents exist: builds a context-augmented prompt (RAG mode)
- else: direct answer prompt (no retrieval)

**Why it matters:** It shows how an agent can choose between “RAG” and “pure LLM” modes.

---

## Comparing the Two Approaches

### Classic RAG
Best when you want:
- predictable, testable pipelines
- persistent vector storage
- straightforward retrieval + generation
- easier production hardening

### Agentic RAG (LangGraph)
Best when you want:
- conditional routing (retrieve or not, choose tools, retry)
- multi-step workflows (plan → search → verify → answer)
- memory/history/state tracked explicitly
- flexibility to extend into more complex behaviors

In practice, many production systems combine both:
- a reliable ingestion/retrieval backbone (classic RAG),
- plus an orchestration layer (agentic workflows) for routing, tool use, retries, summarization, citation formatting, etc.

---

## Environment Variables

Depending on which example you run:

### Groq-based pipeline
- `GROQ_API_KEY` — required to generate LLM outputs with Groq.

### OpenAI + LangGraph pipeline
- `OPENAI_API_KEY` — required for `ChatOpenAI` and `OpenAIEmbeddings`.



---

## Practical Improvements (Next Steps)

If you extend these examples, common upgrades include:

- **Better chunking strategy**
  - chunk by headings/sections
  - add semantic chunking
- **Metadata enrichment**
  - include PDF page numbers, titles, section headers
- **Deduplication**
  - hash chunks to avoid re-adding to vector DB
- **Retrieval quality**
  - hybrid search (BM25 + vectors)
  - reranking (cross-encoder)
- **Citations**
  - format citations as (file, page) and include them in final answers
- **Agent routing**
  - use an LLM router instead of keyword heuristics
  - add fallback behaviors (retry retrieval, ask clarifying questions, summarize context)

---

## What Each Notebook Demonstrates

### Notebook 1: RAG Pipelines (Ingestion → ChromaDB → Retrieval → Groq)
- PDF loading from a directory
- chunking with overlap
- embeddings with SentenceTransformers
- persistent ChromaDB storage
- similarity retrieval
- LLM response generation grounded in retrieved context

### Notebook 2: Agentic RAG with LangGraph
- defining a typed state
- building a FAISS vector store
- conditional decision to retrieve
- LangGraph workflow compilation
- running end-to-end queries via `app.invoke`


## Getting Started

### Jupyter & Virtual Environment Setup

This project uses `uv` for dependency and environment management.

```bash
# Create virtual environment:
uv venv
# Install dependencies:
uv sync
# Register Jupyter kernel:
python -m ipykernel install --user --name rag-demo --display-name "Python (rag-demo)"
```