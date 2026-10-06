from incident_agent.alerts import pick_alert

ALERTS = [
    {"name": "MemoryNearLimit", "service": "grafana", "severity": "warning", "state": "firing", "started_at": "2026-09-28T20:08:39Z"},
    {"name": "HighErrorRate", "service": "checkout", "severity": "critical", "state": "firing", "started_at": "2026-09-28T20:14:40Z"},
    {"name": "HighErrorRate", "service": "payment", "severity": "critical", "state": "firing", "started_at": "2026-09-28T20:14:39Z"},
    {"name": "MemoryGrowth", "service": "cart", "severity": "warning", "state": "pending", "started_at": "2026-09-28T20:00:00Z"},
]


def test_critical_beats_older_warning_and_earliest_wins():
    a, others = pick_alert(ALERTS)
    assert (a["name"], a["service"]) == ("HighErrorRate", "payment")
    assert [o["service"] for o in others] == ["checkout", "grafana"]


def test_service_filter_and_pending_ignored():
    assert pick_alert(ALERTS, "checkout")[0]["service"] == "checkout"
    assert pick_alert(ALERTS, "cart")[0] is None
