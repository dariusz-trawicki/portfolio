"""Graph run configuration: thread_id, limits, run name and tracing metadata.

Tracing is optional and never breaks an investigation:
- LangSmith is enabled purely through environment variables (LANGSMITH_TRACING=true, LANGSMITH_API_KEY);
  LangChain then sends traces without any code on our side.
- Langfuse needs a callback; we add it when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set
  and the package is installed (`pip install -e ".[tracing]"`).
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("incident_agent.tracing")

RECURSION_LIMIT = 60


def langfuse_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _langfuse_handler():
    """A Langfuse handler, or None (no keys, no package, or an initialisation error)."""
    if not langfuse_enabled():
        return None
    try:
        try:
            from langfuse.langchain import CallbackHandler  # langfuse >= 3
        except ImportError:
            from langfuse.callback import CallbackHandler  # langfuse 2.x
        return CallbackHandler()
    except Exception as e:  # tracing must never stop a diagnosis
        log.warning("Langfuse tracing disabled: %s: %s", type(e).__name__, e)
        return None


def run_config(thread_id: str, *, run_name: str, tags: list[str] | None = None,
               metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """The config passed to graph.invoke/stream.

    `thread_id` is the checkpoint key; `run_name`, tags and metadata show up in the tracing tool,
    so a trace can be found by incident, service or entry point (cli/eval/webhook).
    """
    tags = list(tags or [])
    meta = {**(metadata or {}), "thread_id": thread_id,
            # keys recognised by the Langfuse handler: group traces into a session and tag them
            "langfuse_session_id": thread_id, "langfuse_tags": tags}
    cfg: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
        "run_name": run_name,
        "tags": tags,
        "metadata": meta,
    }
    if handler := _langfuse_handler():
        cfg["callbacks"] = [handler]
    return cfg


def flush() -> None:
    """Flushes buffered Langfuse traces. Short-lived processes (CLI) would exit before the background upload."""
    if not langfuse_enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:
        log.debug("Langfuse flush skipped: %s", e)
