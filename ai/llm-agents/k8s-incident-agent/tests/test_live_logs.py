"""search_logs without OpenSearch: the httpx transport is a fake, we check the shape of the queries."""

import json

import httpx

from incident_agent.backends.live import LiveBackend
from incident_agent.config import Settings

HIT = {"_source": {"observedTimestamp": "2026-09-29T10:52:02Z", "body": "payment failed",
                   "resource": {"service.name": "checkout", "k8s.pod.name": "checkout-abc"}}}


def backend(responses: list[list[dict]], seen: list[dict]) -> LiveBackend:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"hits": {"hits": responses.pop(0)}})

    be = LiveBackend.__new__(LiveBackend)  # no cluster connection
    be.s = Settings()
    be.http = httpx.Client(transport=httpx.MockTransport(handler))
    return be


def test_time_filter_accepts_observed_timestamp_and_service_field():
    seen: list[dict] = []
    out = backend([[HIT]], seen).search_logs("checkout", "", 15)
    assert out and out[0]["body"] == "payment failed"
    flt = seen[0]["query"]["bool"]["filter"]
    ranges = flt[0]["bool"]["should"]
    assert {"observedTimestamp", "@timestamp"} == {next(iter(r["range"])) for r in ranges}
    fields = {next(iter(c["match_phrase"])) for c in flt[1]["bool"]["should"]}
    assert fields == {"resource.service.name", "resource.k8s.deployment.name", "attributes.service.name"}
    assert len(seen) == 1                       # hit on the first try, no fallback


def test_falls_back_to_free_text_when_service_field_matches_nothing():
    seen: list[dict] = []
    out = backend([[], [HIT]], seen).search_logs("checkout", "PlaceOrder", 15)
    assert out
    assert len(seen) == 2
    must = seen[1]["query"]["bool"]["must"]
    assert any(m["query_string"]["query"] == '"checkout"' for m in must)
    assert len(seen[1]["query"]["bool"]["filter"]) == 1   # time filter only


def test_text_search_is_restricted_to_explicit_fields():
    """Regression: query_string without `fields` returned 500 (too_many_clauses) on the real index."""
    from incident_agent.backends.live import LOG_SERVICE_FIELDS, LOG_TEXT_FIELDS

    body = LiveBackend._logs_body("payment", "error OR fail*", "2026-09-29T10:00:00+00:00", None)
    qs = [m["query_string"] for m in body["query"]["bool"]["must"]]
    assert qs[0]["fields"] == LOG_TEXT_FIELDS and qs[1]["fields"] == LOG_SERVICE_FIELDS
    assert all(q["lenient"] for q in qs)
