"""Entry point: config -> components -> FastRTC stream (+ metrics server)."""

from __future__ import annotations

import argparse
import sys
import time

from loguru import logger

from english_teacher.config import AppConfig, load_config
from english_teacher.memory import ConversationHistory, MistakeStore
from english_teacher.metrics import Metrics
from english_teacher.pipeline import TeacherPipeline
from english_teacher.tts import resolve_backend


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Local voice English teacher")
    p.add_argument("--config", default=None, help="Path to config YAML (e.g. config.yaml)")
    p.add_argument("--level", help="CEFR level: A1, A2, B1, B2, C1, C2")
    p.add_argument("--topic", help='e.g. "job interview", "travel"')
    p.add_argument("--model", help="Ollama model, e.g. llama3.1:8b")
    p.add_argument("--whisper", help="Whisper size: small / medium / large-v3")
    p.add_argument("--tts", choices=["auto", "say", "piper"], help="TTS backend")
    p.add_argument("--host", help="UI host (0.0.0.0 inside Docker)")
    p.add_argument("--port", type=int, help="UI port")
    p.add_argument("--no-metrics", action="store_true", help="Disable Prometheus endpoint")
    p.add_argument("--reset-mistakes", action="store_true", help="Clear saved mistakes")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def cli_overrides(args: argparse.Namespace) -> dict[str, dict]:
    return {
        "teacher": {"level": args.level, "topic": args.topic},
        "llm": {"model": args.model},
        "stt": {"model_size": args.whisper},
        "tts": {"backend": args.tts},
        "server": {
            "host": args.host,
            "port": args.port,
            "metrics_enabled": False if args.no_metrics else None,
        },
    }


def build_pipeline(cfg: AppConfig, metrics: Metrics) -> TeacherPipeline:
    # Heavy imports happen here, not at module import time.
    from english_teacher.llm import OllamaLLM
    from english_teacher.stt import WhisperSTT
    from english_teacher.tts import create_tts

    llm = OllamaLLM(cfg.llm)
    if not llm.check_model():
        logger.warning(
            f"Model {cfg.llm.model!r} not found at {cfg.llm.host}. Run: ollama pull {cfg.llm.model}"
        )
    elif cfg.llm.warmup:
        logger.info(f"Warming up {cfg.llm.model!r} (loading it into memory)...")
        start = time.perf_counter()
        if llm.warmup():
            logger.info(f"Model ready in {time.perf_counter() - start:.1f}s")
        else:
            logger.warning("Warm-up failed; the first answer may be slow")

    return TeacherPipeline(
        cfg=cfg.teacher,
        stt=WhisperSTT(cfg.stt),
        llm=llm,
        tts=create_tts(cfg.tts),
        history=ConversationHistory(cfg.teacher.max_history_messages),
        mistakes=MistakeStore(cfg.teacher.mistakes_file),
        metrics=metrics,
        chunk_seconds=cfg.tts.chunk_seconds,
        context_window=cfg.llm.num_ctx,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level=args.log_level.upper())

    cfg = load_config(args.config, cli_overrides=cli_overrides(args))
    logger.info(
        f"Config: model={cfg.llm.model} whisper={cfg.stt.model_size} "
        f"tts={resolve_backend(cfg.tts.backend)} level={cfg.teacher.level} "
        f"topic={cfg.teacher.topic!r}"
    )

    if args.reset_mistakes:
        MistakeStore(cfg.teacher.mistakes_file).reset()
        logger.info("Mistakes file cleared.")

    metrics = Metrics()
    metrics.info.labels(
        llm_model=cfg.llm.model,
        stt_model=cfg.stt.model_size,
        tts_backend=resolve_backend(cfg.tts.backend),
        level=cfg.teacher.level,
    ).set(1)
    if cfg.server.metrics_enabled:
        metrics.serve(cfg.server.metrics_host, cfg.server.metrics_port)
        logger.info(
            f"Metrics on http://{cfg.server.metrics_host}:{cfg.server.metrics_port}/metrics"
        )

    pipeline = build_pipeline(cfg, metrics)

    from fastrtc import ReplyOnPause, Stream

    stream = Stream(ReplyOnPause(pipeline.handle), modality="audio", mode="send-receive")
    stream.ui.launch(server_name=cfg.server.host, server_port=cfg.server.port)


if __name__ == "__main__":
    main()
