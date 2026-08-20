# Real-Time Voice Assistant (OpenAI STT + OpenAI LLM + Kokoro EN + ElevenLabs PL)

A real-time voice assistant that listens through your microphone (WebRTC), transcribes speech with **OpenAI**, generates responses with the **OpenAI Chat Completions API**, and speaks back using hybrid TTS:

- **English (EN)** → **Kokoro** (local TTS)
- **Polish (PL)** → **ElevenLabs** (remote TTS)
- **Supported languages:** **English (en)** and **Polish (pl)** only

---

## Features

### 1) Real-time voice loop
- **STT (Speech-to-Text):** OpenAI Speech-to-Text (Whisper)
- **LLM:** OpenAI Chat Completions
- **TTS (Text-to-Speech):**
  - EN → Kokoro (local)
  - PL → ElevenLabs (remote)

### 2) PL/EN-only enforcement
- If the input appears to be in an **unsupported language** (e.g., Cyrillic), the assistant:
  - asks the user to repeat in **Polish or English**
  - **does not call the LLM**
  - **does not add anything to conversation memory/logs**

### 3) Hard-lock safety mode (English-only)
If **ElevenLabs** fails (quota/auth/network/etc.), the session enters **English-only hard lock**:

- The assistant will **speak English only** via Kokoro
- **Non-English user input is blocked**:
  - **not sent to the LLM**
  - **not written to RAM history**
  - **not written to raw logs**
- The assistant replies (via TTS) with:

> `I'm in English-only mode because the Polish voice is unavailable. How can I help you?`

Hard-lock remains active **until you reset the conversation**.

Why: this prevents repeated ElevenLabs failures and keeps the call stable.

### 4) Conversation memory + summarization
The app uses two separate stores:

- **CONVERSATIONS**: context sent to the LLM (may be summarized/trimmed)
- **RAW_LOGS**: full conversation log (never summarized, used for saving)

Optional summarization keeps the LLM context from growing indefinitely:
- When enabled, older dialog is summarized and replaced by a compact **Conversation summary** + recent tail.

### 5) Strict reset + near-reset protection
Reset only triggers on **exact phrases** (punctuation at the end is tolerated):

- `clear conversation`
- `reset conversation`
- `wyczyść rozmowę`

If the user says something *similar* (e.g. typo or different inflection), the assistant **does not call the LLM** and instead explains the exact phrase to say. This prevents the model from “pretending” a reset happened.

### 6) FastRTC – Real-Time Audio Streaming Engine
This project is built on top of `FastRTC`, which is the core component responsible for real-time audio streaming and low-latency interaction.

`FastRTC` enables the system to behave like a live voice call, rather than a classic request/response voice assistant.

FastRTC provides:
- continuous audio streaming,
- pause-based turn detection (`ReplyOnPause`),
- streaming TTS output (audio chunks),
- WebRTC-based low-latency transport,
- a browser-based interface (UI layer).

---

## Requirements

- Python 3.13
- `uv` package manager
- Microphone access
- Environment variables / `.env` file with API keys:
  - `OPENAI_API_KEY` (required)
  - `ELEVENLABS_API_KEY` (optional but required for Polish voice)
  - `ESPEAK_DATA_PATH` (path to espeak-ng-data)

---

## Installation

```bash
brew install espeak-ng
uv venv
source .venv/bin/activate
uv sync
```

---

## Configuration (.env)

Create a `.env` in the project root:

```ini
# Required (OpenAI STT + OpenAI LLM)
OPENAI_API_KEY=<your_openai_api_key>

# Optional but required for Polish TTS
ELEVENLABS_API_KEY=<your_elevenlabs_api_key>

# Optional overrides for ElevenLabs
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

### What to put into `<your_openai_api_key>` and `<your_elevenlabs_api_key>`
These are **your secret API key strings** (treat them like passwords). You paste the key value directly, for example:

```ini
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=sk_...
```
Notes:
- If `ELEVENLABS_API_KEY` is missing, Polish TTS is unavailable and the app will fall back to English behavior.
- If ElevenLabs is present but returns quota/auth errors, the session will hard-lock to English.

---

## Phone / Call Mode (Real-Time Voice Call)

This project supports a phone-like real-time conversation mode (FastRTC “FastPhone”), so you can talk to the agent like on a live call.

### What happens in phone mode?
- FastRTC starts a server and exposes a phone gateway.
- You call a provided number and enter a one-time code to connect to your stream.
- Audio is streamed both ways in real time (WebRTC/WebSocket under the hood, depending on the FastRTC integration).

Run:

```bash
python voice_chat.py --phone
```

You should see logs similar to:
- “Your FastPhone is now live! Call … and use code …”
- A WebSocket connection line like `WebSocket /telephone/handler`

If you don’t pass `--phone`, the app runs with a browser UI.

---

## What provides the “frontend”? Is it WebRTC?
Yes — the interactive UI and audio transport are handled by **FastRTC**:
- In **browser UI mode**, FastRTC serves a small web frontend and uses **WebRTC** to stream microphone audio to the server and stream TTS audio back.
- In **phone mode**, FastRTC provides a telephone bridge (“FastPhone”) that routes the call audio to the same handler.

Your code mostly provides the **handler** (`echo`) and the **audio generators**; FastRTC provides the realtime layer.

---

## Run

```bash
python voice_chat.py
```

Optional flags (if present in your script):
- `--phone` to enable phone mode
- `--reset` to clear in-memory sessions on startup

---

## Voice Commands

### Reset conversation (strict)
Say one of:

- **EN:** `clear conversation` or `reset conversation`
- **PL:** `wyczyść rozmowę`

Effect:
- Clears LLM history (RAM)
- Clears raw logs (if you reset them in code)
- Removes hard-lock (ElevenLabs failure lock) for that session

### Summarization controls (if enabled)
- Enable: `włącz streszczanie` / `enable summarization`
- Disable: `wyłącz streszczanie` / `disable summarization`
- Make summary now: `zrób streszczenie` / `make summary`

### Save full conversation (raw)
- `zapisz rozmowę` / `save conversation`

Saves `RAW_LOGS` to a file in `./logs/`.

---

## Language & Routing Rules (Final Behavior)

### Normal mode (ElevenLabs available)
- User asks for Polish → assistant responds in Polish → **ElevenLabs** speaks it
- User asks for English → assistant responds in English → **Kokoro** speaks it
- If no explicit language request:
  - the session language is chosen using simple PL/EN detection (STT output + heuristics)
  - the assistant replies in the session language

### Hard-lock mode (ElevenLabs unavailable)
- Output: always English TTS via Kokoro
- Input gate:
  - if user speaks English → allowed → goes to LLM
  - if user speaks Polish / other language → **blocked** (no LLM, no RAM, no logs)
- The assistant plays the fixed English-only mode message (via Kokoro)

---

## Troubleshooting

### Polish voice does not work (ElevenLabs)
Symptoms:
- Logs show `401 quota_exceeded`, `401 unauthorized`, `403`, or network errors.
- The session switches to hard-lock mode.

Fix:
1. Verify `ELEVENLABS_API_KEY` is correct.
2. Verify your ElevenLabs account has quota/credits.
3. Reset the conversation (voice: `clear conversation`) after the account issue is resolved.

---

## Security / Privacy Notes
- Transcription and chat completion happen via OpenAI APIs.
- Polish TTS happens via ElevenLabs APIs (when enabled).
- Conversation history is stored **in memory**; saving to disk is optional via the “save conversation” command (if enabled).
