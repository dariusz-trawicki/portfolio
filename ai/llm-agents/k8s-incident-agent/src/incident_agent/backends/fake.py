from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class FakeBackend:
    """Replays responses from a JSON fixture (keys = method names, then service name).

    Used for tests and demos without a cluster: the same graph, a real LLM,
    recorded data. Missing data for a service returns an empty result, just as
    a real system would.
    """

    def __init__(self, data: dict[str, Any]):
        self.d = data
        self.calls: list[tuple[str, tuple]] = []

    @classmethod
    def from_file(cls, path: str | Path) -> "FakeBackend":
        return cls(json.loads(Path(path).read_text()))

    def _by_service(self, method: str, service: str, empty: Any) -> Any:
        self.calls.append((method, (service,)))
        return self.d.get(method, {}).get(service, empty)

    def service_overview(self, service):
        return self._by_service("service_overview", service, {"service": service, "note": "no data"})

    def error_breakdown(self, service):
        return self._by_service("error_breakdown", service, [])

    def pods(self, service):
        return self._by_service("pods", service, [])

    def events(self, service):
        return self._by_service("events", service, [])

    def rollout_history(self, service):
        return self._by_service("rollout_history", service, [])

    def deployment_spec(self, service):
        spec = self._by_service("deployment_spec", service, None)
        if spec is None:
            raise LookupError(f'deployments.apps "{service}" not found')
        return spec

    def search_logs(self, service, text, minutes):
        self.calls.append(("search_logs", (service, text, minutes)))
        return self.d.get("search_logs", {}).get(service, [])

    def prom_query(self, promql):
        self.calls.append(("prom_query", (promql,)))
        return self.d.get("prom_query", {}).get(promql, [])

    def list_metrics(self, pattern):
        self.calls.append(("list_metrics", (pattern,)))
        rx = re.compile(pattern, re.I)
        return [m for m in self.d.get("list_metrics", []) if rx.search(m)]

    def feature_flags(self):
        self.calls.append(("feature_flags", ()))
        return self.d.get("feature_flags", {"total_flags": 0, "non_default_flags": []})

    def firing_alerts(self):
        self.calls.append(("firing_alerts", ()))
        return self.d.get("firing_alerts", [])
