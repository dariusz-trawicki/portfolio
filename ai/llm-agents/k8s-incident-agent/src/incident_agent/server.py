"""Agent webhook: Alertmanager -> FastAPI -> queue -> a single worker -> LangGraph graph.

    Alertmanager --POST /alertmanager--> ingest() --new--> queue --> worker --> investigator()
                                            │                                     │
                                       IncidentRegistry                 report .md/.json + /metrics

Why a queue and a single worker: an investigation takes tens of seconds, while Alertmanager expects
a fast response (otherwise it retries). The endpoint only registers the alert and returns 200;
the worker investigates in the background, one incident at a time (cost and model API rate control).

Remediation (step 5): when the graph proposes an automated fix it pauses (`interrupt()`) and the
incident waits in `awaiting_approval`. A human calls POST /incidents/{id}/approve or /reject
(or `incident-agent approve|reject <id>`); the worker then resumes the graph from its checkpoint.
Nothing is ever executed without that call.

Restarts (step 5c): with a persistent store the registry reloads its incidents on start-up and
`recover()` decides what to do with the ones that were in flight:
  queued            -> queued again
  investigating     -> continued from the last checkpoint (investigation is read-only, so this is safe)
  awaiting_approval -> stays; approving it later resumes the graph from its checkpoint
  remediating       -> failed, never retried: the fix may or may not have run, and repeating
                       a rollback would roll back one revision too far. A human checks the cluster.
"""

from __future__ import annotations

import inspect
import hmac
import json
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from .alertmanager import parse_webhook
from .incidents import IncidentRegistry
from .state import Alert

log = logging.getLogger("incident_agent.server")

# Requests that happen all the time and say nothing: the approval page polls /incidents every few seconds,
# Kubernetes probes /healthz, Prometheus scrapes /metrics. Successful ones are hidden from the access log.
QUIET_PATHS = ("/incidents", "/healthz", "/metrics")


class QuietAccessLog(logging.Filter):
    """uvicorn.access filter: drops successful GETs of QUIET_PATHS, keeps everything else (POSTs, errors)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:   # (client, method, path, http_version, status)
            method, path, status = args[1], str(args[2]).split("?")[0], args[4]
            if method == "GET" and path in QUIET_PATHS and isinstance(status, int) and status < 400:
                return False
        return True

# investigator(incident_id, alert) -> {"diagnosis": dict, "report": str, "tool_calls": int, "usage": dict, ...}
Investigator = Callable[[str, Alert], dict[str, Any]]


class Metrics:
    """Metrics of the agent itself (LLMOps): how many alerts and investigations, how long they take, how many tokens they cost."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()  # own registry: no collisions between instances (tests)
        r = self.registry
        self.alerts = Counter("incident_agent_alerts_received", "Alerts received from Alertmanager, by decision.",
                              ["decision"], registry=r)
        self.investigations = Counter("incident_agent_investigations", "Finished investigations, by status.",
                                      ["status"], registry=r)
        self.duration = Histogram("incident_agent_investigation_duration_seconds", "Investigation wall time.",
                                  buckets=(5, 10, 20, 30, 60, 120, 300, 600), registry=r)
        self.tokens = Counter("incident_agent_llm_tokens", "LLM tokens used, by direction.", ["direction"], registry=r)
        self.llm_calls = Counter("incident_agent_llm_calls", "LLM calls made.", registry=r)
        self.tool_calls = Counter("incident_agent_tool_calls", "Tool calls made by the agent.", registry=r)
        self.queue_depth = Gauge("incident_agent_queue_depth", "Incidents waiting for the worker.", registry=r)
        self.remediations = Counter("incident_agent_remediations", "Remediation events, by action and outcome.",
                                    ["action", "outcome"], registry=r)
        self.awaiting = Gauge("incident_agent_awaiting_approval", "Incidents waiting for a human decision.", registry=r)
        self.approval_wait = Histogram("incident_agent_approval_wait_seconds", "Time from proposal to human decision.",
                                       buckets=(30, 60, 120, 300, 600, 900, 1800, 3600, 4 * 3600, 24 * 3600), registry=r)
        # finer buckets around the typical 5-15 min, so the median read from the histogram is close to the truth
        self.time_to_recover = Histogram("incident_agent_time_to_recover_seconds",
                                         "Incident opened -> fix verified (MTTR).",
                                         buckets=(120, 240, 360, 480, 600, 720, 900, 1200, 1800, 3600, 4 * 3600),
                                         registry=r)
        self._zero_known_series()

    def _zero_known_series(self) -> None:
        """Create every known label combination at 0 right away.

        A labelled counter does not exist until its first inc(); Prometheus then first sees it at 1, and
        increase()/rate() count only changes *between* samples — so the first incident of every pod was
        invisible on the dashboard (a restarted pod starts new series). Starting from 0 fixes that.
        """
        from .remediation import AUTOMATED_ACTIONS

        for decision in ("new", "duplicate", "correlated", "resolved", "ignored"):
            self.alerts.labels(decision)
        for status in ("done", "failed", "skipped"):
            self.investigations.labels(status)
        for direction in ("input", "output"):
            self.tokens.labels(direction)
        for action in AUTOMATED_ACTIONS:
            for outcome in ("proposed", "approved", "rejected", "executed", "failed", "recovered",
                            "not_recovered", "interrupted"):
                self.remediations.labels(action, outcome)

    def render(self) -> bytes:
        return generate_latest(self.registry)


