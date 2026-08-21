# Local AI Agent Demo (Ollama + LangChain + Chainlit)

This project demonstrates how to build a **local AI assistant** powered by:

- **Ollama** (local LLM runtime)
- **LangChain** (agent framework + tools)
- **LangGraph** (memory / state)
- **Chainlit** (chat UI)

Two versions of the agent are provided:

1. `agent_offline.py` – 100% Local Version
2. `agent_online.py` – Online Version (with Tavily Web Search)

---

## Project Structure

```
project/
├── agent_offline.py
├── agent_online.py
├── .env
└── README.md
```

---

## Technologies Used

| Component | Purpose |
|----------|---------|
| Ollama | Runs local LLM models |
| LangChain | Agents, tools, message pipelines |
| LangGraph | Memory & state |
| Chainlit | Browser chat UI |
| Tavily | (Online version) Web search tool |


---

## Prerequisites

Make sure you have installed:

1. **uv** - Fast Python package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
   
```bash
# macOS
brew install uv
```

2. **Ollama** - Local AI model runtime ([download page](https://ollama.com/download/mac))
   
```bash
# macOS
brew install ollama
```

---

## 1. agent_offline.py – 100% Local Version

Works entirely offline using:

- a local Ollama model
- local tools implemented in Python
- no external API calls
- no internet requirement

### Features

- Word counting tool
- Text reversing tool
- Local LLM (Qwen3 via Ollama)
- Real-time streaming responses in Chainlit UI


### Run

1. Start Ollama (terminal I):

```bash
ollama serve
```

2. Pull the model (terminal II):

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

3. Run the agent (terminal II):

```bash
uv sync
uv run agent_offline.py
```

4. Open the URL shown in the terminal.

---

## 2. agent_online.py – Online Version (with Tavily Web Search)

This version extends the offline agent with:

- TavilySearch tool (real web search)
- `.env` configuration using python-dotenv
- the same local tools + LLM

### Requirements

- Get a free API key at: https://tavily.com.

- Create a `.env` file:

```bash
TAVILY_API_KEY=YOUR_TAVILY_API_KEY
```

### Run (terminal II)

```bash
# STOP agent_offline.py (ctr+c)
uv run agent_online.py
```

4. Open the Chainlit UI in the browser.
