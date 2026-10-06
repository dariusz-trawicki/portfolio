"""Configuration: defaults < config.yaml < environment variables < CLI flags.

Environment variables use the form TEACHER_<SECTION>__<FIELD>, e.g.
    TEACHER_LLM__MODEL=llama3.1:8b
    TEACHER_TEACHER__LEVEL=B2
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

ENV_PREFIX = "TEACHER_"
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass
class LLMConfig:
    model: str = "gemma3:4b"
    host: str = "http://localhost:11434"
    num_ctx: int = 4096
    num_predict: int = 150
    temperature: float = 0.6
    keep_alive: str = "30m"  # how long Ollama keeps the model in memory after a request
    warmup: bool = True  # load the model at startup so the first turn is not slow


@dataclass
class STTConfig:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    beam_size: int = 5
    language: str = "en"


@dataclass
class TTSConfig:
    backend: str = "auto"  # auto | say | piper
    say_voice: str = "Samantha"
    piper_model: str = "models/en_US-lessac-medium.onnx"
    chunk_seconds: float = 0.5


@dataclass
class TeacherConfig:
    level: str = "B1"
    topic: str = "everyday life"
    max_history_messages: int = 16
    max_mistakes_in_prompt: int = 8
    mistakes_file: str = "data/teacher_mistakes.json"


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 7860
    metrics_enabled: bool = True
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9100


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    teacher: TeacherConfig = field(default_factory=TeacherConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        self.teacher.level = self.teacher.level.upper()
        if self.teacher.level not in LEVELS:
            raise ValueError(f"teacher.level must be one of {LEVELS}, got {self.teacher.level!r}")
        if self.tts.backend not in ("auto", "say", "piper"):
            raise ValueError(f"tts.backend must be auto|say|piper, got {self.tts.backend!r}")
        if self.teacher.max_history_messages < 0:
            raise ValueError("teacher.max_history_messages must be >= 0")
        if self.llm.num_ctx < self.llm.num_predict:
            raise ValueError("llm.num_ctx must be >= llm.num_predict")


def _coerce(value: Any, target_type: Any) -> Any:
    """Convert strings (from env / CLI) to the type of the dataclass field."""
    if not isinstance(value, str):
        return value
    if target_type in (bool, "bool"):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if target_type in (int, "int"):
        return int(value)
    if target_type in (float, "float"):
        return float(value)
    return value


def _apply(section_obj: Any, values: dict[str, Any], source: str) -> None:
    known = {f.name: f for f in fields(section_obj)}
    for key, value in values.items():
        if key not in known:
            raise ValueError(f"Unknown config key {key!r} in {source}")
        setattr(section_obj, key, _coerce(value, known[key].type))


def apply_mapping(cfg: AppConfig, data: dict[str, Any], source: str = "mapping") -> AppConfig:
    for section, values in (data or {}).items():
        if not hasattr(cfg, section):
            raise ValueError(f"Unknown config section {section!r} in {source}")
        if not isinstance(values, dict):
            raise ValueError(f"Section {section!r} in {source} must be a mapping")
        _apply(getattr(cfg, section), values, source)
    return cfg


def env_overrides(environ: dict[str, str] | None = None) -> dict[str, dict[str, str]]:
    environ = os.environ if environ is None else environ
    out: dict[str, dict[str, str]] = {}
    for key, value in environ.items():
        if not key.startswith(ENV_PREFIX) or "__" not in key:
            continue
        section, _, name = key[len(ENV_PREFIX) :].lower().partition("__")
        out.setdefault(section, {})[name] = value
    return out


def load_config(
    path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    cli_overrides: dict[str, dict[str, Any]] | None = None,
) -> AppConfig:
    cfg = AppConfig()

    environ = os.environ if environ is None else environ
    # Ollama's own variable is respected as a convenience.
    if environ.get("OLLAMA_HOST"):
        host = environ["OLLAMA_HOST"]
        cfg.llm.host = host if host.startswith("http") else f"http://{host}"

    if path:
        p = Path(path)
        if p.exists():
            with p.open(encoding="utf-8") as f:
                apply_mapping(cfg, yaml.safe_load(f) or {}, source=str(p))
        else:
            raise FileNotFoundError(f"Config file not found: {p}")

    apply_mapping(cfg, env_overrides(environ), source="environment")

    if cli_overrides:
        cleaned = {
            s: {k: v for k, v in vals.items() if v is not None} for s, vals in cli_overrides.items()
        }
        apply_mapping(cfg, cleaned, source="CLI")

    cfg.validate()
    return cfg
