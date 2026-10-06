"""Incident agent graph: diagnosis (step 2) and an optional, human-approved remediation branch (step 5).

    START
      │
    triage
      │  (fan-out: 4 parallel, deterministic nodes, no LLM)
      ├── gather_metrics ──┐
      ├── gather_k8s ──────┤
      ├── gather_changes ──┤
      └── gather_logs ─────┤
                           ▼
                      investigate  ◄──────┐   ReAct loop with a hard
                           │              │   tool-call budget
                   route ──┼── tools ─────┘
                           ▼
                        diagnose   (structured output -> Diagnosis)
                           │
              [only when built with `remediation=`]
                        propose ── not automatable ──┐
                           │                          │
                        approve   interrupt(): waits for a human
                           │  rejected ───────────────┤
                        execute   allow-listed executor, not the LLM
                           │                          │
                        verify    did the alert go away? │
                           ▼                          ▼
                         report ◄─────────────────────┘
                           │
                          END

Why this shape:
- Cheap, reliable data is collected by code, in parallel. The LLM gets it up front,
  so it does not burn tokens on obvious queries.
- The LLM decides only where reasoning is needed: what to check next.
- The diagnosis is structured, so it can be scored automatically.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .backends import Backend
from .config import Settings
from .prompts import DIAGNOSIS_SYSTEM, dependencies, INVESTIGATION_KICKOFF, INVESTIGATOR_SYSTEM, language_note
from .report import render_report
from .state import Diagnosis, IncidentState
from .tools import build_tools, to_text


def _text(msg: AnyMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def _usage(msg: Any) -> dict[str, int]:
    meta = getattr(msg, "usage_metadata", None) or {}
    return {
        "llm_calls": 1,
        "input_tokens": meta.get("input_tokens", 0),
        "output_tokens": meta.get("output_tokens", 0),
    }


def render_transcript(messages: list[AnyMessage], max_chars: int) -> str:
    lines = []
    for m in messages:
        if isinstance(m, (SystemMessage, HumanMessage)):
            continue
        if isinstance(m, AIMessage):
            if txt := _text(m).strip():
                lines.append(f"[agent] {txt}")
            for tc in m.tool_calls or []:
                lines.append(f"[call] {tc['name']}({to_text(tc['args'], 300)})")
        elif isinstance(m, ToolMessage):
            lines.append(f"[result {m.name}] {str(m.content)[:max_chars]}")
    return "\n".join(lines)


DEP_LOG_GROUPS = 3  # max collapsed log groups per dependency


def build_graph(backend: Backend, llm, settings: Settings | None = None, checkpointer=None, remediation=None):
    """`remediation` (a remediation.Remediation) adds propose -> approve -> execute -> verify.
    That branch uses `interrupt()`, so it needs a checkpointer."""
    if remediation is not None and checkpointer is None:
        raise ValueError("the remediation branch needs a checkpointer (interrupt() persists state)")
    s = settings or Settings()
    tools = build_tools(backend, s.max_tool_output_chars)
    tools_by_name = {t.name: t for t in tools}
    investigator = llm.bind_tools(tools)
    diagnoser = llm.with_structured_output(Diagnosis, include_raw=True)

    def call(tool_name: str, **args) -> str:
        return tools_by_name[tool_name].invoke(args)

    # ---------------------------------------------------------------- nodes
    def triage(state: IncidentState) -> dict:
        alert = state["alert"]
        alert.service = alert.service.strip().lower()
        return {"alert": alert, "tool_calls_used": 0, "budget_exhausted": False}

    def gather_metrics(state: IncidentState) -> dict:
        svc = state["alert"].service
        return {"evidence": {
            "golden_signals": call("get_service_overview", service=svc),
            "error_breakdown": call("get_error_breakdown", service=svc),
        }}

    def gather_k8s(state: IncidentState) -> dict:
        svc = state["alert"].service
        return {"evidence": {
            "pods": call("get_pods", service=svc),
            "k8s_events": call("get_k8s_events", service=svc),
        }}

    def gather_changes(state: IncidentState) -> dict:
        svc = state["alert"].service
        return {"evidence": {
            "rollout_history": call("get_rollout_history", service=svc),
            "feature_flags": call("get_feature_flags"),
        }}

    def gather_logs(state: IncidentState) -> dict:
        svc = state["alert"].service
        # The alerting service is often just a victim; the cause is frequently in its dependencies' logs
        # (e.g. checkout -> payment). Collect them up front, at no LLM cost.
        deps, errors, quiet = {}, [], []
        for dep in dependencies(svc):
            try:
                found = backend.search_logs(dep, "", 15)
            except Exception as e:
                errors.append(f"{dep}: {type(e).__name__}")
                continue
            if found:
                deps[dep] = found[:DEP_LOG_GROUPS]
            else:
                quiet.append(dep)
        summary = {"with_errors": deps, "no_error_logs": quiet}
        if errors:
            summary["lookup_failed"] = errors
        return {"evidence": {
            "error_logs": call("search_logs", service=svc, text="", minutes=15),
            "dependency_logs": to_text(summary, s.max_tool_output_chars),
        }}

    def investigate(state: IncidentState) -> dict:
        history = state.get("messages") or []
        new: list[AnyMessage] = []
        if not history:
            evidence = "\n".join(f"## {k}\n{v}" for k, v in sorted(state["evidence"].items()))
            new = [
                SystemMessage(INVESTIGATOR_SYSTEM + language_note(s.language)),
                HumanMessage(INVESTIGATION_KICKOFF.format(
                    alert=state["alert"].model_dump_json(indent=2), evidence=evidence,
                )),
            ]
        response = investigator.invoke(history + new)
        return {"messages": new + [response], "usage": _usage(response)}

    def route(state: IncidentState) -> str:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        if not calls:
            return "diagnose"
        if state.get("tool_calls_used", 0) + len(calls) > s.max_tool_calls:
            return "diagnose"
        return "tools"

    def run_tools(state: IncidentState) -> dict:
        last = state["messages"][-1]
        results = []
        for tc in last.tool_calls:
            tool = tools_by_name.get(tc["name"])
            if tool is None:
                content = f"ERROR: no such tool {tc['name']}. Available: {sorted(tools_by_name)}"
            else:
                try:
                    content = tool.invoke(tc["args"])
                except Exception as e:  # e.g. invalid arguments generated by the model
                    content = f"ERROR {type(e).__name__}: {e}"[:500]
            results.append(ToolMessage(content=content, tool_call_id=tc["id"], name=tc["name"]))
        return {"messages": results, "tool_calls_used": state.get("tool_calls_used", 0) + len(results)}

    def diagnose(state: IncidentState) -> dict:
        last = state["messages"][-1]
        exhausted = bool(getattr(last, "tool_calls", None))
        evidence = "\n".join(f"## {k}\n{v}" for k, v in sorted(state["evidence"].items()))
        note = "\nNOTE: the tool-call budget ran out before the investigation finished." if exhausted else ""
        out = diagnoser.invoke([
            SystemMessage(DIAGNOSIS_SYSTEM + language_note(s.language)),
            HumanMessage(
                f"ALERT\n{state['alert'].model_dump_json(indent=2)}\n\n"
                f"AUTOMATICALLY COLLECTED EVIDENCE\n{evidence}\n\n"
                f"INVESTIGATION TRANSCRIPT\n{render_transcript(state['messages'], s.max_tool_output_chars)}{note}"
            ),
        ])
        if out.get("parsing_error") or out.get("parsed") is None:
            raise ValueError(f"The model did not return a valid diagnosis: {out.get('parsing_error')}")
        return {"diagnosis": out["parsed"], "budget_exhausted": exhausted, "usage": _usage(out["raw"])}

    def report(state: IncidentState) -> dict:
        return {"report": render_report(state, s.language)}

    # ---------------------------------------------------------------- remediation (step 5)
    def propose_fix(state: IncidentState) -> dict:
        from .remediation import propose

        p = propose(state["diagnosis"], remediation.executor, remediation.min_confidence)
        return {"proposal": p.to_dict()}

    def approve(state: IncidentState) -> dict:
        # Pauses the graph; the checkpoint keeps everything until a human answers (minutes or hours).
        # On resume this node runs again from the top and interrupt() returns the human's answer.
        answer = interrupt({"type": "approval", "alert": state["alert"].model_dump(),
                            "diagnosis": state["diagnosis"].model_dump(), "proposal": state["proposal"]})
        if not isinstance(answer, dict):
            answer = {"approved": bool(answer)}
        return {"decision": {"approved": bool(answer.get("approved")), "by": answer.get("by", "unknown"),
                             "comment": answer.get("comment", ""), "at": answer.get("at", "")}}

    def execute_fix(state: IncidentState) -> dict:
        p = state["proposal"]
        try:
            out = remediation.executor.execute(p["action"], p["target"])
            if isinstance(out, dict):          # GitOps executor: {"output": ..., "pr": {...}}
                return {"execution": {"ok": True, **out}}
            return {"execution": {"ok": True, "output": out}}
        except Exception as e:  # a failed fix is reported, never retried blindly
            return {"execution": {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}}

    def verify_fix(state: IncidentState) -> dict:
        pr = (state.get("execution") or {}).get("pr")
        if pr and remediation.await_merge:     # second human gate: wait for the merge, then watch the recovery
            merge = remediation.await_merge(pr)
            if not merge.get("merged"):
                return {"verification": {"recovered": False, "after_s": merge.get("after_s", 0.0),
                                         "checked": f"PR #{pr['number']}", "detail": merge.get("detail", "PR not merged")}}
            return {"verification": {**remediation.verify(state["alert"]), "merge_wait_s": merge.get("after_s", 0.0)}}
        return {"verification": remediation.verify(state["alert"])}

    def after_propose(state: IncidentState) -> str:
        return "approve" if state["proposal"]["executable"] else "report"

    def after_approve(state: IncidentState) -> str:
        return "execute" if state["decision"]["approved"] else "report"

    def after_execute(state: IncidentState) -> str:
        return "verify" if state["execution"]["ok"] else "report"

    # ---------------------------------------------------------------- graph
    g = StateGraph(IncidentState)
    for name, fn in [
        ("triage", triage), ("gather_metrics", gather_metrics), ("gather_k8s", gather_k8s),
        ("gather_changes", gather_changes), ("gather_logs", gather_logs),
        ("investigate", investigate), ("tools", run_tools), ("diagnose", diagnose), ("report", report),
    ]:
        g.add_node(name, fn)

    gatherers = ["gather_metrics", "gather_k8s", "gather_changes", "gather_logs"]
    g.add_edge(START, "triage")
    for n in gatherers:
        g.add_edge("triage", n)
    g.add_edge(gatherers, "investigate")  # waits for all 4 branches
    g.add_conditional_edges("investigate", route, {"tools": "tools", "diagnose": "diagnose"})
    g.add_edge("tools", "investigate")
    if remediation is None:
        g.add_edge("diagnose", "report")
    else:
        for name, fn in [("propose", propose_fix), ("approve", approve), ("execute", execute_fix), ("verify", verify_fix)]:
            g.add_node(name, fn)
        g.add_edge("diagnose", "propose")
        g.add_conditional_edges("propose", after_propose, {"approve": "approve", "report": "report"})
        g.add_conditional_edges("approve", after_approve, {"execute": "execute", "report": "report"})
        g.add_conditional_edges("execute", after_execute, {"verify": "verify", "report": "report"})
        g.add_edge("verify", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)
