from __future__ import annotations

import re

# OTel Demo dependency map (who calls whom). In production you would build it
# from traces (service graph); a static version from the docs is enough here.
SERVICE_MAP = """\
frontend-proxy -> frontend, image-provider, flagd-ui
frontend -> ad, cart, checkout, currency, product-catalog, recommendation, shipping
checkout -> cart, currency, email, payment, product-catalog, shipping, kafka(orders)
cart -> valkey-cart
recommendation -> product-catalog
product-catalog -> astronomy-db
shipping -> quote
kafka(orders) -> accounting, fraud-detection
all services -> flagd (feature flags)"""



def _clean(name: str) -> str:
    """`kafka(orders)` -> `kafka`."""
    return re.sub(r"\(.*\)", "", name).strip()


def _edges() -> list[tuple[str, str]]:
    """Edges (caller, callee) from SERVICE_MAP; skips the 'all services -> flagd' line."""
    out = []
    for line in SERVICE_MAP.splitlines():
        src, _, dst = line.partition("->")
        src = _clean(src)
        if src == "all services":
            continue
        out += [(src, _clean(d)) for d in dst.split(",") if d.strip()]
    return out


def dependencies(service: str) -> list[str]:
    """Direct dependencies (what the service calls) from SERVICE_MAP. `kafka(orders)` -> `kafka`."""
    return [d for s, d in _edges() if s == service]


def neighbours(service: str) -> set[str]:
    """Neighbours in both directions: dependencies and the services that call `service`.

    Used for alert correlation: while checkout is firing, an alert for payment (its dependency)
    or for frontend (its client) is probably the same incident.
    """
    return {d for s, d in _edges() if s == service} | {s for s, d in _edges() if d == service}


INVESTIGATOR_SYSTEM = f"""\
You are an experienced on-call SRE. You are investigating an incident in Kubernetes
(a namespace running a microservice-based e-commerce application).

Your goal: find the ROOT CAUSE, not just describe the symptom.

Working rules:
1. The alerting service is often just a victim. Check its dependencies (map below)
   before concluding that the problem is in the service itself.
2. Ask "what changed?" first: new deployment revisions, env/limit changes,
   enabled feature flags. Most incidents are caused by a change.
3. Back every hypothesis with at least one concrete piece of evidence from the tools
   (a number, an event, a log line, a revision diff). Do not guess.
4. The "1h_ago" window is a comparison point, not a guaranteed healthy baseline —
   if it already looks abnormal, say so instead of treating it as normal.
5. You have a limited tool-call budget. Do not repeat queries whose answers
   are already in the collected evidence.
6. You have read-only access. You do not fix anything — you only diagnose.
7. Once you have enough evidence, finish with a short summary of your hypothesis
   (without calling tools).

Service dependency map:
{SERVICE_MAP}
"""

INVESTIGATION_KICKOFF = """\
ALERT
{alert}

AUTOMATICALLY COLLECTED EVIDENCE (for the alerting service; dependency_logs = error logs of its direct dependencies)
{evidence}

Investigate the incident. Start with hypotheses, then verify them with tools."""

DIAGNOSIS_SYSTEM = """\
Based on the investigation transcript, produce the final incident diagnosis.

- culprit_service: the service where the cause lies (may differ from the alerting service).
- Choose category and recommended_action from the allowed values.
- If the cause is an enabled feature flag: action = disable_feature_flag,
  action_target = the flag name.
- If the cause is a new deployment revision (image, env, limits):
  action = rollback_deployment, action_target = the deployment name.
- If the evidence is ambiguous, lower the confidence and consider escalate_to_human.
- evidence: only facts that actually appeared during the investigation."""


LANGUAGE_NOTES = {
    "en": "",
    "pl": (
        "\n\nLANGUAGE: write all free text (your reasoning, root_cause, evidence, rationale) in Polish. "
        "Keep technical identifiers unchanged: service names, flag names, metric names, log lines, "
        "and the enum values of category and recommended_action stay exactly as defined (English)."
    ),
}


def language_note(lang: str) -> str:
    return LANGUAGE_NOTES.get(lang, "")
