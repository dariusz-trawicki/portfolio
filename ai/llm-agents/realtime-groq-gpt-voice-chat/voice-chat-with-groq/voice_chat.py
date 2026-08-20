from __future__ import annotations

import os
import sys
import time
import argparse
import io
import wave
import re
import datetime
import inspect
import asyncio
from typing import Any, Dict, List, Tuple

import numpy as np
from numpy.typing import NDArray

from dotenv import load_dotenv
from loguru import logger
from groq import Groq

from fastrtc import ReplyOnPause, Stream, get_tts_model, KokoroTTSOptions

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings


# ============================================================
# ENV
# ============================================================
load_dotenv()

# Ensure espeak-ng data path for espeakng-loader
if not os.environ.get("ESPEAK_DATA_PATH"):
    os.environ["ESPEAK_DATA_PATH"] = "/opt/homebrew/share/espeak-ng-data"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise RuntimeError("Missing GROQ_API_KEY in env/.env")

ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or "JBFqnCBsd6RMkjVDRZzb"
ELEVEN_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "").strip() or "eleven_multilingual_v2"

groq_client = Groq(api_key=GROQ_API_KEY)
tts_kokoro = get_tts_model(model="kokoro")
tts_eleven = ElevenLabs(api_key=ELEVEN_API_KEY) if ELEVEN_API_KEY else None


# ============================================================
# LOGS
# ============================================================
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


# ============================================================
# MEMORY (RAM)
# ============================================================
CONVERSATIONS: Dict[str, List[dict]] = {}          # LLM context (may be summarized)
RAW_LOGS: Dict[str, List[dict]] = {}              # Full log (never summarized)
SESSION_LANG: Dict[str, str] = {}                 # "pl"|"en"
SESSION_SUMMARY_ENABLED: Dict[str, bool] = {}     # True/False
SESSION_ELEVEN_DISABLED: Dict[str, bool] = {}     # True/False (HARD LOCK until reset)


# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT_BASE = (
    "You are a helpful assistant in a real-time voice call. "
    "Your output will be converted to audio. Do not use emojis or special characters. "
    "Only Polish (pl) and English (en) are supported.\n"
    "Keep responses short and natural for speech.\n"
)


# ============================================================
# SETTINGS
# ============================================================
WHISPER_MODEL = "whisper-large-v3"

DEFAULT_VOICE = "bf_alice"
DEFAULT_SPEED = 1.0
DEFAULT_ACCENT = "en-us"

MAX_MESSAGES_BEFORE_SUMMARY = 18
KEEP_LAST_MESSAGES = 6
SUMMARY_MAX_TOKENS = 220

DEFAULT_SUMMARY_ENABLED = False
AUTO_SUMMARY_ENABLED = False  # True -> autosummary when enabled


# ============================================================
# SESSION KEY
# ============================================================
def get_session_key(*args: Any, **kwargs: Any) -> str:
    for k in ("session_id", "client_id", "user_id", "uuid"):
        if k in kwargs and kwargs[k]:
            return str(kwargs[k])
    return "default"


# ============================================================
# STRICT COMMANDS
# ============================================================
RESET_PHRASES = {
    "clear conversation",
    "reset conversation",
    "wyczyść rozmowę",
}

CMD_SUMMARY_ON = {"włącz streszczanie", "wlacz streszczanie", "enable summarization"}
CMD_SUMMARY_OFF = {"wyłącz streszczanie", "wylacz streszczanie", "disable summarization"}
CMD_SUMMARY_NOW = {"zrób streszczenie", "zrob streszczenie", "make summary"}
CMD_SAVE = {"zapisz rozmowę", "zapisz rozmowe", "save conversation"}


def _strip_trailing_punct(text: str) -> str:
    return re.sub(r"[^\w\sąćęłńóśżź]+$", "", (text or "").strip())


def _norm(text: str) -> str:
    return _strip_trailing_punct(text).strip().lower()


def is_exact_cmd(text: str, allowed: set[str]) -> bool:
    return _norm(text) in allowed