class IncidentService:
    def __init__(self, registry: IncidentRegistry, investigator: Investigator, out_dir: Path,
                 metrics: Metrics | None = None):
        self.registry, self.investigator, self.out_dir = registry, investigator, Path(out_dir)
        self.metrics = metrics or Metrics()
        # ("investigate", incident_id, None) | ("resume", incident_id, decision)
        self._queue: queue.Queue[tuple[str, str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ input
    def ingest(self, payload: Any) -> list[dict[str, Any]]:
        """Registers the alerts from a payload; new incidents go to the queue. Does not wait for the investigation."""
        decisions = []
        for incoming in parse_webhook(payload):
            d = self.registry.handle(incoming)
            self.metrics.alerts.labels(d.kind).inc()
            if d.kind == "new":
                self._queue.put(("investigate", d.incident_id, None))
                self.metrics.queue_depth.set(self._queue.qsize())
            decisions.append({"decision": d.kind, "incident_id": d.incident_id,
                              "alert": incoming.alert.name, "service": incoming.alert.service})
            log.info("alert %s/%s -> %s %s", incoming.alert.name, incoming.alert.service, d.kind, d.incident_id or "")
        return decisions

    def decide(self, incident_id: str, approved: bool, by: str = "", comment: str = "") -> dict[str, Any]:
        """A human decision on a proposed fix. KeyError = unknown incident, ValueError = not awaiting approval."""
        from .remediation import make_decision

        if not hasattr(self.investigator, "resume"):
            raise ValueError("this server runs without remediation")
        inc = self.registry.begin_remediation(incident_id)
        decision = make_decision(approved, by=by, comment=comment)
        if inc.awaiting_since:
            wait = (self.registry._clock() - inc.awaiting_since).total_seconds()
            self.metrics.approval_wait.observe(max(wait, 0))
        action = ((inc.result or {}).get("proposal") or {}).get("action", "unknown")
        self.metrics.remediations.labels(action, "approved" if approved else "rejected").inc()
        self.registry.note(incident_id, decision=decision)       # visible at once, not after the verification
        self._queue.put(("resume", incident_id, decision))
        self.metrics.queue_depth.set(self._queue.qsize())
        self._refresh_awaiting()
        log.info("incident %s %s by %s", incident_id, "APPROVED" if approved else "rejected", decision["by"])
        return decision

    def _refresh_awaiting(self) -> None:
        self.metrics.awaiting.set(sum(1 for i in self.registry.all() if i.status == "awaiting_approval"))

    # ------------------------------------------------------------ restart
    def recover(self) -> dict[str, int]:
        """Re-queues work that a restart interrupted (see the module docstring). Returns counts per action."""
        counts = {"requeued": 0, "continued": 0, "awaiting": 0, "interrupted": 0}
        for inc in sorted(self.registry.all(), key=lambda i: i.opened_at):   # oldest first, as they arrived
            if inc.status == "queued":
                self._queue.put(("investigate", inc.id, None))
                counts["requeued"] += 1
            elif inc.status == "investigating":
                self._queue.put(("investigate", inc.id, "recover"))
                counts["continued"] += 1
            elif inc.status == "awaiting_approval":
                counts["awaiting"] += 1
            elif inc.status == "remediating":
                action = ((inc.result or {}).get("proposal") or {}).get("action", "unknown")
                self.registry.fail(inc.id, "the agent restarted while the fix was running; it is not retried "
                                   "automatically — check the cluster by hand (kubectl rollout history / flagd-ui)",
                                   inc.duration_s or 0.0)
                self.metrics.remediations.labels(action, "interrupted").inc()
                counts["interrupted"] += 1
        self.metrics.queue_depth.set(self._queue.qsize())
        self._refresh_awaiting()
        if any(counts.values()):
            log.info("recovered after restart: %s", counts)
        return counts

    # ------------------------------------------------------------ worker
    def start(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="incident-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """Waits until the queue is empty and the worker has finished the current investigation (for tests)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                kind, incident_id, payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            # taken off the queue = no longer waiting (before, the gauge kept counting it for the whole investigation)
            self.metrics.queue_depth.set(self._queue.qsize())
            try:
                if kind == "resume":
                    self._resume(incident_id, payload)
                else:
                    self._investigate(incident_id, recovering=payload == "recover")
            except Exception:  # one incident must not kill the worker
                log.exception("worker error on %s", incident_id)
            finally:
                self._queue.task_done()
                self.metrics.queue_depth.set(self._queue.qsize())

    def _investigate(self, incident_id: str, recovering: bool = False) -> None:
        alert = self.registry.claim(incident_id)  # pick the alert only now: correlated ones may have arrived
        if alert is None:
            self.metrics.investigations.labels("skipped").inc()
            log.info("incident %s skipped: alerts resolved before the investigation started", incident_id)
            return
        started = time.monotonic()
        run = getattr(self.investigator, "recover", None) if recovering else None
        try:
            result = (run or self.investigator)(incident_id, alert)
        except Exception as e:
            elapsed = time.monotonic() - started
            msg = (f"{type(e).__name__}: {str(e)[:300]}. State up to the last successful step is checkpointed; "
                   f"resume with: incident-agent investigate --resume {incident_id}")
            self.registry.fail(incident_id, msg, elapsed)
            self.metrics.investigations.labels("failed").inc()
            self.metrics.duration.observe(elapsed)
            log.error("incident %s failed: %s", incident_id, msg)
            return
        elapsed = time.monotonic() - started
        self._save(incident_id, result)
        proposal = result.get("proposal") or {}
        if result.get("awaiting_approval"):
            self.registry.await_approval(incident_id, result, elapsed)
            self.metrics.remediations.labels(proposal.get("action", "unknown"), "proposed").inc()
            self._refresh_awaiting()
            log.info("incident %s: fix proposed, AWAITING APPROVAL: %s  ->  incident-agent approve %s",
                     incident_id, proposal.get("command"), incident_id)
        else:
            self.registry.finish(incident_id, result, elapsed)
            if proposal and not proposal.get("executable"):
                self.metrics.remediations.labels(proposal.get("action", "unknown"), "not_automated").inc()
        usage = result.get("usage") or {}
        self.metrics.investigations.labels("done").inc()
        self.metrics.duration.observe(elapsed)
        self.metrics.tokens.labels("input").inc(usage.get("input_tokens", 0))
        self.metrics.tokens.labels("output").inc(usage.get("output_tokens", 0))
        self.metrics.llm_calls.inc(usage.get("llm_calls", 0))
        self.metrics.tool_calls.inc(result.get("tool_calls", 0))
        log.info("incident %s investigated in %.0fs", incident_id, elapsed)

    def _resume(self, incident_id: str, decision: dict[str, Any]) -> None:
        """Continues a paused graph with the human decision: execute -> verify -> report (or just report)."""
        inc = self.registry.get(incident_id)
        action = ((inc.result or {}).get("proposal") or {}).get("action", "unknown")
        try:
            progress = lambda update: self.registry.note(incident_id, **update)  # noqa: E731
            if "on_progress" in inspect.signature(self.investigator.resume).parameters:
                result = self.investigator.resume(incident_id, decision, on_progress=progress)
            else:
                result = self.investigator.resume(incident_id, decision)
        except Exception as e:
            msg = f"remediation failed: {type(e).__name__}: {str(e)[:300]}"
            self.registry.fail(incident_id, msg, inc.duration_s or 0.0)
            self.metrics.remediations.labels(action, "failed").inc()
            log.error("incident %s %s", incident_id, msg)
            return
        self._save(incident_id, result)
        self.registry.finish(incident_id, result)
        execution, verification = result.get("execution") or {}, result.get("verification") or {}
        if execution:
            self.metrics.remediations.labels(action, "executed" if execution.get("ok") else "failed").inc()
        if verification.get("recovered") is True:
            self.metrics.remediations.labels(action, "recovered").inc()
            mttr = (self.registry._clock() - inc.opened_at).total_seconds()
            self.metrics.time_to_recover.observe(max(mttr, 0))
        elif verification.get("recovered") is False:
            self.metrics.remediations.labels(action, "not_recovered").inc()
        log.info("incident %s remediation finished: execution=%s verification=%s", incident_id,
                 execution.get("ok"), verification.get("recovered"))

    def _save(self, incident_id: str, result: dict[str, Any]) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / f"{incident_id}.md").write_text(result.get("report", ""))
        (self.out_dir / f"{incident_id}.json").write_text(json.dumps(result.get("diagnosis"), indent=2))


# ---------------------------------------------------------------- investigators
def result_from_state(state: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    """Graph state -> the incident result. A paused graph has no `report` yet; render a preliminary one."""
    from .report import render_report

    out = {"diagnosis": state["diagnosis"].model_dump(),
           "report": state.get("report") or render_report(state, lang),
           "tool_calls": state.get("tool_calls_used", 0), "usage": state.get("usage", {}),
           "budget_exhausted": state.get("budget_exhausted", False)}
    for key in ("proposal", "decision", "execution", "verification"):
        if state.get(key):
            out[key] = state[key]
    if state.get("__interrupt__"):
        out["awaiting_approval"] = True
    return out


class GraphInvestigator:
    """The real investigation: the LangGraph graph. thread_id = incident id, so a failed investigation
    can be resumed from its checkpoint (`incident-agent investigate --resume <id>`) and a paused one
    continues after a human decision (`resume`)."""

    def __init__(self, backend, llm, settings, remediation=None):
        self.backend, self.llm, self.s, self.remediation = backend, llm, settings, remediation

    def _run(self, incident_id: str, graph_input, alert: Alert | None, tag: str = "resume") -> dict[str, Any]:
        """graph_input: the graph input, or a function(graph, cfg) -> state for custom flows (recover)."""
        from .checkpointing import open_checkpointer
        from .graph import build_graph
        from .tracing import flush, run_config

        meta = {"alert": alert.name, "service": alert.service, "severity": alert.severity} if alert else {}
        cfg = run_config(incident_id, run_name=f"incident:{alert.service if alert else tag}",
                         tags=["webhook"] + ([alert.name] if alert else []) + ([tag] if tag != "new" else []),
                         metadata=meta)
        try:
            with open_checkpointer(self.s.checkpoint_db) as cp:
                graph = build_graph(self.backend, self.llm, self.s, checkpointer=cp, remediation=self.remediation)
                state = graph_input(graph, cfg) if callable(graph_input) else graph.invoke(graph_input, cfg)
        finally:
            flush()
        return result_from_state(state, self.s.language)

    def __call__(self, incident_id: str, alert: Alert) -> dict[str, Any]:
        return self._run(incident_id, {"alert": alert}, alert, tag="new")

    def resume(self, incident_id: str, decision: dict[str, Any], on_progress=None) -> dict[str, Any]:
        """Continues the paused graph. `on_progress({"execution": ...})` is called as soon as the fix has been
        executed, so the approval page can show e.g. the rollback PR while the verifier is still waiting."""
        from langgraph.types import Command

        def run(graph, cfg):
            for chunk in graph.stream(Command(resume=decision), cfg, stream_mode="updates"):
                update = chunk.get("execute") if isinstance(chunk, dict) else None
                if on_progress and update and update.get("execution"):
                    on_progress({"execution": update["execution"]})
            return graph.get_state(cfg).values

        return self._run(incident_id, run, None)

    def recover(self, incident_id: str, alert: Alert) -> dict[str, Any]:
        """After a restart: continue an interrupted investigation from its last checkpoint."""
        def continue_(graph, cfg):
            snap = graph.get_state(cfg)
            if not snap.values:            # died before the first checkpoint: start over
                return graph.invoke({"alert": alert}, cfg)
            if snap.interrupts:            # already paused before a fix: show it for approval again
                return {**snap.values, "__interrupt__": snap.interrupts}
            if snap.next:                  # None = continue from the last saved step
                return graph.invoke(None, cfg)
            return snap.values             # finished just before the restart

        return self._run(incident_id, continue_, alert, tag="recover")


def graph_investigator(backend, llm, settings, remediation=None) -> GraphInvestigator:
    return GraphInvestigator(backend, llm, settings, remediation)


def dry_run_investigator(incident_id: str, alert: Alert) -> dict[str, Any]:
    """No LLM, no cluster: exercises only the webhook -> queue -> report path (zero cost)."""
    diagnosis = {"root_cause": f"dry-run: no investigation was performed for {alert.name}.",
                 "culprit_service": alert.service, "category": "unknown", "confidence": 0.0, "evidence": [],
                 "recommended_action": "escalate_to_human", "action_target": alert.service,
                 "rationale": "Dry run: the LLM was not called."}
    return {"diagnosis": diagnosis, "report": f"# Dry run: {alert.name} — {alert.service}\n", "tool_calls": 0,
            "usage": {}, "budget_exhausted": False}


# ---------------------------------------------------------------- FastAPI
def create_app(service: IncidentService, token: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        service.start()
        yield
        service.stop()

    app = FastAPI(title="k8s-incident-agent webhook", lifespan=lifespan)

    def authorize(request: Request) -> None:
        if not token:
            return
        given = request.headers.get("authorization", "")
        if not hmac.compare_digest(given, f"Bearer {token}"):
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    @app.post("/alertmanager")
    async def alertmanager(request: Request) -> dict[str, Any]:
        authorize(request)
        try:
            payload = await request.json()
            decisions = service.ingest(payload)
        except ValueError as e:  # bad JSON or not an Alertmanager payload
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"received": len(decisions), "decisions": decisions}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> HTMLResponse:
        from .ui import PAGE

        # no data in the page itself; it reads /incidents with the token you give it
        return HTMLResponse(PAGE, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                           "Content-Security-Policy": "default-src 'self'; "
                                           "style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
                                           "frame-ancestors 'none'"})

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "queued": service._queue.qsize()}

    @app.get("/incidents")
    def incidents(request: Request) -> list[dict[str, Any]]:
        authorize(request)
        return [i.summary() for i in service.registry.all()]

    @app.get("/incidents/{incident_id}")
    def incident(incident_id: str, request: Request) -> dict[str, Any]:
        authorize(request)
        inc = service.registry.get(incident_id)
        if inc is None:
            raise HTTPException(status_code=404, detail="no such incident")
        return {**inc.summary(), "report": (inc.result or {}).get("report")}

    async def _decision_body(request: Request) -> dict[str, Any]:
        # CSRF guard: a malicious page open in the same browser can POST a plain form or text/plain to
        # localhost, but it cannot send application/json cross-origin without a CORS preflight, which this
        # server never allows. So a decision must arrive as JSON.
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="send the decision as application/json")
        try:
            body = await request.json()
        except ValueError:
            body = {}
        return body if isinstance(body, dict) else {}

    def _decide(incident_id: str, approved: bool, body: dict[str, Any]) -> dict[str, Any]:
        try:
            decision = service.decide(incident_id, approved, by=str(body.get("by", "")), comment=str(body.get("comment", "")))
        except KeyError:
            raise HTTPException(status_code=404, detail="no such incident") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None
        return {"incident_id": incident_id, "decision": decision, "status": "remediating"}

    @app.post("/incidents/{incident_id}/approve")
    async def approve(incident_id: str, request: Request) -> dict[str, Any]:
        authorize(request)
        return _decide(incident_id, True, await _decision_body(request))

    @app.post("/incidents/{incident_id}/reject")
    async def reject(incident_id: str, request: Request) -> dict[str, Any]:
        authorize(request)
        return _decide(incident_id, False, await _decision_body(request))

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(service.metrics.render(), media_type=CONTENT_TYPE_LATEST)

    return app
