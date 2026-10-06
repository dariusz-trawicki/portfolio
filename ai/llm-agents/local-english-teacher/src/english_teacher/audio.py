"""Audio helpers shared by STT and TTS."""

from __future__ import annotations

from collections.abc import Iterator
from math import gcd

import numpy as np
from scipy.signal import resample_poly

WHISPER_SR = 16000


def to_whisper_input(
    sample_rate: int, audio: np.ndarray, target_sr: int = WHISPER_SR
) -> np.ndarray:
    """int16/float audio of any shape -> mono float32 in [-1, 1] at target_sr."""
    if audio.dtype == np.int16:
        x = audio.astype(np.float32) / 32768.0
    else:
        x = audio.astype(np.float32)

    x = np.squeeze(x)
    if x.ndim > 1:
        # FastRTC delivers (channels, samples)
        x = x.mean(axis=0)

    if sample_rate != target_sr and x.size:
        g = gcd(int(sample_rate), int(target_sr))
        x = resample_poly(x, target_sr // g, sample_rate // g).astype(np.float32)

    return x


def float_to_int16(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16)


def chunk_audio(
    sample_rate: int, audio: np.ndarray, chunk_seconds: float = 0.5
) -> Iterator[tuple[int, np.ndarray]]:
    """Split audio into fixed-size chunks for pseudo-streaming playback."""
    size = max(1, int(sample_rate * chunk_seconds))
    for start in range(0, audio.shape[0], size):
        yield sample_rate, audio[start : start + size]


def silence(sample_rate: int = 16000, seconds: float = 0.5) -> tuple[int, np.ndarray]:
    return sample_rate, np.zeros(int(sample_rate * seconds), dtype=np.int16)
