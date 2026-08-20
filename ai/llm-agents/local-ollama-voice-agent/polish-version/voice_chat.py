import sys
import argparse
import os
import tempfile
import subprocess
import threading
import time

from fastrtc import ReplyOnPause, Stream
from loguru import logger
from ollama import chat
from faster_whisper import WhisperModel

import numpy as np
import librosa
from pydub import AudioSegment

# ---------- STT: Whisper (Polish) ----------

whisper = WhisperModel("small", device="cpu", compute_type="int8")

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# ---------- TTS: macOS `say` + Zosia ----------

TTS_VOICE = "Zosia"
tts_lock = threading.Lock()


def tts_to_array(text: str):
    """
    macOS `say` -> audio file (AIFF/WAV) -> (sample_rate, np.int16)
    We use the external `say` command to avoid pyttsx3
    and its unpredictable behavior on macOS.
    """
    logger.debug(f"🔊 SAY TTS text: {text!r}")

    # temporary file (AIFF/WAV)
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
        tmp_path = f.name

    cmd = ["say", "-v", TTS_VOICE, "-o", tmp_path, text]

    with tts_lock:
        try:
            # run `say` and wait for it to finish
            subprocess.run(cmd, check=True)
        except Exception:
            logger.exception("Error while generating TTS via `say`")
            sr = 16000
            silence = np.zeros(int(sr * 0.5), dtype=np.int16)
            return sr, silence

    # wait a bit until the file is fully written
    try:
        last_size = -1
        for _ in range(10):  # up to ~0.5 s
            if not os.path.exists(tmp_path):
                time.sleep(0.05)
                continue
            size = os.path.getsize(tmp_path)
            if size > 0 and size == last_size:
                break
            last_size = size
            time.sleep(0.05)
    except Exception:
        logger.exception("Error while waiting for TTS file to stabilize")

    try:
        # load audio through pydub/ffmpeg
        audio_seg = AudioSegment.from_file(tmp_path)
        sample_rate = audio_seg.frame_rate
        n_channels = audio_seg.channels

        samples = np.array(audio_seg.get_array_of_samples()).astype(np.int16)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

        if samples.size == 0:
            logger.error("`say`/pydub returned empty audio (0 samples). Using silence fallback.")
            sr = 16000
            silence = np.zeros(int(sr * 0.5), dtype=np.int16)
            return sr, silence

        logger.debug(
            f"SAY audio: sr={sample_rate}, shape={samples.shape}, dtype={samples.dtype}"
        )
        return sample_rate, samples

    except Exception:
        logger.exception("Error reading TTS audio file via pydub/ffmpeg")
        sr = 16000
        silence = np.zeros(int(sr * 0.5), dtype=np.int16)
        return sr, silence

    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def tts_stream(text: str):
    """
    Pseudo-streaming: generate full audio, then
    split it into chunks and yield them to FastRTC.
    """
    try:
        sr, audio = tts_to_array(text)
    except Exception:
        logger.exception("Error in tts_to_array")
        sr = 16000
        audio = np.zeros(int(sr * 0.5), dtype=np.int16)

    chunk_duration = 0.5  # seconds
    chunk_size = int(sr * chunk_duration)

    n = audio.shape[0]
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        chunk = audio[start:end]
        yield (sr, chunk)
        start = end


def echo(audio):
    sample_rate, audio_array = audio
    logger.debug(
        f"echo CALLED: sr={sample_rate}, shape={audio_array.shape}, dtype={audio_array.dtype}"
    )

    # --- 1. Convert to float32 [-1,1] ---
    if audio_array.dtype == "int16":
        audio_float32 = audio_array.astype("float32") / 32768.0
    else:
        audio_float32 = audio_array.astype("float32")

    audio_float32 = audio_float32.squeeze()

    # --- 2. Convert to mono (if stereo) ---
    if audio_float32.ndim > 1:
        audio_float32 = np.mean(audio_float32, axis=0)

    # --- 3. Resample to 16 kHz ---
    target_sr = 16000
    if sample_rate != target_sr:
        audio_float32 = librosa.resample(
            audio_float32, orig_sr=sample_rate, target_sr=target_sr
        )
        sample_rate = target_sr

    logger.debug(
        f"audio_float32 after resample shape={audio_float32.shape}, sr={sample_rate}"
    )

    # --- 4. STT: Whisper (Polish) ---
    segments, info = whisper.transcribe(
        audio_float32,
        language="pl",
        task="transcribe",
        beam_size=5,
        vad_filter=True,
        temperature=0.0,
    )
    transcript = "".join(seg.text for seg in segments).strip()
    logger.debug(f"Transcript: {transcript!r}")

    if not transcript:
        return

    # --- 5. LLM response (Ollama) ---
    response = chat(
        model="gemma3:4b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a kind voice assistant. "
                    "You reply in simple, natural Polish. "
                    "Use at most 1–4 short sentences, total up to 240 characters. "
                    "Avoid foreign names, abbreviations, and complex sentences."
                ),
            },
            {"role": "user", "content": transcript},
        ],
        options={"num_predict": 120},
    )

    response_text = response["message"]["content"].strip()
    logger.debug(f"🤖 Response: {response_text}")

    if not response_text:
        return

    # --- 5a. Take only the first sentence for TTS ---
    separators = ".!?"
    sent = response_text
    for sep in separators:
        if sep in sent:
            sent = sent.split(sep)[0] + sep
            break
    response_text = sent.strip()

    MAX_TTS_CHARS = 240
    if len(response_text) > MAX_TTS_CHARS:
        logger.debug(
            f"Trimming TTS response from {len(response_text)} to {MAX_TTS_CHARS} characters."
        )
        response_text = response_text[:MAX_TTS_CHARS]

    logger.debug(f"First sentence for TTS: {response_text}")

    # --- 6. TTS output streaming – macOS `say` (Zosia) ---
    for audio_chunk in tts_stream(response_text):
        yield audio_chunk


def create_stream():
    return Stream(ReplyOnPause(echo), modality="audio", mode="send-receive")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Voice Chat Advanced")
    parser.add_argument(
        "--phone",
        action="store_true",
        help="Launch with FastRTC phone interface (get a temporary phone number)",
    )
    args = parser.parse_args()

    stream = create_stream()

    if args.phone:
        logger.info("Launching with FastRTC phone interface...")
        stream.fastphone()
    else:
        logger.info("Launching with Gradio UI...")
        stream.ui.launch()
