from __future__ import annotations

import dataclasses
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .config import Settings

app = typer.Typer(help="Kubernetes incident diagnosis agent (LangGraph).", no_args_is_help=True)
chaos_app = typer.Typer(help="Fault injection for the OTel Demo.", no_args_is_help=True)
app.add_typer(chaos_app, name="chaos")
eval_app = typer.Typer(help="Score the agent against the injected faults.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
console = Console()


def _llm(settings: Settings):
    from langchain.chat_models import init_chat_model

    kwargs = {} if settings.temperature is None else {"temperature": settings.temperature}
    return init_chat_model(settings.model, **kwargs)


def _remediation(mode: str, backend_kind: str, be, s: Settings, rollback: Optional[str] = None):
    """--fixes live | dry-run | off. A fake backend never touches a cluster, so it is always dry-run.
    --rollback kubectl | gitops (default: ROLLBACK_MODE): how a live rollback is applied."""
    from .remediation import dry_run_remediation, live_remediation

    rollback = (rollback or s.rollback_mode).lower()
    if mode not in ("live", "dry-run", "off"):
        console.print("[red]--fixes must be live, dry-run or off.[/red]")
        raise typer.Exit(2)
    if rollback not in ("kubectl", "gitops"):
        console.print("[red]--rollback must be kubectl or gitops.[/red]")
        raise typer.Exit(2)
    if mode == "off":
        return None
    if mode == "dry-run" or backend_kind == "fake":
        return dry_run_remediation(s.namespace)
    if rollback == "gitops":
        from .gitops import gitops_remediation

        try:
            return gitops_remediation(be, s)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(2)
    return live_remediation(be, s.namespace)


def _print_update(update: dict) -> None:
    for node, delta in update.items():
        if node == "investigate":
            msg = delta["messages"][-1]
            for tc in getattr(msg, "tool_calls", None) or []:
                console.print(f"  [cyan]→ {tc['name']}[/cyan] {json.dumps(tc['args'], ensure_ascii=False)}")
            if not getattr(msg, "tool_calls", None):
                console.print("  [magenta]agent concludes the investigation[/magenta]")
        elif node != "tools":
            console.print(f"[dim]✓ {node}[/dim]")


@app.command()
def doctor():
    """Check that the agent can reach the cluster, Prometheus, logs, flagd and the model."""
    from .doctor import run_all

    icon = {"ok": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}
    t = Table("", "check", "result", "what to do", show_lines=False)
    results = run_all(Settings())
    for status, name, detail, hint in results:
        t.add_row(icon[status], name, detail, hint)
    console.print(t)
    if any(r[0] == "fail" for r in results):
        raise typer.Exit(1)


@app.command()
def alerts():
    """Show active alerts in Prometheus."""
    from .backends.live import LiveBackend

    rows = LiveBackend(Settings()).firing_alerts()
    t = Table("state", "alert", "service", "severity", "since", "summary")
    for a in rows:
        t.add_row(a["state"], a["name"], a["service"], a["severity"], a["started_at"] or "", a["summary"])
    console.print(t if rows else "[green]No active alerts.[/green]")


@app.command()
def investigate(
    service: Optional[str] = typer.Option(None, help="Service to investigate; with --from-prometheus it filters alerts."),
    alert_name: str = typer.Option("ManualInvestigation", help="Alert name for a manual run."),
    summary: str = typer.Option("", help="Symptom description for a manual run."),
    from_prometheus: bool = typer.Option(False, "--from-prometheus", help="Take the most important firing alert from Prometheus (critical > warning)."),
    backend: str = typer.Option("live", help="live | fake"),
    fixture: Optional[str] = typer.Option(None, help="JSON file for --backend fake."),
    thread_id: Optional[str] = typer.Option(None, help="Thread (checkpoint) id. Random by default."),
    resume: Optional[str] = typer.Option(None, help="Resume an interrupted investigation from its checkpoint (thread id)."),
    out_dir: Path = typer.Option(Path("reports"), help="Where to write the report."),
    lang: Optional[str] = typer.Option(None, help="Language of the agent's text and report: en | pl (default: AGENT_LANGUAGE or en)."),
    remediate: bool = typer.Option(False, "--remediate", help="Propose a fix after the diagnosis and ask you to approve it here."),
    fixes: str = typer.Option("live", help="With --remediate: live | dry-run (fake backend is always dry-run)."),
    rollback: Optional[str] = typer.Option(None, help="With --remediate: kubectl | gitops (default: ROLLBACK_MODE)."),
):
    """Investigate an incident and write a diagnosis report (optionally propose a fix for you to approve)."""
    from .backends import make_backend
    from .checkpointing import open_checkpointer
    from .graph import build_graph
    from .state import Alert
    from .tracing import flush, run_config

    s = Settings()
    if lang:
        if lang not in ("en", "pl"):
            console.print("[red]--lang must be en or pl.[/red]")
            raise typer.Exit(2)
        s = dataclasses.replace(s, language=lang)
    be = make_backend(backend, s, fixture)

    if resume:
        alert = None
    elif from_prometheus:
        from .alerts import pick_alert

        a, others = pick_alert(be.firing_alerts(), service)
        if a is None:
            where = f" for service {service}" if service else ""
            console.print(f"[yellow]No firing alerts{where}. "
                          "'pending' alerts are still waiting for confirmation — try again in a minute.[/yellow]")
            raise typer.Exit(1)
        for o in others:
            console.print(f"[dim]skipped: {o['name']} · {o['service']} ({o['severity']})[/dim]")
        alert = Alert(name=a["name"], service=a["service"], severity=a["severity"],
                      summary=a["summary"], labels=a["labels"], started_at=a["started_at"])
    elif backend == "fake" and not service:
        alert = Alert(**json.loads(Path(fixture).read_text())["alert"])
    elif service:
        alert = Alert(name=alert_name, service=service, summary=summary)
    else:
        console.print("[red]Pass --service or --from-prometheus.[/red]")
        raise typer.Exit(2)

    thread = resume or thread_id or f"{alert.service}-{uuid.uuid4().hex[:8]}"
    cfg = run_config(thread, run_name="investigate", tags=["cli"] + (["resume"] if resume else []),
                     metadata={"alert": alert.name, "service": alert.service} if alert else {})

    with open_checkpointer(s.checkpoint_db) as cp:
        rem = _remediation(fixes, backend, be, s, rollback) if remediate else None
        graph = build_graph(be, _llm(s), s, checkpointer=cp, remediation=rem)
        graph_input = {"alert": alert}
        if resume:
            snap = graph.get_state(cfg)
            if not snap.values:
                console.print(f"[red]No checkpoint found for thread {resume}.[/red]")
                raise typer.Exit(2)
            alert = snap.values["alert"]
            graph_input = None  # None = continue from the last saved step
            console.print(f"[dim]resuming from: {', '.join(snap.next) or 'end'} "
                          f"(evidence from checkpoint: {len(snap.values.get('evidence', {}))})[/dim]")
        console.rule(f"[bold]{alert.name}[/bold] · {alert.service} · thread {thread}")
        try:
            for update in graph.stream(graph_input, cfg, stream_mode="updates"):
                _print_update(update)
            pending = graph.get_state(cfg).interrupts
            if pending:  # paused before a fix: the human (you) decides here
                from langgraph.types import Command

                from .remediation import make_decision

                p = pending[0].value["proposal"]
                d = pending[0].value["diagnosis"]
                console.rule("[bold yellow]Proposed fix — nothing has been changed yet[/bold yellow]")
                console.print(f"culprit [bold]{d['culprit_service']}[/bold] · {d['category']} · "
                              f"confidence {d['confidence']:.0%}\n{d['root_cause']}\n")
                console.print(f"[bold]{p['command']}[/bold]")
                approved = typer.confirm("Approve this fix?", default=False)
                comment = typer.prompt("Comment (optional)", default="", show_default=False)
                decision = make_decision(approved, by=os.getenv("USER", "cli"), comment=comment)
                for update in graph.stream(Command(resume=decision), cfg, stream_mode="updates"):
                    _print_update(update)
        except Exception as e:
            console.print(f"\n[red]Investigation interrupted:[/red] {type(e).__name__}: {str(e)[:300]}")
            console.print(f"State up to the last successful step is saved. After fixing the cause, resume with:\n"
                          f"  [bold]incident-agent investigate --resume {thread}[/bold]")
            raise typer.Exit(1)
        finally:
            flush()
        final = graph.get_state(cfg).values

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{alert.service}.md"
    path.write_text(final["report"])
    (path.with_suffix(".json")).write_text(final["diagnosis"].model_dump_json(indent=2))
    console.print(Markdown(final["report"]))
    console.print(f"\n[green]Report:[/green] {path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Address to bind. Use 0.0.0.0 only with WEBHOOK_TOKEN set."),
    port: int = typer.Option(8787),
    backend: str = typer.Option("live", help="live | fake"),
    fixture: Optional[str] = typer.Option(None, help="JSON file for --backend fake."),
    dry_run: bool = typer.Option(False, "--dry-run", help="No LLM and no cluster: only exercise webhook -> queue -> report."),
    out_dir: Path = typer.Option(Path("reports/incidents"), help="Where to write incident reports."),
    lang: Optional[str] = typer.Option(None, help="Language of the agent's text and report: en | pl."),
    fixes: str = typer.Option("live", help="Proposed fixes: live (executed after approval) | dry-run | off."),
    rollback: Optional[str] = typer.Option(None, help="How rollbacks are applied: kubectl | gitops (a PR; default: ROLLBACK_MODE)."),
):
    """Run the webhook: accept alerts from Alertmanager and investigate every new incident in the background."""
    import logging
    import uvicorn

    from .incidents import IncidentRegistry
    from .server import IncidentService, create_app, dry_run_investigator, graph_investigator

    s = Settings()
    if lang:
        if lang not in ("en", "pl"):
            console.print("[red]--lang must be en or pl.[/red]")
            raise typer.Exit(2)
        s = dataclasses.replace(s, language=lang)
    if dry_run:
        investigator = dry_run_investigator
    else:
        from .backends import make_backend

        be = make_backend(backend, s, fixture)
        investigator = graph_investigator(be, _llm(s), s, _remediation(fixes, backend, be, s, rollback))
    if host not in ("127.0.0.1", "localhost") and not s.webhook_token:
        console.print("[yellow]Warning: listening on a non-local address without WEBHOOK_TOKEN — "
                      "anyone who can reach this port can trigger paid LLM investigations.[/yellow]")
    from .checkpointing import redact

    # incidents survive a restart (same database as the checkpoints); a dry run keeps them in memory only
    store = None
    if not dry_run:
        from .store import open_store

        store = open_store(s.checkpoint_db)
    registry = IncidentRegistry(s.dedup_window_minutes, store=store)
    service = IncidentService(registry, investigator, out_dir)
    mode = "dry-run (no LLM)" if dry_run else f"{backend} backend, model {s.model}"
    fix_mode = "off" if dry_run or getattr(investigator, "remediation", None) is None else (
        "dry-run" if backend == "fake" or fixes == "dry-run" else
        f"live, rollbacks via {(rollback or s.rollback_mode)}, human approval required")
    console.print(f"[bold]Webhook[/bold] http://{host}:{port}/alertmanager · {mode} · fixes {fix_mode} · "
                  f"auth {'on' if s.webhook_token else 'off'} · dedup window {s.dedup_window_minutes} min")
    console.print(f"[bold]State[/bold] {'memory only (dry run)' if store is None else redact(s.checkpoint_db)}"
                  + (f" · {len(registry.all())} incident(s) loaded" if store is not None else ""))
    if fix_mode != "off":
        console.print(f"[bold]Approval page[/bold] http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}/")
    # our own log lines (alert decisions, investigations, approvals) next to uvicorn's
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    from .server import QuietAccessLog

    logging.getLogger("uvicorn.access").addFilter(QuietAccessLog())   # no "GET /incidents 200" every 3 s
    for noisy in ("httpx", "httpcore", "anthropic"):                   # one line per Prometheus/OpenSearch/LLM call
        logging.getLogger(noisy).setLevel(logging.WARNING)
    uvicorn.run(create_app(service, s.webhook_token), host=host, port=port, log_level="info")


