"""Durable agent state. LangGraph saves a checkpoint after every node, so an investigation can be
resumed after a failure and a paused one (awaiting approval) survives an agent restart.

CHECKPOINT_DB picks the store:
  .data/checkpoints.sqlite                      a file (default; `make serve` on your laptop)
  postgresql://agent:<pw>@postgres:5432/agent   PostgresSaver (the agent running in the cluster)

SQLite is fine for one process on one machine. In the cluster the pod can be rescheduled to another
node at any time, so the state must live outside the pod: Postgres (with a PersistentVolume).
"""

from __future__ import annotations

import atexit
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# Explicit allow-list of our types that may be restored from a checkpoint
# (safer than deserializing arbitrary classes).
ALLOWED_TYPES = [("incident_agent.state", "Alert"), ("incident_agent.state", "Diagnosis")]

_pools: dict[str, Any] = {}
_ready: set[str] = set()          # URLs whose checkpoint tables are already migrated
_lock = threading.Lock()


def is_postgres(url: str) -> bool:
    return url.startswith(("postgresql://", "postgres://"))


def redact(url: str) -> str:
    """postgresql://agent:secret@host/db -> postgresql://agent:***@host/db (for logs and `doctor`)."""
    return re.sub(r"(://[^:/@]+):[^@]*@", r"\1:***@", url)


def postgres_pool(url: str):
    """One small connection pool per URL, shared by the checkpointer and the incident store.

    autocommit + prepare_threshold=0 + dict_row are what PostgresSaver expects.
    """
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as e:  # pragma: no cover - depends on the installed extras
        raise RuntimeError('Postgres support is not installed: pip install -e ".[postgres]"') from e
    with _lock:
        if not _pools:
            atexit.register(close_pools)   # close cleanly on exit (otherwise psycopg waits for its threads)
        if url not in _pools:
            _pools[url] = ConnectionPool(url, min_size=1, max_size=4, open=True, timeout=30,
                                         kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        return _pools[url]


def close_pools() -> None:
    with _lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()
        _ready.clear()


def _serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_TYPES)


@contextmanager
def open_checkpointer(url: str) -> Iterator[Any]:
    """A LangGraph checkpointer for a SQLite path or a Postgres URL."""
    if is_postgres(url):
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver(postgres_pool(url), serde=_serde())
        if url not in _ready:      # creates/migrates the tables; idempotent, but once per process is enough
            saver.setup()
            _ready.add(url)
        yield saver
        return

    from langgraph.checkpoint.sqlite import SqliteSaver

    Path(url).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(url, check_same_thread=False)
    try:
        yield SqliteSaver(conn, serde=_serde())
    finally:
        conn.close()
