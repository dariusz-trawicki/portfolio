# Ollama - local runtime for LLM

`Ollama` is a local runtime for large language models (LLMs) that lets you download, run, and interact with AI models directly on your computer.
It provides a simple command-line interface and a local HTTP server, allowing apps and scripts to use models like LLaMA, Qwen, Mistral, Phi, and others — all without sending data to the cloud.

#### Prerequisites

Make sure you have these installed:

1. **uv** - Fast Python package manager
   
```bash
# macOS:
brew install uv
```

2. **Ollama** - local AI model runtime 
   
```bash
# macOS
brew install ollama
```

#### Start the Ollama server

Open a terminal and run:

```bash
ollama serve
```

This launches the local LLM server on: http://localhost:11434. Leave this terminal open — it must stay running.

#### Pull a model

In a second terminal:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M

# Prints a list of all models that are installed locally in Ollama, 
# along with their names and sizes. Check which models you’ve already pulled:
ollama list
```

#### Run the model

```bash
ollama run qwen3:4b-instruct-2507-q4_K_M
```

This opens an interactive chat session in the terminal, for example:

```
>>> hello
Hello! How can I assist you today?
>>> /bye
```

#### Use Ollama from Python (example)

```bash
uv venv
uv run demo_ollama.py

# using LangChain’s ChatOllama
uv run langchain_llm.py
```