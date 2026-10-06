import httpx

from incident_agent import doctor
from incident_agent.config import Settings


def client(metrics, rules=6):
    def handler(req):
        if req.url.path.endswith("__name__/values"):
            return httpx.Response(200, json={"data": metrics})
        groups = [{"name": "incident-lab", "rules": [{"name": f"R{i}"} for i in range(rules)]}]
        return httpx.Response(200, json={"data": {"groups": groups}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_missing_metric_suggests_similar_names():
    names = [m for m in doctor.EXPECTED_METRICS if m != "container_cpu_usage_seconds_total"]
    res = doctor.check_prometheus(Settings(), client(names + ["container_cpu_user_seconds_total"]))
    warn = [r for r in res if r[0] == "warn"]
    assert len(warn) == 1 and "container_cpu_user_seconds_total" in warn[0][3]


def test_old_rule_set_asks_for_apply_values():
    res = doctor.check_prometheus(Settings(), client(list(doctor.EXPECTED_METRICS), rules=5))
    rules = [r for r in res if r[1] == "alert rules"][0]
    assert rules[0] == "warn" and "apply-values" in rules[3]
