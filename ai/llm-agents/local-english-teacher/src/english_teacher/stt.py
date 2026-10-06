"""Speech-to-text with faster-whisper (imported lazily so tests stay lightweight)."""

from __future__ import annotations

import numpy as np
from loguru import logger

from english_teacher.audio import to_whisper_input
from english_teacher.config import STTConfig


class WhisperSTT:
    def __init__(self, cfg: STTConfig):
        from faster_whisper import WhisperModel

        self.cfg = cfg
        logger.info(f"Loading Whisper '{cfg.model_size}' ({cfg.device}, {cfg.compute_type})...")
        self.model = WhisperModel(cfg.model_size, device=cfg.device, compute_type=cfg.compute_type)

    def transcribe(self, sample_rate: int, audio: np.ndarray) -> str:
        x = to_whisper_input(sample_rate, audio)
        segments, _ = self.model.transcribe(
            x,
            language=self.cfg.language or None,
            task="transcribe",
            beam_size=self.cfg.beam_size,
            vad_filter=True,
            temperature=0.0,
            condition_on_previous_text=False,
        )
        return "".join(seg.text for seg in segments).strip()
