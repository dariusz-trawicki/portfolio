from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import AIMessage

ACTION_LABELS = {
    "rollback_deployment": "Roll back deployment",
    "disable_feature_flag": "Disable feature flag",
    "increase_resources": "Increase resource limits",
    "restart_pods": "Restart pods",
    "scale_up": "Scale up replicas",
    "escalate_to_human": "Escalate to a human",
    "none": "No action",
}


PL_ACTION_LABELS = {
    "rollback_deployment": "Wycofaj wdrożenie (rollback)",
    "disable_feature_flag": "Wyłącz flagę funkcji",
    "increase_resources": "Zwiększ limity zasobów",
    "restart_pods": "Zrestartuj pody",
    "scale_up": "Zwiększ liczbę replik",
    "escalate_to_human": "Eskaluj do człowieka",
    "none": "Brak akcji",
}


REMEDIATION_TEXT = {
    "en": {"title": "Remediation", "proposed": "Proposed", "not_automated": "Not automated",
           "awaiting": "Awaiting human approval", "approved": "Approved", "rejected": "Rejected",
           "by": "by", "executed": "Executed", "failed": "Execution failed", "recovered": "Verified: the alert is gone",
           "not_recovered": "NOT verified", "unverified": "Not verified", "after": "after"},
    "pl": {"title": "Naprawa", "proposed": "Propozycja", "not_automated": "Nieautomatyzowana",
           "awaiting": "Czeka na akceptację człowieka", "approved": "Zaakceptowana", "rejected": "Odrzucona",
           "by": "przez", "executed": "Wykonana", "failed": "Wykonanie nie powiodło się",
           "recovered": "Zweryfikowana: alert zgasł", "not_recovered": "NIEzweryfikowana", "unverified": "Niezweryfikowana",
           "after": "po"},
}


def render_remediation(state, lang: str = "en") -> str:
    """The remediation section; empty when the graph ran without the remediation branch."""
    p = state.get("proposal")
    if not p:
        return ""
    t = REMEDIATION_TEXT.get(lang, REMEDIATION_TEXT["en"])
    lines = [f"\n## {t['title']}"]
    if not p.get("executable"):
        lines.append(f"- {t['not_automated']}: `{p['action']}` → `{p['target']}` — {p['reason']}")
        return "\n".join(lines) + "\n"
    lines.append(f"- {t['proposed']}: `{p['command']}`")
    d = state.get("decision")
    if not d:
        lines.append(f"- {t['awaiting']}")
        return "\n".join(lines) + "\n"
    verdict = t["approved"] if d.get("approved") else t["rejected"]
    note = f" — {d['comment']}" if d.get("comment") else ""
    lines.append(f"- {verdict} {t['by']} `{d.get('by', 'unknown')}`{note}")
    e = state.get("execution")
    if e:
        lines.append(f"- {t['executed']}: {e['output']}" if e.get("ok") else f"- {t['failed']}: {e.get('error')}")
    v = state.get("verification")
    if v:
        if v.get("recovered") is True:
            how = f", {v['method']}" if v.get("method") else ""
            lines.append(f"- {t['recovered']} ({v.get('checked')}, {t['after']} {v.get('after_s')} s{how})")
        elif v.get("recovered") is False:
            lines.append(f"- {t['not_recovered']}: {v.get('detail', '')}")
        else:
            lines.append(f"- {t['unverified']}: {v.get('detail', '')}")
    return "\n".join(lines) + "\n"


def render_report(state, lang: str = "en") -> str:
    if lang == "pl":
        return _render_pl(state)
    return _render_en(state)


def _render_pl(state) -> str:
    alert, d = state["alert"], state["diagnosis"]
    usage = state.get("usage", {})
    steps = [
        f"`{tc['name']}({', '.join(f'{k}={v!r}' for k, v in tc['args'].items())})`"
        for m in state.get("messages", []) if isinstance(m, AIMessage)
        for tc in (m.tool_calls or [])
    ]
    warn = "\n> ⚠️ Budżet wywołań narzędzi wyczerpał się przed końcem śledztwa — diagnoza może być niepełna.\n" \
        if state.get("budget_exhausted") else ""
    evidence = "\n".join(f"- {e}" for e in d.evidence) or "- (brak)"
    trail = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) or "_(agent nie potrzebował dodatkowych narzędzi)_"
    return f"""# Incydent: {alert.name} — {alert.service}

_Wygenerowano: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · tryb: diagnoza (tylko odczyt)_
{warn}
| | |
|---|---|
| **Alert** | {alert.name} ({alert.severity}) — {alert.summary or "brak opisu"} |
| **Winowajca** | `{d.culprit_service}` |
| **Kategoria** | `{d.category}` |
| **Pewność** | {d.confidence:.0%} |
| **Zalecana akcja** | {PL_ACTION_LABELS[d.recommended_action]} → `{d.action_target}` |

## Przyczyna źródłowa
{d.root_cause}

## Dowody
{evidence}

## Uzasadnienie akcji
{d.rationale}
{render_remediation(state, 'pl')}

## Przebieg śledztwa
{trail}

---
Wywołania narzędzi: {state.get("tool_calls_used", 0)} · wywołania LLM: {usage.get("llm_calls", 0)} · \
tokeny: {usage.get("input_tokens", 0)} wej. / {usage.get("output_tokens", 0)} wyj.
"""


def _render_en(state) -> str:
    alert, d = state["alert"], state["diagnosis"]
    usage = state.get("usage", {})
    steps = [
        f"`{tc['name']}({', '.join(f'{k}={v!r}' for k, v in tc['args'].items())})`"
        for m in state.get("messages", []) if isinstance(m, AIMessage)
        for tc in (m.tool_calls or [])
    ]
    warn = "\n> ⚠️ Tool budget exhausted before the investigation finished — the diagnosis may be incomplete.\n" \
        if state.get("budget_exhausted") else ""
    evidence = "\n".join(f"- {e}" for e in d.evidence) or "- (none)"
    trail = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) or "_(the agent needed no additional tools)_"

    return f"""# Incident: {alert.name} — {alert.service}

_Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · mode: diagnosis (read-only)_
{warn}
| | |
|---|---|
| **Alert** | {alert.name} ({alert.severity}) — {alert.summary or "no description"} |
| **Culprit service** | `{d.culprit_service}` |
| **Category** | `{d.category}` |
| **Confidence** | {d.confidence:.0%} |
| **Recommended action** | {ACTION_LABELS[d.recommended_action]} → `{d.action_target}` |

## Root cause
{d.root_cause}

## Evidence
{evidence}

## Action rationale
{d.rationale}
{render_remediation(state, 'en')}

## Investigation trail
{trail}

---
Tool calls: {state.get("tool_calls_used", 0)} · LLM calls: {usage.get("llm_calls", 0)} · \
tokens: {usage.get("input_tokens", 0)} in / {usage.get("output_tokens", 0)} out
"""
