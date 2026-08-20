# Azure OpenAI

Minimal example of Azure OpenAI API integration using Python.

---

## Azure Setup

### 1. Create an Azure OpenAI Resource

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search for **Azure OpenAI** → click **Create Azure OpenAI resource**
3. Fill in the required fields: Subscription, Resource Group, Region, Name.
4. Once created, navigate to the resource → **Keys and Endpoint**
5. Copy **KEY 1** and **Endpoint** — you'll need them for `.env`

### 2. Deploy a Model in Azure AI Foundry

1. Inside the resource, click **Explore Foundry Portal**.
2. Go to **Deployments** → **+** → **Base model** → select e.g. `gpt-4.1-mini`.
3. Leave the deployment name as default (e.g. `gpt-4.1-mini`) — copy it to `.env`.
4. Click **Customize** and set token limit (e.g. 30k tokens/min).
5. After deployment, a **Chat Playground** appears where you can test the model.

You can also find your `API Key` and `Endpoint` here:
`Azure OpenAI → your-resource → Deployments → gpt-4.1-mini`

---

## Project Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed
- Azure account with a paid subscription (Pay-As-You-Go or higher)

### 1. Clone and initialize

```bash
uv init
uv add openai python-dotenv
```

### 2. Create `.env` file

```env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_KEY=your_key_1_here
AZURE_DEPLOYMENT_NAME=gpt-4.1-mini
```

---

## Examples

### 1. chat_basic.py

Minimal example of a single-turn chat completion with Azure OpenAI.

Sends one question to the model and prints the response.
No conversation history — each call is independent.

### Run

```bash
uv run chat_basic.py
```

**Example output:**
```
The average distance from the Earth to the Moon is about 384,400 kilometers (238,855 miles).
This distance can vary slightly due to the Moon's elliptical orbit around the Earth.
```


### 2. chat_multiturn.py

Demonstrates **multi-turn conversation** — passing the full message history to the API.

Unlike a single prompt, multi-turn sends the entire conversation context:
- `system` — sets the assistant's behavior
- `user` — user message
- `assistant` — previous assistant response (injected manually)
- `user` — follow-up question

This is how chatbots maintain context — the model has no memory between calls,
so the full history must be passed on every request.

Also shows additional parameters:
- `max_completion_tokens` — hard limit on response length
- `temperature`, `top_p` — control response randomness
- `frequency_penalty`, `presence_penalty` — reduce repetition

### Run

```bash
uv run chat_multiturn.py
```

**Example output:**
```
1. Iconic Symbol: It is one of the most recognizable landmarks in the world and a symbol of Paris and France. Its unique iron lattice structure sets it apart from other monuments.
2. Engineering Marvel: When it was completed...
```
