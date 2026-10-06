from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from kubernetes import client, config

from ..config import Settings
from ..logs import collapse, compact_log

SECRET_LIKE = re.compile(r"(secret|password|passwd|token|api[_-]?key|credential)", re.I)
# query_string without `fields` searches ALL fields; with OTel's dynamic mapping
# (attributes.*) `fail*` expands into >1024 clauses and OpenSearch returns 500
# (too_many_clauses). That is why free text is searched in a few fields only.
LOG_TEXT_FIELDS = ["body", "severity.text", "attributes.exception.message", "attributes.exception.type"]
LOG_SERVICE_FIELDS = ["resource.service.name", "resource.k8s.deployment.name",
                      "resource.k8s.pod.name", "attributes.service.name"]
SERVER_KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'


def _ts(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _age(dt: datetime | None) -> str | None:
    if not dt:
        return None
    secs = int((datetime.now(timezone.utc) - dt).total_seconds())
    if secs < 120:
        return f"{secs}s"
    if secs < 7200:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


def active_flags_from_definitions(flags: dict[str, Any]) -> dict[str, Any]:
    """From flagd definitions, picks the flags that can yield a variant other than 'off'.

    A flag with a `targeting.if: [condition, then, else]` rule is active when either branch
    != 'off' — even if `defaultVariant` is 'off' (this is how productCatalogFailure works).
    """
    active = []
    for key, f in flags.items():
        if key.startswith("loadGenerator"):
            continue
        variants = f.get("variants", {})
        rule = (f.get("targeting") or {}).get("if")
        if isinstance(rule, list) and len(rule) == 3:
            for branch, variant in (("when condition is true", rule[1]), ("otherwise", rule[2])):
                if variant != "off":
                    active.append({"flag": key, "variant": variant, "value": variants.get(variant),
                                   "scope": f"targeted: {branch}", "condition": rule[0],
                                   "description": f.get("description", "")})
        elif f.get("defaultVariant") not in ("off", None):
            variant = f["defaultVariant"]
            active.append({"flag": key, "variant": variant, "value": variants.get(variant),
                           "scope": "all requests", "description": f.get("description", "")})
    return {"source": "flag definitions (flagd-ui)", "total_flags": len(flags), "non_default_flags": active}


class LiveBackend:
    def __init__(self, settings: Settings):
        self.s = settings
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()
        self.http = httpx.Client(timeout=15)

    # ------------------------------------------------------------ Prometheus
    def prom_query(self, promql: str) -> list[dict[str, Any]]:
        r = self.http.get(f"{self.s.prometheus_url}/api/v1/query", params={"query": promql})
        r.raise_for_status()
        out = []
        for item in r.json()["data"]["result"][:30]:
            value = item.get("value", [None, None])[1]
            out.append({"labels": item["metric"], "value": value})
        return out

    def _scalar(self, promql: str) -> float | None:
        res = self.prom_query(promql)
        if not res or res[0]["value"] in (None, "NaN"):
            return None
        return round(float(res[0]["value"]), 4)

    def service_overview(self, service: str) -> dict[str, Any]:
        sel = f'service_name="{service}", {SERVER_KINDS}'
        calls = f"traces_span_metrics_calls_total{{{sel}}}"
        errors = f'traces_span_metrics_calls_total{{{sel}, status_code="STATUS_CODE_ERROR"}}'
        bucket = f"traces_span_metrics_duration_milliseconds_bucket{{{sel}}}"

        def window(offset: str = "") -> dict[str, Any]:
            o = f" offset {offset}" if offset else ""
            rps = self._scalar(f"sum(rate({calls}[5m]{o}))")
            err = self._scalar(f"sum(rate({errors}[5m]{o}))") or 0.0
            return {
                "requests_per_s": rps,
                "error_ratio": round(err / rps, 4) if rps else None,
                "p95_ms": self._scalar(f"histogram_quantile(0.95, sum by (le) (rate({bucket}[5m]{o})))"),
            }

        # cAdvisor (kubelet) — deployment pods are named <svc>-<rs hash>-<pod hash>
        c_sel = (f'namespace="{self.s.namespace}", pod=~"{service}-[a-z0-9]+-[a-z0-9]+", '
                 'container!="", container!="POD"')
        return {
            "service": service,
            "now_5m": window(),
            "1h_ago_5m": window("1h"),
            "memory_working_set_mb": self._scalar(
                f"sum(container_memory_working_set_bytes{{{c_sel}}}) / 1024 / 1024"
            ),
            "memory_limit_utilization": self._scalar(
                f"max(sum by (pod, container) (container_memory_working_set_bytes{{{c_sel}}}) "
                f"/ sum by (pod, container) (container_spec_memory_limit_bytes{{{c_sel}}} > 0))"
            ),
            "memory_growth_kb_per_s_10m": self._scalar(
                f"sum(deriv(container_memory_working_set_bytes{{{c_sel}}}[10m])) / 1024"
            ),
            "cpu_cores": self._scalar(f"sum(rate(container_cpu_usage_seconds_total{{{c_sel}}}[5m]))"),
            "cpu_throttled_ratio": self._scalar(
                f"sum(rate(container_cpu_cfs_throttled_periods_total{{{c_sel}}}[5m])) "
                f"/ sum(rate(container_cpu_cfs_periods_total{{{c_sel}}}[5m]))"
            ),
        }

    def error_breakdown(self, service: str) -> list[dict[str, Any]]:
        q = (
            f'topk(8, sum by (span_name, span_kind) (rate(traces_span_metrics_calls_total'
            f'{{service_name="{service}", status_code="STATUS_CODE_ERROR"}}[5m])))'
        )
        return [
            {"span": r["labels"].get("span_name"), "kind": r["labels"].get("span_kind"),
             "errors_per_s": round(float(r["value"]), 4)}
            for r in self.prom_query(q)
            if r["value"] not in (None, "NaN") and float(r["value"]) > 0
        ]

    def list_metrics(self, pattern: str) -> list[str]:
        r = self.http.get(f"{self.s.prometheus_url}/api/v1/label/__name__/values")
        r.raise_for_status()
        rx = re.compile(pattern, re.I)
        return [m for m in r.json()["data"] if rx.search(m)][:60]

    def firing_alerts(self) -> list[dict[str, Any]]:
        r = self.http.get(f"{self.s.prometheus_url}/api/v1/alerts")
        r.raise_for_status()
        return [
            {
                "name": a["labels"].get("alertname"),
                "service": a["labels"].get("service", ""),
                "severity": a["labels"].get("severity", "warning"),
                "summary": a.get("annotations", {}).get("summary", ""),
                "labels": a["labels"],
                "started_at": a.get("activeAt"),
                "state": a.get("state"),
            }
            for a in r.json()["data"]["alerts"]
        ]

    # ------------------------------------------------------------ Kubernetes
    def _selector(self, service: str) -> str:
        return f"opentelemetry.io/name={service}"

    def pods(self, service: str) -> list[dict[str, Any]]:
        pods = self.core.list_namespaced_pod(self.s.namespace, label_selector=self._selector(service))
        out = []
        for p in pods.items:
            containers = []
            for cs in p.status.container_statuses or []:
                last = cs.last_state.terminated if cs.last_state else None
                waiting = cs.state.waiting if cs.state else None
                containers.append({
                    "name": cs.name,
                    "ready": cs.ready,
                    "restarts": cs.restart_count,
                    "image": cs.image,
                    "waiting_reason": waiting.reason if waiting else None,
                    "waiting_message": (waiting.message or "")[:200] if waiting else None,
                    "last_termination": {
                        "reason": last.reason, "exit_code": last.exit_code,
                        "finished": _ts(last.finished_at),
                    } if last else None,
                })
            out.append({
                "pod": p.metadata.name,
                "phase": p.status.phase,
                "age": _age(p.metadata.creation_timestamp),
                "revision_hash": (p.metadata.labels or {}).get("pod-template-hash"),
                "containers": containers,
            })
        return out

    def events(self, service: str) -> list[dict[str, Any]]:
        evs = self.core.list_namespaced_event(self.s.namespace).items
        rel = [
            e for e in evs
            if e.involved_object.name == service or e.involved_object.name.startswith(f"{service}-")
        ]

        def when(e):
            return e.last_timestamp or e.event_time or e.metadata.creation_timestamp

        rel.sort(key=lambda e: when(e) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return [
            {
                "ago": _age(when(e)), "type": e.type, "reason": e.reason,
                "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                "count": e.count, "message": (e.message or "")[:250],
            }
            for e in rel[:20]
        ]

    @staticmethod
    def _template_summary(tpl) -> dict[str, Any]:
        summary = {}
        for c in tpl.spec.containers:
            env = {}
            for e in c.env or []:
                if e.value_from:
                    env[e.name] = "<valueFrom>"
                elif SECRET_LIKE.search(e.name):
                    env[e.name] = "<redacted>"
                else:
                    env[e.name] = e.value
            res = c.resources
            summary[c.name] = {
                "image": c.image,
                "env": env,
                "limits": dict(res.limits or {}) if res else {},
                "requests": dict(res.requests or {}) if res else {},
            }
        return summary

    @staticmethod
    def _diff(old: dict, new: dict) -> list[str]:
        changes = []
        for name, n in new.items():
            o = old.get(name, {})
            if o.get("image") != n["image"]:
                changes.append(f"{name}: image {o.get('image')} -> {n['image']}")
            for k in ("limits", "requests"):
                if o.get(k) != n[k]:
                    changes.append(f"{name}: {k} {o.get(k)} -> {n[k]}")
            oe, ne = o.get("env", {}), n["env"]
            for key in sorted(set(oe) | set(ne)):
                if oe.get(key) != ne.get(key):
                    changes.append(f"{name}: env {key} {oe.get(key)!r} -> {ne.get(key)!r}")
        return changes

    def rollout_history(self, service: str) -> list[dict[str, Any]]:
        rss = self.apps.list_namespaced_replica_set(self.s.namespace, label_selector=self._selector(service)).items
        rss = [r for r in rss if any(o.name == service for o in r.metadata.owner_references or [])]
        rss.sort(key=lambda r: int((r.metadata.annotations or {}).get("deployment.kubernetes.io/revision", 0)))
        out, prev = [], None
        for r in rss:
            cur = self._template_summary(r.spec.template)
            out.append({
                "revision": (r.metadata.annotations or {}).get("deployment.kubernetes.io/revision"),
                "created": _ts(r.metadata.creation_timestamp),
                "age": _age(r.metadata.creation_timestamp),
                "replicas_desired": r.spec.replicas,
                "replicas_ready": r.status.ready_replicas or 0,
                "images": {k: v["image"] for k, v in cur.items()},
                "changes_vs_previous": self._diff(prev, cur) if prev else ["(oldest retained revision)"],
            })
            prev = cur
        return out[-5:]

    def deployment_spec(self, service: str) -> dict[str, Any]:
        d = self.apps.read_namespaced_deployment(service, self.s.namespace)
        return {
            "deployment": service,
            "replicas": d.spec.replicas,
            "ready": d.status.ready_replicas or 0,
            "updated": d.status.updated_replicas or 0,
            "revision": (d.metadata.annotations or {}).get("deployment.kubernetes.io/revision"),
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason, "message": (c.message or "")[:200]}
                for c in d.status.conditions or []
            ],
            "containers": self._template_summary(d.spec.template),
        }

    # ------------------------------------------------------------ flags and logs
    def feature_flags(self) -> dict[str, Any]:
        """Flags that differ from 'off'. Read from the definitions (flagd-ui) first, because only they show
        targeted flags; if flagd-ui is unreachable, fall back to OFREP evaluation with a warning."""
        try:
            r = self.http.get(f"{self.s.flagd_ui_url}/api/read")
            r.raise_for_status()
            return active_flags_from_definitions(r.json()["flags"])
        except Exception as e:
            ui_error = f"{type(e).__name__}: {str(e)[:120]}"
        r = self.http.post(f"{self.s.flagd_url}/ofrep/v1/evaluate/flags", json={"context": {}})
        r.raise_for_status()
        flags = r.json().get("flags", [])
        active = [
            {"flag": f["key"], "variant": f.get("variant"), "value": f.get("value")}
            for f in flags
            if f.get("variant") not in ("off", None) and not f["key"].startswith("loadGenerator")
        ]
        return {"source": "OFREP evaluation without context", "total_flags": len(flags), "non_default_flags": active,
                "warning": "flag definitions unavailable (" + ui_error + "); flags enabled only for specific "
                           "targets (e.g. one product id) are NOT visible here"}

    def search_logs(self, service: str, text: str, minutes: int) -> list[dict[str, Any]]:
        text = text.strip() or "error OR exception OR fail* OR timeout OR refused OR unavailable"
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        url = f"{self.s.opensearch_url}/{self.s.logs_index}/_search"
        # 1) precise: the service field; 2) fallback: free text with the service name.
        # The service name lives in different fields depending on the log source (SDK vs collector),
        # so any of them is accepted.
        service_filters = [
            {"bool": {"minimum_should_match": 1, "should": [
                {"match_phrase": {"resource.service.name": service}},
                {"match_phrase": {"resource.k8s.deployment.name": service}},
                {"match_phrase": {"attributes.service.name": service}},
            ]}},
            None,
        ]
        hits: list[dict[str, Any]] = []
        for svc_filter in service_filters:
            body = self._logs_body(service, text, since, svc_filter)
            r = self.http.post(url, json=body)
            r.raise_for_status()
            hits = r.json()["hits"]["hits"]
            if hits:
                break
        return collapse([compact_log(h["_source"]) for h in hits])

    @staticmethod
    def _logs_body(service: str, text: str, since: str, svc_filter: dict | None) -> dict[str, Any]:
        """The log query. OTel Demo stores time in `observedTimestamp` (not `@timestamp`),
        so the time filter accepts both fields. A range on a missing field does not return 400,
        just zero hits — so a fallback based on the HTTP status would not work here."""
        must = [{"query_string": {"query": text, "fields": LOG_TEXT_FIELDS, "lenient": True}}]
        filters: list[dict[str, Any]] = [{"bool": {"minimum_should_match": 1, "should": [
            {"range": {"observedTimestamp": {"gte": since}}},
            {"range": {"@timestamp": {"gte": since}}},
        ]}}]
        if svc_filter:
            filters.append(svc_filter)
        else:
            must.append({"query_string": {"query": f'"{service}"', "fields": LOG_SERVICE_FIELDS, "lenient": True}})
        return {
            "size": 60,  # after collapsing duplicates only a few groups usually remain
            "sort": [
                {"observedTimestamp": {"order": "desc", "unmapped_type": "date"}},
                {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
            ],
            "query": {"bool": {"must": must, "filter": filters}},
        }
