"""Choosing which alert to investigate when several are firing at once."""

from __future__ import annotations

from typing import Any

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def pick_alert(alerts: list[dict[str, Any]], service: str | None = None) -> tuple[dict | None, list[dict]]:
    """Returns (the chosen alert, the remaining firing alerts).

    Order: severity first (critical > warning), then the alert that fired earliest —
    it is usually the closest to the root cause.
    """
    firing = [a for a in alerts if a.get("state") == "firing" and a.get("service")]
    if service:
        firing = [a for a in firing if a["service"] == service]
    firing.sort(key=lambda a: (SEVERITY_RANK.get(a.get("severity", ""), 9), a.get("started_at") or ""))
    return (firing[0] if firing else None), firing[1:]