def _decide(incident_id: str, approved: bool, by: Optional[str], comment: str, url: str) -> None:
    import httpx

    s = Settings()
    headers = {"Authorization": f"Bearer {s.webhook_token}"} if s.webhook_token else {}
    verb = "approve" if approved else "reject"
    try:
        r = httpx.post(f"{url.rstrip('/')}/incidents/{incident_id}/{verb}", headers=headers, timeout=10,
                       json={"by": by or os.getenv("USER", "cli"), "comment": comment})
    except httpx.HTTPError as e:
        console.print(f"[red]Cannot reach the agent at {url}: {e}[/red] (is `make serve` running?)")
        raise typer.Exit(1)
    if r.status_code != 200:
        console.print(f"[red]{r.status_code}: {r.json().get('detail', r.text)}[/red]")
        raise typer.Exit(1)
    word = "[green]Approved[/green] — the fix runs now" if approved else "[yellow]Rejected[/yellow] — nothing will change"
    console.print(f"{word}: {incident_id}. Follow it with: make incidents")


@app.command()
def approve(
    incident_id: str,
    by: Optional[str] = typer.Option(None, help="Who approves (default: $USER)."),
    comment: str = typer.Option("", help="Optional comment for the report."),
    url: str = typer.Option("http://localhost:8787", help="The running agent (incident-agent serve)."),
):
    """Approve the fix proposed for an incident (the agent never fixes anything without this)."""
    _decide(incident_id, True, by, comment, url)


