"""Where the incident list lives between restarts.

Checkpoints (checkpointing.py) hold the *graph* state of each investigation. The registry
(incidents.py) holds the *incident* list: status, alerts, decision, result. Both must survive a
restart, otherwise an incident paused at `awaiting_approval` would have a resumable checkpoint
that nobody can see or approve.

One row per incident, the whole incident as JSON. The same database as the checkpoints:
a SQLite file locally, Postgres in the cluster.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

from .checkpointing import is_postgres, postgres_pool


class IncidentStore(Protocol):
    def load(self, limit: int = 500) -> list[dict[str, Any]]: ...
    def save(self, record: dict[str, Any]) -> None: ...


class MemoryStore:
    """No persistence (tests, `serve --dry-run`)."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def load(self, limit: int = 500) -> list[dict[str, Any]]:
        rows = sorted(self.records.values(), key=lambda r: r["opened_at"])
        return [json.loads(json.dumps(r)) for r in rows[-limit:]]

    def save(self, record: dict[str, Any]) -> None:
        self.records[record["id"]] = json.loads(json.dumps(record))


class SqliteStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS incidents "
                               "(id TEXT PRIMARY KEY, opened_at TEXT NOT NULL, data TEXT NOT NULL)")

    def load(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM (SELECT data, opened_at FROM incidents "
                                      "ORDER BY opened_at DESC LIMIT ?) ORDER BY opened_at", (limit,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def save(self, record: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO incidents (id, opened_at, data) VALUES (?, ?, ?) "
                               "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                               (record["id"], record["opened_at"], json.dumps(record)))


class PostgresStore:
    def __init__(self, url: str):
        self._pool = postgres_pool(url)
        with self._pool.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, opened_at TIMESTAMPTZ NOT NULL, "
                         "data JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())")

    def load(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            rows = conn.execute("SELECT data FROM (SELECT data, opened_at FROM incidents "
                                "ORDER BY opened_at DESC LIMIT %s) t ORDER BY opened_at", (limit,)).fetchall()
        return [r["data"] for r in rows]

    def save(self, record: dict[str, Any]) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO incidents (id, opened_at, data) VALUES (%s, %s, %s::jsonb) "
                         "ON CONFLICT (id) DO UPDATE SET data = excluded.data, updated_at = now()",
                         (record["id"], record["opened_at"], json.dumps(record)))


def open_store(url: str) -> IncidentStore:
    """The same CHECKPOINT_DB value as the checkpointer: a SQLite path or a Postgres URL."""
    return PostgresStore(url) if is_postgres(url) else SqliteStore(url)
