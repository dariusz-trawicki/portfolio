"""Webhook end-to-end without a cluster or LLM: FastAPI TestClient + background worker + fake investigator.

One test runs the real graph (ScriptedLLM + FakeBackend) to check the whole path
Alertmanager -> queue -> LangGraph -> report -> checkpoint.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from incident_agent.backends.fake import FakeBackend
from incident_agent.config import Settings
from incident_agent.incidents import IncidentRegistry
from incident_agent.server import IncidentService, create_app, dry_run_investigator, graph_investigator
from test_graph import FIXTURE, ScriptedLLM, ai

PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "alertmanager-firing.json").read_text())

RESULT = {"diagnosis": {"culprit_service": "payment", "category": "feature_flag", "root_cause": "r",
                        "recommended_action": "disable_feature_flag"},
          "report": "# Incident: HighErrorRate — checkout\n", "tool_calls": 2,
          "usage": {"llm_calls": 3, "input_tokens": 1000, "output_tokens": 200}, "budget_exhausted": False}


def make(tmp_path, investigator, token=None):
    service = IncidentService(IncidentRegistry(30), investigator, tmp_path / "out")
    return service, TestClient(create_app(service, token))


def metric(client, line_prefix):
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(line_prefix):
            return float(line.split()[-1])
    return None


def test_alerts_are_deduplicated_and_investigated_once(tmp_path):
    seen = []
    service, client = make(tmp_path, lambda iid, alert: seen.append((iid, alert.name, alert.service)) or RESULT)
    with client:
        r1 = client.post("/alertmanager", json=PAYLOAD)
        assert r1.status_code == 200
        kinds = [d["decision"] for d in r1.json()["decisions"]]
        assert kinds == ["new", "correlated"]                       # checkout = new, payment = neighbour
        assert service.wait_idle()

        r2 = client.post("/alertmanager", json=PAYLOAD)             # Alertmanager repeats the notification
        assert [d["decision"] for d in r2.json()["decisions"]] == ["duplicate", "duplicate"]
        assert service.wait_idle()

        assert len(seen) == 1 and seen[0][1:] == ("HighErrorRate", "checkout")
        assert metric(client, 'incident_agent_alerts_received_total{decision="new"}') == 1.0
        assert metric(client, 'incident_agent_alerts_received_total{decision="duplicate"}') == 2.0
        assert metric(client, 'incident_agent_investigations_total{status="done"}') == 1.0
        assert metric(client, 'incident_agent_llm_tokens_total{direction="input"}') == 1000.0
        assert metric(client, "incident_agent_tool_calls_total") == 2.0

        [inc] = client.get("/incidents").json()
        assert inc["status"] == "done" and inc["culprit_service"] == "payment"
        assert {a["role"] for a in inc["alerts"]} == {"primary", "correlated"}
        detail = client.get(f"/incidents/{inc['id']}").json()
        assert detail["report"].startswith("# Incident")
        assert (tmp_path / "out" / f"{inc['id']}.md").exists()
        assert json.loads((tmp_path / "out" / f"{inc['id']}.json").read_text())["culprit_service"] == "payment"


def test_resolved_before_worker_starts_is_skipped_without_calling_the_investigator(tmp_path):
    gate, calls = threading.Event(), []
    service, client = make(tmp_path, lambda iid, alert: calls.append(iid) or RESULT)
    # the worker is not running yet (start() happens in lifespan), so the alert waits in the queue
    r = client.post("/alertmanager", json=PAYLOAD)
    assert r.status_code == 200
    resolved = copy.deepcopy(PAYLOAD)
    for a in resolved["alerts"]:
        a["status"] = "resolved"
    assert [d["decision"] for d in client.post("/alertmanager", json=resolved).json()["decisions"]] == ["resolved"] * 2
    with client:                                                    # now the worker starts
        assert service.wait_idle()
    assert calls == []
    assert client.get("/incidents").json()[0]["status"] == "skipped"
    gate.set()


def test_investigator_failure_is_recorded_and_worker_survives(tmp_path):
    def flaky(iid, alert):
        if alert.service == "checkout":
            raise RuntimeError("model API down")
        return RESULT

    service, client = make(tmp_path, flaky)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle()
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "failed"
        assert "model API down" in inc["error"] and f"--resume {inc['id']}" in inc["error"]
        assert metric(client, 'incident_agent_investigations_total{status="failed"}') == 1.0

        # an unrelated incident is still investigated after the failure
        other = copy.deepcopy(PAYLOAD)
        other["alerts"] = [{"status": "firing", "fingerprint": "zzz",
                            "labels": {"alertname": "MemoryGrowth", "service": "recommendation"}}]
        client.post("/alertmanager", json=other)
        assert service.wait_idle()
        assert {i["status"] for i in client.get("/incidents").json()} == {"failed", "done"}


def test_bad_payloads_get_400_and_nothing_is_registered(tmp_path):
    service, client = make(tmp_path, dry_run_investigator)
    with client:
        assert client.post("/alertmanager", json={"nope": 1}).status_code == 400
        assert client.post("/alertmanager", content=b"not json",
                           headers={"content-type": "application/json"}).status_code == 400
        assert client.get("/incidents").json() == []


def test_bearer_token_protects_webhook_and_incident_list_but_not_health_and_metrics(tmp_path):
    service, client = make(tmp_path, dry_run_investigator, token="s3cret")
    with client:
        assert client.post("/alertmanager", json=PAYLOAD).status_code == 401
        assert client.post("/alertmanager", json=PAYLOAD, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/incidents").status_code == 401
        ok = {"Authorization": "Bearer s3cret"}
        assert client.post("/alertmanager", json=PAYLOAD, headers=ok).status_code == 200
        assert client.get("/incidents", headers=ok).status_code == 200
        assert client.get("/healthz").status_code == 200
        assert client.get("/metrics").status_code == 200


def test_unknown_incident_is_404(tmp_path):
    _, client = make(tmp_path, dry_run_investigator)
    with client:
        assert client.get("/incidents/nope").status_code == 404


def test_dry_run_produces_a_report_without_llm(tmp_path):
    service, client = make(tmp_path, dry_run_investigator)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle()
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "done" and inc["recommended_action"] == "escalate_to_human"


def test_real_graph_behind_the_webhook_writes_checkpoint_and_report(tmp_path):
    from incident_agent.checkpointing import open_checkpointer
    from incident_agent.graph import build_graph

    db = str(tmp_path / "cp.sqlite")
    settings = Settings(checkpoint_db=db)
    llm = ScriptedLLM([ai("That is enough.")])
    investigator = graph_investigator(FakeBackend.from_file(FIXTURE), llm, settings)
    service, client = make(tmp_path, investigator)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "done", inc
        assert inc["recommended_action"] == "rollback_deployment"
        assert metric(client, 'incident_agent_llm_tokens_total{direction="input"}') > 0

    # thread_id = incident id, so `investigate --resume <id>` sees the same checkpoint
    with open_checkpointer(db) as cp:
        graph = build_graph(FakeBackend({}), ScriptedLLM([]), checkpointer=cp)
        state = graph.get_state({"configurable": {"thread_id": inc["id"]}}).values
    assert state["diagnosis"].culprit_service == "checkout"
    assert state["alert"].name == "HighErrorRate"


def test_serve_command_dry_run_is_wired(monkeypatch):
    """`incident-agent serve --dry-run` wires the service and hands the app to uvicorn."""
    import incident_agent.cli as cli
    from typer.testing import CliRunner

    captured = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: captured.update(app=app, **kw))
    monkeypatch.setenv("WEBHOOK_TOKEN", "tok")
    r = CliRunner().invoke(cli.app, ["serve", "--dry-run", "--port", "9999"])
    assert r.exit_code == 0, r.output
    assert captured["port"] == 9999 and captured["host"] == "127.0.0.1"
    out = " ".join(r.output.split())                  # rich wraps long lines in a narrow terminal
    assert "dry-run" in out and "auth on" in out and "fixes off" in out
    with TestClient(captured["app"]) as c:
        assert c.post("/alertmanager", json=PAYLOAD).status_code == 401


def test_access_log_hides_polling_but_keeps_decisions_and_errors():
    import logging

    from incident_agent.server import QuietAccessLog

    def rec(method, path, status):
        return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                                 ("127.0.0.1:1", method, path, "1.1", status), None)

    f = QuietAccessLog()
    assert not f.filter(rec("GET", "/incidents", 200))
    assert not f.filter(rec("GET", "/healthz", 200)) and not f.filter(rec("GET", "/metrics", 200))
    assert f.filter(rec("POST", "/incidents/x/approve", 200))     # a human decision is always logged
    assert f.filter(rec("GET", "/incidents", 401))                # so is a bad token
    assert f.filter(rec("POST", "/alertmanager", 200))


def test_known_metric_series_exist_from_the_start():
    """Otherwise increase() never counts the first event of a pod and the dashboard shows 0."""
    from incident_agent.server import Metrics

    text = Metrics().render().decode()
    for line in ('incident_agent_investigations_total{status="done"} 0.0',
                 'incident_agent_alerts_received_total{decision="correlated"} 0.0',
                 'incident_agent_llm_tokens_total{direction="input"} 0.0',
                 'incident_agent_remediations_total{action="disable_feature_flag",outcome="recovered"} 0.0'):
        assert line in text, line


def test_queue_gauge_counts_only_waiting_incidents(tmp_path):
    """Live: the dashboard showed Queue = 1 while the only incident was being investigated, not waiting."""
    started, release = threading.Event(), threading.Event()

    def slow(iid, alert):
        started.set()
        release.wait(5)
        return RESULT

    service, client = make(tmp_path, slow)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert started.wait(5)
        assert metric(client, "incident_agent_queue_depth") == 0.0  # being investigated, not queued
        release.set()
        assert service.wait_idle()
