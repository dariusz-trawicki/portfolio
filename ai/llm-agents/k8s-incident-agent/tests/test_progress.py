"""The approval page shows the decision and the executed fix (e.g. the rollback PR) while the verifier still waits."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from incident_agent import remediation as rem
from incident_agent.backends.fake import FakeBackend
from incident_agent.config import Settings
from incident_agent.incidents import IncidentRegistry
from incident_agent.server import IncidentService, create_app, graph_investigator
from incident_agent.store import open_store
from test_graph import FIXTURE, ScriptedLLM, ai

PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "alertmanager-firing.json").read_text())


class PrExecutor(rem.DryRunExecutor):
    def execute(self, action, target):
        return {"output": "PR #2 opened: https://github.com/o/r/pull/2", "pr": {"number": 2, "url": "https://github.com/o/r/pull/2"}}


def test_decision_and_pr_are_visible_while_the_verifier_is_still_waiting(tmp_path):
    reached, release = threading.Event(), threading.Event()

    def verify(alert):                       # stands in for "waiting for a human to merge the PR"
        reached.set()
        assert release.wait(30)
        return {"recovered": True, "after_s": 60.0, "checked": "x"}

    db = str(tmp_path / "state.sqlite")
    remediation = rem.Remediation(PrExecutor(), verify)
    investigator = graph_investigator(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("That is enough.")]),
                                      Settings(checkpoint_db=db), remediation)
    service = IncidentService(IncidentRegistry(30, store=open_store(db)), investigator, tmp_path / "out")
    with TestClient(create_app(service)) as client:
        client.post("/alertmanager", json=PAYLOAD)
        assert service.wait_idle(30)
        [inc] = client.get("/incidents").json()
        assert inc["status"] == "awaiting_approval" and not inc["execution"]
        client.post(f"/incidents/{inc['id']}/approve", json={"by": "dartit", "comment": "go"})
        assert reached.wait(30)              # the worker is now inside verify()
        mid = client.get(f"/incidents/{inc['id']}").json()
        assert mid["status"] == "remediating"
        assert mid["decision"]["by"] == "dartit"
        assert mid["execution"]["ok"] and "pull/2" in mid["execution"]["output"]
        assert mid["verification"] is None
        release.set()
        assert service.wait_idle(30)
        done = client.get(f"/incidents/{inc['id']}").json()
    assert done["status"] == "done" and done["verification"]["recovered"] is True
    assert "pull/2" in done["execution"]["output"]


def test_investigators_without_on_progress_still_work(tmp_path):
    """A resume(incident_id, decision) without the callback (older/fake investigators) must keep working."""
    from incident_agent.alertmanager import parse_webhook

    class Old:
        def __call__(self, incident_id, alert):
            raise AssertionError("not used")

        def resume(self, incident_id, decision):
            return {"diagnosis": {"culprit_service": "checkout"}, "report": "# done\n", "decision": decision,
                    "execution": {"ok": True, "output": "ran"}, "verification": {"recovered": True, "after_s": 1.0}}

    registry = IncidentRegistry(30)
    for incoming in parse_webhook(PAYLOAD):
        registry.handle(incoming)
    [inc] = registry.all()
    registry.claim(inc.id)
    registry.await_approval(inc.id, {"diagnosis": {"culprit_service": "checkout"}, "proposal": {"action": "rollback_deployment"}}, 1.0)
    service = IncidentService(registry, Old(), tmp_path)
    decision = service.decide(inc.id, True, by="dartit")
    service._resume(inc.id, decision)
    assert registry.get(inc.id).status == "done" and registry.get(inc.id).result["execution"]["output"] == "ran"
