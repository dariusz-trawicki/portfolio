"""Remediation (step 5): turning a diagnosis into a fix that a human approves.

The split of responsibilities is deliberate:

    LLM         -> proposes (recommended_action + action_target inside the Diagnosis)
    this module -> checks the proposal against an allow-list and describes the exact command
    a human     -> approves or rejects (LangGraph `interrupt()`; there is no auto-approve)
    Executor    -> plain code that knows exactly two actions; the model never calls it directly
    verifier    -> confirms the alert actually went away, otherwise the incident is escalated

Only two actions are automated, both reversible:
  * disable_feature_flag -> set the flag to "off" through the flagd-ui API
  * rollback_deployment  -> `kubectl rollout undo` to the previous revision
Everything else (increase_resources, restart_pods, scale_up, escalate_to_human, none) is reported
as a manual follow-up.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .prompts import _edges
from .state import Alert, Diagnosis

AUTOMATED_ACTIONS = ("disable_feature_flag", "rollback_deployment")
MIN_CONFIDENCE = 0.6     # below this the agent does not even propose an automated fix


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def application_services() -> set[str]:
    """Deployments a rollback may target: services from the dependency map (never Prometheus, Grafana...)."""
    return {name for edge in _edges() for name in edge}


@dataclass
class Proposal:
    action: str
    target: str
    executable: bool
    reason: str
    command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Executor(Protocol):
    def validate(self, action: str, target: str) -> tuple[bool, str]: ...
    def describe(self, action: str, target: str) -> str: ...
    def execute(self, action: str, target: str) -> str: ...


def propose(diagnosis: Diagnosis, executor: Executor, min_confidence: float = MIN_CONFIDENCE) -> Proposal:
    action, target = diagnosis.recommended_action, diagnosis.action_target.strip()
    if action not in AUTOMATED_ACTIONS:
        return Proposal(action, target, False, f"'{action}' is not automated — manual follow-up")
    if diagnosis.confidence < min_confidence:
        return Proposal(action, target, False,
                        f"confidence {diagnosis.confidence:.0%} is below {min_confidence:.0%} — escalate instead")
    ok, why = executor.validate(action, target)
    if not ok:
        return Proposal(action, target, False, why)
    return Proposal(action, target, True, why, executor.describe(action, target))


# ---------------------------------------------------------------- executors
class LiveExecutor:
    """Acts on the real cluster. Every action is validated again right before it runs."""

    def __init__(self, namespace: str, backend):
        self.ns, self.backend = namespace, backend

    def validate(self, action: str, target: str) -> tuple[bool, str]:
        if action == "disable_feature_flag":
            from .chaos import current_variant, read_flags

            flags = read_flags(self.ns)["flags"]
            if target not in flags or target.startswith("loadGenerator"):
                return False, f"unknown or protected flag '{target}'"
            if current_variant(flags[target]) == "off" and flags[target].get("defaultVariant") == "off":
                return False, f"flag '{target}' is already off"
            return True, f"flag '{target}' is currently on"
        if action == "rollback_deployment":
            if target not in application_services():
                return False, f"'{target}' is not an application deployment from the service map"
            history = self.backend.rollout_history(target)
            if len(history) < 2:
                return False, f"deployment '{target}' has no previous revision to roll back to"
            return True, f"deployment '{target}' has {len(history)} revisions"
        return False, f"action '{action}' is not automated"

    def describe(self, action: str, target: str) -> str:
        if action == "disable_feature_flag":
            return f"flagd-ui API: set flag {target} -> off"
        return f"kubectl -n {self.ns} rollout undo deployment/{target}"

    def execute(self, action: str, target: str) -> str:
        ok, why = self.validate(action, target)        # the world may have changed while we waited
        if not ok:
            raise RuntimeError(f"refused: {why}")
        if action == "disable_feature_flag":
            from .chaos import set_flag

            set_flag(self.ns, target, "off")
            return f"flag {target} set to off"
        from .chaos import _kubectl

        out = _kubectl(["rollout", "undo", f"deployment/{target}"], self.ns).strip()
        status = _kubectl(["rollout", "status", f"deployment/{target}", "--timeout=180s"], self.ns).strip()
        return f"{out}; {status.splitlines()[-1] if status else 'rollout finished'}"


class DryRunExecutor:
    """Records what it would do and changes nothing (fake backend, demos, tests)."""

    def __init__(self, namespace: str = "otel-demo"):
        self.ns = namespace
        self.executed: list[tuple[str, str]] = []

    def validate(self, action: str, target: str) -> tuple[bool, str]:
        if action not in AUTOMATED_ACTIONS:
            return False, f"action '{action}' is not automated"
        if not target:
            return False, "empty action target"
        return True, "dry run: not checked against the cluster"

    def describe(self, action: str, target: str) -> str:
        return "[dry run] " + LiveExecutor.describe(self, action, target)  # type: ignore[arg-type]

    def execute(self, action: str, target: str) -> str:
        self.executed.append((action, target))
        return f"[dry run] would {action} {target}"


# ---------------------------------------------------------------- verification
# Waiting for the alert itself is slow by design: HighErrorRate uses a 5m window plus
# keep_firing_for: 5m (to stop flapping), so it clears ~10 min after a perfect fix. The fast probe
# asks the same question over a short window and needs a few healthy readings in a row.
FAST_WINDOW = "2m"
HEALTHY_READINGS = 3

_SPANS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'


def _q(label: str, value: str) -> str:
    return f'{label}="{value.replace(chr(92), "").replace(chr(34), "")}"'


def fast_probe_query(alert: Alert, namespace: str = "otel-demo") -> tuple[str, float] | None:
    """(PromQL, threshold) answering "is it healthy now?" for the alert type, or None (no fast probe).

    Healthy means the query result is below the threshold — the same thresholds as the alert rules.
    """
    svc = _q("service_name", alert.service)
    if alert.name == "HighErrorRate":
        sel = f"{svc}, {_SPANS}"
        return (f'sum(rate(traces_span_metrics_calls_total{{{sel}, status_code="STATUS_CODE_ERROR"}}[{FAST_WINDOW}])) '
                f'/ sum(rate(traces_span_metrics_calls_total{{{sel}}}[{FAST_WINDOW}]))', 0.05)
    if alert.name == "HighOperationErrorRate" and alert.labels.get("span_name"):
        sel = f'{svc}, {_q("span_name", alert.labels["span_name"])}, {_SPANS}'
        return (f'sum(rate(traces_span_metrics_calls_total{{{sel}, status_code="STATUS_CODE_ERROR"}}[{FAST_WINDOW}])) '
                f'/ sum(rate(traces_span_metrics_calls_total{{{sel}}}[{FAST_WINDOW}]))', 0.05)
    if alert.name == "KafkaConsumerLag":
        return f'max(kafka_consumer_group_lag_ratio{{{_q("group", alert.service)}}})', 100
    if alert.name == "HighCpuUsage":
        return (f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}", '
                f'pod=~"{alert.service}-[a-z0-9]+-[a-z0-9]+", container!="", container!="POD"}}[{FAST_WINDOW}]))', 0.5)
    return None


def make_probe(prom_query: Callable[[str], list[dict]], alert: Alert,
               namespace: str = "otel-demo") -> Callable[[], bool | None] | None:
    """A callable: True = healthy now, False = still broken, None = no data (e.g. no traffic in the window)."""
    spec = fast_probe_query(alert, namespace)
    if spec is None:
        return None
    query, threshold = spec

    def probe() -> bool | None:
        try:
            rows = prom_query(query)
        except Exception:
            return None
        if not rows or rows[0].get("value") in (None, "NaN"):
            return None
        return float(rows[0]["value"]) < threshold

    return probe


def verify_recovery(firing_alerts: Callable[[], list[dict]], alert: Alert, *, timeout_s: float = 15 * 60,
                    poll_s: float = 20, probe: Callable[[], bool | None] | None = None,
                    healthy_readings: int = HEALTHY_READINGS, sleep: Callable[[float], None] = time.sleep,
                    clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Recovered when the alert that opened the incident stops firing, or — faster — when the fast
    probe reports healthy `healthy_readings` times in a row. "No data" never counts as healthy."""
    start, streak = clock(), 0
    checked = f"{alert.name} · {alert.service}"
    while True:
        elapsed = round(clock() - start, 1)
        if probe is not None:
            healthy = probe()
            streak = streak + 1 if healthy is True else 0
            if streak >= healthy_readings:
                return {"recovered": True, "after_s": elapsed, "checked": checked, "method": f"metric, {FAST_WINDOW} window"}
        still = [a for a in firing_alerts()
                 if a.get("state") == "firing" and a.get("name") == alert.name and a.get("service") == alert.service]
        if not still:
            return {"recovered": True, "after_s": elapsed, "checked": checked, "method": "alert cleared"}
        if elapsed >= timeout_s:
            return {"recovered": False, "after_s": elapsed, "checked": checked,
                    "detail": "alert still firing after the fix — escalate to a human"}
        sleep(poll_s)


@dataclass
class Remediation:
    """Everything the graph needs for the remediation branch."""

    executor: Executor
    verify: Callable[[Alert], dict[str, Any]]
    min_confidence: float = MIN_CONFIDENCE
    # GitOps (step 5e): the fix is a PR a human still has to merge. Called with execution["pr"]; returns
    # {"merged": bool, ...}. None = the executor's fix takes effect immediately (kubectl, flags).
    await_merge: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def live_remediation(backend, namespace: str, verify_timeout_s: float = 15 * 60) -> Remediation:
    def verify(alert: Alert) -> dict[str, Any]:
        return verify_recovery(backend.firing_alerts, alert, timeout_s=verify_timeout_s,
                               probe=make_probe(backend.prom_query, alert, namespace))

    return Remediation(LiveExecutor(namespace, backend), verify)


def dry_run_remediation(namespace: str = "otel-demo") -> Remediation:
    return Remediation(DryRunExecutor(namespace), lambda alert: {"recovered": None, "detail": "dry run: not verified"})


def make_decision(approved: bool, by: str = "", comment: str = "") -> dict[str, Any]:
    return {"approved": bool(approved), "by": by or "unknown", "comment": comment, "at": _now()}
