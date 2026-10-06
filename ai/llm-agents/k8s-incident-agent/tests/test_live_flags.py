"""Targeted flags: OFREP without context cannot see them, the flagd-ui definitions can.

Lesson from the evaluation: for productCatalogFailure the tool returned "no active flags",
the agent burned its budget and rightly escalated to a human — the tool was at fault, not the model.
"""

import copy
import json
from pathlib import Path

import httpx

from incident_agent.backends.live import LiveBackend, active_flags_from_definitions
from incident_agent.chaos import apply_variant
from incident_agent.config import Settings

FLAGS = json.loads((Path(__file__).parent / "fixtures" / "demo.flagd.json").read_text())["flags"]


def injected(flag: str, variant: str) -> dict:
    flags = copy.deepcopy(FLAGS)
    apply_variant(flags[flag], variant)
    return flags


def test_clean_definitions_have_no_active_flags():
    out = active_flags_from_definitions(FLAGS)
    assert out["non_default_flags"] == [] and out["total_flags"] == len(FLAGS)


def test_targeted_flag_is_reported_with_its_condition():
    out = active_flags_from_definitions(injected("productCatalogFailure", "on"))
    [f] = out["non_default_flags"]
    assert f["flag"] == "productCatalogFailure" and f["value"] is True
    assert f["scope"] == "targeted: when condition is true"
    assert "OLJCESPC7Z" in json.dumps(f["condition"])


def test_plain_flag_and_load_generator_flags():
    flags = injected("paymentFailure", "50%")
    flags["loadGeneratorFloodHomepage"]["defaultVariant"] = "on"
    [f] = active_flags_from_definitions(flags)["non_default_flags"]
    assert (f["flag"], f["variant"], f["scope"]) == ("paymentFailure", "50%", "all requests")


def backend(handler) -> LiveBackend:
    be = LiveBackend.__new__(LiveBackend)
    be.s = Settings()
    be.http = httpx.Client(transport=httpx.MockTransport(handler))
    return be


def test_live_backend_prefers_flag_definitions():
    def handler(req: httpx.Request):
        assert req.url.path == "/feature/api/read"
        return httpx.Response(200, json={"flags": injected("productCatalogFailure", "on")})

    out = backend(handler).feature_flags()
    assert out["source"].startswith("flag definitions")
    assert out["non_default_flags"][0]["flag"] == "productCatalogFailure"


def test_live_backend_falls_back_to_ofrep_with_a_warning():
    def handler(req: httpx.Request):
        if req.url.path.endswith("/api/read"):
            return httpx.Response(502)
        return httpx.Response(200, json={"flags": [{"key": "paymentFailure", "variant": "50%", "value": 0.5},
                                                   {"key": "productCatalogFailure", "variant": "off", "value": False}]})

    out = backend(handler).feature_flags()
    assert out["source"].startswith("OFREP")
    assert [f["flag"] for f in out["non_default_flags"]] == ["paymentFailure"]
    assert "NOT visible" in out["warning"]
