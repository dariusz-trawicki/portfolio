# 🕸️ LangGraph Search Agent

A minimal LangGraph agent that decides whether a question requires a live web search or can be answered directly by the LLM.

## How it works

```
START
  ↓
[analyze] — LLM decides: needs_search? (True / False)
              ↓ True                  ↓ False
           [search]               [answer]
           Tavily API                 ↓
              ↓                      END
           [answer]
              ↓
             END
```

## Stack

| Component | Technology |
|---|---|
| Agent framework | LangGraph |
| LLM | GPT-4o (OpenAI) |
| Web search | Tavily Search |
| Structured output | Pydantic `BaseModel` |
| Environment | python-dotenv |
| Package manager | uv |

## Project structure

```
.
├── main.py            # agent logic
├── .env.example       # API keys template (copy to .env)
├── .python-version    # Python version for uv
├── pyproject.toml     # managed by uv
└── uv.lock            # locked dependencies
```

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure API keys

Create a `.env` file:

```bash
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

- OpenAI key: [platform.openai.com](https://platform.openai.com)
- Tavily key: [app.tavily.com](https://app.tavily.com) — free tier: 1000 requests/month


### 3. Run

```bash
uv run main.py
```

## Example output

```
[analyze] needs_search=True  | reason=Weather is real-time data...
[search]  searching for: What is the weather like in Warsaw today?
[search]  results found
[answer]  Today in Warsaw it is mostly clear, 8°C...

✅ Answer: Today in Warsaw it is mostly clear, 8°C...

──────────────────────────────────────────────────

[analyze] needs_search=False | reason=Math does not require internet...
[answer]  2 to the power of 10 is 1024.

✅ Answer: 2 to the power of 10 is 1024.
```

## Key concepts

### State
A `TypedDict` that flows through all nodes — each node reads and modifies it:

```python
class AgentState(TypedDict):
    question: str
    search_results: str
    answer: str
    needs_search: bool
```

### Nodes
Functions that take `state` as input and return a partial state update:

| Node | Responsibility |
|---|---|
| `analyze` | LLM decides if search is needed (`with_structured_output`) |
| `search` | Calls Tavily API, stores results in state |
| `answer` | Generates final answer with or without search context |

### Conditional edge (router)
```python
def router(state: AgentState):
    if state["needs_search"]:
        return "search"
    return "answer"
```

## Dependencies

```
langgraph
langchain
langchain-openai
langchain-community
langchain-tavily
tavily-python
python-dotenv
```
