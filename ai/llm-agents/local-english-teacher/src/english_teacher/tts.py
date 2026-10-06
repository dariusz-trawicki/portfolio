"""Text-to-speech backends.

- SayTTS:   macOS built-in `say` (no extra dependencies, macOS only)
- PiperTTS: Piper neural TTS (cross-platform, used in Docker)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Protocol

import numpy as np
from loguru import logger

from english_teacher.audio import float_to_int16
from english_teacher.config import TTSConfig


class TTS(Protocol):
    name: str

    def synthesize(self, text: str) -> tuple[int, np.ndarray]: ...


def read_wav_int16_mono(path: str | Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got sample width {width}")
    samples = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return sr, samples


class SayTTS:
    name = "say"

    def __init__(self, voice: str = "Samantha", sample_rate: int = 22050):
        if shutil.which("say") is None:
            raise RuntimeError("`say` is not available (macOS only). Use tts.backend=piper.")
        self.voice = voice
        self.sample_rate = sample_rate
        self._lock = threading.Lock()

    def synthesize(self, text: str) -> tuple[int, np.ndarray]:
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = [
            "say",
            "-v",
            self.voice,
            "--file-format=WAVE",
            f"--data-format=LEI16@{self.sample_rate}",
            "-o",
            tmp_path,
            text,
        ]
        try:
            with self._lock:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            return read_wav_int16_mono(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


class PiperTTS:
    name = "piper"

    def __init__(self, model_path: str | Path):
        from piper import PiperVoice

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper voice not found: {model_path}. Download it with `make voice` (see README)."
            )
        logger.info(f"Loading Piper voice {model_path.name}...")
        self.voice = PiperVoice.load(str(model_path))
        self._lock = threading.Lock()

    def synthesize(self, text: str) -> tuple[int, np.ndarray]:
        chunks: list[np.ndarray] = []
        sample_rate = 22050
        with self._lock:
            for chunk in self.voice.synthesize(text):
                sample_rate = chunk.sample_rate
                chunks.append(float_to_int16(chunk.audio_float_array))
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
        return sample_rate, audio


def resolve_backend(backend: str, system: str | None = None) -> str:
    if backend != "auto":
        return backend
    system = system or platform.system()
    return "say" if system == "Darwin" else "piper"


def create_tts(cfg: TTSConfig) -> TTS:
    backend = resolve_backend(cfg.backend)
    logger.info(f"TTS backend: {backend}")
    if backend == "say":
        return SayTTS(voice=cfg.say_voice)
    return PiperTTS(cfg.piper_model)