def is_reset_command(text: str) -> bool:
    return is_exact_cmd(text, RESET_PHRASES)


def looks_like_reset_attempt(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    if t in RESET_PHRASES:
        return False
    if t.startswith("wyczy") or t.startswith("wyczysc"):
        return True
    if ("reset" in t or "clear" in t) and "conversation" in t:
        return True
    return False


# ============================================================
# CYRILLIC (PL/EN only)
# ============================================================
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]")


def contains_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text or ""))


# ============================================================
# FORCED LANGUAGE INTENT
# ============================================================
PERSIST_PAT = r"\b(od\s+teraz|from\s+now\s+on|always|zawsze)\b"

FORCE_PL_PATTERNS = [
    r"\b(po\s*polsku)\b",
    r"\b(mów|mow|powiedz|odpowiadaj)\s+po\s*polsku\b",
    r"\b(say|reply|respond)\s+in\s+polish\b",
    r"\b(in\s+polish)\b",
    r"\b(speak)\s+polish\b",
]
FORCE_EN_PATTERNS = [
    r"\b(po\s*angielsku)\b",
    r"\b(mów|mow|powiedz|odpowiadaj)\s+po\s+angielsku\b",
    r"\b(say|reply|respond)\s+in\s+english\b",
    r"\b(in\s+english)\b",
    r"\b(speak)\s+english\b",
]


def detect_forced_lang(transcript: str) -> tuple[str | None, bool]:
    t = (transcript or "").strip().lower()
    if not t:
        return None, False

    persistent = re.search(PERSIST_PAT, t, re.IGNORECASE) is not None

    for pat in FORCE_PL_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return "pl", persistent
    for pat in FORCE_EN_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return "en", persistent
    return None, False


# ============================================================
# PL/EN GUESS + CONFIDENCE
# ============================================================
def guess_pl_en_with_confidence(text: str) -> tuple[str, float]:
    t = (text or "").strip()
    if not t:
        return "en", 0.2
    tl = t.lower()

    if any(ch in tl for ch in "ąćęłńóśżź"):
        return "pl", 0.95

    tokens = re.findall(r"[a-zA-Ząćęłńóśżź]+", tl)

    pl_words = {
        "mam", "jak", "sie", "się", "masz", "czesc", "cześć", "dziekuje", "dzięki", "prosze", "proszę",
        "dzien", "dzień", "dobry", "co", "robisz", "mozna", "moge", "mogę", "pomoc", "pomóc", "mi",
        "tobie", "czy", "jestem", "nazywam", "imie", "imię", "twoje", "twoj", "twój", "moja", "moj", "mój",
        "po", "polsku", "angielsku", "rozmowe", "rozmowę", "powiedz", "mow", "mów",
        "włącz", "wlacz", "wyłącz", "wylacz", "streszczanie", "streszczenie", "zrób", "zrob", "zapisz",
    }
    en_words = {
        "hello", "hi", "hey", "yeah", "yes", "no",
        "how", "are", "you", "your", "my", "name", "is", "what", "who", "why", "when", "where",
        "can", "could", "would", "should", "please", "thanks", "thank",
        "good", "morning", "day", "evening",
        "help", "assist", "talk", "speak", "english", "polish", "in", "say", "reply", "respond",
        "i", "me", "we", "they", "them", "this", "that", "it", "do", "does", "did",
        "tell", "switch", "to", "enable", "disable", "summarization", "summary", "save", "conversation",
    }

    pl_hits = sum(1 for tok in tokens if tok in pl_words)
    en_hits = sum(1 for tok in tokens if tok in en_words)

    if "?" in t and en_hits >= 2:
        en_hits += 1

    if pl_hits >= 2 and pl_hits > en_hits:
        return "pl", 0.80
    if pl_hits == 1 and pl_hits > en_hits:
        return "pl", 0.60

    if en_hits >= 3 and en_hits > pl_hits:
        return "en", 0.85
    if en_hits >= 2 and en_hits > pl_hits:
        return "en", 0.75
    if en_hits == 1 and en_hits > pl_hits:
        return "en", 0.60

    return "en", 0.55


