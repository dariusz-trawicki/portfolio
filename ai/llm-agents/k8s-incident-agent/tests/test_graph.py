"""Graph tests without a cluster or a real LLM.

ScriptedLLM replays pre-written model responses and FakeBackend replays
recorded cluster data. We test the graph logic: parallel evidence gathering,
the tool loop, the budget limit, checkpoints.
"""

from __future__ import annotations

import typing
from pathlib import Path

import pytest
import yaml
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from incident_agent.backends.fake import FakeBackend
from incident_agent.backends.live import LiveBackend
from incident_agent.checkpointing import open_checkpointer
from incident_agent.config import Settings
from incident_agent.graph import build_graph
from incident_agent.state import Action, Alert, Category, Diagnosis

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "payment-unreachable-deploy.json"

DIAG = Diagnosis(
    root_cause="Revision 2 of the checkout deployment changed PAYMENT_ADDR to a non-existent host payment-v2.",
    culprit_service="checkout",
    category="config_change",
    confidence=0.9,
    evidence=["revision 2: env PAYMENT_ADDR 'payment:8080' -> 'payment-v2:8080'",
              "log: lookup payment-v2 ... no such host"],
    recommended_action="rollback_deployment",
    action_target="checkout",
    rationale="Rolling back to revision 1 restores the correct address; payment is healthy.",
)


def ai(content: str = "", calls: list[tuple[str, dict]] | None = None) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[{"name": n, "args": a, "id": f"call_{i}"} for i, (n, a) in enumerate(calls or [])],
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )


class ScriptedLLM:
    def __init__(self, turns: list[AIMessage], diagnosis: Diagnosis = DIAG, repeat_last: bool = False):
        self.turns, self.diagnosis, self.repeat_last = list(turns), diagnosis, repeat_last
        self.seen: list[list] = []

    def bind_tools(self, tools):
        def step(messages):
            self.seen.append(messages)
            if self.repeat_last and len(self.turns) == 1:
                t = self.turns[0]
                return ai(t.content, [(c["name"], c["args"]) for c in t.tool_calls])
            return self.turns.pop(0)
        return RunnableLambda(step)

    def with_structured_output(self, schema, include_raw=False):
        return RunnableLambda(lambda _: {"raw": ai("{}"), "parsed": self.diagnosis, "parsing_error": None})


def run(llm, settings=None, checkpointer=None, thread="t1"):
    backend = FakeBackend.from_file(FIXTURE)
    graph = build_graph(backend, llm, settings or Settings(), checkpointer=checkpointer)
    alert = Alert(name="HighErrorRate", service="Checkout ", summary="41% errors")
    cfg = {"configurable": {"thread_id": thread}}
    result = graph.invoke({"alert": alert}, cfg)
    return result, backend, graph, cfg


def test_happy_path_collects_evidence_runs_tools_and_reports():
    llm = ScriptedLLM([
        ai("Hypothesis: payment unavailable or a change in checkout.",
           [("get_service_overview", {"service": "payment"}), ("get_deployment_spec", {"service": "checkout"})]),
        ai("Payment is healthy, checkout calls payment-v2 after the change in revision 2."),
    ])
    result, backend, _, _ = run(llm)

    # triage normalised the service name
    assert result["alert"].service == "checkout"
    # all 4 parallel branches added evidence
    assert set(result["evidence"]) == {
        "golden_signals", "error_breakdown", "pods", "k8s_events",
        "rollout_history", "feature_flags", "error_logs", "dependency_logs",
    }
    assert "payment-v2" in result["evidence"]["rollout_history"]
    # the model got the evidence in its very first call
    assert "payment-v2" in llm.seen[0][1].content
    # tool loop
    assert result["tool_calls_used"] == 2
    assert ("service_overview", ("payment",)) in backend.calls
    assert not result["budget_exhausted"]
    # diagnosis and report
    assert result["diagnosis"].recommended_action == "rollback_deployment"
    assert "`checkout`" in result["report"] and "Roll back deployment" in result["report"]
    assert result["usage"]["llm_calls"] == 3  # 2x investigate + diagnose


