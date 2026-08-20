# AI Memory-Enabled Assistant

A conversational AI chatbot built with **Streamlit** and **LangChain** that combines a local LLM (`Ollama`) with long-term vector memory (`ChromaDB`) and a safe math calculator tool.

---

## Features

- **Long-term memory** — past conversations are stored as embeddings in ChromaDB and retrieved semantically on each new query
- **Short-term memory** — recent conversation history is passed to the LLM as a sliding window (no context overflow)
- **Math calculator** — arithmetic expressions are evaluated locally without calling the LLM
- **Deduplication** — near-identical memories are not stored twice
- **Persistent storage** — memory survives app restarts (`./memory_db/`)
- **Clear memory** — two-step confirmation button to wipe the vector store

---

## Architecture

```
User Input
    │
    ├── math expression? ──► eval() with timeout ──► display result
    │
    └── natural language?
            │
            ├── similarity_search() ──► ChromaDB (long-term memory)
            │
            ├── sliding window ──────► session_state (short-term memory)
            │
            ├── SystemMessage + HumanMessage ──► Ollama LLM
            │
            └── store_memory() ──────► ChromaDB (with deduplication)
```

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Ollama (`llama3.2`) |
| Embeddings | Ollama (`llama3.2`) |
| Vector Store | ChromaDB |
| LLM Framework | LangChain |
| Package Manager | uv |

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) installed and running locally
- `llama3.2` model pulled in Ollama

---

## Setup

**1. Install dependencies**
```bash
uv venv
uv sync
```
**2. Pull the model**
```bash
ollama pull llama3.2
```

**3. Start Ollama**
```bash
ollama serve
```

**4. Run the app**
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Project Structure

```
ai-memory-agent/
├── app.py              # Main Streamlit application
├── memory_db/          # ChromaDB persistence directory (auto-created)
├── pyproject.toml      # uv project config
└── README.md
```

---

## Configuration

All tuneable parameters are defined at the top of `app.py`:

| Constant | Default | Description |
|---|---|---|
| `MODEL_NAME` | `llama3.2` | Ollama model used for LLM and embeddings |
| `TOP_K_MEMORIES` | `3` | Number of memories retrieved per query |
| `MAX_HISTORY_TURNS` | `10` | Max conversation turns sent to the LLM |
| `DEDUP_THRESHOLD` | `0.15` | Cosine distance below which a memory is considered a duplicate |
| `CALC_TIMEOUT_SEC` | `2` | Max seconds allowed for math expression evaluation |
