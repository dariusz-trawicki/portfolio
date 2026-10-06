"""Step 5d: the manifests agree with the code (no cluster needed).

Drift between YAML and Python is the usual way an in-cluster deployment breaks quietly:
a metric renamed in code leaves an empty Grafana panel, a new service in the dependency map
cannot be rolled back because RBAC does not list it, a port changes in one place only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from incident_agent.remediation import application_services
from incident_agent.server import Metrics

ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "deploy" / "k8s"


def docs(name: str) -> list[dict]:
    return [d for d in yaml.safe_load_all((K8S / name).read_text()) if d]


def find(items: list[dict], kind: str, name: str) -> dict:
    return next(d for d in items if d["kind"] == kind and d["metadata"]["name"] == name)


def agent_container() -> dict:
    dep = find(docs("30-agent.yaml"), "Deployment", "incident-agent")
    return dep["spec"]["template"]["spec"]["containers"][0]


def test_rollback_permission_covers_exactly_the_application_services():
    role = find(docs("10-rbac.yaml"), "Role", "incident-agent-rollback")
    [rule] = role["rules"]
    assert rule["verbs"] == ["patch"] and rule["resources"] == ["deployments"]
    assert set(rule["resourceNames"]) == application_services()


def test_the_agent_can_never_read_secrets_exec_or_delete():
    for role in (d for d in docs("10-rbac.yaml") if d["kind"] in ("Role", "ClusterRole")):
        for rule in role["rules"]:
            assert "secrets" not in rule["resources"] and "pods/exec" not in rule["resources"]
            assert not {"delete", "deletecollection", "create", "*", "update"} & set(rule["verbs"]), rule
    assert all(d["kind"] != "ClusterRoleBinding" for d in docs("10-rbac.yaml"))


def test_single_replica_and_no_overlap_during_updates():
    dep = find(docs("30-agent.yaml"), "Deployment", "incident-agent")
    assert dep["spec"]["replicas"] == 1 and dep["spec"]["strategy"]["type"] == "Recreate"


def test_pod_is_hardened_and_matches_the_image_user():
    dep = find(docs("30-agent.yaml"), "Deployment", "incident-agent")
    pod = dep["spec"]["template"]["spec"]
    c = agent_container()
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert c["securityContext"]["readOnlyRootFilesystem"] is True
    assert c["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert f"USER {pod['securityContext']['runAsUser']}" in (ROOT / "Dockerfile").read_text()


def test_metrics_scrape_and_service_point_at_the_container_port():
    items = docs("30-agent.yaml")
    dep = find(items, "Deployment", "incident-agent")
    port = agent_container()["ports"][0]["containerPort"]
    ann = dep["spec"]["template"]["metadata"]["annotations"]
    assert ann["prometheus.io/scrape"] == "true" and int(ann["prometheus.io/port"]) == port
    assert ann["prometheus.io/path"] == "/metrics"
    assert str(port) in agent_container()["args"]
    assert find(items, "Service", "incident-agent")["spec"]["ports"][0]["port"] == port


def test_state_goes_to_postgres_and_config_keys_are_real_settings():
    env = {e["name"]: e.get("value") for e in agent_container()["env"]}
    assert env["CHECKPOINT_DB"].startswith("postgresql://agent:$(POSTGRES_PASSWORD)@postgres:5432/")
    known = set(re.findall(r'_env\("([A-Z_]+)"', (ROOT / "src/incident_agent/config.py").read_text()))
    cfg = find(docs("30-agent.yaml"), "ConfigMap", "incident-agent-config")
    assert set(cfg["data"]) <= known, set(cfg["data"]) - known


def test_alertmanager_overlay_targets_the_agent_service_with_the_mounted_token():
    overlay = yaml.safe_load((ROOT / "infra" / "alertmanager-to-cluster-agent.yaml").read_text())
    am = overlay["prometheus"]["alertmanager"]
    [hook] = am["config"]["receivers"][0]["webhook_configs"]
    svc = find(docs("30-agent.yaml"), "Service", "incident-agent")
    assert hook["url"] == (f"http://{svc['metadata']['name']}.{svc['metadata']['namespace']}.svc:"
                           f"{svc['spec']['ports'][0]['port']}/alertmanager")
    [mount] = am["extraSecretMounts"]
    assert hook["http_config"]["authorization"]["credentials_file"] == f"{mount['mountPath']}/token"
    # the receiver name must match the route in the main values file (the overlay replaces the list)
    base = yaml.safe_load((ROOT / "infra" / "otel-demo-values.yaml").read_text())
    assert am["config"]["receivers"][0]["name"] == base["prometheus"]["alertmanager"]["config"]["route"]["receiver"]


def test_every_dashboard_metric_exists_in_the_agent():
    m = Metrics()
    m.duration.observe(1)
    m.approval_wait.observe(1)
    m.time_to_recover.observe(1)
    m.tokens.labels("input").inc()
    m.alerts.labels("new").inc()
    m.investigations.labels("done").inc()
    m.remediations.labels("x", "proposed").inc()
    exposed = set(re.findall(r"^(incident_agent_\w+?)(?:\{| )", m.render().decode(), re.M))
    dashboard = (ROOT / "deploy" / "grafana" / "incident-agent.json").read_text()
    used = set(re.findall(r"incident_agent_\w+", dashboard))
    assert used and used <= exposed, used - exposed
    panels = json.loads(dashboard)["panels"]
    assert all(t["datasource"]["uid"] == "webstore-metrics" for p in panels for t in p.get("targets", []))


def test_outcome_colours_are_fixed_and_distinct():
    """Grafana's palette colours series by their order, so 'executed' and 'recovered' came out the same yellow."""
    panels = {p["title"]: p for p in json.loads((ROOT / "deploy" / "grafana" / "incident-agent.json").read_text())["panels"]}
    for title in ("Remediations by outcome", "Alerts by decision"):
        colours = {o["matcher"]["options"]: o["properties"][0]["value"]["fixedColor"]
                   for o in panels[title]["fieldConfig"]["overrides"]}
        assert len(set(colours.values())) == len(colours), colours
        assert panels[title]["targets"][0]["expr"].endswith("> 0")      # no legend entries for things that never happened


