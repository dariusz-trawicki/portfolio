"""Evaluation harness: runs the agent against every injected fault and scores the result.

For each scenario (and each repetition):

    reset -> wait for a quiet cluster -> inject -> wait for a firing alert
          -> investigation -> score against `expected` -> reset

Scoring compares the structured `Diagnosis` with the scenario's ground truth:
  * culprit  - `culprit_service` equals `expected.culprit_service`
  * category - `category` is in `expected.category` (list of acceptable values)
  * action   - `recommended_action` is in `expected.action`
A run is "correct" when all three match.

Every side effect (chaos, clock, alert polling, running the agent) is injected through
`EvalEnv`, so the whole loop is tested without a cluster and without a real LLM.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .alerts import pick_alert
from .state import Alert


# ---------------------------------------------------------------- scoring
def score(diagnosis: dict[str, Any], expected: dict[str, Any]) -> dict[str, bool]:
    culprit = diagnosis["culprit_service"].strip().lower() == expected["culprit_service"]
    category = diagnosis["category"] in expected["category"]
    action = diagnosis["recommended_action"] in expected["action"]
    return {"culprit": culprit, "category": category, "action": action,
            "correct": culprit and category and action}


# ---------------------------------------------------------------- results
@dataclass
class RunResult:
    scenario: str
    repeat: int
    # ok | no_alert | dirty_env | error | aborted
    status: str
    detail: str = ""
    culprit: bool = False
    category: bool = False
    action: bool = False
    correct: bool = False
    diagnosis: dict[str, Any] | None = None
    time_to_alert_s: float | None = None
    investigate_s: float | None = None
    tool_calls: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    budget_exhausted: bool = False
    report_path: str | None = None


@dataclass
class EvalEnv:
    """Everything the loop touches in the outside world."""

    reset: Callable[[], Any]
    inject: Callable[[dict], Any]
    firing_alerts: Callable[[], list[dict]]
    # (alert, run_label) -> {"diagnosis": dict, "report": str, "tool_calls": int, "usage": dict, "budget_exhausted": bool}
    investigate: Callable[[Alert, str], dict[str, Any]]
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    log: Callable[[str], None] = print


@dataclass
class EvalConfig:
    repeat: int = 1
    alert_timeout_s: float = 15 * 60      # how long to wait for the alert after injecting the fault
    clean_for_s: float = 5 * 60           # this long without firing alerts = "quiet" (= keep_firing_for)
    clean_timeout_s: float = 20 * 60      # give up waiting for a quiet cluster after this many seconds
    poll_s: float = 15.0
    out_dir: Path = field(default_factory=lambda: Path("reports/eval"))
    # Background-noise alerts that neither block "quiet" nor may trigger a run: "Name" or "Name:service".
    ignore_alerts: tuple[str, ...] = ()
    # Abort the evaluation after this many dirty_env runs in a row: the cluster will not calm down
    # on its own, and every further wait wastes another 20 minutes.
    max_dirty_in_a_row: int = 2


# ---------------------------------------------------------------- waiting
def is_ignored(alert: dict, patterns: tuple[str, ...]) -> bool:
    name, service = alert.get("name"), alert.get("service")
    return any(p == name or p == f"{name}:{service}" for p in patterns)


def describe(alerts: list[dict]) -> str:
    return ", ".join(sorted({f"{a.get('name')}·{a.get('service') or '?'}" for a in alerts}))


def _relevant(env: EvalEnv, cfg: EvalConfig) -> list[dict]:
    return [a for a in env.firing_alerts() if not is_ignored(a, cfg.ignore_alerts)]


def wait_until_quiet(env: EvalEnv, cfg: EvalConfig) -> list[dict]:
    """Waits until no alert (except ignored ones) has been firing for `clean_for_s` in a row.

    Returns [] on success and, on timeout, the alerts that were still firing,
    so the results show WHAT blocked the evaluation.
    """
    start = env.clock()
    quiet_since: float | None = None
    firing: list[dict] = []
    last_seen = ""
    while env.clock() - start < cfg.clean_timeout_s:
        firing = [a for a in _relevant(env, cfg) if a.get("state") == "firing"]
        now = env.clock()
        if firing:
            quiet_since = None
            seen = describe(firing)
            if seen != last_seen:  # log only changes so we don't flood the console
                env.log(f"  still firing: {seen}")
                last_seen = seen
        else:
            quiet_since = quiet_since if quiet_since is not None else now
            if now - quiet_since >= cfg.clean_for_s:
                return []
        env.sleep(cfg.poll_s)
    return firing or [{"name": "flapping", "service": "alerts came and went; no full quiet window"}]


def wait_for_alert(env: EvalEnv, cfg: EvalConfig, service: str, seen: dict[str, str] | None = None) -> dict | None:
    """Waits for a `firing` alert for `service`.

    `seen` (optional) collects every other alert that showed up meanwhile
    ("Name·service" -> furthest state: pending < firing). On no_alert this tells whether the fault
    fired an alert elsewhere (another service), only reached pending, or nothing at all —
    three different fixes.
    """
    start = env.clock()
    while env.clock() - start < cfg.alert_timeout_s:
        current = _relevant(env, cfg)
        if seen is not None:
            for a in current:
                key = f"{a.get('name')}·{a.get('service') or '?'}"
                if seen.get(key) != "firing":
                    seen[key] = a.get("state") or "?"
        alert, _ = pick_alert(current, service)
        if alert is not None:
            return alert
        env.sleep(cfg.poll_s)
    return None


# ---------------------------------------------------------------- loop
def run_one(env: EvalEnv, cfg: EvalConfig, scenario: dict, repeat: int) -> RunResult:
    sid = scenario["id"]
    res = RunResult(scenario=sid, repeat=repeat, status="error")
    try:
        env.log(f"[{sid} #{repeat}] reset + waiting for a quiet cluster")
        env.reset()
        blocking = wait_until_quiet(env, cfg)
        if blocking:
            res.status = "dirty_env"
            res.detail = f"alerts kept firing after reset: {describe(blocking)}; run skipped"
            return res

        env.log(f"[{sid} #{repeat}] inject")
        env.inject(scenario)
        t0 = env.clock()
        seen: dict[str, str] = {}
        picked = wait_for_alert(env, cfg, scenario["alert_service"], seen)
        if picked is None:
            res.status = "no_alert"
            others = ", ".join(f"{k} ({v})" for k, v in sorted(seen.items())) or "none"
            res.detail = (f"no firing alert for {scenario['alert_service']} within {cfg.alert_timeout_s:.0f}s; "
                          f"alerts seen meanwhile: {others}")
            return res
        res.time_to_alert_s = round(env.clock() - t0, 1)

        alert = Alert(name=picked["name"], service=picked["service"], severity=picked["severity"],
                      summary=picked["summary"], labels=picked["labels"], started_at=picked["started_at"])
        env.log(f"[{sid} #{repeat}] investigating {alert.name} · {alert.service}")
        t1 = env.clock()
        out = env.investigate(alert, f"{sid}-{repeat}")
        res.investigate_s = round(env.clock() - t1, 1)

        res.diagnosis = out["diagnosis"]
        res.__dict__.update(score(out["diagnosis"], scenario["expected"]))
        usage = out.get("usage", {})
        res.tool_calls = out.get("tool_calls", 0)
        res.llm_calls = usage.get("llm_calls", 0)
        res.input_tokens = usage.get("input_tokens", 0)
        res.output_tokens = usage.get("output_tokens", 0)
        res.budget_exhausted = bool(out.get("budget_exhausted"))
        if out.get("report"):
            path = cfg.out_dir / f"{sid}-{repeat}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out["report"])
            res.report_path = str(path)
        res.status = "ok"
        return res
    except Exception as e:  # one broken run must not kill a multi-hour evaluation
        res.status, res.detail = "error", f"{type(e).__name__}: {str(e)[:300]}"
        return res
    finally:
        try:
            env.reset()
        except Exception as e:
            env.log(f"[{sid} #{repeat}] WARNING: final reset failed: {e}")


def run_eval(env: EvalEnv, cfg: EvalConfig, scenarios: list[dict]) -> list[RunResult]:
    results: list[RunResult] = []
    dirty_in_a_row = 0
    for sc in scenarios:
        for r in range(1, cfg.repeat + 1):
            if cfg.max_dirty_in_a_row and dirty_in_a_row >= cfg.max_dirty_in_a_row:
                results.append(RunResult(scenario=sc["id"], repeat=r, status="aborted",
                                         detail=f"not run: {dirty_in_a_row} dirty_env runs in a row"))
                continue
            res = run_one(env, cfg, sc, r)
            dirty_in_a_row = dirty_in_a_row + 1 if res.status == "dirty_env" else 0
            if dirty_in_a_row == cfg.max_dirty_in_a_row:
                env.log(f"ABORTING: the cluster did not get quiet {dirty_in_a_row} times in a row ({res.detail}). "
                        "Fix the environment or pass --ignore-alert, then re-run the remaining scenarios with -s.")
            env.log(f"[{sc['id']} #{r}] {res.status}" + (" · correct" if res.correct else "") +
                    (f" · {res.detail}" if res.detail else ""))
            results.append(res)
    return results


# ---------------------------------------------------------------- output
def _frac(k: int, n: int) -> str:
    return f"{k}/{n}"


def summarize(results: list[RunResult]) -> dict[str, Any]:
    """Aggregates per scenario and overall. Runs that got no verdict from the agent
    (no_alert, dirty_env, error, aborted) count as misses: the metric is end-to-end."""
    def agg(rs: list[RunResult]) -> dict[str, Any]:
        ok = [r for r in rs if r.status == "ok"]
        n = len(rs)
        avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
        return {
            "runs": n,
            "completed": len(ok),
            "culprit": sum(r.culprit for r in rs),
            "category": sum(r.category for r in rs),
            "action": sum(r.action for r in rs),
            "correct": sum(r.correct for r in rs),
            "avg_time_to_alert_s": avg([r.time_to_alert_s for r in ok if r.time_to_alert_s is not None]),
            "avg_investigate_s": avg([r.investigate_s for r in ok if r.investigate_s is not None]),
            "avg_tool_calls": avg([r.tool_calls for r in ok]),
            "avg_tokens": avg([r.input_tokens + r.output_tokens for r in ok]),
        }

    by_scenario: dict[str, list[RunResult]] = {}
    for r in results:
        by_scenario.setdefault(r.scenario, []).append(r)
    return {"overall": agg(results), "scenarios": {sid: agg(rs) for sid, rs in by_scenario.items()}}


def render_table(results: list[RunResult], meta: dict[str, Any] | None = None) -> str:
    s = summarize(results)
    fmt = lambda v, unit="": "–" if v is None else f"{v:,.0f}{unit}"  # noqa: E731
    lines = []
    if meta:
        lines.append(f"_Model: `{meta.get('model')}` · repeats per scenario: {meta.get('repeat')} · "
                     f"{meta.get('started')}_\n")
    lines += [
        "| Scenario | Culprit | Category | Action | All correct | Time to alert | Investigation | Tool calls | Tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for sid, a in s["scenarios"].items():
        n = a["runs"]
        lines.append(
            f"| `{sid}` | {_frac(a['culprit'], n)} | {_frac(a['category'], n)} | {_frac(a['action'], n)} | "
            f"**{_frac(a['correct'], n)}** | {fmt(a['avg_time_to_alert_s'], ' s')} | "
            f"{fmt(a['avg_investigate_s'], ' s')} | {fmt(a['avg_tool_calls'])} | {fmt(a['avg_tokens'])} |"
        )
    o = s["overall"]
    n = o["runs"]
    lines.append(
        f"| **Total** | **{_frac(o['culprit'], n)}** | **{_frac(o['category'], n)}** | **{_frac(o['action'], n)}** | "
        f"**{_frac(o['correct'], n)}** | {fmt(o['avg_time_to_alert_s'], ' s')} | "
        f"{fmt(o['avg_investigate_s'], ' s')} | {fmt(o['avg_tool_calls'])} | {fmt(o['avg_tokens'])} |"
    )
    bad = [r for r in results if r.status != "ok"]
    if bad:
        lines.append("\nRuns without a verdict (counted as misses):\n")
        lines += [f"- `{r.scenario}` #{r.repeat}: {r.status} — {r.detail}" for r in bad]
    exhausted = [r for r in results if r.budget_exhausted]
    if exhausted:
        lines.append("\nTool budget exhausted in: " + ", ".join(f"`{r.scenario}` #{r.repeat}" for r in exhausted))
    return "\n".join(lines) + "\n"


def save(results: list[RunResult], cfg: EvalConfig, meta: dict[str, Any]) -> tuple[Path, Path]:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    jpath, mpath = cfg.out_dir / "results.json", cfg.out_dir / "results.md"
    jpath.write_text(json.dumps(
        {"meta": meta, "summary": summarize(results), "runs": [asdict(r) for r in results]},
        indent=2, ensure_ascii=False))
    mpath.write_text(render_table(results, meta))
    return jpath, mpath


def load_results(path: Path) -> tuple[list[RunResult], dict[str, Any]]:
    data = json.loads(path.read_text())
    return [RunResult(**r) for r in data["runs"]], data.get("meta", {})


def new_out_dir(base: Path) -> Path:
    return base / f"{datetime.now():%Y%m%d-%H%M%S}"
