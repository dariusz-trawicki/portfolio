"""Prometheus metrics for the voice pipeline."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

LATENCY_BUCKETS = (0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 7.5, 10, 15, 20, 30)


class Metrics:
    """All pipeline metrics live in their own registry (easy to test, no global state)."""

    def __init__(self, registry: CollectorRegistry | None = None):
        self.registry = registry or CollectorRegistry()
        r = self.registry

        self.stage_latency = Histogram(
            "teacher_stage_latency_seconds",
            "Latency of one pipeline stage",
            ["stage"],  # stt | llm | tts
            buckets=LATENCY_BUCKETS,
            registry=r,
        )
        self.response_latency = Histogram(
            "teacher_response_latency_seconds",
            "Time from end of student speech to first audio chunk sent back",
            buckets=LATENCY_BUCKETS,
            registry=r,
        )
        self.turns = Counter("teacher_turns_total", "Completed conversation turns", registry=r)
        self.empty_transcripts = Counter(
            "teacher_empty_transcripts_total", "Utterances with no recognised speech", registry=r
        )
        self.errors = Counter(
            "teacher_errors_total", "Errors by pipeline stage", ["stage"], registry=r
        )
        self.corrections = Counter(
            "teacher_corrections_total", "Grammar corrections given by the teacher", registry=r
        )
        self.llm_tokens = Counter(
            "teacher_llm_tokens_total", "LLM tokens processed", ["type"], registry=r
        )
        self.llm_tokens_per_second = Histogram(
            "teacher_llm_tokens_per_second",
            "LLM generation speed",
            buckets=(2, 5, 10, 15, 20, 30, 40, 60, 80, 120),
            registry=r,
        )
        self.audio_seconds = Counter(
            "teacher_audio_seconds_total", "Audio duration", ["direction"], registry=r
        )
        self.info = Gauge(
            "teacher_info",
            "Static info about the running configuration",
            ["llm_model", "stt_model", "tts_backend", "level"],
            registry=r,
        )

    @contextmanager
    def time_stage(self, stage: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        except Exception:
            self.errors.labels(stage=stage).inc()
            raise
        finally:
            self.stage_latency.labels(stage=stage).observe(time.perf_counter() - start)

    def serve(self, host: str, port: int) -> None:
        start_http_server(port, addr=host, registry=self.registry)
