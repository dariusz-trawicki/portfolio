"""Fault injection without a cluster: kubectl/helm calls are replaced with fakes."""

import json
import subprocess
from pathlib import Path

import pytest

from incident_agent import chaos

FLAGS = json.loads((Path(__file__).parent / "fixtures" / "demo.flagd.json").read_text())


@pytest.fixture
def fake_cluster(monkeypatch):
    store = {"flags": json.loads(json.dumps(FLAGS)), "cmds": []}

    def kubectl(args, namespace, stdin=None):
        store["cmds"].append(args)
        if args[:2] == ["exec", "deploy/flagd"]:
            return json.dumps(store["flags"])
        if args[:3] == ["exec", "-i", "deploy/flagd"]:
            store["flags"] = json.loads(stdin)
        return ""

    monkeypatch.setattr(chaos, "_kubectl", kubectl)

    # flagd-ui API: "up" by default and holding the same state as the file
    def ui_read():
        store["cmds"].append(["ui-read"])
        return json.loads(json.dumps(store["flags"]))

    def ui_write(config):
        store["cmds"].append(["ui-write"])
        store["flags"] = json.loads(json.dumps(config))

    monkeypatch.setattr(chaos, "_ui_read", ui_read)
    monkeypatch.setattr(chaos, "_ui_write", ui_write)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "kind: List", ""))
    return store


def test_every_flag_scenario_exists_in_demo_flag_file():
    for sid, sc in chaos.load_scenarios().items():
        if sc["inject"]["type"] == "flag":
            flag = FLAGS["flags"][sc["inject"]["flag"]]
            assert sc["inject"]["variant"] in flag["variants"], sid


def test_inject_and_reset_flag(fake_cluster):
    chaos.inject(chaos.load_scenarios()["payment-failure"], "otel-demo")
    assert fake_cluster["flags"]["flags"]["paymentFailure"]["defaultVariant"] == "50%"
    done = chaos.reset("otel-demo", "otel-demo")
    assert fake_cluster["flags"]["flags"]["paymentFailure"]["defaultVariant"] == "off"
    assert any("paymentFailure" in d for d in done)
    assert ["apply", "-f", "-"] in fake_cluster["cmds"]
    # reset also restores cart's gRPC readiness probe, which the chart cannot define
    patch = fake_cluster["cmds"][-1]
    assert patch[:3] == ["patch", "deployment", "cart"] and patch[-1].endswith("cart-readiness-probe.yaml")


def test_cart_probe_patch_is_grpc_on_the_cart_container():
    import yaml
    spec = yaml.safe_load(chaos.PATCHES["cart"].read_text())["spec"]["template"]["spec"]["containers"][0]
    assert spec["name"] == "cart" and spec["readinessProbe"]["grpc"]["port"] == 8080


def test_k8s_scenario_runs_kubectl(fake_cluster):
    chaos.inject(chaos.load_scenarios()["currency-oom"], "otel-demo")
    assert fake_cluster["cmds"][-1] == ["set", "resources", "deployment/currency", "--limits=memory=2Mi"]


def test_unknown_variant_is_rejected(fake_cluster):
    with pytest.raises(ValueError):
        chaos.set_flag("otel-demo", "paymentFailure", "33%")


def test_flag_with_targeting_is_switched_in_the_rule_not_default_variant(fake_cluster):
    """productCatalogFailure ignores defaultVariant (targeting decides) — switched the way flagd-ui does it."""
    chaos.inject(chaos.load_scenarios()["product-catalog-failure"], "otel-demo")
    flag = fake_cluster["flags"]["flags"]["productCatalogFailure"]
    assert flag["targeting"]["if"][1] == "on"                 # product OLJCESPC7Z -> failure
    assert flag["targeting"]["if"][2] == "off"                # other products unchanged
    assert chaos.current_variant(flag) == "on"
    done = chaos.reset("otel-demo", "otel-demo")
    flag = fake_cluster["flags"]["flags"]["productCatalogFailure"]
    assert flag["targeting"]["if"][1] == "off" and flag["defaultVariant"] == "off"
    assert any("productCatalogFailure" in d for d in done)


def test_flags_go_through_flagd_ui_api_not_kubectl_exec(fake_cluster):
    """Writing around the flagd-ui API made states diverge: flagd saw the fault, the agent (via /api/read) did not."""
    chaos.inject(chaos.load_scenarios()["payment-failure"], "otel-demo")
    assert ["ui-read"] in fake_cluster["cmds"] and ["ui-write"] in fake_cluster["cmds"]
    assert not any(c[0] == "exec" for c in fake_cluster["cmds"])


def test_kubectl_exec_is_only_a_fallback_when_the_api_is_down(fake_cluster, monkeypatch, capsys):
    import httpx

    def down(*a, **k):
        raise httpx.ConnectError("port-forward not running")

    monkeypatch.setattr(chaos, "_ui_read", down)
    monkeypatch.setattr(chaos, "_ui_write", down)
    chaos.inject(chaos.load_scenarios()["payment-failure"], "otel-demo")
    assert fake_cluster["flags"]["flags"]["paymentFailure"]["defaultVariant"] == "50%"
    assert [c[:2] for c in fake_cluster["cmds"] if c[0] == "exec"] == [["exec", "deploy/flagd"], ["exec", "-i"]]
    assert "stale flags" in capsys.readouterr().err
