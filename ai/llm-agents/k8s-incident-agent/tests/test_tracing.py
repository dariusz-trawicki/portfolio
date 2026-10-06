"""Tracing is optional and must never break an investigation."""

from __future__ import annotations

import sys
import types

import pytest

from incident_agent import tracing


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_run_config_carries_thread_limits_and_metadata():
    cfg = tracing.run_config("checkout-abc", run_name="incident:checkout", tags=["webhook", "HighErrorRate"],
                             metadata={"service": "checkout"})
    assert cfg["configurable"] == {"thread_id": "checkout-abc"}
    assert cfg["recursion_limit"] == tracing.RECURSION_LIMIT
    assert cfg["run_name"] == "incident:checkout" and cfg["tags"] == ["webhook", "HighErrorRate"]
    assert cfg["metadata"]["service"] == "checkout" and cfg["metadata"]["langfuse_session_id"] == "checkout-abc"
    assert "callbacks" not in cfg                                   # without Langfuse keys nothing is added


def test_langfuse_handler_added_only_when_keys_present(monkeypatch):
    fake = types.ModuleType("langfuse.langchain")
    fake.CallbackHandler = lambda: "HANDLER"
    monkeypatch.setitem(sys.modules, "langfuse", types.ModuleType("langfuse"))
    monkeypatch.setitem(sys.modules, "langfuse.langchain", fake)
    assert "callbacks" not in tracing.run_config("t", run_name="r")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert tracing.run_config("t", run_name="r")["callbacks"] == ["HANDLER"]


def test_missing_langfuse_package_does_not_break_the_run(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)             # the import will raise ImportError
    monkeypatch.setitem(sys.modules, "langfuse.langchain", None)
    monkeypatch.setitem(sys.modules, "langfuse.callback", None)
    cfg = tracing.run_config("t", run_name="r")
    assert "callbacks" not in cfg and cfg["configurable"]["thread_id"] == "t"
    tracing.flush()                                                # does not raise either


def test_flush_is_noop_without_keys():
    tracing.flush()
