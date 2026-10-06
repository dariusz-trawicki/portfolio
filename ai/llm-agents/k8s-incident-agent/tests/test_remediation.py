"""Remediation (step 5) without a cluster or a real LLM: propose -> interrupt -> human -> execute -> verify."""

from __future__ import annotations

import pytest
from langgraph.types import Command

from incident_agent import remediation as rem
from incident_agent.backends.fake import FakeBackend
from incident_agent.checkpointing import open_checkpointer
from incident_agent.graph import build_graph
from incident_agent.state import Alert
from test_graph import DIAG, FIXTURE, ScriptedLLM, ai

ALERT = Alert(name="HighErrorRate", service="checkout", severity="critical")


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


# ---------------------------------------------------------------- propose
def test_propose_automated_action_with_enough_confidence():
    p = rem.propose(DIAG, rem.DryRunExecutor())
    assert p.executable and p.action == "rollback_deployment" and p.target == "checkout"
    assert "rollout undo deployment/checkout" in p.command


def test_low_confidence_is_never_proposed_for_automation():
    p = rem.propose(DIAG.model_copy(update={"confidence": 0.35}), rem.DryRunExecutor())
    assert not p.executable and "below" in p.reason


@pytest.mark.parametrize("action", ["increase_resources", "restart_pods", "scale_up", "escalate_to_human", "none"])
def test_non_automated_actions_are_manual_follow_ups(action):
    p = rem.propose(DIAG.model_copy(update={"recommended_action": action}), rem.DryRunExecutor())
    assert not p.executable and "not automated" in p.reason


def test_rollback_target_must_be_an_application_service():
    class Backend:
        def rollout_history(self, s):
            return [{"revision": "1"}, {"revision": "2"}]

    ex = rem.LiveExecutor("otel-demo", Backend())
    assert ex.validate("rollback_deployment", "checkout")[0]
    ok, why = ex.validate("rollback_deployment", "prometheus")
    assert not ok and "not an application deployment" in why


def test_rollback_needs_a_previous_revision():
    class Backend:
        def rollout_history(self, s):
            return [{"revision": "1"}]

    ok, why = rem.LiveExecutor("otel-demo", Backend()).validate("rollback_deployment", "checkout")
    assert not ok and "no previous revision" in why


def test_flag_validation_reads_definitions_and_refuses_protected_or_off_flags(monkeypatch):
    import incident_agent.chaos as chaos

    flags = {"flags": {
        "paymentFailure": {"defaultVariant": "50%", "variants": {"off": 0, "50%": 0.5}},
        "cartFailure": {"defaultVariant": "off", "variants": {"off": False, "on": True}},
        "loadGeneratorFloodHomepage": {"defaultVariant": "on", "variants": {"off": 0, "on": 100}},
    }}
    monkeypatch.setattr(chaos, "read_flags", lambda ns: flags)
    ex = rem.LiveExecutor("otel-demo", backend=None)
    assert ex.validate("disable_feature_flag", "paymentFailure")[0]
    assert "already off" in ex.validate("disable_feature_flag", "cartFailure")[1]
    assert "protected" in ex.validate("disable_feature_flag", "loadGeneratorFloodHomepage")[1]
    assert "unknown" in ex.validate("disable_feature_flag", "nope")[1]


def test_live_executor_revalidates_right_before_acting(monkeypatch):
    import incident_agent.chaos as chaos

    monkeypatch.setattr(chaos, "read_flags", lambda ns: {"flags": {"paymentFailure": {"defaultVariant": "off",
                                                                                      "variants": {"off": 0}}}})
    with pytest.raises(RuntimeError, match="refused: flag 'paymentFailure' is already off"):
        rem.LiveExecutor("otel-demo", backend=None).execute("disable_feature_flag", "paymentFailure")


# ---------------------------------------------------------------- verification
def test_verify_recovery_waits_until_the_alert_is_gone():
    clock, polls = Clock(), {"n": 0}

    def firing():
        polls["n"] += 1
        return [{"state": "firing", "name": "HighErrorRate", "service": "checkout"}] if polls["n"] <= 3 else []

    out = rem.verify_recovery(firing, ALERT, timeout_s=600, poll_s=30, sleep=clock.sleep, clock=clock.now)
    assert out["recovered"] is True and out["after_s"] == 90


