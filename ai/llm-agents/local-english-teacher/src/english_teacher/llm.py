"""LLM client for Ollama."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from english_teacher.config import LLMConfig


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    eval_seconds: float = 0.0

    @property
    def tokens_per_second(self) -> float:
        if self.eval_seconds <= 0:
            return 0.0
        return self.completion_tokens / self.eval_seconds


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from an ollama response (object in >=0.4, dict in older versions)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, default)
    return default if value is None else value


def parse_response(response: Any) -> LLMResult:
    message = _get(response, "message", {}) or {}
    content = _get(message, "content", "") or ""
    return LLMResult(
        text=content.strip(),
        prompt_tokens=int(_get(response, "prompt_eval_count", 0) or 0),
        completion_tokens=int(_get(response, "eval_count", 0) or 0),
        eval_seconds=float(_get(response, "eval_duration", 0) or 0) / 1e9,  # ns -> s
    )


class OllamaLLM:
    def __init__(self, cfg: LLMConfig):
        from ollama import Client

        self.cfg = cfg
        self.client = Client(host=cfg.host)

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        response = self.client.chat(
            model=self.cfg.model,
            messages=messages,
            keep_alive=self.cfg.keep_alive,
            options={
                "num_predict": self.cfg.num_predict,
                "num_ctx": self.cfg.num_ctx,
                "temperature": self.cfg.temperature,
            },
        )
        return parse_response(response)

    def warmup(self) -> bool:
        """Load the model into memory (empty prompt, no generation). Never raises."""
        try:
            self.client.generate(model=self.cfg.model, prompt="", keep_alive=self.cfg.keep_alive)
            return True
        except Exception:
            return False

    def check_model(self) -> bool:
        """True if the model is available locally in Ollama."""
        try:
            self.client.show(self.cfg.model)
            return True
        except Exception:
            return False
