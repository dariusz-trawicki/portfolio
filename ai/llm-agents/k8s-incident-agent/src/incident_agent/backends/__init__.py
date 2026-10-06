"""Data sources for the agent. Every operation is READ-ONLY.

`Backend` is the common interface. `LiveBackend` talks to the cluster,
Prometheus, OpenSearch and flagd. `FakeBackend` replays recorded responses
from a JSON file, so the agent can be tested and demoed without a cluster.
"""

from __future__ import annotations

from typing import Any, Protocol


class Backend(Protocol):
    # metrics
    def service_overview(self, service: str) -> dict[str, Any]: ...
    def error_breakdown(self, service: str) -> list[dict[str, Any]]: ...
    def prom_query(self, promql: str) -> list[dict[str, Any]]: ...
    def list_metrics(self, pattern: str) -> list[str]: ...
    def firing_alerts(self) -> list[dict[str, Any]]: ...
    # kubernetes
    def pods(self, service: str) -> list[dict[str, Any]]: ...
    def events(self, service: str) -> list[dict[str, Any]]: ...
    def rollout_history(self, service: str) -> list[dict[str, Any]]: ...
    def deployment_spec(self, service: str) -> dict[str, Any]: ...
    # changes and logs
    def feature_flags(self) -> dict[str, Any]: ...
    def search_logs(self, service: str, text: str, minutes: int) -> list[dict[str, Any]]: ...


def make_backend(kind: str, settings, fixture: str | None = None) -> Backend:
    if kind == "live":
        from .live import LiveBackend

        return LiveBackend(settings)
    if kind == "fake":
        from .fake import FakeBackend

        if not fixture:
            raise ValueError("--backend fake requires --fixture")
        return FakeBackend.from_file(fixture)
    raise ValueError(f"Unknown backend: {kind}")
