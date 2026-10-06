"""Log compaction and dependency logs. Data modelled on a real OpenSearch document."""

import json

from incident_agent.logs import collapse, compact_log
from incident_agent.prompts import dependencies


def payment_doc(ts: str, level: str = "gold") -> dict:
    msg = f"Payment request failed. Invalid token. demo.user_context.loyalty_level={level}"
    return {
        "attributes": {"exception.message": msg, "exception.type": "Error",
                       "exception.stacktrace": "Error: ...\n at charge.js:48", "service.name": "payment"},
        "body": msg,
        "observedTimestamp": ts,
        "@timestamp": ts,
        "resource": {"k8s.pod.name": "payment-6fc54b7f7-sscn5", "k8s.pod.uid": "6226-uid",
                     "service.instance.id": "e46b", "service.name": "payment", "service.version": "3.1.0"},
        "severity": {"text": "warn", "number": 13},
    }


def test_compact_log_keeps_only_useful_fields():
    out = compact_log(payment_doc("2026-09-29T10:29:12Z"))
    assert out == {
        "time": "2026-09-29T10:29:12Z", "severity": "warn", "service": "payment",
        "pod": "payment-6fc54b7f7-sscn5",
        "body": "Payment request failed. Invalid token. demo.user_context.loyalty_level=gold",
    }  # no uids, versions or stacktrace; exception == body, so it is not duplicated


def test_exception_kept_when_it_adds_information():
    doc = {"body": "charge failed", "attributes": {"exception.message": "rpc Unavailable"}}
    assert compact_log(doc)["exception"] == "rpc Unavailable"


def test_collapse_merges_duplicates_and_shrinks_payload():
    raw = [payment_doc(f"2026-09-29T10:{m:02d}:00Z") for m in (29, 28, 27)] + [payment_doc("2026-09-29T10:26:00Z", "silver")]
    entries = [compact_log(d) for d in raw]
    groups = collapse(entries)
    assert len(groups) == 2
    assert groups[0]["count"] == 3 and groups[0]["time"].endswith("10:29:00Z") and groups[0]["first_seen"].endswith("10:27:00Z")
    assert "count" not in groups[1]
    assert len(json.dumps(groups)) < len(json.dumps(raw)) / 3


def test_collapse_ignores_ids_and_numbers():
    a = {"service": "cart", "severity": "error", "body": "order 123e4567-e89b-12d3-a456-426614174000 failed after 31 ms"}
    b = {"service": "cart", "severity": "error", "body": "order 00000000-0000-0000-0000-000000000001 failed after 7 ms"}
    assert collapse([a, b])[0]["count"] == 2


def test_dependencies_from_service_map():
    assert "payment" in dependencies("checkout") and "kafka" in dependencies("checkout")
    assert dependencies("recommendation") == ["product-catalog"]
    assert dependencies("payment") == []


def test_gather_logs_includes_dependency_errors():
    from test_graph import FIXTURE, ScriptedLLM, ai

    from incident_agent.backends.fake import FakeBackend
    from incident_agent.graph import build_graph
    from incident_agent.state import Alert

    data = json.loads(FIXTURE.read_text())
    data["search_logs"]["payment"] = collapse([compact_log(payment_doc("2026-09-29T10:29:12Z"))])
    llm = ScriptedLLM([ai("Enough.")])
    result = build_graph(FakeBackend(data), llm).invoke(
        {"alert": Alert(name="HighErrorRate", service="checkout")}, {"configurable": {"thread_id": "t"}})
    dep = json.loads(result["evidence"]["dependency_logs"])
    assert "Invalid token" in dep["with_errors"]["payment"][0]["body"]
    assert "cart" in dep["no_error_logs"]
    assert "Invalid token" in llm.seen[0][1].content    # the model sees the cause from its first call
