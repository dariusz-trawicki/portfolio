# RAG AI – Local PDF Q&A with Hugging Face & Streamlit

A fully local RAG (`Retrieval-Augmented Generation`) demo.
Upload PDFs, build a knowledge base, and ask questions in natural language — no `API keys` required.

---

## Project Structure

```
.
├── app.py                # UI and app logic
├── ingest.py             # PDF → chunks → FAISS vectorstore
├── config.py             # LLM pipeline configuration
├── requirements.txt      # Dependencies
├── pdfs/                 # Uploaded PDFs (auto-created)
└── vectorstore/          # FAISS index (auto-created)
```

---

## How It Works

```
PDF → text extraction → chunks (400 chars, 50 overlap)
    → embeddings (all-MiniLM-L6-v2) → FAISS index

Question → embedding → similarity search → top chunks
         → flan-t5-small → answer
```

---

## Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | `google/flan-t5-small` (HuggingFace, local) |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Vector Store | FAISS (local) |
| PDF parsing | PyMuPDF (fitz) |
| Orchestration | LangChain |
| Env manager | uv |

---

## Requirements

- Python 3.11
- [uv](https://github.com/astral-sh/uv)
- ~500MB free RAM (flan-t5-small model)

---

## Setup

```sh
uv sync
```

---

## Configuration

Edit `config.py` to change the LLM model:

```python
# Faster, less accurate (default)
pipeline("text2text-generation", model="google/flan-t5-small", ...)

# Slower, more accurate (requires ~1.5GB RAM)
pipeline("text2text-generation", model="google/flan-t5-base", ...)
```

Edit `ingest.py` to change chunking parameters:

```python
RecursiveCharacterTextSplitter(
    chunk_size=400,    # characters per chunk
    chunk_overlap=50   # overlap between chunks
)
```

---

## Running

```bash
# 1. Generate sample PDF (optional – only if you don't have 
#     your own PDFs)
uv run python sample.py

# 2. Process PDFs and build the vector store
uv run python ingest.py

# 3. Launch the Streamlit app
uv run streamlit run app.py
```

Open http://localhost:8502

---

## Usage (`Streamlit UI`)

1. **Upload PDF** – upload one or more PDF files
2. **Build Knowledge Base** – click the button and wait for processing
3. **Ask a question** – type your question (e.g. `What is Streamlit?`)and press `Enter`
4. The answer and source chunks appear below
