# Voice AI Agent

A real-time voice chat application powered by local AI models. This project allows you to have voice conversations with AI models running locally on your machine.

## Features

- Real-time speech-to-text conversion
- Local LLM inference using Ollama
- Text-to-speech response generation
- Web interface for interaction
- Phone number interface option

## Prerequisites

- MacOS
- [Ollama](https://ollama.ai/) - Run LLMs locally
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Installation

### 1. Install prerequisites with Homebrew

```bash
brew install ollama 
brew install uv
brew install ffmpeg
```

### 2. Set up Python environment and install dependencies

```bash
# In Terminal I:
uv sync
```

### 4. Download required models in Ollama

```bash
# 1. In Terminal II:
ollama serve  # keep this terminal open
```

### 5. Pull the model

```bash
# 2. In Terminal I:
ollama pull gemma3:4b    # pull the model
ollama list              # list the pulled models
```

## Run

### Voice Chat (with system prompt)

#### Web UI (default)
```bash
# In Terminal I:

python voice_chat.py
# Output:
# INFO:     Warming up STT model.
# INFO:     STT model warmed up.
# INFO:     Warming up VAD model.
# INFO:     VAD model warmed up.
# 2025-12-08 13:28:46.189 | INFO     | __main__:<module>:56 - Launching with Gradio UI...
# * Running on local URL:  http://127.0.0.1:7860
# To create a public link, set `share=True` in `launch()`.
```

Open http://127.0.0.1:7860, then click `Record` and start speaking.


#### Phone Number Interface
Get a temporary phone number that anyone can call to interact with your AI:
```bash
# In Terminal I:
# STOP voice_chat.py (ctr+c)
python voice_chat.py --phone
# Example Output:
# INFO:     Warming up STT model.
# INFO:     STT model warmed up.
# INFO:     Warming up VAD model.
# INFO:     VAD model warmed up.
# 2025-12-08 13:08:47.373 | INFO     | __main__:<module>:52 - Launching with FastRTC phone interface...
# INFO:     Started server process [42509]
# INFO:     Waiting for application startup.
# INFO:     Visit https://fastrtc.org/userguide/api/ for WebRTC or Websocket API docs.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
# INFO:     Your FastPhone is now live! Call +1 877-713-4471 and use code 691168 to connect to your stream.
# INFO:     You have 30:00 minutes remaining in your quota (Resetting on 2026-01-03)
# INFO:     Visit https://fastrtc.org/userguide/audio/#telephone-integration for information on making your handler compatible with phone usage.
```

This will provide you with a temporary phone number that you can call to interact with the AI using your voice. Call (example) +1 877-713-4471 and use code 691168 + #.

## How it works

The application uses:
- `FastRTC` for WebRTC communication
- `Moonshine` for local speech-to-text conversion
- `Kokoro` for text-to-speech synthesis
- `Ollama` for running local LLM inference with `Gemma` models

When you speak, your audio is:
1. Transcribed to text using Moonshine
2. Sent to a local LLM via Ollama for processing
3. The LLM response is converted back to speech with Kokoro
4. The audio response is streamed back to you via FastRTC