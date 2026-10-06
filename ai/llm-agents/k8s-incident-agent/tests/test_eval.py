"""The evaluation loop tested without a cluster or a real LLM: chaos, clock and agent are injected."""

from __future__ import annotations

from pathlib import Path

from incident_agent import eval as ev
from incident_agent.chaos import load_scenarios

SC = load_scenarios()

GOOD = {"culprit_service": "payment", "category": "feature_flag", "recommended_action": "disable_feature_flag"}
ALERT = {"state": "firing", "name": "HighErrorRate", "service": "checkout", "severity": "critical",
         "summary": "errors", "labels": {}, "started_at": "2026-09-29T10:00:00Z"}


class Clock:
    """Fake time: sleep() only advances the clock."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make_env(tmp_path, *, alerts, diagnosis=GOOD, fail_investigate=False, log=None):
    """`alerts(phase)` returns firing alerts for the 'quiet' (before inject) or 'injected' phase."""
    clock, calls = Clock(), []
    state = {"phase": "quiet"}

    def inject(sc):
        calls.append(("inject", sc["id"]))
        state["phase"] = "injected"

    def reset():
        calls.append(("reset",))
        state["phase"] = "quiet"

    def investigate(alert, label):
        calls.append(("investigate", alert.service, label))
        if fail_investigate:
            raise RuntimeError("model API down")
        return {"diagnosis": diagnosis, "report": "# Incident", "tool_calls": 2,
                "usage": {"llm_calls": 3, "input_tokens": 1000, "output_tokens": 200}, "budget_exhausted": False}

    env = ev.EvalEnv(reset=reset, inject=inject, firing_alerts=lambda: alerts(state["phase"]),
                     investigate=investigate, sleep=clock.sleep, clock=clock.now,
                     log=(log or (lambda m: None)))
    cfg = ev.EvalConfig(alert_timeout_s=600, clean_for_s=120, clean_timeout_s=600, poll_s=15, out_dir=tmp_path)
    return env, cfg, calls


def normal(phase):
    return [ALERT] if phase == "injected" else []


def test_score_uses_acceptable_lists():
    exp = SC["payment-failure"]["expected"]
    assert ev.score(GOOD, exp)["correct"]
    assert ev.score({**GOOD, "category": "application_bug"}, exp)["correct"]      # both categories are acceptable
    wrong = ev.score({**GOOD, "culprit_service": "checkout"}, exp)
    assert wrong["culprit"] is False and wrong["correct"] is False and wrong["action"] is True
    assert ev.score({**GOOD, "culprit_service": " Payment "}, exp)["culprit"]       # normalised


def test_happy_path_order_and_metrics(tmp_path):
    env, cfg, calls = make_env(tmp_path, alerts=normal)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "ok" and res.correct
    assert res.tool_calls == 2 and res.input_tokens == 1000 and res.llm_calls == 3
    assert res.time_to_alert_s is not None
    # reset -> inject -> investigate -> reset, in exactly this order
    assert [c[0] for c in calls] == ["reset", "inject", "investigate", "reset"]
    assert calls[2][1] == "checkout"
    assert Path(res.report_path).read_text() == "# Incident"


def test_waits_for_quiet_cluster_before_injecting(tmp_path):
    # after a reset the old alert keeps firing for a while (keep_firing_for)
    seen = {"n": 0}

    def alerts(phase):
        if phase == "quiet":
            seen["n"] += 1
            return [ALERT] if seen["n"] <= 5 else []
        return [ALERT]

    env, cfg, calls = make_env(tmp_path, alerts=alerts)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "ok"
    assert seen["n"] > 5 + cfg.clean_for_s / cfg.poll_s - 1   # a full quiet window is required, not a single clean poll


def test_cluster_never_quiet_skips_run_without_injecting(tmp_path):
    env, cfg, calls = make_env(tmp_path, alerts=lambda phase: [ALERT])
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "dirty_env" and not res.correct
    assert ("inject", "payment-failure") not in calls


def test_alert_never_fires_is_a_miss_and_still_resets(tmp_path):
    env, cfg, calls = make_env(tmp_path, alerts=lambda phase: [])
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "no_alert" and not res.correct
    assert calls[-1] == ("reset",) and "investigate" not in [c[0] for c in calls]


def test_alert_for_other_service_is_ignored(tmp_path):
    other = {**ALERT, "service": "recommendation"}
    env, cfg, _ = make_env(tmp_path, alerts=lambda phase: [other] if phase == "injected" else [])
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])   # alert_service to checkout
    assert res.status == "no_alert"


def test_agent_crash_is_recorded_and_next_run_continues(tmp_path):
    env, cfg, calls = make_env(tmp_path, alerts=normal, fail_investigate=True)
    cfg.repeat = 2
    results = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert [r.status for r in results] == ["error", "error"]
    assert "model API down" in results[0].detail
    assert calls[-1] == ("reset",)


def test_summary_table_and_roundtrip(tmp_path):
    env, cfg, _ = make_env(tmp_path, alerts=normal)
    cfg.repeat = 2
    results = ev.run_eval(env, cfg, [SC["payment-failure"], SC["cart-failure"]])
    # cart-failure alerts for `cart`, not `checkout` -> no_alert
    assert [r.status for r in results] == ["ok", "ok", "no_alert", "no_alert"]
    summary = ev.summarize(results)
    assert summary["scenarios"]["payment-failure"]["correct"] == 2
    assert summary["overall"]["correct"] == 2 and summary["overall"]["runs"] == 4
    table = ev.render_table(results, {"model": "m", "repeat": 2, "started": "now"})
    assert "| `payment-failure` | 2/2 | 2/2 | 2/2 | **2/2**" in table
    assert "| **Total** |" in table and "no_alert" in table

    jpath, mpath = ev.save(results, cfg, {"model": "m", "repeat": 2, "started": "now"})
    loaded, meta = ev.load_results(jpath)
    assert ev.render_table(loaded, meta) == mpath.read_text()


def test_cli_rejects_unknown_scenario():
    from typer.testing import CliRunner

    import incident_agent.cli as cli

    r = CliRunner().invoke(cli.app, ["eval", "run", "--scenario", "nope"])
    assert r.exit_code == 2 and "Unknown scenario" in r.output


# ---------------------------------------------------------------- dirty cluster (lesson from the first full run)
STUCK = {**ALERT, "name": "MemoryNearLimit", "service": "fraud-detection", "severity": "warning"}


def test_dirty_env_names_the_blocking_alert(tmp_path):
    logs = []
    env, cfg, _ = make_env(tmp_path, alerts=lambda phase: [STUCK], log=logs.append)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "dirty_env"
    assert "MemoryNearLimit·fraud-detection" in res.detail
    # the console shows what is firing, but only once (logged on change, not every 15 s)
    assert sum("still firing: MemoryNearLimit·fraud-detection" in m for m in logs) == 1


def test_eval_aborts_after_consecutive_dirty_runs_instead_of_wasting_hours(tmp_path):
    env, cfg, calls = make_env(tmp_path, alerts=lambda phase: [STUCK])
    ids = ["payment-failure", "cart-failure", "bad-image", "currency-oom"]
    results = ev.run_eval(env, cfg, [SC[i] for i in ids])
    assert [r.status for r in results] == ["dirty_env", "dirty_env", "aborted", "aborted"]
    assert sum(c == ("reset",) for c in calls) == 4          # 2 runs × (start + finally), nothing after that
    assert "aborted" in ev.render_table(results)


def test_ignored_background_alert_does_not_block_or_trigger(tmp_path):
    def alerts(phase):
        return [STUCK] + ([ALERT] if phase == "injected" else [])

    env, cfg, _ = make_env(tmp_path, alerts=alerts)
    cfg.ignore_alerts = ("MemoryNearLimit:fraud-detection",)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "ok" and res.correct


def test_ignored_alert_on_the_scenario_service_is_not_picked_as_trigger(tmp_path):
    stale = {**ALERT, "name": "MemoryNearLimit"}           # noise on checkout before anything was injected
    env, cfg, _ = make_env(tmp_path, alerts=lambda phase: [stale])
    cfg.ignore_alerts = ("MemoryNearLimit",)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "no_alert"


def test_is_ignored_patterns():
    assert ev.is_ignored(STUCK, ("MemoryNearLimit",))
    assert ev.is_ignored(STUCK, ("MemoryNearLimit:fraud-detection",))
    assert not ev.is_ignored(STUCK, ("MemoryNearLimit:checkout",))
    assert not ev.is_ignored(STUCK, ())


def test_no_alert_reports_what_fired_elsewhere(tmp_path):
    """The fault fired an alert for another service (and only pending for the right one) — the result must show it."""
    elsewhere = {**ALERT, "name": "HighLatencyP95", "service": "accounting"}
    pending = {**ALERT, "state": "pending", "name": "HighErrorRate", "service": "checkout"}

    def alerts(phase):
        return [elsewhere, pending] if phase == "injected" else []

    env, cfg, _ = make_env(tmp_path, alerts=alerts)
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.status == "no_alert"
    assert "HighLatencyP95·accounting (firing)" in res.detail
    assert "HighErrorRate·checkout (pending)" in res.detail


def test_no_alert_with_nothing_seen_says_none(tmp_path):
    env, cfg, _ = make_env(tmp_path, alerts=lambda phase: [])
    [res] = ev.run_eval(env, cfg, [SC["payment-failure"]])
    assert res.detail.endswith("alerts seen meanwhile: none")
