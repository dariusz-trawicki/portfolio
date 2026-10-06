"""Incident registry: decides which incoming alerts are a new incident and which are echoes of an old one.

Alertmanager may send the same alert many times (repeat_interval, group membership changes),
and one fault usually fires several alerts at once (checkout, payment, frontend...).
Without deduplication the agent would investigate the same fault several times and pay for each.

Decision per alert:
  new         a new incident — needs investigating
  duplicate   the same alert (fingerprint) as in an open incident
  correlated  a different alert, but the same service or a dependency-map neighbour of an open incident
  resolved    the alert went away
  ignored     no `service` label, or a resolved alert we know nothing about

An incident stays open while any of its alerts is firing, and for another `window_minutes`
after the last one resolves. That way a flapping alert (firing -> resolved -> firing)
does not open a new incident every time.

Except for a FINISHED incident (done / failed) that has gone quiet: its investigation is over, so an
alert that fires again afterwards is new evidence, not an echo. It opens a new incident that `follows`
the old one. (Found live: a transient error was diagnosed as noise; 15 minutes later a real fault on
the same service was silently absorbed by that finished incident and never investigated.)

With a store (store.py) every change is written through, and the registry reloads its incidents
on start-up — so a restart of the agent does not lose an incident that waits for approval.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .alertmanager import IncomingAlert
from .alerts import SEVERITY_RANK
from .prompts import neighbours as default_neighbours
from .state import Alert

log = logging.getLogger("incident_agent.incidents")

# queued -> investigating -> done | failed;  queued -> skipped (alerts resolved before its turn came)
# with remediation:  investigating -> awaiting_approval -> remediating -> done | failed
STATUSES = ("queued", "investigating", "awaiting_approval", "remediating", "done", "failed", "skipped")
FINISHED = ("done", "failed")


@dataclass
class Incident:
    id: str
    service: str
    opened_at: datetime
    last_active: datetime
    status: str = "queued"
    alerts: dict[str, Alert] = field(default_factory=dict)       # fingerprint -> alert
    roles: dict[str, str] = field(default_factory=dict)          # fingerprint -> primary | correlated
    active: set[str] = field(default_factory=set)                # fingerprints that are still firing
    resolved_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    duration_s: float | None = None
    awaiting_since: datetime | None = None
    follows: str | None = None        # the finished incident this one recurred after

    def summary(self) -> dict[str, Any]:
        r = self.result or {}
        d = r.get("diagnosis") or {}
        p = r.get("proposal") or {}
        return {
            "id": self.id,
            "service": self.service,
            "status": self.status,
            "opened_at": self.opened_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "alerts": [{"fingerprint": fp, "name": a.name, "service": a.service, "severity": a.severity,
                        "role": self.roles[fp], "firing": fp in self.active}
                       for fp, a in self.alerts.items()],
            "culprit_service": d.get("culprit_service"),
            "root_cause": d.get("root_cause"),
            "confidence": d.get("confidence"),
            "category": d.get("category"),
            "recommended_action": d.get("recommended_action"),
            "duration_s": self.duration_s,
            "error": self.error,
            "proposal": {k: p.get(k) for k in ("action", "target", "executable", "reason", "command")} if p else None,
            "awaiting_since": self.awaiting_since.isoformat() if self.awaiting_since else None,
            "decision": r.get("decision"),
            "execution": r.get("execution"),
            "verification": r.get("verification"),
            "follows": self.follows,
        }

    # ------------------------------------------------------------ persistence
    def to_record(self) -> dict[str, Any]:
        """Everything needed to rebuild the incident after a restart (JSON-safe)."""
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {"id": self.id, "service": self.service, "status": self.status,
                "opened_at": iso(self.opened_at), "last_active": iso(self.last_active),
                "resolved_at": iso(self.resolved_at), "awaiting_since": iso(self.awaiting_since),
                "alerts": {fp: a.model_dump() for fp, a in self.alerts.items()}, "roles": dict(self.roles),
                "active": sorted(self.active), "result": self.result, "error": self.error,
                "duration_s": self.duration_s, "follows": self.follows}

    @classmethod
    def from_record(cls, r: dict[str, Any]) -> "Incident":
        dt = lambda v: datetime.fromisoformat(v) if v else None  # noqa: E731
        return cls(id=r["id"], service=r["service"], status=r["status"], opened_at=dt(r["opened_at"]),
                   last_active=dt(r["last_active"]), resolved_at=dt(r.get("resolved_at")),
                   awaiting_since=dt(r.get("awaiting_since")),
                   alerts={fp: Alert(**a) for fp, a in r.get("alerts", {}).items()}, roles=dict(r.get("roles", {})),
                   active=set(r.get("active", [])), result=r.get("result"), error=r.get("error"),
                   duration_s=r.get("duration_s"), follows=r.get("follows"))


@dataclass(frozen=True)
class Decision:
    kind: str
    incident_id: str | None = None
    fingerprint: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentRegistry:
    def __init__(self, window_minutes: int = 30, *, neighbours: Callable[[str], set[str]] = default_neighbours,
                 clock: Callable[[], datetime] = _utcnow, store=None):
        self.window = timedelta(minutes=window_minutes)
        self._neighbours = neighbours
        self._clock = clock
        self._store = store                # store.IncidentStore or None (memory only)
        self._incidents: dict[str, Incident] = {}
        self._by_fp: dict[str, str] = {}   # fingerprint -> id of the last incident it was assigned to
        self._lock = threading.RLock()
        if store is not None:
            for record in store.load():    # oldest first, so the newest incident wins a shared fingerprint
                inc = Incident.from_record(record)
                self._incidents[inc.id] = inc
                for fp in inc.alerts:
                    self._by_fp[fp] = inc.id

    def _persist(self, inc: Incident) -> None:
        """Write-through. A failing database must not stop alert intake: log it and carry on in memory."""
        if self._store is None:
            return
        try:
            self._store.save(inc.to_record())
        except Exception:
            log.exception("could not persist incident %s", inc.id)

    # ------------------------------------------------------------ queries
    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def all(self) -> list[Incident]:
        with self._lock:
            return sorted(self._incidents.values(), key=lambda i: i.opened_at, reverse=True)

    def _is_open(self, inc: Incident, now: datetime) -> bool:
        if inc.status == "skipped":
            return False  # nobody investigated it; a new alert must open a fresh incident, not join a dead one
        if inc.status in FINISHED and not inc.active:
            return False  # investigated and quiet: whatever fires next is new evidence (see the module docstring)
        return bool(inc.active) or now - inc.last_active < self.window

    def _recent_finished(self, fp: str, service: str, now: datetime) -> Incident | None:
        """The finished, quiet incident that a new alert recurs after (same alert or a related service)."""
        near = self._neighbours(service) | {service}
        cands = [i for i in self._incidents.values()
                 if i.status in FINISHED and not i.active and now - i.last_active < self.window
                 and (fp in i.alerts or i.service in near)]
        return max(cands, key=lambda i: i.last_active) if cands else None

    # ------------------------------------------------------------ input
    def handle(self, incoming: IncomingAlert) -> Decision:
        with self._lock:
            now = self._clock()
            d = self._resolve(incoming, now) if not incoming.firing else self._fire(incoming, now)
            if d.incident_id and d.kind != "ignored":
                self._persist(self._incidents[d.incident_id])
            return d

    def _resolve(self, incoming: IncomingAlert, now: datetime) -> Decision:
        inc = self._incidents.get(self._by_fp.get(incoming.fingerprint, ""))
        if inc is None or incoming.fingerprint not in inc.active:
            return Decision("ignored", inc.id if inc else None, incoming.fingerprint)
        inc.active.discard(incoming.fingerprint)
        inc.last_active = now
        if not inc.active:
            inc.resolved_at = now
        return Decision("resolved", inc.id, incoming.fingerprint)

    def _fire(self, incoming: IncomingAlert, now: datetime) -> Decision:
        alert, fp = incoming.alert, incoming.fingerprint
        if not alert.service:
            return Decision("ignored", None, fp)

        # 1) the same alert in an open incident (including one flapping inside the dedup window)
        known = self._incidents.get(self._by_fp.get(fp, ""))
        if known and self._is_open(known, now):
            self._touch(known, fp, alert, now)
            return Decision("duplicate", known.id, fp)

        # 2) another alert of the same service or of a dependency-map neighbour
        related = self._find_related(alert.service, now)
        if related:
            self._attach(related, fp, alert, now, "correlated")
            return Decision("correlated", related.id, fp)

        # 3) a new incident (possibly a recurrence after a finished one)
        prev = self._recent_finished(fp, alert.service, now)
        inc = Incident(id=f"{alert.service}-{uuid.uuid4().hex[:8]}", service=alert.service,
                       opened_at=now, last_active=now, follows=prev.id if prev else None)
        if prev:
            log.info("%s/%s fired again after finished incident %s -> new incident %s",
                     alert.name, alert.service, prev.id, inc.id)
        self._incidents[inc.id] = inc
        self._attach(inc, fp, alert, now, "primary")
        return Decision("new", inc.id, fp)

    def _find_related(self, service: str, now: datetime) -> Incident | None:
        near = self._neighbours(service) | {service}
        candidates = [i for i in self._incidents.values() if i.service in near and self._is_open(i, now)]
        # the oldest open incident is the closest to the root cause
        return min(candidates, key=lambda i: i.opened_at) if candidates else None

    def _attach(self, inc: Incident, fp: str, alert: Alert, now: datetime, role: str) -> None:
        inc.alerts[fp] = alert
        inc.roles[fp] = role
        self._by_fp[fp] = inc.id
        self._touch(inc, fp, alert, now)

    def _touch(self, inc: Incident, fp: str, alert: Alert, now: datetime) -> None:
        inc.alerts[fp] = alert
        inc.roles.setdefault(fp, "correlated")
        inc.active.add(fp)
        inc.last_active = now
        inc.resolved_at = None

    # ------------------------------------------------------------ lifecycle (worker)
    def claim(self, incident_id: str) -> Alert | None:
        """The worker takes an incident for investigation. None = nothing to investigate (alerts resolved while queued)."""
        with self._lock:
            inc = self._incidents[incident_id]
            if not inc.active:
                inc.status = "skipped"
                self._persist(inc)
                return None
            inc.status = "investigating"
            self._persist(inc)
            return self._primary(inc)

    def _primary(self, inc: Incident) -> Alert:
        """The alert to investigate: the most severe of the firing ones, the earliest on a tie."""
        firing = [inc.alerts[fp] for fp in inc.active]
        return min(firing, key=lambda a: (SEVERITY_RANK.get(a.severity, 9), a.started_at or ""))

    def await_approval(self, incident_id: str, result: dict[str, Any], duration_s: float) -> None:
        """The investigation proposed an automated fix; the graph is paused until a human decides."""
        with self._lock:
            inc = self._incidents[incident_id]
            inc.status, inc.result, inc.duration_s = "awaiting_approval", result, duration_s
            inc.awaiting_since = self._clock()
            self._persist(inc)

    def begin_remediation(self, incident_id: str) -> Incident:
        """Accepts a human decision exactly once. Raises KeyError (unknown id) or ValueError (wrong state)."""
        with self._lock:
            inc = self._incidents[incident_id]
            if inc.status != "awaiting_approval":
                raise ValueError(f"incident {incident_id} is '{inc.status}', not awaiting approval")
            inc.status = "remediating"
            self._persist(inc)
            return inc

    def note(self, incident_id: str, **updates: Any) -> None:
        """Progress of a running remediation (the decision, the executed fix) shown while the graph is still
        busy verifying — with a rollback PR that can be a long wait for a human merge."""
        with self._lock:
            inc = self._incidents[incident_id]
            inc.result = {**(inc.result or {}), **updates}
            self._persist(inc)

    def finish(self, incident_id: str, result: dict[str, Any], duration_s: float | None = None) -> None:
        """duration_s = investigation time; a finished remediation passes None and keeps it."""
        with self._lock:
            inc = self._incidents[incident_id]
            inc.status, inc.result = "done", result
            if duration_s is not None:
                inc.duration_s = duration_s
            self._persist(inc)

    def fail(self, incident_id: str, error: str, duration_s: float) -> None:
        with self._lock:
            inc = self._incidents[incident_id]
            inc.status, inc.error, inc.duration_s = "failed", error, duration_s
            self._persist(inc)
