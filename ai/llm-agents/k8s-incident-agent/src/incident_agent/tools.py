"""Tools available to the LLM. All of them are read-only.

State-changing actions (rollback, disabling a flag) are deliberately NOT here.
They will arrive in step 5 as a separate graph node behind human approval,
not as a tool the model can call on its own.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool

from .backends import Backend


def to_text(data: Any, max_chars: int) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(text) > max_chars:
        text = text[:max_chars] + f"... [truncated {len(text) - max_chars} chars]"
    return text


def build_tools(backend: Backend, max_chars: int = 4000) -> list[BaseTool]:
    def safe(fn, *args) -> str:
        try:
            return to_text(fn(*args), max_chars)
        except Exception as e:  # a tool error is information for the agent too
            return f"ERROR {type(e).__name__}: {e}"[:500]

    @tool
    def get_service_overview(service: str) -> str:
        """Service golden signals (traffic, error ratio, p95) now and one hour ago, plus pod memory/CPU."""
        return safe(backend.service_overview, service)

    @tool
    def get_error_breakdown(service: str) -> str:
        """Which operations (spans) of the service produce errors, sorted descending."""
        return safe(backend.error_breakdown, service)

    @tool
    def get_pods(service: str) -> str:
        """Service pods: readiness, restarts, last termination reason (e.g. OOMKilled), waiting reason (e.g. ImagePullBackOff)."""
        return safe(backend.pods, service)

    @tool
    def get_k8s_events(service: str) -> str:
        """Recent Kubernetes events for the service deployment and pods."""
        return safe(backend.events, service)

    @tool
    def get_rollout_history(service: str) -> str:
        """Recent deployment revisions with a list of changes vs the previous one (image, env, limits)."""
        return safe(backend.rollout_history, service)

    @tool
    def get_deployment_spec(service: str) -> str:
        """Current deployment spec: replicas, conditions, images, environment variables, limits."""
        return safe(backend.deployment_spec, service)

    @tool
    def get_feature_flags() -> str:
        """Feature flags whose value differs from the default 'off', including flags enabled only for specific targets (scope 'targeted', e.g. one product id). An enabled flag is a common incident cause."""
        return safe(backend.feature_flags)

    @tool
    def search_logs(service: str, text: str = "", minutes: int = 15) -> str:
        """Search the service logs. `text` is a Lucene query (empty = common error keywords)."""
        return safe(backend.search_logs, service, text, minutes)

    @tool
    def prometheus_query(promql: str) -> str:
        """Any PromQL (instant) query. Span metrics: traces_span_metrics_calls_total, traces_span_metrics_duration_milliseconds_bucket with a service_name label."""
        return safe(backend.prom_query, promql)

    @tool
    def list_metrics(pattern: str) -> str:
        """Prometheus metric names matching a regular expression (max 60)."""
        return safe(backend.list_metrics, pattern)

    return [
        get_service_overview, get_error_breakdown, get_pods, get_k8s_events,
        get_rollout_history, get_deployment_spec, get_feature_flags, search_logs,
        prometheus_query, list_metrics,
    ]