def is_strict_english(text: str) -> bool:
    """
    Used ONLY for HARD_LOCK_GATE behavior:
    - allow English input to reach LLM
    - block everything else (incl. Polish)
    """
    g, conf = guess_pl_en_with_confidence(text)
    return g == "en" and conf >= 0.70


# ============================================================
# AUDIO -> WAV (Groq Whisper)
# ============================================================
def _ensure_int16_mono(audio_data: NDArray[np.int16 | np.float32]) -> NDArray[np.int16]:
    a = np.asarray(audio_data)
    if a.ndim == 2:
        a = a[0]
    if a.dtype != np.int16:
        a = np.clip(a, -1.0, 1.0)
        a = (a * 32767.0).astype(np.int16)
    return a


def audio_to_wav_bytes(audio: tuple[int, NDArray[np.int16 | np.float32]]) -> bytes:
    sr, data = audio
    pcm16 = _ensure_int16_mono(data)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def transcribe_with_whisper(audio: tuple[int, NDArray[np.int16 | np.float32]]) -> str:
    wav_bytes = audio_to_wav_bytes(audio)
    t0 = time.time()
    resp = groq_client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=WHISPER_MODEL,
        temperature=0.0,
        response_format="json",
    )
    dt = time.time() - t0
    text = (resp.text or "").strip()
    guess, conf = guess_pl_en_with_confidence(text)
    logger.debug(f"[whisper] {dt:.2f}s → {text!r} (guess={guess}, conf={conf:.2f})")
    return text


# ============================================================
# RESET / INIT SESSION
# ============================================================
def reset_conversation(session_key: str, lang: str = "en") -> None:
    CONVERSATIONS[session_key] = [
        {"role": "system", "content": SYSTEM_PROMPT_BASE},
        {
            "role": "system",
            "content": (
                "Conversation reset: you must not reference any prior facts (including the user's name) "
                "unless the user explicitly states them again AFTER the reset."
            ),
        },
    ]
    RAW_LOGS[session_key] = []
    SESSION_LANG[session_key] = lang
    SESSION_SUMMARY_ENABLED[session_key] = DEFAULT_SUMMARY_ENABLED
    SESSION_ELEVEN_DISABLED[session_key] = False  # reset removes HARD LOCK
    logger.info(f"[{session_key}] Conversation reset (lang={lang})")


# ============================================================
# SUMMARIZATION
# ============================================================
def force_make_summary(session_key: str) -> bool:
    msgs = CONVERSATIONS.get(session_key, [])
    if not msgs:
        return False

    system_msgs = [
        m for m in msgs
        if m.get("role") == "system"
        and not str(m.get("content", "")).startswith("Conversation summary:")
    ]
    dialog = [m for m in msgs if m.get("role") in ("user", "assistant")]

    if len(dialog) <= KEEP_LAST_MESSAGES:
        return False

    chunk = dialog[:-KEEP_LAST_MESSAGES]
    tail = dialog[-KEEP_LAST_MESSAGES:]

    logger.info(
        f"[{session_key}] Summarizing: total={len(msgs)}, summarize_chunk={len(chunk)}, keep_tail={len(tail)}"
    )

    summarizer_messages = [
        {"role": "system", "content": "Summarize concisely. Keep important facts, names, goals, constraints. No emojis."},
        {"role": "user", "content": f"Summarize these messages:\n{chunk}"},
    ]

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=SUMMARY_MAX_TOKENS,
        messages=summarizer_messages,
    )
    summary_text = (resp.choices[0].message.content or "").strip()

    CONVERSATIONS[session_key] = [
        *system_msgs,
        {"role": "system", "content": f"Conversation summary:\n{summary_text}"},
        *tail,
    ]
    return True


def summarize_history_if_needed(session_key: str) -> bool:
    if not AUTO_SUMMARY_ENABLED:
        return False
    if not SESSION_SUMMARY_ENABLED.get(session_key, DEFAULT_SUMMARY_ENABLED):
        return False
    if len(CONVERSATIONS.get(session_key, [])) <= MAX_MESSAGES_BEFORE_SUMMARY:
        return False
    return force_make_summary(session_key)


