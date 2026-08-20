# Real-Time Voice Assistant (Groq Whisper + Groq LLM + Kokoro EN + ElevenLabs PL)

A real-time voice assistant that listens through your microphone (WebRTC), transcribes speech with **Groq Whisper**, generates responses with the **Groq LLM**, and speaks back using hybrid TTS:

- **English (EN)** → **Kokoro** (local TTS)
- **Polish (PL)** → **ElevenLabs** (remote TTS)
- **Supported languages:** **English (en)** and **Polish (pl)** only

---

## Features

### 1) Real-time voice loop
- **STT (Speech-to-Text):** Groq Whisper (`whisper-large-v3`)
- **LLM:** Groq Chat Completions (e.g. `llama-3.1-8b-instant`)
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
- pause-based turn detection,
- streaming TTS output,
- WebRTC-based low-latency transport,
- a browser-based interface (UI leyer).

---

## Requirements

- Python 3.13
- `uv` package manager
- Microphone access
- Environment variables / `.env` file with API keys:
  - `GROQ_API_KEY` (required)
  - `ELEVENLABS_API_KEY` (optional but required for Polish voice)

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
GROQ_API_KEY=your_groq_key_here
ESPEAK_DATA_PATH=path_to_espeak-ng-data

# Optional but required for Polish TTS
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb          # optional override
ELEVENLABS_MODEL_ID=eleven_multilingual_v2         # optional override
```

Notes:
- If `ELEVENLABS_API_KEY` is missing, Polish TTS is unavailable and the app will fall back to English behavior.
- If ElevenLabs is present but returns quota/auth errors, the session will hard-lock to English.

---

## Phone / Call Mode (Real-Time Voice Call)

This project supports a phone-like real-time conversation mode, allowing you to interact with the AI agent as if you were on a live call.

#### What is Phone Mode?

Phone mode uses FastRTC to stream audio continuously, enabling:
- near-real-time speech recognition (STT),
- streaming text-to-speech (TTS),
- natural turn-taking based on pauses in speech.

Instead of a push-to-talk or request/response flow, the system behaves like a live voice call.

---
## Run

Run the final script (example filename — adjust to your actual final file name):

```bash
python voice_chat.py
```

Some builds expose optional flags (depending on your script):
- `--phone` to enable phone mode
- `--reset` to clear in-memory sessions on startup

Example:

```bash
python voice_chat.py --phone
# Output:
# 2025-12-15 15:55:57.161 | INFO     | __main__:<module>:798 - ElevenLabs enabled (voice_id=JBFqnCBsd6RMkjVDRZzb, model_id=eleven_multilingual_v2)
# INFO:     Warming up VAD model.
# INFO:     VAD model warmed up.
# INFO:     Started server process [15624]
# INFO:     Waiting for application startup.
# INFO:     Visit https://fastrtc.org/userguide/api/ for WebRTC or Websocket API docs.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
# INFO:     Your FastPhone is now live! Call +1 877-713-4471 and use code 663345 to connect to your stream.
# INFO:     You have 30:00 minutes remaining in your quota (Resetting on 2026-01-03)
# INFO:     Visit https://fastrtc.org/userguide/audio/#telephone-integration for information on making your handler compatible with phone usage.
# INFO:     172.31.63.89:0 - "WebSocket /telephone/handler" [accepted]
# INFO:     connection open
```

This will start the voice assistant in phone mode. You can call the provided number and use the code to interact with the AI using your voice:
- call: `+1 877-713-4471`  (in Poland: `+001 877-713-4471`)
- use code (example): `663345#`

---

## Voice Commands

### Reset conversation (strict)
Say one of:

- **EN:** `clear conversation` or `reset conversation`
- **PL:** `wyczyść rozmowę`

Effect:
- Clears LLM history
- Clears raw logs (depending on implementation)
- Removes hard-lock (ElevenLabs failure lock) for that session

### Summarization controls
If implemented in your final version:

- Enable: `włącz streszczanie` / `enable summarization`
- Disable: `wyłącz streszczanie` / `disable summarization`
- Make summary now: `zrób streszczenie` / `make summary`

### Save full conversation (raw)
If implemented:

- `zapisz rozmowę` / `save conversation`

This saves `RAW_LOGS` to a file in `./logs/`.

---

## Language & Routing Rules (Final Behavior)

### Normal mode (ElevenLabs available)
- User asks for Polish → assistant responds in Polish → **ElevenLabs** speaks it
- User asks for English → assistant responds in English → **Kokoro** speaks it
- If no explicit language request:
  - the session language is chosen using simple PL/EN detection (Whisper + heuristics)
  - the assistant replies in the session language

### Hard-lock mode (ElevenLabs unavailable)
- Output: always English TTS via Kokoro
- Input gate:
  - if user speaks English → allowed → goes to LLM
  - if user speaks Polish / other language → **blocked** (no LLM, no RAM, no logs)
- The assistant plays the fixed English-only mode message (via Kokoro)

---

## Logging

The app typically logs:
- Whisper transcription + heuristic language guess
- language policy decisions (forced/session/hard-lock)
- TTS selection (ElevenLabs vs Kokoro)
- summarization events (if enabled)

If you see repeated ElevenLabs failures (401/403/quota/network), hard-lock is expected behavior.

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

### The assistant ignores Polish after a failure
That is by design in **hard-lock** mode. Reset the conversation to attempt Polish again.

### Unsupported language detected
If you speak a language outside PL/EN (or the transcript contains Cyrillic), the assistant will ask you to repeat in PL/EN and won’t call the LLM.

---

## Security / Privacy Notes
- Transcription and chat completion happen via Groq APIs.
- Polish TTS happens via ElevenLabs APIs (when enabled).
- Conversation history is stored **in memory**; saving to disk is optional via the “save conversation” command (if enabled).