@app.command()
def reject(
    incident_id: str,
    by: Optional[str] = typer.Option(None, help="Who rejects (default: $USER)."),
    comment: str = typer.Option("", help="Optional comment for the report."),
    url: str = typer.Option("http://localhost:8787", help="The running agent (incident-agent serve)."),
):
    """Reject the fix proposed for an incident."""
    _decide(incident_id, False, by, comment, url)


@app.command("gitops-bootstrap")
def gitops_bootstrap(
    out: Path = typer.Option(..., help="Local clone of the (empty) GitOps repository, e.g. ../k8s-gitops-demo."),
    repo_url: str = typer.Option(..., help="https:// URL of that repository (ArgoCD reads values from it)."),
    values: list[Path] = typer.Option(
        [Path("infra/otel-demo-values.yaml"), Path("infra/alertmanager-to-cluster-agent.yaml")],
        help="Helm values files, merged in order (like several `helm -f`)."),
    chart_version: str = typer.Option("0.42.1", help="opentelemetry-demo chart version ArgoCD installs."),
    branch: str = typer.Option("main"),
):
    """Write the GitOps repository's files: merged values, the ArgoCD Application, a README (step 5e)."""
    from .gitops import bootstrap

    for p in bootstrap(out, repo_url, values, chart_version, branch):
        console.print(f"[green]wrote[/green] {p}")
    console.print("Next: commit + push, protect `main` (require a PR), then `make gitops-up`.")


