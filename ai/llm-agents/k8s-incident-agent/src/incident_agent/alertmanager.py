"""Parsing the Alertmanager webhook payload (version 4) into agent alerts.

Alertmanager sends one request per alert group; each alert in the group has its own
status (firing/resolved) and fingerprint — a stable identifier of its label set.
Format reference: https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .state import Alert


@dataclass(frozen=True)
class IncomingAlert:
    fingerprint: str
    firing: bool
    alert: Alert


def _fingerprint(raw: dict[str, Any]) -> str:
    """Alertmanager sends a fingerprint since 0.19; if it is missing we compute our own from the labels."""
    fp = raw.get("fingerprint")
    if fp:
        return str(fp)
    labels = json.dumps(raw.get("labels") or {}, sort_keys=True)
    return hashlib.sha1(labels.encode()).hexdigest()[:16]


def _started_at(raw: dict[str, Any]) -> str | None:
    ts = raw.get("startsAt")
    # "0001-01-01T00:00:00Z" is Go's zero time, i.e. "no time"
    return None if not ts or str(ts).startswith("0001-") else str(ts)


def parse_webhook(payload: Any) -> list[IncomingAlert]:
    """Turns a v4 payload into a list of alerts. Raises ValueError when it is not an Alertmanager payload."""
    if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
        raise ValueError("not an Alertmanager webhook payload: missing 'alerts' list")
    out = []
    for raw in payload["alerts"]:
        if not isinstance(raw, dict):
            raise ValueError("'alerts' must contain objects")
        labels = {str(k): str(v) for k, v in (raw.get("labels") or {}).items()}
        notes = raw.get("annotations") or {}
        alert = Alert(
            name=labels.get("alertname", "unknown"),
            service=labels.get("service", "").strip().lower(),
            severity=labels.get("severity", "warning"),
            summary=str(notes.get("summary") or notes.get("description") or ""),
            labels=labels,
            started_at=_started_at(raw),
        )
        out.append(IncomingAlert(fingerprint=_fingerprint(raw), firing=raw.get("status") == "firing", alert=alert))
    return out