# ============================================================
# SAVE RAW CONVERSATION
# ============================================================
def save_full_conversation(session_key: str) -> str:
    os.makedirs("logs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_session = re.sub(r"[^a-zA-Z0-9_\-]+", "_", session_key)[:64] or "session"
    filename = f"logs/conversation_{safe_session}_{ts}.txt"

    lines: List[str] = []
    for m in RAW_LOGS.get(session_key, []):
        role = m.get("role", "unknown")
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"USER: {content}")
        elif role == "assistant":
            lines.append(f"ASSISTANT: {content}")
        else:
            lines.append(f"{str(role).upper()}: {content}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines).strip() + "\n")

    return filename


# ============================================================
# HARD LOCK: if Eleven unavailable -> English ONLY until reset
# ============================================================
def is_locked_en(session_key: str) -> bool:
    return bool(SESSION_ELEVEN_DISABLED.get(session_key, False))


HARD_LOCK_TTS_LINE = "I'm in English-only mode because the Polish voice is unavailable. How can I help you?"


# ============================================================
# TTS helpers
# ============================================================
def _safe_close_gen(gen: Any) -> None:
    """
    Fixes: RuntimeWarning: coroutine method 'aclose' ... was never awaited
    by safely closing sync/async generators.
    """
    if gen is None:
        return
    try:
        if hasattr(gen, "aclose"):
            r = gen.aclose()
            if inspect.isawaitable(r):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(r)
                else:
                    loop.create_task(r)
            return
    except Exception:
        pass
    try:
        if hasattr(gen, "close"):
            gen.close()
    except Exception:
        pass


def speak_kokoro_en(text: str, voice: Any, speed: Any, accent: Any):
    v = str(voice) if voice else DEFAULT_VOICE
    try:
        s = float(speed) if speed is not None else DEFAULT_SPEED
    except Exception:
        s = DEFAULT_SPEED
    s = min(2.0, max(0.5, s))
    a = accent if accent in ("en-us", "en-uk") else DEFAULT_ACCENT

    opts = KokoroTTSOptions(voice=v, speed=s, lang=a)

    gen = None
    try:
        gen = tts_kokoro.stream_tts_sync(text, options=opts)
        for chunk in gen:
            yield chunk
    finally:
        _safe_close_gen(gen)


def speak_eleven_pl(text: str):
    """
    Generator for Eleven PL. It may raise due to quota/network/etc.
    """
    if not tts_eleven:
        return

    resp_iter = tts_eleven.text_to_speech.convert(
        voice_id=ELEVEN_VOICE_ID,
        model_id=ELEVEN_MODEL_ID,
        text=text,
        output_format="pcm_24000",
        voice_settings=VoiceSettings(
            stability=0.35,
            similarity_boost=0.9,
            style=0.0,
            use_speaker_boost=True,
            speed=1.0,
        ),
    )
    for chunk in resp_iter:
        if not chunk:
            continue
        audio_array = np.frombuffer(chunk, dtype=np.int16).reshape(1, -1)
        yield (24000, audio_array)


def rewrite_text_to_language(text: str, target_lang: str) -> str:
    if target_lang not in ("pl", "en"):
        return text
    sysmsg = (
        "Rewrite the message in Polish only. Keep meaning. Natural for speech. No extra commentary."
        if target_lang == "pl"
        else "Rewrite the message in English only. Keep meaning. Natural for speech. No extra commentary."
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=220,
            messages=[
                {"role": "system", "content": sysmsg},
                {"role": "user", "content": text},
            ],
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or text
    except Exception as e:
        logger.error(f"[rewrite] failed: {e!r}")
        return text


def rewrite_to_language_if_needed(text: str, target_lang: str) -> str:
    g, conf = guess_pl_en_with_confidence(text)
    if conf >= 0.70 and g != target_lang:
        return rewrite_text_to_language(text, target_lang)
    return text


def _hard_lock_to_en(session_key: str) -> None:
    SESSION_ELEVEN_DISABLED[session_key] = True
    SESSION_LANG[session_key] = "en"


def speak_pl_en(text: str, lang: str, voice: Any, speed: Any, accent: Any, session_key: str):
    """
    Required behavior:
    - If Eleven fails once -> HARD LOCK English until reset.
    - In HARD LOCK: speak English via Kokoro, regardless of requested lang.
    - Never throws (no traceback).
    """
    # HARD LOCK path
    if is_locked_en(session_key):
        SESSION_LANG[session_key] = "en"
        logger.debug("[tts] Using Kokoro (EN/local)")
        text_en = rewrite_text_to_language(text, "en")
        yield from speak_kokoro_en(text_en, voice, speed, accent)
        return

    # Polish desired -> try Eleven once
    if lang == "pl":
        if not tts_eleven:
            _hard_lock_to_en(session_key)
            logger.warning(f"[tts] Eleven not configured -> switch session {session_key} to EN (HARD LOCK)")
            yield from speak_kokoro_en(HARD_LOCK_TTS_LINE, voice, speed, accent)
            return

        logger.debug("[tts] Using ElevenLabs (PL)")
        produced = False
        try:
            for item in speak_eleven_pl(text):
                produced = True
                yield item
        except Exception as e:
            # IMPORTANT: do not print stacktrace (no logger.exception)
            logger.error(f"[tts] ElevenLabs failed (caught in speak_pl_en): {e!r}")
            produced = False

        if produced:
            return

        # Failure -> HARD LOCK EN until reset
        _hard_lock_to_en(session_key)
        logger.warning(f"[tts] Eleven unavailable -> switch session {session_key} to EN (HARD LOCK)")
        yield from speak_kokoro_en(HARD_LOCK_TTS_LINE, voice, speed, accent)
        return

    # English
    logger.debug("[tts] Using Kokoro (EN/local)")
    yield from speak_kokoro_en(text, voice, speed, accent)


# ============================================================
# FRAGMENT FILTER
# ============================================================
def is_too_short_or_fragment(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True

    all_cmds = RESET_PHRASES | CMD_SUMMARY_ON | CMD_SUMMARY_OFF | CMD_SUMMARY_NOW | CMD_SAVE
    if is_exact_cmd(t, all_cmds):
        return False

    words = re.findall(r"\w+", t.lower())
    if len(words) <= 1:
        return True

    if len(words) == 2 and t.endswith((",", ".", "!", ";", ":")):
        return True

    if t.lower() in {"so", "so,", "ok", "okay", "yes", "no", "ahem", "mm", "mm-hmm"}:
        return True

    return False


# ============================================================
# MAIN HANDLER
# ============================================================
def echo(audio, *args, **kwargs: Any):
    session_key = get_session_key(*args, **kwargs)

    voice = kwargs.get("voice", DEFAULT_VOICE)
    speed = kwargs.get("speed", DEFAULT_SPEED)
    accent = kwargs.get("lang", DEFAULT_ACCENT)

    if session_key not in CONVERSATIONS:
        reset_conversation(session_key, lang="en")
    if session_key not in RAW_LOGS:
        RAW_LOGS[session_key] = []
    if session_key not in SESSION_SUMMARY_ENABLED:
        SESSION_SUMMARY_ENABLED[session_key] = DEFAULT_SUMMARY_ENABLED
    if session_key not in SESSION_ELEVEN_DISABLED:
        SESSION_ELEVEN_DISABLED[session_key] = False
    if session_key not in SESSION_LANG:
        SESSION_LANG[session_key] = "en"

    transcript = transcribe_with_whisper(audio)
    transcript = (transcript or "").strip()
    logger.debug(f"[{session_key}] Transcript: {transcript!r}")

    if not transcript:
        yield from speak_pl_en("I didn't catch that. Please repeat.", "en", voice, speed, accent, session_key)
        return

    # If HARD LOCK is active and user speaks NOT-English => block EVERYTHING except one fixed EN TTS line.
    if is_locked_en(session_key) and not is_strict_english(transcript):
        logger.debug(f"[{session_key}] HARD_LOCK_GATE: blocked non-English input (no LLM, no RAM, no logs)")
        yield from speak_pl_en(HARD_LOCK_TTS_LINE, "en", voice, speed, accent, session_key)
        return

    # PL/EN only: reject Cyrillic (but still obey HARD_LOCK_GATE above)
    if contains_cyrillic(transcript):
        say_lang = "en" if is_locked_en(session_key) else SESSION_LANG.get(session_key, "en")
        msg_pl = "Przepraszam — obsługuję tylko polski i angielski. Powtórz proszę po polsku albo po angielsku."
        msg_en = "Sorry — I only support Polish and English. Please repeat in Polish or English."
        yield from speak_pl_en(msg_pl if say_lang == "pl" else msg_en, say_lang, voice, speed, accent, session_key)
        return

    # Fragment filter
    if is_too_short_or_fragment(transcript):
        say_lang = "en" if is_locked_en(session_key) else SESSION_LANG.get(session_key, "en")
        msg_pl = "Powtórz proszę."
        msg_en = "Please repeat that."
        yield from speak_pl_en(msg_pl if say_lang == "pl" else msg_en, say_lang, voice, speed, accent, session_key)
        return

    # Exact reset
    if is_reset_command(transcript):
        cmd = _norm(transcript)
        reset_reply_lang = "pl" if cmd in ("wyczyść rozmowę", "wyczysc rozmowe") else "en"
        reset_conversation(session_key, lang=reset_reply_lang)

        msg_pl = "Rozmowa wyczyszczona. W czym mogę pomóc?"
        msg_en = "Conversation reset. How can I help you now?"
        yield from speak_pl_en(msg_pl if reset_reply_lang == "pl" else msg_en, reset_reply_lang, voice, speed, accent, session_key)
        return

    # Near reset attempt -> block LLM pretending reset
    if looks_like_reset_attempt(transcript):
        guess, _ = guess_pl_en_with_confidence(transcript)
        msg_pl = "Jeśli chcesz wyczyścić rozmowę, powiedz dokładnie: „wyczyść rozmowę” albo „wyczysc rozmowe”."
        msg_en = "If you want to reset the conversation, say exactly: “clear conversation” or “reset conversation”."
        yield from speak_pl_en(msg_pl if guess == "pl" else msg_en, guess, voice, speed, accent, session_key)
        return

    # Decide reply language
    if is_locked_en(session_key):
        SESSION_LANG[session_key] = "en"
        reply_lang = "en"
        logger.debug(f"[{session_key}] lang_policy=LOCKED_EN (eleven_disabled=True)")
    else:
        forced_lang, persistent = detect_forced_lang(transcript)
        if forced_lang in ("pl", "en"):
            reply_lang = forced_lang
            if persistent:
                SESSION_LANG[session_key] = forced_lang
            logger.debug(f"[{session_key}] lang_policy=forced({forced_lang}) persistent={persistent}")
        else:
            prev = SESSION_LANG.get(session_key)
            guess, conf = guess_pl_en_with_confidence(transcript)

            if prev is None:
                SESSION_LANG[session_key] = guess
            else:
                if conf >= 0.70:
                    SESSION_LANG[session_key] = guess

            reply_lang = SESSION_LANG.get(session_key, "en")
            logger.debug(f"[{session_key}] lang_policy=session({reply_lang}) prev={prev} guess={guess} conf={conf:.2f}")

    # STRICT COMMANDS
    if is_exact_cmd(transcript, CMD_SUMMARY_ON):
        SESSION_SUMMARY_ENABLED[session_key] = True
        msg_pl = "Włączyłem streszczanie."
        msg_en = "Summarization enabled."
        yield from speak_pl_en(msg_pl if reply_lang == "pl" else msg_en, reply_lang, voice, speed, accent, session_key)
        return

    if is_exact_cmd(transcript, CMD_SUMMARY_OFF):
        SESSION_SUMMARY_ENABLED[session_key] = False
        msg_pl = "Wyłączyłem streszczanie."
        msg_en = "Summarization disabled."
        yield from speak_pl_en(msg_pl if reply_lang == "pl" else msg_en, reply_lang, voice, speed, accent, session_key)
        return

    if is_exact_cmd(transcript, CMD_SUMMARY_NOW):
        did = force_make_summary(session_key)
        msg = ("Zrobiłem streszczenie." if did else "Nie ma jeszcze czego streszczać.") if reply_lang == "pl" else ("I created a summary." if did else "Nothing to summarize yet.")
        yield from speak_pl_en(msg, reply_lang, voice, speed, accent, session_key)
        return

    if is_exact_cmd(transcript, CMD_SAVE):
        fn = save_full_conversation(session_key)
        msg_pl = f"Zapisałem rozmowę do pliku: {fn}"
        msg_en = f"I saved the conversation to: {fn}"
        yield from speak_pl_en(msg_pl if reply_lang == "pl" else msg_en, reply_lang, voice, speed, accent, session_key)
        return

    # Normal dialog => now we DO log and send to LLM
    CONVERSATIONS[session_key].append({"role": "user", "content": transcript})
    RAW_LOGS[session_key].append({"role": "user", "content": transcript})

    summarize_history_if_needed(session_key)

    effective_lang = "en" if is_locked_en(session_key) else reply_lang
    lang_instruction = "Reply in Polish (pl) only." if effective_lang == "pl" else "Reply in English (en) only."

    # include summary system messages, exclude other system messages
    history: List[dict] = []
    for m in CONVERSATIONS[session_key]:
        if m.get("role") == "system":
            c = str(m.get("content", ""))
            if c.startswith("Conversation summary:"):
                history.append(m)
        else:
            history.append(m)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BASE + "\n" + lang_instruction},
        *history,
    ]

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=240,
        messages=messages,
    )
    response_text = (resp.choices[0].message.content or "").strip()

    # Guard response language
    response_text = rewrite_to_language_if_needed(response_text, effective_lang)

    logger.debug(f"[{session_key}] Response: {response_text!r}")

    CONVERSATIONS[session_key].append({"role": "assistant", "content": response_text})
    RAW_LOGS[session_key].append({"role": "assistant", "content": response_text})

    summarize_history_if_needed(session_key)

    # TTS (may set HARD LOCK if Eleven fails)
    yield from speak_pl_en(response_text, effective_lang, voice, speed, accent, session_key)