@app.command("gitops-break")
def gitops_break(
    repo_dir: Path = typer.Option(..., "--dir", help="Local clone of the GitOps repository."),
    service: str = typer.Option("checkout"),
):
    """Demo: edit values/otel-demo.yaml so that `service` gets a bad PAYMENT_ADDR (commit + merge it yourself;
    `make gitops-break` does that). It is the GitOps twin of the payment-unreachable-deploy scenario."""
    from .gitops import break_service

    path = repo_dir / "values" / "otel-demo.yaml"
    path.write_text(break_service(path.read_text(), service))
    console.print(f"[yellow]edited[/yellow] {path}: {service} PAYMENT_ADDR=payment-v2:8080")


@app.command()
def graph(out: Path = typer.Option(Path("docs/graph.mmd"))):
    """Write the graph diagram (Mermaid)."""
    from .backends.fake import FakeBackend
    from .graph import build_graph

    class _NoLLM:
        def bind_tools(self, tools):
            return self

        def with_structured_output(self, *a, **k):
            return self

    g = build_graph(FakeBackend({}), _NoLLM())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(g.get_graph().draw_mermaid())
    console.print(f"Wrote {out}")


# ------------------------------------------------------------------ chaos
@chaos_app.command("list")
def chaos_list():
    """List the fault scenarios."""
    from .chaos import load_scenarios

    t = Table("id", "type", "description", "expected culprit", "expected action")
    for sid, sc in load_scenarios().items():
        e = sc["expected"]
        t.add_row(sid, sc["inject"]["type"], sc["description"], e["culprit_service"], ", ".join(e["action"]))
    console.print(t)


@chaos_app.command("inject")
def chaos_inject(scenario_id: str):
    """Inject a fault."""
    from .chaos import inject, load_scenarios

    sc = load_scenarios()[scenario_id]
    done = inject(sc, Settings().namespace)
    console.print(f"[red]Injected:[/red] {done}\nAn alert should fire for service "
                  f"[bold]{sc['alert_service']}[/bold] within a few minutes.")


