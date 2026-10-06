"""Environment diagnostics: can the agent reach all of its data sources?

Every check returns (status, name, detail, hint). status: ok | warn | fail.
"""

from __future__ import annotations

import os
import subprocess
from typing import Callable

import httpx

from .config import Settings

EXPECTED_METRICS = {
    "traces_span_metrics_calls_total": "HighErrorRate alert and golden signals",
    "traces_span_metrics_duration_milliseconds_bucket": "HighLatencyP95 alert, p95",
    "k8s_container_restarts": "PodRestarting alert",
    "k8s_container_ready": "ContainerNotReady alert",
    "container_memory_working_set_bytes": "MemoryGrowth/MemoryNearLimit alerts, memory in golden signals",
    "container_spec_memory_limit_bytes": "MemoryNearLimit alert",
    "container_cpu_usage_seconds_total": "CPU in golden signals",
}

Check = tuple[str, str, str, str]


def _cmd(args: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"{args[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def in_cluster() -> bool:
    """True inside a pod (the agent deployed by `make agent-up`)."""
    return bool(os.getenv("KUBERNETES_SERVICE_HOST"))


def check_tools(s: Settings) -> list[Check]:
    out = []
    tools = [("kubectl", ["kubectl", "version", "--client"])]
    if not in_cluster():   # the image ships kubectl only (for `rollout undo`); helm and kind are lab tools
        tools += [("helm", ["helm", "version", "--short"]), ("kind", ["kind", "version"])]
    for tool, args in tools:
        code, txt = _cmd(args)
        out.append(("ok" if code == 0 else "fail", f"tool {tool}", txt.splitlines()[0] if txt else "",
                    "" if code == 0 else f"install {tool}"))
    return out


def check_cluster(s: Settings) -> list[Check]:
    code, txt = _cmd(["kubectl", "-n", s.namespace, "get", "deploy", "--no-headers"])
    if code != 0:
        return [("fail", "cluster", txt[:200], "kubectl cannot see the cluster: `kubectl config current-context`")]
    rows = [line.split() for line in txt.splitlines() if line.strip()]
    not_ready = [r[0] for r in rows if r[1].split("/")[0] != r[1].split("/")[1]]
    status = "ok" if rows and not not_ready else "warn"
    detail = f"{len(rows)} deployments, not ready: {', '.join(not_ready) or 'none'}"
    hint = "wait (`make wait`) or `kubectl -n otel-demo describe pod <pod>`" if not_ready else ""
    return [(status, "OTel Demo deployments", detail, hint)]


def check_prometheus(s: Settings, http: httpx.Client) -> list[Check]:
    out: list[Check] = []
    try:
        names = set(http.get(f"{s.prometheus_url}/api/v1/label/__name__/values").json()["data"])
    except Exception as e:
        return [("fail", "Prometheus", str(e)[:150], "run `make port-forward`")]
    out.append(("ok", "Prometheus", f"{len(names)} metrics", ""))
    for m, used_for in EXPECTED_METRICS.items():
        if m in names:
            out.append(("ok", f"metric {m}", used_for, ""))
        else:
            words = [w for w in m.split("_") if w not in ("total", "bytes", "seconds", "k8s")]
            similar = sorted(n for n in names if sum(w in n for w in words) >= 2)[:5]
            out.append(("warn", f"metric {m}", f"missing — needed for: {used_for}",
                        f"similar: {', '.join(similar) or 'none'}; fix the name in infra/otel-demo-values.yaml "
                        "and backends/live.py (after a fresh install wait 2-3 min)"))
    try:
        groups = http.get(f"{s.prometheus_url}/api/v1/rules").json()["data"]["groups"]
        rules = [r["name"] for g in groups if g["name"] == "incident-lab" for r in g["rules"]]
        out.append(("ok" if len(rules) >= 6 else "warn" if rules else "fail", "alert rules", ", ".join(rules) or "none",
                    "" if len(rules) >= 6 else "outdated rules — `make apply-values`" if rules
                    else "helm did not load serverFiles — check `helm get values otel-demo -n otel-demo`"))
    except Exception as e:
        out.append(("fail", "alert rules", str(e)[:150], ""))
    return out


def check_opensearch(s: Settings, http: httpx.Client) -> list[Check]:
    try:
        r = http.post(f"{s.opensearch_url}/{s.logs_index}/_search", json={"size": 1})
        r.raise_for_status()
        hits = r.json()["hits"]["hits"]
    except Exception as e:
        return [("fail", "OpenSearch", str(e)[:150], "run `make port-forward`; the index appears after the first logs")]
    if not hits:
        return [("warn", "OpenSearch", "index is empty", "wait a few minutes for logs")]
    doc = hits[0]["_source"]
    flat: list[str] = []

    def walk(prefix, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        else:
            flat.append(prefix)

    walk("", doc)
    ts = [f for f in flat if "timestamp" in f.lower()]
    svc = [f for f in flat if "service" in f.lower() and "name" in f.lower()]
    out = [("ok", "OpenSearch", f"logs present; sample fields: {', '.join(flat[:6])}", "")]
    out.append(("ok" if "@timestamp" in flat else "warn", "log timestamp field", ", ".join(ts) or "none",
                "" if "@timestamp" in flat else "search_logs will fall back to no time filter — "
                f"change '@timestamp' in backends/live.py to {ts[0] if ts else '?'}"))
    out.append(("ok" if svc else "warn", "log service field", ", ".join(svc) or "none",
                "" if svc else "search by service name is full-text and may pick up noise"))
    return out


def check_flagd(s: Settings, http: httpx.Client) -> list[Check]:
    try:
        r = http.post(f"{s.flagd_url}/ofrep/v1/evaluate/flags", json={"context": {}})
        r.raise_for_status()
        flags = r.json().get("flags", [])
        on = [f["key"] for f in flags if f.get("variant") not in ("off", None) and not f["key"].startswith("loadGenerator")]
        return [("ok" if flags else "warn", "flagd (OFREP)", f"{len(flags)} flags, enabled: {', '.join(on) or 'none'}",
                 "`incident-agent chaos reset` if something was left on" if on else "")]
    except Exception as e:
        return [("fail", "flagd (OFREP)", str(e)[:150], "run `make port-forward` (port 8016)")]


def check_flagd_ui(s: Settings, http: httpx.Client) -> list[Check]:
    try:
        r = http.get(f"{s.flagd_ui_url}/api/read")
        r.raise_for_status()
        targeted = [k for k, f in r.json()["flags"].items() if "targeting" in f]
        return [("ok", "flag definitions (flagd-ui)", f"readable; flags with targeting: {', '.join(targeted) or 'none'}", "")]
    except Exception as e:
        return [("warn", "flag definitions (flagd-ui)", str(e)[:150],
                 "run `make port-forward` (port 8080); without it the agent cannot see targeted flags")]


def check_state(s: Settings) -> list[Check]:
    from .checkpointing import is_postgres, open_checkpointer, redact

    try:
        with open_checkpointer(s.checkpoint_db) as cp:
            cp.get_tuple({"configurable": {"thread_id": "doctor"}})
        from .store import open_store

        n = len(open_store(s.checkpoint_db).load())
    except Exception as e:
        hint = "is the postgres pod Ready? `kubectl -n incident-agent get pods`" if is_postgres(s.checkpoint_db) \
            else "check that the directory is writable"
        return [("fail", "state (checkpoints + incidents)", f"{redact(s.checkpoint_db)}: {str(e)[:120]}", hint)]
    return [("ok", "state (checkpoints + incidents)", f"{redact(s.checkpoint_db)} · {n} incident(s)", "")]


# What the in-cluster service account must and must not be allowed to do (deploy/k8s/rbac.yaml).
RBAC_EXPECTED = [
    ("list", "pods", True), ("list", "events", True),
    ("list", "replicasets.apps", True), ("patch", "deployments.apps/checkout", True),
    ("patch", "deployments.apps/prometheus", False), ("delete", "pods", False),
    ("create", "pods/exec", False), ("get", "secrets", False), ("delete", "deployments.apps", False),
]


def check_rbac(s: Settings) -> list[Check]:
    """Only in the cluster: asks the API server what this pod's service account may do."""
    if not in_cluster():
        return []
    wrong = []
    for verb, resource, expected in RBAC_EXPECTED:
        code, txt = _cmd(["kubectl", "auth", "can-i", verb, resource, "-n", s.namespace])
        allowed = txt.strip().startswith("yes")
        if allowed != expected:
            wrong.append(f"{verb} {resource}: {'allowed' if allowed else 'denied'}")
    if wrong:
        return [("fail", "RBAC (least privilege)", "; ".join(wrong), "kubectl apply -f deploy/k8s/rbac.yaml")]
    return [("ok", "RBAC (least privilege)", "read + patch of app deployments only; no exec, secrets or delete", "")]


def check_gitops(s: Settings) -> list[Check]:
    """Only when rollbacks go through Git: can the token read the repo and the values file?"""
    if s.rollback_mode != "gitops":
        return []
    if not s.gitops_repo or not s.gitops_token:
        return [("fail", "GitOps rollback", "GITOPS_REPO / GITOPS_TOKEN not set", "make agent-gitops")]
    from .gitops import GitHub

    try:
        where = GitHub(s.gitops_repo, s.gitops_token, s.github_api_url).can_read(s.gitops_values_path, s.gitops_base_branch)
    except Exception as e:
        return [("fail", "GitOps rollback", str(e)[:150], "token needs Contents + Pull requests (read/write) on that repo")]
    return [("ok", "GitOps rollback", f"PRs against {where}; a human merges, ArgoCD applies", "")]


def check_llm(s: Settings) -> list[Check]:
    provider = s.model.split(":", 1)[0]
    key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    if key and not os.getenv(key):
        return [("fail", "LLM model", s.model, f"{key} is not set — `set -a; source .env; set +a`")]
    return [("ok", "LLM model", s.model, "")]


def run_all(s: Settings) -> list[Check]:
    http = httpx.Client(timeout=10)
    steps: list[Callable[[], list[Check]]] = [
        lambda: check_tools(s), lambda: check_cluster(s), lambda: check_prometheus(s, http),
        lambda: check_opensearch(s, http), lambda: check_flagd(s, http), lambda: check_flagd_ui(s, http),
        lambda: check_state(s), lambda: check_rbac(s), lambda: check_gitops(s), lambda: check_llm(s),
    ]
    results: list[Check] = []
    for step in steps:
        results.extend(step())
    return results
