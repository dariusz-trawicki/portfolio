"""Step 5c: incidents and checkpoints survive an agent restart.

Every test runs against SQLite and — when TEST_POSTGRES_URL is set — against a real Postgres
(PostgresSaver + the incidents table), e.g.:
    TEST_POSTGRES_URL=postgresql://agent@127.0.0.1:5433/agent pytest tests/test_persistence.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from incident_agent import remediation as rem
from incident_agent.backends.fake import FakeBackend
from incident_agent.checkpointing import close_pools, is_postgres, open_checkpointer, postgres_pool, redact
from incident_agent.config import Settings
from incident_agent.incidents import Incident, IncidentRegistry
from incident_agent.server import IncidentService, create_app, graph_investigator
from incident_agent.store import MemoryStore, open_store
from test_graph import FIXTURE, ScriptedLLM, ai

PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "alertmanager-firing.json").read_text())
PG_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.fixture(params=["sqlite", "postgres"])
def db(request, tmp_path):
    if request.param == "sqlite":
        yield str(tmp_path / "state.sqlite")
        return
    if not PG_URL:
        pytest.skip("set TEST_POSTGRES_URL to run against Postgres")
    with postgres_pool(PG_URL).connection() as conn:   # a clean database for every test
        for table in ("incidents", "checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    close_pools()
    yield PG_URL
    close_pools()


def service_for(db, executor=None, llm=None, backend=None):
    """One 'process' of the agent: a fresh registry loaded from the store and a fresh graph investigator."""
    executor = executor or rem.DryRunExecutor()
    remediation = rem.Remediation(executor, lambda a: {"recovered": True, "after_s": 120.0, "checked": "x"})
    investigator = graph_investigator(backend or FakeBackend.from_file(FIXTURE),
                                      llm or ScriptedLLM([ai("That is enough.")]),
                                      Settings(checkpoint_db=db), remediation)
    registry = IncidentRegistry(30, store=open_store(db))
    service = IncidentService(registry, investigator, Path(db).parent / "out" if not is_postgres(db) else Path("/tmp/ia-out"))
    return service, TestClient(create_app(service)), executor


# ---------------------------------------------------------------- store + registry
def test_incident_record_round_trip():
    reg = IncidentRegistry(30, store=MemoryStore())
    from incident_agent.alertmanager import parse_webhook

    for incoming in parse_webhook(PAYLOAD):
        reg.handle(incoming)
    [inc] = reg.all()
    again = Incident.from_record(json.loads(json.dumps(inc.to_record())))
    assert again.summary() == inc.summary()
    assert again.active == inc.active and again.opened_at == inc.opened_at


def test_registry_reloads_incidents_and_keeps_deduplicating(db):
    from incident_agent.alertmanager import parse_webhook

    first = IncidentRegistry(30, store=open_store(db))
    kinds = [first.handle(i).kind for i in parse_webhook(PAYLOAD)]
    assert kinds == ["new", "correlated"]

    restarted = IncidentRegistry(30, store=open_store(db))            # a new process
    [inc] = restarted.all()
    assert inc.status == "queued" and len(inc.alerts) == 2
    # Alertmanager re-sends after the restart: recognised as the same incident, not a new investigation
    assert [restarted.handle(i).kind for i in parse_webhook(PAYLOAD)] == ["duplicate", "duplicate"]


def test_redact_hides_the_password():
    assert redact("postgresql://agent:s3cr3t@postgres:5432/agent") == "postgresql://agent:***@postgres:5432/agent"
    assert redact(".data/checkpoints.sqlite") == ".data/checkpoints.sqlite"


# ---------------------------------------------------------------- the point of 5c
def test_incident_awaiting_approval_survives_a_restart(db):
    service, client, executor = service_for(db)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "awaiting_approval"
    # the pod is rescheduled: new registry, new graph, nothing in memory — only the database
    service2, client2, executor2 = service_for(db, llm=ScriptedLLM([]))  # the LLM must not be called again
    with client2:
        [again] = client2.get("/incidents").json()
        assert again["id"] == inc["id"] and again["status"] == "awaiting_approval"
        assert again["proposal"]["action"] == "rollback_deployment"
        r = client2.post(f"/incidents/{inc['id']}/approve", json={"by": "dartit", "comment": "after restart"})
        assert r.status_code == 200
        assert service2.wait_idle(30)
        done = client2.get(f"/incidents/{inc['id']}").json()
    assert done["status"] == "done" and done["verification"]["recovered"] is True
    assert "Approved by `dartit` — after restart" in done["report"]
    assert executor.executed == [] and executor2.executed == [("rollback_deployment", "checkout")]


def test_interrupted_investigation_continues_from_its_checkpoint(db):
    """The process dies while the model is thinking; after the restart the evidence is not gathered again."""

    class DyingLLM(ScriptedLLM):
        def bind_tools(self, tools):
            def step(messages):
                raise RuntimeError("process killed")
            return RunnableLambda(step)

    service, _, _ = service_for(db, llm=DyingLLM([]))
    from incident_agent.alertmanager import parse_webhook

    for incoming in parse_webhook(PAYLOAD):
        service.registry.handle(incoming)
    [inc] = service.registry.all()
    alert = service.registry.claim(inc.id)                 # status investigating, persisted
    with pytest.raises(RuntimeError):
        service.investigator(inc.id, alert)                # gather_* checkpointed, investigate died

    backend = FakeBackend.from_file(FIXTURE)
    service2, client2, _ = service_for(db, backend=backend)
    with client2:                                          # start() -> recover() -> continue
        assert service2.wait_idle(30)
        again = client2.get(f"/incidents/{inc.id}").json()
    assert again["status"] == "awaiting_approval"
    gathered = {name for name, _ in backend.calls}
    assert not gathered & {"pods", "events", "rollout_history", "feature_flags"}, gathered


def test_fix_interrupted_by_a_restart_is_failed_not_retried(db):
    service, client, executor = service_for(db)
    with client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
    service.registry.begin_remediation(inc["id"])          # approved, and the process died mid-fix

    service2, client2, executor2 = service_for(db)
    with client2:
        assert service2.wait_idle(10)
        again = client2.get(f"/incidents/{inc['id']}").json()
        m = client2.get("/metrics").text
    assert again["status"] == "failed" and "not retried" in again["error"]
    assert executor2.executed == []                        # a rollback is never repeated blindly
    assert 'outcome="interrupted"' in m


def test_checkpointer_works_for_both_backends(db):
    with open_checkpointer(db) as cp:
        assert cp.get_tuple({"configurable": {"thread_id": "nope"}}) is None