@chaos_app.command("reset")
def chaos_reset():
    """Revert all faults (flags -> off, deployments -> helm state)."""
    from .chaos import reset

    s = Settings()
    for line in reset(s.namespace, s.helm_release):
        console.print(f"[green]✓[/green] {line}")


# ------------------------------------------------------------------ eval
@eval_app.command("run")
def eval_run(
    scenario: Optional[list[str]] = typer.Option(None, "--scenario", "-s", help="Scenario id (repeatable). Default: all."),
    repeat: int = typer.Option(1, "--repeat", "-n", min=1, help="Runs per scenario (the LLM is non-deterministic)."),
    alert_timeout: int = typer.Option(15, help="Minutes to wait for the alert after injecting."),
    clean_for: int = typer.Option(5, help="Minutes without firing alerts that count as a quiet cluster."),
    clean_timeout: int = typer.Option(20, help="Minutes to wait for a quiet cluster before skipping a run."),
    out_dir: Path = typer.Option(Path("reports/eval"), help="Base directory; each evaluation gets its own timestamped folder."),
    ignore_alert: Optional[list[str]] = typer.Option(None, "--ignore-alert", help="Background alert to ignore: Name or Name:service (repeatable)."),
    max_dirty: int = typer.Option(2, help="Abort after this many dirty_env runs in a row (0 = never)."),
):
    """For each scenario: reset, inject, wait for the alert, investigate, score against ground truth."""
    from . import eval as ev
    from .backends.live import LiveBackend
    from .chaos import inject, load_scenarios, reset
    from .graph import build_graph
    from .tracing import flush, run_config

    s = Settings()
    catalogue = load_scenarios()
    ids = scenario or list(catalogue)
    unknown = [i for i in ids if i not in catalogue]
    if unknown:
        console.print(f"[red]Unknown scenario(s): {', '.join(unknown)}[/red] (see: incident-agent chaos list)")
        raise typer.Exit(2)

    be = LiveBackend(s)
    llm = _llm(s)
    cfg = ev.EvalConfig(repeat=repeat, alert_timeout_s=alert_timeout * 60, clean_for_s=clean_for * 60,
                        clean_timeout_s=clean_timeout * 60, out_dir=ev.new_out_dir(out_dir),
                        ignore_alerts=tuple(ignore_alert or ()), max_dirty_in_a_row=max_dirty)

    def investigate(alert, label):
        graph = build_graph(be, llm, s)  # no checkpointer: every run starts from scratch
        try:
            state = graph.invoke({"alert": alert}, run_config(
                label, run_name=f"eval:{alert.service}", tags=["eval"],
                metadata={"alert": alert.name, "service": alert.service}))
        finally:
            flush()
        return {"diagnosis": state["diagnosis"].model_dump(), "report": state["report"],
                "tool_calls": state.get("tool_calls_used", 0), "usage": state.get("usage", {}),
                "budget_exhausted": state.get("budget_exhausted", False)}

    env = ev.EvalEnv(
        reset=lambda: reset(s.namespace, s.helm_release),
        inject=lambda sc: inject(sc, s.namespace),
        firing_alerts=be.firing_alerts,
        investigate=investigate,
        log=lambda m: console.print(f"[dim]{m}[/dim]"),
    )
    meta = {"model": s.model, "repeat": repeat, "started": f"{datetime.now():%Y-%m-%d %H:%M}"}
    if cfg.ignore_alerts:
        meta["ignored_alerts"] = list(cfg.ignore_alerts)
    results: list = []
    try:
        results = ev.run_eval(env, cfg, [catalogue[i] for i in ids])
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted; resetting the cluster.[/yellow]")
        reset(s.namespace, s.helm_release)
        raise typer.Exit(130)
    jpath, mpath = ev.save(results, cfg, meta)
    console.print(Markdown(ev.render_table(results, meta)))
    console.print(f"[green]Results:[/green] {jpath}\n[green]Table:[/green] {mpath}")


@eval_app.command("report")
def eval_report(results_json: Path):
    """Re-render the results table from a saved results.json."""
    from . import eval as ev

    results, meta = ev.load_results(results_json)
    console.print(Markdown(ev.render_table(results, meta)))


if __name__ == "__main__":
    app()
