"""Compacting logs before they reach the model.

A raw OTel document in OpenSearch has dozens of fields (uids, instance.id, versions),
and during an incident the same message repeats dozens of times. What matters for a diagnosis:
when, how severe, which service/pod, the message and how many times. The rest is wasted tokens.
"""

from __future__ import annotations

import re
from typing import Any

# Order = priority: take the first field that exists.
_TIME = ("observedTimestamp", "@timestamp", "timestamp", "time")
_SEVERITY = ("severity.text", "severityText", "level")
_SERVICE = ("resource.service.name", "attributes.service.name", "resource.k8s.deployment.name", "service.name")
_POD = ("resource.k8s.pod.name", "k8s.pod.name")
_BODY = ("body", "message", "attributes.message")
_EXC = ("attributes.exception.message", "exception.message")

# Variable parts of a message (uuid, hex, numbers) — ignored when grouping duplicates.
_VARIABLE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|0x[0-9a-f]+|\d+", re.I)


def flatten(src: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}

    def walk(prefix: str, obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        else:
            flat[prefix] = obj

    walk("", src)
    return flat


def _first(flat: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if flat.get(k) not in (None, ""):
            return str(flat[k])
    return None


def compact_log(src: dict[str, Any], max_body: int = 300) -> dict[str, Any]:
    """One document -> the few fields that carry information."""
    f = flatten(src)
    body = _first(f, _BODY) or ""
    exc = _first(f, _EXC)
    out = {
        "time": _first(f, _TIME),
        "severity": _first(f, _SEVERITY),
        "service": _first(f, _SERVICE),
        "pod": _first(f, _POD),
        "body": body[:max_body],
    }
    if exc and exc.strip() != body.strip():  # don't duplicate when exception == log body
        out["exception"] = exc[:max_body]
    return {k: v for k, v in out.items() if v}


def collapse(entries: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Collapses repeated messages into one entry with a counter.

    Input sorted newest first. Output: groups in order of first (newest) occurrence,
    with `count` and `first_seen` when count > 1.
    """
    groups: dict[tuple, dict[str, Any]] = {}
    for e in entries:
        key = (e.get("service"), e.get("severity"), _VARIABLE.sub("#", e.get("body", "")))
        g = groups.get(key)
        if g is None:
            groups[key] = {**e, "count": 1}
        else:
            g["count"] += 1
            if e.get("time"):
                g["first_seen"] = e["time"]
    out = list(groups.values())[:limit]
    for g in out:
        if g["count"] == 1:
            g.pop("count")
    return out