def test_verify_recovery_times_out_and_asks_for_escalation():
    clock = Clock()
    stuck = lambda: [{"state": "firing", "name": "HighErrorRate", "service": "checkout"}]  # noqa: E731
    out = rem.verify_recovery(stuck, ALERT, timeout_s=120, poll_s=30, sleep=clock.sleep, clock=clock.now)
    assert out["recovered"] is False and "escalate" in out["detail"]


def test_other_alerts_do_not_block_verification():
    clock = Clock()
    other = lambda: [{"state": "firing", "name": "MemoryGrowth", "service": "email"}]  # noqa: E731
    assert rem.verify_recovery(other, ALERT, sleep=clock.sleep, clock=clock.now)["recovered"] is True


# ---------------------------------------------------------------- the graph
def remediation_run(tmp_path, decision, verify_result=None):
    executor = rem.DryRunExecutor()
    verified = []

    def verify(alert):
        verified.append(alert.service)
        return verify_result or {"recovered": True, "after_s": 240.0, "checked": "HighErrorRate · checkout"}

    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("That is enough.")]), checkpointer=cp,
                            remediation=rem.Remediation(executor, verify))
        cfg = {"configurable": {"thread_id": "inc-1"}}
        first = graph.invoke({"alert": ALERT.model_copy()}, cfg)
        paused = graph.get_state(cfg)
        final = graph.invoke(Command(resume=decision), cfg) if decision is not None else None
    return first, paused, final, executor, verified


def test_graph_pauses_for_a_human_before_doing_anything(tmp_path):
    first, paused, _, executor, verified = remediation_run(tmp_path, decision=None)
    assert "__interrupt__" in first
    [intr] = paused.interrupts
    assert intr.value["proposal"]["action"] == "rollback_deployment"
    assert paused.next == ("approve",)
    assert executor.executed == [] and verified == []          # nothing happened without approval


def test_approved_fix_is_executed_verified_and_reported(tmp_path):
    _, _, final, executor, verified = remediation_run(
        tmp_path, rem.make_decision(True, by="dartit", comment="go"))
    assert executor.executed == [("rollback_deployment", "checkout")]
    assert verified == ["checkout"]
    assert final["verification"]["recovered"] is True
    assert "## Remediation" in final["report"]
    assert "Approved by `dartit` — go" in final["report"] and "Verified: the alert is gone" in final["report"]


def test_rejected_fix_is_not_executed(tmp_path):
    _, _, final, executor, verified = remediation_run(tmp_path, rem.make_decision(False, by="dartit"))
    assert executor.executed == [] and verified == []
    assert "Rejected by `dartit`" in final["report"] and "execution" not in final


def test_not_automatable_diagnosis_goes_straight_to_the_report(tmp_path):
    llm = ScriptedLLM([ai("That is enough.")], diagnosis=DIAG.model_copy(update={"recommended_action": "scale_up"}))
    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), llm, checkpointer=cp,
                            remediation=rem.dry_run_remediation())
        out = graph.invoke({"alert": ALERT.model_copy()}, {"configurable": {"thread_id": "x"}})
    assert "__interrupt__" not in out
    assert "Not automated: `scale_up`" in out["report"]


def test_failed_execution_skips_verification_and_is_reported(tmp_path):
    class Broken(rem.DryRunExecutor):
        def execute(self, action, target):
            raise RuntimeError("kubectl: connection refused")

    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("ok")]), checkpointer=cp,
                            remediation=rem.Remediation(Broken(), lambda a: pytest.fail("must not verify")))
        cfg = {"configurable": {"thread_id": "y"}}
        graph.invoke({"alert": ALERT.model_copy()}, cfg)
        out = graph.invoke(Command(resume=rem.make_decision(True, by="me")), cfg)
    assert out["execution"]["ok"] is False and "Execution failed" in out["report"]


