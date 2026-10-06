"""Injecting and reverting the faults from the scenarios/scenarios.yaml catalogue.

Flags: demo.flagd.json lives in an emptyDir shared by the flagd and flagd-ui containers;
flagd watches the file and reloads flags on its own.

We write through the flagd-ui API (GET /api/read, POST /api/write — the same calls the browser makes).
flagd-ui reads the file only at start-up and then keeps the state in memory, so writing around the
API (kubectl exec) made the states diverge: flagd saw the fault, while /api/read — which the agent
reads — still showed every flag as off. Worse, changing a flag in the UI would overwrite the file
with stale state and silently revert the injected fault. `kubectl exec` remains only as a fallback
when flagd-ui is unreachable (e.g. the port-forward is down).

Kubernetes changes are reverted declaratively by re-applying the helm manifest,
so reset is idempotent no matter what the agent did.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import yaml

from .config import Settings

FLAG_FILE = "/app/data/demo.flagd.json"
SCENARIOS_FILE = Path(__file__).resolve().parents[2] / "scenarios" / "scenarios.yaml"
# Patches the chart cannot express (e.g. the gRPC readiness probe for cart); reset re-applies them.
PATCHES = {"cart": Path(__file__).resolve().parents[2] / "infra" / "cart-readiness-probe.yaml"}


def load_scenarios(path: Path = SCENARIOS_FILE) -> dict[str, dict]:
    data = yaml.safe_load(path.read_text())
    return {s["id"]: s for s in data["scenarios"]}


def _kubectl(args: list[str], namespace: str, stdin: str | None = None) -> str:
    cmd = ["kubectl", "-n", namespace, *args]
    res = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> {res.stderr.strip()}")
    return res.stdout


FLAGD_SCHEMA = "https://flagd.dev/schema/v0/flags.json"


def _ui_url() -> str:
    return Settings().flagd_ui_url


def _ui_read() -> dict:
    r = httpx.get(f"{_ui_url()}/api/read", timeout=10)
    r.raise_for_status()
    return {"$schema": FLAGD_SCHEMA, **r.json()}


def _ui_write(config: dict) -> None:
    r = httpx.post(f"{_ui_url()}/api/write", json={"data": config}, timeout=10)
    r.raise_for_status()


def _warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def read_flags(namespace: str) -> dict:
    try:
        return _ui_read()
    except httpx.HTTPError as e:
        _warn(f"flagd-ui API unavailable ({e}); reading the flag file via kubectl exec")
    raw = _kubectl(["exec", "deploy/flagd", "-c", "flagd-ui", "--", "cat", FLAG_FILE], namespace)
    return json.loads(raw)


def write_flags(namespace: str, config: dict) -> None:
    try:
        _ui_write(config)
        return
    except httpx.HTTPError as e:
        _warn(f"flagd-ui API unavailable ({e}); writing the flag file via kubectl exec — "
              "flagd-ui and the agent will show stale flags until the flagd pod restarts")
    _kubectl(
        ["exec", "-i", "deploy/flagd", "-c", "flagd-ui", "--", "sh", "-c", f"cat > {FLAG_FILE}"],
        namespace,
        stdin=json.dumps(config, indent=2),
    )


def _targeting_if(flag: dict) -> list | None:
    """The `targeting.if` rule as [condition, variant_if_true, variant_if_false], or None."""
    rule = (flag.get("targeting") or {}).get("if")
    return rule if isinstance(rule, list) and len(rule) == 3 else None


def current_variant(flag: dict) -> str:
    rule = _targeting_if(flag)
    return rule[1] if rule else flag["defaultVariant"]


def apply_variant(flag: dict, variant: str) -> None:
    """Switches the variant the way flagd-ui does (Storage.update_flag).

    A targeted flag (e.g. productCatalogFailure: only product OLJCESPC7Z) ignores
    `defaultVariant` — the `targeting.if[1]` branch decides the result. Changing only
    `defaultVariant` was therefore a silent no-op and the scenario never caused a fault.
    """
    rule = _targeting_if(flag)
    if rule:
        rule[1] = variant
    else:
        flag["defaultVariant"] = variant


def set_flag(namespace: str, flag: str, variant: str) -> None:
    config = read_flags(namespace)
    if flag not in config["flags"]:
        raise KeyError(f"No such flag: {flag}")
    variants = config["flags"][flag]["variants"]
    if variant not in variants:
        raise ValueError(f"{flag}: no variant {variant!r}, available: {list(variants)}")
    apply_variant(config["flags"][flag], variant)
    write_flags(namespace, config)


def inject(scenario: dict, namespace: str) -> str:
    spec = scenario["inject"]
    if spec["type"] == "flag":
        set_flag(namespace, spec["flag"], spec["variant"])
        return f"flag {spec['flag']} = {spec['variant']}"
    if spec["type"] == "k8s":
        cmd = spec["cmd"]
        assert cmd[0] == "kubectl", "k8s scenarios may only use kubectl"
        _kubectl(cmd[1:], namespace)
        return " ".join(cmd)
    raise ValueError(f"Unknown type: {spec['type']}")


def reset(namespace: str, release: str) -> list[str]:
    done = []
    # 1) every fault flag to "off" (load-generator traffic flags are left untouched)
    config = read_flags(namespace)
    for name, flag in config["flags"].items():
        if name.startswith("loadGenerator"):
            continue
        if "off" in flag["variants"] and (current_variant(flag) != "off" or flag["defaultVariant"] != "off"):
            apply_variant(flag, "off")
            flag["defaultVariant"] = "off"
            done.append(f"flag {name} -> off")
    write_flags(namespace, config)
    # 2) restore deployments to the helm state
    manifest = subprocess.run(
        ["helm", "get", "manifest", release, "-n", namespace],
        capture_output=True, text=True, check=True,
    ).stdout
    _kubectl(["apply", "-f", "-"], namespace, stdin=manifest)
    done.append(f"kubectl apply of helm release {release} manifest")
    # 3) patches outside the chart (unchanged = no-op, no pod restarts)
    for deployment, patch in PATCHES.items():
        if patch.exists():
            _kubectl(["patch", "deployment", deployment, "--patch-file", str(patch)], namespace)
            done.append(f"patch deployment/{deployment} ({patch.name})")
    return done