# ---------------------------------------------------------------- step 5e (GitOps rollback)
def make_vars() -> dict[str, str]:
    """Raw values of the Makefile's `NAME ?= value` / `NAME = value` lines, exactly as make would store them."""
    return {m.group(1): m.group(2).lstrip() for m in re.finditer(r"^([A-Z_]+)\s*\??=(.*)$", (ROOT / "Makefile").read_text(), re.M)}


def test_makefile_assignments_have_no_trailing_spaces_or_inline_comments():
    """`VAR ?= x   # note` stores 'x   ' (spaces included) — broke paths, and made an 'empty' variable non-empty."""
    bad = {k: v for k, v in make_vars().items() if v != v.strip() or "#" in v}
    assert not bad, bad


def test_gitops_config_in_the_pod_is_optional_and_uses_real_settings():
    refs = agent_container()["envFrom"]
    optional = {next(iter(r.values()))["name"]: next(iter(r.values())).get("optional") for r in refs}
    assert optional["incident-agent-gitops"] is True                       # without `make agent-gitops` the pod still starts
    known = set(re.findall(r'(?:_env\("|getenv\(")([A-Z_]+)', (ROOT / "src/incident_agent/config.py").read_text()))
    makefile = (ROOT / "Makefile").read_text()
    used = set(re.findall(r"--from-literal=([A-Z_]+)", makefile[makefile.index("agent-gitops:"):]))
    assert {"ROLLBACK_MODE", "GITOPS_REPO", "GITOPS_TOKEN"} <= used and used <= known, used - known


def test_application_manifest_matches_the_chart_version_and_protects_the_cart_probe(tmp_path):
    from incident_agent import gitops

    version = make_vars()["CHART_VER"]
    gitops.bootstrap(tmp_path, "https://github.com/x/y", [ROOT / "infra" / "otel-demo-values.yaml"], version)
    app = yaml.safe_load((tmp_path / "argocd" / "application.yaml").read_text())
    assert app["spec"]["sources"][0]["targetRevision"] == version
    assert app["spec"]["destination"]["namespace"] == make_vars()["NS"]
    [ign] = app["spec"]["ignoreDifferences"]
    assert ign["name"] == "cart" and "RespectIgnoreDifferences=true" in app["spec"]["syncPolicy"]["syncOptions"]
    cli = (ROOT / "src/incident_agent/cli.py").read_text()
    assert f'chart_version: str = typer.Option("{version}"' in cli          # the CLI default follows the Makefile


def test_rollback_pr_needs_no_extra_cluster_permissions():
    """GitOps rollbacks only read the cluster (history for validation) and talk to GitHub: nothing new in RBAC."""
    role = find(docs("10-rbac.yaml"), "Role", "incident-agent-read")
    assert all(set(r["verbs"]) <= {"get", "list", "watch"} for r in role["rules"])


def test_argocd_default_project_exists_for_the_core_install():
    """ArgoCD core has no server to create the `default` project; the Application references it (real failure, 02.10)."""
    [project] = list(yaml.safe_load_all((ROOT / "deploy" / "gitops" / "default-project.yaml").read_text()))
    assert project["kind"] == "AppProject" and project["metadata"]["name"] == "default"
    assert project["metadata"]["namespace"] == "argocd"
    from incident_agent import gitops

    app = yaml.safe_load(gitops.APPLICATION.format(chart_version="x", repo_url="https://x/y", branch="main"))
    assert app["spec"]["project"] == project["metadata"]["name"]
    assert "deploy/gitops/default-project.yaml" in (ROOT / "Makefile").read_text()