def test_remediation_branch_requires_a_checkpointer():
    with pytest.raises(ValueError, match="checkpointer"):
        build_graph(FakeBackend({}), ScriptedLLM([]), remediation=rem.dry_run_remediation())


def test_polish_report_has_a_polish_remediation_section(tmp_path):
    from incident_agent.config import Settings

    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("ok")]), Settings(language="pl"),
                            checkpointer=cp, remediation=rem.dry_run_remediation())
        cfg = {"configurable": {"thread_id": "pl"}}
        graph.invoke({"alert": ALERT.model_copy()}, cfg)
        out = graph.invoke(Command(resume=rem.make_decision(False, by="ja")), cfg)
    assert "## Naprawa" in out["report"] and "Odrzucona przez `ja`" in out["report"]


# ---------------------------------------------------------------- webhook server: approve / reject
def approval_server(tmp_path, token=None):
    from fastapi.testclient import TestClient

    from incident_agent.config import Settings
    from incident_agent.incidents import IncidentRegistry
    from incident_agent.server import IncidentService, create_app, graph_investigator

    executor = rem.DryRunExecutor()
    remediation = rem.Remediation(executor, lambda a: {"recovered": True, "after_s": 300.0, "checked": "x"})
    investigator = graph_investigator(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("That is enough.")]),
                                      Settings(checkpoint_db=str(tmp_path / "cp.sqlite")), remediation)
    service = IncidentService(IncidentRegistry(30), investigator, tmp_path / "out")
    return service, TestClient(create_app(service, token)), executor


def payload():
    import json
    from pathlib import Path

    return json.loads((Path(__file__).parent / "fixtures" / "alertmanager-firing.json").read_text())


def metric(client, prefix):
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(prefix):
            return float(line.split()[-1])
    return None


def test_server_waits_for_approval_then_executes_and_verifies(tmp_path):
    service, client, executor = approval_server(tmp_path)
    with client:
        client.post("/alertmanager", json=payload())
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "awaiting_approval" and inc["awaiting_since"]
        assert inc["proposal"]["executable"] and inc["proposal"]["action"] == "rollback_deployment"
        assert "Awaiting human approval" in client.get(f"/incidents/{inc['id']}").json()["report"]
        assert executor.executed == []                                          # nothing done yet
        assert metric(client, "incident_agent_awaiting_approval") == 1.0

        # Alertmanager keeps re-sending while we wait: still one incident, no second investigation
        assert {d["decision"] for d in client.post("/alertmanager", json=payload()).json()["decisions"]} == {"duplicate"}

        r = client.post(f"/incidents/{inc['id']}/approve", json={"by": "dartit", "comment": "go"})
        assert r.status_code == 200 and r.json()["decision"]["approved"] is True
        assert service.wait_idle(30)
        done = client.get(f"/incidents/{inc['id']}").json()
        assert done["status"] == "done"
        assert done["execution"]["ok"] and done["verification"]["recovered"] is True
        assert "Approved by `dartit` — go" in done["report"]
        assert executor.executed == [("rollback_deployment", "checkout")]
        assert metric(client, 'incident_agent_remediations_total{action="rollback_deployment",outcome="recovered"}') == 1.0
        assert metric(client, "incident_agent_time_to_recover_seconds_count") == 1.0
        assert metric(client, "incident_agent_awaiting_approval") == 0.0

        # a decision is accepted exactly once
        assert client.post(f"/incidents/{inc['id']}/approve", json={}).status_code == 409


def test_server_reject_changes_nothing(tmp_path):
    service, client, executor = approval_server(tmp_path)
    with client:
        client.post("/alertmanager", json=payload())
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        assert client.post(f"/incidents/{inc['id']}/reject", json={"by": "dartit"}).status_code == 200
        assert service.wait_idle(30)
        done = client.get(f"/incidents/{inc['id']}").json()
        assert done["status"] == "done" and done["decision"]["approved"] is False and done["execution"] is None
        assert executor.executed == []


