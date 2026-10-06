"""Webhook parser and incident registry: dedup, correlation, window, lifecycle. No network, no LLM."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from incident_agent.alertmanager import parse_webhook
from incident_agent.incidents import IncidentRegistry
from incident_agent.prompts import dependencies, neighbours

PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "alertmanager-firing.json").read_text())


class Clock:
    def __init__(self):
        self.t = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, minutes: float):
        self.t += timedelta(minutes=minutes)


def incoming(name="HighErrorRate", service="checkout", fp="fp1", status="firing", severity="critical", **extra):
    labels = {"alertname": name, "severity": severity, **({"service": service} if service else {})}
    return parse_webhook({"alerts": [{"status": status, "labels": labels, "annotations": {"summary": "s"},
                                      "startsAt": "2026-09-29T11:59:00Z", "fingerprint": fp, **extra}]})[0]


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def reg(clock):
    return IncidentRegistry(window_minutes=30, clock=clock)


# ---------------------------------------------------------------- parser
def test_parse_payload_v4():
    a, b = parse_webhook(PAYLOAD)
    assert a.firing and a.fingerprint == "a1b2c3d4e5f60001"
    assert (a.alert.name, a.alert.service, a.alert.severity) == ("HighErrorRate", "checkout", "critical")
    assert a.alert.summary == "checkout error ratio = 41.2%"
    assert a.alert.started_at == "2026-09-29T15:42:10Z"
    assert b.alert.service == "payment"


def test_parse_resolved_normalises_service_and_go_zero_time():
    r = parse_webhook({"alerts": [{"status": "resolved", "labels": {"alertname": "X", "service": " Checkout "},
                                   "startsAt": "0001-01-01T00:00:00Z"}]})[0]
    assert not r.firing and r.alert.service == "checkout" and r.alert.started_at is None
    assert r.alert.severity == "warning"


def test_parse_computes_fingerprint_when_missing_and_it_is_stable():
    raw = {"alerts": [{"status": "firing", "labels": {"alertname": "X", "service": "a"}}]}
    assert parse_webhook(raw)[0].fingerprint == parse_webhook(raw)[0].fingerprint


@pytest.mark.parametrize("bad", [None, [], "x", {}, {"alerts": "no"}, {"alerts": [1]}])
def test_parse_rejects_non_alertmanager_payloads(bad):
    with pytest.raises(ValueError):
        parse_webhook(bad)


# ---------------------------------------------------------------- dependency map
def test_neighbours_both_directions_and_no_flagd_hub():
    n = neighbours("checkout")
    assert {"payment", "cart", "kafka", "frontend"} <= n          # dependencies and a client
    assert "flagd" not in neighbours("payment")                    # the hub does not connect everything to everything
    assert "checkout" in neighbours("payment")
    assert dependencies("kafka") == ["accounting", "fraud-detection"]


# ---------------------------------------------------------------- deduplication
def test_first_alert_is_new_and_repeat_is_duplicate(reg):
    d1 = reg.handle(incoming())
    assert d1.kind == "new"
    d2 = reg.handle(incoming())
    assert (d2.kind, d2.incident_id) == ("duplicate", d1.incident_id)
    assert len(reg.all()) == 1


def test_same_service_other_alert_is_correlated(reg):
    new = reg.handle(incoming("HighErrorRate", "checkout", "fp1"))
    d = reg.handle(incoming("HighLatencyP95", "checkout", "fp2", severity="warning"))
    assert (d.kind, d.incident_id) == ("correlated", new.incident_id)


def test_neighbour_service_is_correlated_but_unrelated_is_new(reg):
    new = reg.handle(incoming("HighErrorRate", "checkout", "fp1"))
    assert reg.handle(incoming("PodRestarting", "payment", "fp2")).incident_id == new.incident_id
    far = reg.handle(incoming("MemoryGrowth", "recommendation", "fp3"))
    assert far.kind == "new" and far.incident_id != new.incident_id


def test_alert_without_service_is_ignored(reg):
    assert reg.handle(incoming(service="")).kind == "ignored"
    assert reg.all() == []


def test_resolved_alert_of_unknown_fingerprint_is_ignored(reg):
    assert reg.handle(incoming(status="resolved", fp="never-seen")).kind == "ignored"


# ---------------------------------------------------------------- dedup window
def test_flapping_alert_inside_window_does_not_open_new_incident(reg, clock):
    first = reg.handle(incoming())
    clock.advance(2)
    assert reg.handle(incoming(status="resolved")).kind == "resolved"
    assert reg.get(first.incident_id).resolved_at is not None
    clock.advance(10)                                               # < 30 min window
    again = reg.handle(incoming())
    assert (again.kind, again.incident_id) == ("duplicate", first.incident_id)
    assert reg.get(first.incident_id).resolved_at is None           # incident active again


def test_alert_after_window_opens_new_incident(reg, clock):
    first = reg.handle(incoming())
    reg.handle(incoming(status="resolved"))
    clock.advance(31)
    second = reg.handle(incoming())
    assert second.kind == "new" and second.incident_id != first.incident_id


def test_incident_stays_open_while_alert_keeps_firing_past_window(reg, clock):
    first = reg.handle(incoming())
    clock.advance(120)                                              # nobody resolved the alert
    assert reg.handle(incoming("HighLatencyP95", "checkout", "fp2")).incident_id == first.incident_id


def test_incident_resolves_only_when_all_alerts_are_resolved(reg):
    reg.handle(incoming("A", "checkout", "fp1"))
    reg.handle(incoming("B", "payment", "fp2"))
    inc = reg.all()[0]
    reg.handle(incoming("A", "checkout", "fp1", status="resolved"))
    assert inc.resolved_at is None and inc.active == {"fp2"}
    reg.handle(incoming("B", "payment", "fp2", status="resolved"))
    assert inc.resolved_at is not None


# ---------------------------------------------------------------- lifecycle
def test_claim_picks_most_severe_firing_alert(reg):
    new = reg.handle(incoming("HighLatencyP95", "checkout", "fp1", severity="warning"))
    reg.handle(incoming("HighErrorRate", "checkout", "fp2", severity="critical"))
    alert = reg.claim(new.incident_id)
    assert alert.name == "HighErrorRate"                            # critical, even though it arrived later
    assert reg.get(new.incident_id).status == "investigating"


def test_claim_skips_incident_whose_alerts_resolved_in_queue(reg):
    new = reg.handle(incoming())
    reg.handle(incoming(status="resolved"))
    assert reg.claim(new.incident_id) is None
    assert reg.get(new.incident_id).status == "skipped"


def test_alert_after_skipped_incident_opens_a_fresh_incident(reg):
    """A 'skipped' incident was never investigated — a new alert must not join it and get lost."""
    old = reg.handle(incoming())
    reg.handle(incoming(status="resolved"))
    reg.claim(old.incident_id)
    fresh = reg.handle(incoming())
    assert fresh.kind == "new" and fresh.incident_id != old.incident_id


def test_finish_and_fail_record_outcome(reg):
    a = reg.handle(incoming("A", "checkout", "fp1")).incident_id
    b = reg.handle(incoming("B", "recommendation", "fp2")).incident_id
    reg.finish(a, {"diagnosis": {"culprit_service": "payment", "category": "feature_flag",
                                 "recommended_action": "disable_feature_flag"}}, 12.5)
    reg.fail(b, "boom", 3.0)
    s = reg.get(a).summary()
    assert (s["status"], s["culprit_service"], s["duration_s"]) == ("done", "payment", 12.5)
    assert reg.get(b).summary()["error"] == "boom"


# ---------------------------------------------------------------- recurrence after a finished incident
DONE = {"diagnosis": {"culprit_service": "checkout", "category": "unknown", "recommended_action": "escalate_to_human"}}


def test_alert_after_a_finished_quiet_incident_opens_a_new_one(reg, clock):
    """Live bug (02.10): a transient error was diagnosed as noise; 15 min later payment-failure fired the same
    alerts and they were absorbed by the finished incident as duplicates — never investigated."""
    old = reg.handle(incoming()).incident_id
    reg.claim(old)
    reg.finish(old, DONE, 30.0)
    clock.advance(5)
    reg.handle(incoming(status="resolved"))                         # the noise went away
    clock.advance(10)                                               # still inside the 30 min window
    again = reg.handle(incoming())                                  # same alert, real fault this time
    assert again.kind == "new" and again.incident_id != old
    assert reg.get(again.incident_id).follows == old
    # a neighbour's alert joins the NEW incident, not the finished one
    assert reg.handle(incoming("HighErrorRate", "payment", "fp9")).incident_id == again.incident_id


def test_finished_incident_still_firing_keeps_absorbing_its_echoes(reg, clock):
    """While its alerts are still firing it is the same ongoing problem: repeats and neighbours join it."""
    old = reg.handle(incoming()).incident_id
    reg.claim(old)
    reg.finish(old, DONE, 30.0)
    clock.advance(10)
    assert reg.handle(incoming()).kind == "duplicate"
    assert reg.handle(incoming("HighErrorRate", "payment", "fp2")).incident_id == old


def test_flapping_during_an_investigation_is_still_absorbed(reg, clock):
    old = reg.handle(incoming()).incident_id
    reg.claim(old)                                                  # investigating, not finished
    reg.handle(incoming(status="resolved"))
    clock.advance(3)
    assert reg.handle(incoming()).incident_id == old


def test_follows_survives_a_restart():
    from incident_agent.incidents import Incident
    from incident_agent.store import MemoryStore

    store = MemoryStore()
    reg = IncidentRegistry(30, store=store)
    first = reg.handle(incoming()).incident_id
    reg.claim(first)
    reg.finish(first, DONE, 1.0)
    reg.handle(incoming(status="resolved"))
    second = reg.handle(incoming()).incident_id
    again = IncidentRegistry(30, store=store).get(second)
    assert isinstance(again, Incident) and again.follows == first
    assert again.summary()["follows"] == first