def test_budget_limit_stops_runaway_agent():
    looping = ai("Let me check once more.", [("get_pods", {"service": "checkout"})])
    llm = ScriptedLLM([looping], repeat_last=True)
    result, *_ = run(llm, Settings(max_tool_calls=3))
    assert result["tool_calls_used"] == 3
    assert result["budget_exhausted"] is True
    assert "Tool budget exhausted" in result["report"]


def test_bad_tool_calls_do_not_crash_the_graph():
    llm = ScriptedLLM([
        ai("", [("delete_namespace", {"name": "otel-demo"}), ("get_pods", {"wrong_arg": 1}),
                ("get_deployment_spec", {"service": "does-not-exist"})]),
        ai("Done."),
    ])
    result, *_ = run(llm)
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert "no such tool delete_namespace" in tool_msgs[0].content
    assert tool_msgs[1].content.startswith("ERROR")
    assert "not found" in tool_msgs[2].content
    assert result["diagnosis"] is not None


def test_state_survives_restart_via_sqlite_checkpoint(tmp_path):
    db = str(tmp_path / "cp.sqlite")
    llm = ScriptedLLM([ai("That is enough.")])
    with open_checkpointer(db) as cp:
        run(llm, checkpointer=cp, thread="incident-42")
    # a new process: fresh graph, same database
    with open_checkpointer(db) as cp:
        graph = build_graph(FakeBackend({}), ScriptedLLM([]), checkpointer=cp)
        state = graph.get_state({"configurable": {"thread_id": "incident-42"}}).values
    assert state["diagnosis"].culprit_service == "checkout"
    assert state["report"].startswith("# Incident")


def test_rollout_diff_shows_env_and_limit_changes():
    old = {"checkout": {"image": "a:1", "env": {"PAYMENT_ADDR": "payment:8080"}, "limits": {"memory": "20Mi"}, "requests": {}}}
    new = {"checkout": {"image": "a:1", "env": {"PAYMENT_ADDR": "payment-v2:8080"}, "limits": {"memory": "6Mi"}, "requests": {}}}
    diff = LiveBackend._diff(old, new)
    assert "checkout: env PAYMENT_ADDR 'payment:8080' -> 'payment-v2:8080'" in diff
    assert any("limits" in d and "6Mi" in d for d in diff)


def test_scenarios_ground_truth_matches_schema():
    cats, acts = set(typing.get_args(Category)), set(typing.get_args(Action))
    scenarios = yaml.safe_load((ROOT / "scenarios" / "scenarios.yaml").read_text())["scenarios"]
    assert len({s["id"] for s in scenarios}) == len(scenarios)
    for s in scenarios:
        assert set(s["expected"]["category"]) <= cats, s["id"]
        assert set(s["expected"]["action"]) <= acts, s["id"]
        if s["inject"]["type"] == "k8s":
            assert s["inject"]["cmd"][0] == "kubectl"


@pytest.mark.parametrize("flag", ["paymentFailure", "cartFailure", "recommendationCacheFailure"])
def test_flag_scenarios_reference_real_demo_flags(flag):
    scenarios = yaml.safe_load((ROOT / "scenarios" / "scenarios.yaml").read_text())["scenarios"]
    assert flag in {s["inject"].get("flag") for s in scenarios}


def test_polish_language_report_and_prompt():
    from incident_agent.config import Settings as S
    llm = ScriptedLLM([ai("That is enough.")])
    result, *_ = run(llm, S(language="pl"))
    assert "LANGUAGE: write all free text" in llm.seen[0][0].content       # the prompt asks for Polish
    assert result["report"].startswith("# Incydent:") and "Wycofaj wdrożenie" in result["report"]
    assert result["diagnosis"].category == "config_change"                 # enums stay in English
