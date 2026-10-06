"""The conversation turn: audio in -> transcript -> LLM -> speech out.

All dependencies are injected, so the pipeline can be tested with fakes
(no Whisper, Ollama or audio device needed).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Protocol

import numpy as np
from loguru import logger

from english_teacher.audio import chunk_audio, silence
from english_teacher.config import TeacherConfig
from english_teacher.llm import LLMResult
from english_teacher.memory import ConversationHistory, MistakeStore
from english_teacher.metrics import Metrics
from english_teacher.prompts import build_system_prompt
from english_teacher.text import clean_for_tts, extract_correction
from english_teacher.tts import TTS

CONTEXT_WARN_RATIO = 0.9

FALLBACK_REPLY = "Sorry, I had a problem. Could you say that again?"


class STT(Protocol):
    def transcribe(self, sample_rate: int, audio: np.ndarray) -> str: ...


class LLM(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> LLMResult: ...


class TeacherPipeline:
    def __init__(
        self,
        cfg: TeacherConfig,
        stt: STT,
        llm: LLM,
        tts: TTS,
        history: ConversationHistory,
        mistakes: MistakeStore,
        metrics: Metrics,
        chunk_seconds: float = 0.5,
        context_window: int = 0,
    ):
        self.cfg = cfg
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.history = history
        self.mistakes = mistakes
        self.metrics = metrics
        self.chunk_seconds = chunk_seconds
        self.context_window = context_window  # llm.num_ctx; 0 disables the warning

    def build_messages(self, transcript: str) -> list[dict[str, str]]:
        system = build_system_prompt(
            self.cfg.level,
            self.cfg.topic,
            self.mistakes.recent(self.cfg.max_mistakes_in_prompt),
        )
        return [
            {"role": "system", "content": system},
            *self.history.snapshot(),
            {"role": "user", "content": transcript},
        ]

    def _warn_if_context_nearly_full(self, prompt_tokens: int) -> None:
        if self.context_window <= 0:
            return
        if prompt_tokens >= CONTEXT_WARN_RATIO * self.context_window:
            logger.warning(
                f"Prompt used {prompt_tokens}/{self.context_window} tokens of the context window. "
                "Ollama may silently truncate it: lower teacher.max_history_messages "
                "or raise llm.num_ctx."
            )

    def __call__(self, audio: tuple[int, np.ndarray]) -> Iterator[tuple[int, np.ndarray]]:
        return self.handle(audio)

    def handle(self, audio: tuple[int, np.ndarray]) -> Iterator[tuple[int, np.ndarray]]:
        turn_start = time.perf_counter()
        sample_rate, audio_array = audio
        self.metrics.audio_seconds.labels(direction="in").inc(
            audio_array.shape[-1] / float(sample_rate)
        )

        # 1. Speech -> text
        try:
            with self.metrics.time_stage("stt"):
                transcript = self.stt.transcribe(sample_rate, audio_array)
        except Exception:
            logger.exception("STT error")
            return
        logger.info(f"STUDENT: {transcript!r}")

        if not transcript:
            self.metrics.empty_transcripts.inc()
            return

        # 2. LLM
        try:
            with self.metrics.time_stage("llm"):
                result = self.llm.chat(self.build_messages(transcript))
            self.metrics.llm_tokens.labels(type="prompt").inc(result.prompt_tokens)
            self.metrics.llm_tokens.labels(type="completion").inc(result.completion_tokens)
            if result.tokens_per_second > 0:
                self.metrics.llm_tokens_per_second.observe(result.tokens_per_second)
            self._warn_if_context_nearly_full(result.prompt_tokens)
            reply = clean_for_tts(result.text)
            remember = True
        except Exception:
            logger.exception("LLM error")
            reply, remember = FALLBACK_REPLY, False

        logger.info(f"TEACHER: {reply!r}")
        if not reply:
            return

        # 3. Memory is saved BEFORE yielding: a stopped stream must not lose the turn.
        if remember:
            self.history.add_exchange(transcript, reply)
            correction = extract_correction(reply)
            if correction:
                self.metrics.corrections.inc()
                try:
                    self.mistakes.add(*correction)
                except Exception:
                    logger.exception("Could not save mistake")

        # 4. Text -> speech
        try:
            with self.metrics.time_stage("tts"):
                sr, speech = self.tts.synthesize(reply)
            if speech.size == 0:
                raise ValueError("TTS returned empty audio")
        except Exception:
            logger.exception("TTS error")
            sr, speech = silence()

        self.metrics.audio_seconds.labels(direction="out").inc(speech.shape[0] / float(sr))
        self.metrics.turns.inc()

        first = True
        for chunk in chunk_audio(sr, speech, self.chunk_seconds):
            if first:
                self.metrics.response_latency.observe(time.perf_counter() - turn_start)
                first = False
            yield chunk