# ============================================================
# Stream/UI
# ============================================================
def create_stream():
    return Stream(
        ReplyOnPause(echo, input_sample_rate=16000),
        modality="audio",
        mode="send-receive",
        ui_args={
            "title": "PL/EN: Groq Whisper + Groq LLM + Kokoro EN + Eleven PL (HARD LOCK EN on remote TTS failure)",
            "inputs": [
                {"name": "voice", "type": "dropdown", "choices": [DEFAULT_VOICE], "label": "Kokoro voice (EN)", "value": DEFAULT_VOICE},
                {"name": "speed", "type": "slider", "min": 0.5, "max": 2.0, "step": 0.1, "label": "Kokoro speed (EN)", "value": DEFAULT_SPEED},
                {"name": "lang", "type": "dropdown", "choices": ["en-us", "en-uk"], "label": "Kokoro accent (EN)", "value": DEFAULT_ACCENT},
            ],
        },
    )


# ============================================================
# Entry
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if not ELEVEN_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set → Polish replies will HARD-LOCK to English (Kokoro) immediately.")
    else:
        logger.info(f"ElevenLabs enabled (voice_id={ELEVEN_VOICE_ID}, model_id={ELEVEN_MODEL_ID})")

    if args.reset:
        CONVERSATIONS.clear()
        RAW_LOGS.clear()
        SESSION_LANG.clear()
        SESSION_SUMMARY_ENABLED.clear()
        SESSION_ELEVEN_DISABLED.clear()

    stream = create_stream()
    stream.fastphone() if args.phone else stream.ui.launch()
