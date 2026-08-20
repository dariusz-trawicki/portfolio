# PageIndex + Claude Haiku — Vectorless RAG Demo

A minimal, reasoning-based RAG pipeline that skips chunking and vector databases entirely. Instead, [PageIndex](https://pageindex.ai) builds a hierarchical tree index from a PDF, and Claude Haiku reasons over that tree to find and answer from the right sections.

## How it works

```
PDF → PageIndex builds a tree index (sections, subsections, page refs)
    → Claude reasons over the tree to pick relevant node IDs
    → Relevant sections are retrieved and passed to Claude
    → Claude generates a grounded, cited answer
```

No embeddings, no chunk overlap tuning, no vector DB.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- A **PageIndex** API key: https://dash.pageindex.ai/api-keys
- An **Anthropic** API key: https://console.anthropic.com/settings/keys

## Project structure

```
pageindex-demo/
├── pyproject.toml
├── .venv/
├── .env
├── data/
│   └── sample_document.pdf
└── pageindex_vectorless_rag.ipynb
```

## Setup

### 1. Install uv (skip if already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Initialize the project

```bash
mkdir pageindex-demo && cd pageindex-demo
uv init
```

### 3. Install dependencies

```bash
uv add pageindex anthropic python-dotenv jupyterlab ipykernel
```

`uv add` installs everything into this project's own `.venv` and records it in `pyproject.toml` — this avoids the classic "installed with pip but the notebook kernel can't see it" problem.

### 4. Add the demo files

Place the notebook in the project root, and the sample PDF inside a `data/` subfolder:

```bash
mkdir data
# copy sample_document.pdf into ./data/
# copy pageindex_vectorless_rag.ipynb into the project root
```

### 5. Create your `.env` file

In the project root, create a file named `.env` with:

```dotenv
PAGEINDEX_API_KEY=your_pageindex_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 6. Launch Jupyter through uv

```bash
uv run jupyter lab
```

Using `uv run` (rather than launching Jupyter some other way) ensures the notebook kernel runs inside this project's `.venv`, so it can actually see the packages you just installed.

### 7. Open the notebook and check the PDF path

The notebook expects:

```python
PDF_PATH = "./data/sample_document.pdf"
```

Confirm the kernel selected in the top-right of JupyterLab points to this project's `.venv`, then run the cells in order (Shift+Enter).


## What's in the notebook

1. **Setup** — install clients, load API keys, initialize `PageIndexClient` and `Anthropic`
2. **Upload & Index** — send the PDF to PageIndex, poll until the tree is built
3. **Inspect the Tree** — print the hierarchical section structure
4. **LLM Tree Search** — Claude Haiku reasons over the tree to find relevant `node_id`s
5. **Full Pipeline** — `vectorless_rag()` combines search, retrieval, and answer generation

## Resources

- PageIndex docs: https://docs.pageindex.ai
- PageIndex GitHub (self-hosted, open-source option): https://github.com/VectifyAI/PageIndex
- Anthropic docs: https://docs.claude.com