def test_approval_endpoints_404_401_and_no_remediation(tmp_path):
    from fastapi.testclient import TestClient

    from incident_agent.incidents import IncidentRegistry
    from incident_agent.server import IncidentService, create_app, dry_run_investigator

    service, client, _ = approval_server(tmp_path, token="s3cret")
    with client:
        assert client.post("/incidents/nope/approve").status_code == 401
        assert client.post("/incidents/nope/approve", json={}, headers={"Authorization": "Bearer s3cret"}).status_code == 404

    plain = IncidentService(IncidentRegistry(30), dry_run_investigator, tmp_path / "o2")
    with TestClient(create_app(plain)) as c:
        c.post("/alertmanager", json=payload())
        assert plain.wait_idle()
        [inc] = c.get("/incidents").json()
        r = c.post(f"/incidents/{inc['id']}/approve", json={})
        assert r.status_code == 409 and "without remediation" in r.json()["detail"]


# ---------------------------------------------------------------- CLI
def test_cli_approve_calls_the_running_agent(monkeypatch):
    import httpx
    from typer.testing import CliRunner

    import incident_agent.cli as cli

    seen = {}

    def post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, body=json)
        return httpx.Response(200, json={"status": "remediating"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setenv("WEBHOOK_TOKEN", "tok")
    r = CliRunner().invoke(cli.app, ["approve", "checkout-123", "--by", "dartit", "--comment", "ok"])
    assert r.exit_code == 0, r.output
    assert seen["url"] == "http://localhost:8787/incidents/checkout-123/approve"
    assert seen["headers"] == {"Authorization": "Bearer tok"} and seen["body"] == {"by": "dartit", "comment": "ok"}


def test_cli_reject_reports_a_conflict(monkeypatch):
    import httpx
    from typer.testing import CliRunner

    import incident_agent.cli as cli

    monkeypatch.setattr(httpx, "post", lambda url, **k: httpx.Response(
        409, json={"detail": "incident x is 'done', not awaiting approval"}, request=httpx.Request("POST", url)))
    r = CliRunner().invoke(cli.app, ["reject", "x"])
    assert r.exit_code == 1 and "not awaiting approval" in r.output


@pytest.mark.parametrize("answer, expected", [("y\nlooks right\n", "Approved by"), ("n\n\n", "Rejected by")])
def test_cli_investigate_remediate_asks_before_acting(tmp_path, monkeypatch, answer, expected):
    from typer.testing import CliRunner

    import incident_agent.cli as cli

    monkeypatch.setenv("CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setattr(cli, "_llm", lambda s: ScriptedLLM([ai("That is enough.")]))
    r = CliRunner().invoke(cli.app, ["investigate", "--backend", "fake", "--fixture", str(FIXTURE),
                                     "--out-dir", str(tmp_path), "--remediate"], input=answer)
    assert r.exit_code == 0, r.output
    assert "Proposed fix — nothing has been changed yet" in r.output
    report = next(tmp_path.glob("*-checkout.md")).read_text()
    assert expected in report
    assert ("[dry run] would rollback_deployment checkout" in report) == answer.startswith("y")


def test_live_executor_runs_exactly_rollout_undo_and_waits_for_the_rollout(monkeypatch):
    """The only code that changes the cluster: check the exact commands."""
    import incident_agent.chaos as chaos

    calls = []
    monkeypatch.setattr(chaos, "_kubectl", lambda args, ns, stdin=None: calls.append((args, ns)) or
                        ("deployment.apps/checkout rolled back" if args[1] == "undo" else
                         "Waiting...\ndeployment \"checkout\" successfully rolled out"))

    class Backend:
        def rollout_history(self, s):
            return [{"revision": "4"}, {"revision": "5"}]

    out = rem.LiveExecutor("otel-demo", Backend()).execute("rollback_deployment", "checkout")
    assert calls == [(["rollout", "undo", "deployment/checkout"], "otel-demo"),
                     (["rollout", "status", "deployment/checkout", "--timeout=180s"], "otel-demo")]
    assert "rolled back" in out and "successfully rolled out" in out


def test_live_executor_disables_a_flag_through_chaos_set_flag(monkeypatch):
    import incident_agent.chaos as chaos

    monkeypatch.setattr(chaos, "read_flags", lambda ns: {"flags": {"paymentFailure": {
        "defaultVariant": "50%", "variants": {"off": 0, "50%": 0.5}}}})
    calls = []
    monkeypatch.setattr(chaos, "set_flag", lambda ns, flag, variant: calls.append((ns, flag, variant)))
    out = rem.LiveExecutor("otel-demo", backend=None).execute("disable_feature_flag", "paymentFailure")
    assert calls == [("otel-demo", "paymentFailure", "off")] and "off" in out


# ---------------------------------------------------------------- 5b: fast verification probe
def test_fast_probe_queries_match_alert_types():
    q, thr = rem.fast_probe_query(Alert(name="HighErrorRate", service="checkout"))
    assert 'service_name="checkout"' in q and "[2m]" in q and thr == 0.05
    q, _ = rem.fast_probe_query(Alert(name="HighOperationErrorRate", service="cart",
                                      labels={"span_name": "oteldemo.CartService/EmptyCart"}))
    assert 'span_name="oteldemo.CartService/EmptyCart"' in q
    q, thr = rem.fast_probe_query(Alert(name="KafkaConsumerLag", service="fraud-detection"))
    assert 'group="fraud-detection"' in q and thr == 100
    assert rem.fast_probe_query(Alert(name="PodRestarting", service="currency")) is None   # falls back to the alert
    q, _ = rem.fast_probe_query(Alert(name="HighErrorRate", service='x"} or vector(1) #'))
    assert '"} or' not in q                                                                  # no PromQL injection


def test_probe_needs_consecutive_healthy_readings_and_ignores_no_data():
    clock = Clock()
    readings = iter([True, None, True, True, False, True, True, True])
    stuck = lambda: [{"state": "firing", "name": "HighErrorRate", "service": "checkout"}]  # noqa: E731
    out = rem.verify_recovery(stuck, ALERT, poll_s=20, probe=lambda: next(readings),
                              sleep=clock.sleep, clock=clock.now)
    assert out["recovered"] is True and out["method"].startswith("metric")
    assert out["after_s"] == 140          # 8th reading = 7 sleeps of 20 s; None and False reset the streak


def test_make_probe_reads_prometheus_and_treats_errors_as_no_data():
    probe = rem.make_probe(lambda q: [{"labels": {}, "value": "0.01"}], ALERT)
    assert probe() is True
    assert rem.make_probe(lambda q: [{"labels": {}, "value": "0.4"}], ALERT)() is False
    assert rem.make_probe(lambda q: [], ALERT)() is None
    assert rem.make_probe(lambda q: [{"labels": {}, "value": "NaN"}], ALERT)() is None

    def down(q):
        raise ConnectionError("port-forward down")

    assert rem.make_probe(down, ALERT)() is None


def test_alert_clearing_still_counts_without_a_probe():
    clock = Clock()
    out = rem.verify_recovery(lambda: [], ALERT, sleep=clock.sleep, clock=clock.now)
    assert out["recovered"] is True and out["method"] == "alert cleared"


# ---------------------------------------------------------------- 5b: approval page + CSRF guard
def test_index_serves_the_approval_page_with_safe_headers(tmp_path):
    _, client, _ = approval_server(tmp_path)
    with client:
        r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Approve fix" in r.text and "/incidents" in r.text
    assert "innerHTML" not in r.text                          # agent/LLM text is only ever inserted as text
    assert r.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_decisions_must_be_json_so_a_foreign_page_cannot_forge_them(tmp_path):
    service, client, executor = approval_server(tmp_path)
    with client:
        client.post("/alertmanager", json=payload())
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        forged = client.post(f"/incidents/{inc['id']}/approve", content="by=attacker",
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert forged.status_code == 415
        assert client.post(f"/incidents/{inc['id']}/approve", content="{}",
                           headers={"Content-Type": "text/plain"}).status_code == 415
        assert client.get("/incidents").json()[0]["status"] == "awaiting_approval"
        assert executor.executed == []
        summary = client.get("/incidents").json()[0]
        assert summary["root_cause"] and summary["confidence"] == 0.9
