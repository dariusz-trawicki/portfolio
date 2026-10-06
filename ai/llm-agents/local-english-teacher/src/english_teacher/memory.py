"""Conversation memory (in-process sliding window) and persistent mistake store."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger


class ConversationHistory:
    """Thread-safe sliding window of chat messages."""

    def __init__(self, max_messages: int = 16):
        self.max_messages = max_messages
        self._messages: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def snapshot(self) -> list[dict[str, str]]:
        with self._lock:
            if self.max_messages == 0:
                return []
            return list(self._messages[-self.max_messages :])

    def add_exchange(self, user: str, assistant: str) -> None:
        with self._lock:
            self._messages.append({"role": "user", "content": user})
            self._messages.append({"role": "assistant", "content": assistant})
            # Keep a little more than the window, never grow unbounded.
            del self._messages[: max(0, len(self._messages) - self.max_messages * 2)]

    def __len__(self) -> int:
        with self._lock:
            return len(self._messages)


class MistakeStore:
    """Mistakes persisted to a JSON file so the teacher can revisit them across sessions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Could not read mistakes file")
            return []
        if not text.strip():
            return []  # an empty file simply means "no mistakes yet"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Keep the broken file for inspection instead of silently overwriting it later.
            backup = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                os.replace(self.path, backup)
                logger.warning(
                    f"Mistakes file is not valid JSON; moved to {backup}, starting fresh"
                )
            except OSError:
                logger.warning("Mistakes file is not valid JSON, starting fresh")
            return []
        return data if isinstance(data, list) else []

    def recent(self, n: int) -> list[dict[str, str]]:
        return self.load()[-n:] if n > 0 else []

    def add(self, wrong: str, correct: str) -> None:
        with self._lock:
            mistakes = self.load()
            mistakes.append(
                {
                    "wrong": wrong,
                    "correct": correct,
                    "date": datetime.now().isoformat(timespec="seconds"),
                }
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(mistakes, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)  # atomic write
        logger.info(f"Saved mistake: {wrong!r} -> {correct!r}")

    def reset(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
