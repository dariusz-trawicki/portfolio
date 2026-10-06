"""Step 5e: rollback as a PR (no network: GitHub is a small in-memory fake behind httpx.MockTransport)."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import httpx
import pytest
import yaml
from langgraph.types import Command

from incident_agent import gitops, remediation as rem
from incident_agent.backends.fake import FakeBackend
from incident_agent.checkpointing import open_checkpointer
from incident_agent.config import Settings
from incident_agent.graph import build_graph
from incident_agent.state import Alert
from test_graph import DIAG, FIXTURE, ScriptedLLM, ai

REPO, PATH = "dartit/k8s-gitops-demo", "values/otel-demo.yaml"
ALERT = Alert(name="HighErrorRate", service="checkout", severity="critical")


def dump(d) -> str:
    return yaml.safe_dump(d, sort_keys=False)


class FakeGitHub:
    """Just enough of the GitHub REST API; `history` is the values file per commit, oldest first."""

    def __init__(self, history: list[dict], titles: list[str] | None = None):
        self.commits = [{"sha": f"{i:040x}"[::-1][:40].replace(" ", "0"), "html_url": f"https://github.com/{REPO}/commit/{i}",
                         "commit": {"message": (titles or [f"commit {i}"] * len(history))[i]}} for i in range(len(history))]
        self.files = {c["sha"]: dump(h) for c, h in zip(self.commits, history)}
        self.branches = {"main": self.commits[-1]["sha"]}
        self.branch_files: dict[str, str] = {}
        self.prs: dict[int, dict] = {}
        self.calls: list[tuple[str, str]] = []

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle), base_url="https://api.github.com")

    def handle(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path.removeprefix(f"/repos/{REPO}")
        self.calls.append((req.method, path))
        q = dict(req.url.params)
        body = json.loads(req.content) if req.content else {}
        if req.method == "GET" and path == "/commits":
            return httpx.Response(200, json=list(reversed(self.commits))[: int(q["per_page"])])
        if req.method == "GET" and path.startswith("/contents/"):
            ref = q["ref"]
            sha = self.branches.get(ref, ref)
            text = self.branch_files.get(ref) or self.files[sha]
            return httpx.Response(200, json={"content": base64.b64encode(text.encode()).decode(), "sha": f"blob-{sha[:6]}"})
        if req.method == "GET" and path.startswith("/git/ref/heads/"):
            return httpx.Response(200, json={"object": {"sha": self.branches[path.rsplit("/heads/", 1)[1]]}})
        if req.method == "POST" and path == "/git/refs":
            self.branches[body["ref"].removeprefix("refs/heads/")] = body["sha"]
            return httpx.Response(201, json={})
        if req.method == "PUT" and path.startswith("/contents/"):
            assert body["branch"] != "main", "the agent must never write to the base branch"
            self.branch_files[body["branch"]] = base64.b64decode(body["content"]).decode()
            return httpx.Response(200, json={})
        if req.method == "POST" and path == "/pulls":
            n = len(self.prs) + 1
            self.prs[n] = {"number": n, "html_url": f"https://github.com/{REPO}/pull/{n}", "head": body["head"],
                           "state": "open", "merged": False, "body": body["body"], "title": body["title"]}
            return httpx.Response(201, json=self.prs[n])
        if req.method == "GET" and path == "/pulls":
            head = q["head"].split(":", 1)[1]
            return httpx.Response(200, json=[p for p in self.prs.values() if p["head"] == head and p["state"] == "open"])
        if m := re.fullmatch(r"/pulls/(\d+)", path):
            return httpx.Response(200, json=self.prs[int(m.group(1))])
        return httpx.Response(404, json={"message": f"unhandled {req.method} {path}"})


BASE = {"components": {"kafka": {"resources": {"limits": {"memory": "1Gi"}}}, "checkout": {"replicas": 1}}}
BAD_ENV = {"envOverrides": [{"name": "PAYMENT_ADDR", "value": "payment-v2:8080"}]}


def history_with_bad_deploy():
    good = BASE
    bad = {"components": {**BASE["components"], "checkout": {"replicas": 1, **BAD_ENV}}}
    later = {"components": {**bad["components"], "kafka": {"resources": {"limits": {"memory": "2Gi"}}}}}
    return [good, bad, later]       # the newest commit is about kafka; the culprit for checkout is the one before


def rollback_for(gh: FakeGitHub) -> gitops.RollbackPR:
    return gitops.RollbackPR(gitops.GitHub(REPO, "t", client=gh.client()), "main", PATH)


# ---------------------------------------------------------------- planning
def test_plan_finds_the_last_commit_that_changed_the_service_and_restores_only_that_section():
    gh = FakeGitHub(history_with_bad_deploy(), ["bootstrap", "checkout: payment-v2", "kafka: more memory"])
    plan = rollback_for(gh).plan("checkout")
    assert plan.culprit_title == "checkout: payment-v2" and plan.keys == ["envOverrides"]
    restored = yaml.safe_load(plan.new_text)
    assert restored["components"]["checkout"] == {"replicas": 1}                       # the bad env is gone
    assert restored["components"]["kafka"]["resources"]["limits"]["memory"] == "2Gi"   # unrelated newer change kept


def test_the_pr_changes_only_the_lines_of_the_reverted_section():
    """A real values file has many keys; the PR must not reorder or rewrite any of them (found live: the first
    version sorted every key alphabetically, so the PR diff touched ~100 unrelated lines)."""
    import difflib

    big = {"components": {"kafka": {"resources": {"limits": {"memory": "1Gi"}}}, "agent": {"enabled": False},
                          "checkout": {"replicas": 1}},
           "prometheus": {"zeta": 1, "alpha": {"b": 2, "a": 1}}, "grafana": {"x": 1}}
    bad = {**big, "components": {**big["components"], "checkout": {"replicas": 1, **BAD_ENV}}}
    gh = FakeGitHub([big, bad], ["bootstrap", "bad deploy"])
    plan = rollback_for(gh).plan("checkout")
    before, after = dump(bad).splitlines(), plan.new_text.splitlines()
    changed = [l for l in difflib.unified_diff(before, after, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    assert changed == ["-    envOverrides:", "-    - name: PAYMENT_ADDR", "-      value: payment-v2:8080"], changed


def test_a_section_that_did_not_exist_before_is_removed():
    gh = FakeGitHub([{"components": {}}, {"components": {"checkout": BAD_ENV}}])
    restored = yaml.safe_load(rollback_for(gh).plan("checkout").new_text)
    assert "checkout" not in restored["components"]


def test_no_recent_change_in_git_means_drift_and_nothing_to_revert():
    gh = FakeGitHub(history_with_bad_deploy())
    with pytest.raises(gitops.NothingToRevert, match="outside Git"):
        rollback_for(gh).plan("payment")


def test_a_repo_with_one_commit_has_nothing_to_revert_to():
    with pytest.raises(gitops.NothingToRevert, match="fewer than 2"):
        rollback_for(FakeGitHub([BASE])).plan("checkout")


# ---------------------------------------------------------------- opening the PR
def test_pr_goes_to_an_agent_branch_never_to_main_and_carries_the_diff():
    gh = FakeGitHub(history_with_bad_deploy(), ["bootstrap", "checkout: payment-v2", "kafka"])
    rb = rollback_for(gh)
    pr = rb.open(rb.plan("checkout"), why="HighErrorRate")
    assert pr["branch"].startswith("incident-agent/revert-checkout-") and not pr["reused"]
    assert pr["branch"] in gh.branch_files and "main" not in gh.branch_files
    assert "checkout: payment-v2" in gh.prs[1]["title"] and "HighErrorRate" in gh.prs[1]["body"]
    assert "PAYMENT_ADDR" not in gh.branch_files[pr["branch"]]


def test_a_second_approval_reuses_the_open_pr():
    gh = FakeGitHub(history_with_bad_deploy())
    rb = rollback_for(gh)
    first, second = rb.open(rb.plan("checkout")), rb.open(rb.plan("checkout"))
    assert second["reused"] and second["number"] == first["number"] and len(gh.prs) == 1


def test_github_errors_are_reported_not_swallowed():
    gh = FakeGitHub(history_with_bad_deploy())
    bad = gitops.RollbackPR(gitops.GitHub("someone/else", "t", client=gh.client()), "main", PATH)
    with pytest.raises(RuntimeError, match="GitHub GET"):
        bad.plan("checkout")


# ---------------------------------------------------------------- waiting for the human merge
class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def wait(gh, pr, timeout=600, on_poll=None):
    clock = Clock()

    def sleep(s):
        clock.sleep(s)
        if on_poll:
            on_poll(clock.t)

    return gitops.wait_for_merge(gitops.GitHub(REPO, "t", client=gh.client()), pr, timeout_s=timeout, poll_s=30,
                                 sleep=sleep, clock=clock.now)


def opened(gh):
    rb = rollback_for(gh)
    return rb.open(rb.plan("checkout"))


def test_merge_is_detected():
    gh = FakeGitHub(history_with_bad_deploy())
    pr = opened(gh)
    out = wait(gh, pr, on_poll=lambda t: gh.prs[1].update(merged=True, state="closed") if t >= 90 else None)
    assert out == {"merged": True, "after_s": 90.0}


def test_closing_without_merging_ends_the_wait_with_an_explanation():
    gh = FakeGitHub(history_with_bad_deploy())
    pr = opened(gh)
    gh.prs[1]["state"] = "closed"
    out = wait(gh, pr)
    assert out["merged"] is False and "closed without merging" in out["detail"]


def test_not_merged_in_time_times_out():
    gh = FakeGitHub(history_with_bad_deploy())
    out = wait(gh, opened(gh), timeout=120)
    assert out["merged"] is False and "not merged within 2 min" in out["detail"]


# ---------------------------------------------------------------- executor + graph
class History:
    """Cluster side: two revisions, so the generic rollback validation passes."""

    def rollout_history(self, service):
        return [{"revision": "1", "images": {service: "x:1"}}, {"revision": "2", "images": {service: "x:1"}}]


def executor(gh):
    return gitops.GitOpsExecutor("otel-demo", History(), rollback_for(gh))


def test_proposal_shows_the_commit_that_will_be_reverted():
    gh = FakeGitHub(history_with_bad_deploy(), ["bootstrap", "checkout: payment-v2", "kafka"])
    p = rem.propose(DIAG, executor(gh))
    assert p.executable and "checkout: payment-v2" in p.command and "a human merges it" in p.command
    assert gh.prs == {}                                  # proposing opens nothing


def test_drift_makes_the_rollback_not_executable_with_a_clear_reason():
    gh = FakeGitHub(history_with_bad_deploy())
    p = rem.propose(DIAG.model_copy(update={"action_target": "payment"}), executor(gh))
    assert not p.executable and "outside Git" in p.reason


def test_github_outage_at_proposal_time_downgrades_to_escalation():
    gh = FakeGitHub(history_with_bad_deploy())
    ex = gitops.GitOpsExecutor("otel-demo", History(), gitops.RollbackPR(
        gitops.GitHub("someone/else", "t", client=gh.client()), "main", PATH))
    p = rem.propose(DIAG, ex)
    assert not p.executable and "cannot read the GitOps repository" in p.reason


def test_feature_flag_fixes_do_not_touch_git(monkeypatch):
    import incident_agent.chaos as chaos

    calls = []
    monkeypatch.setattr(chaos, "read_flags", lambda ns: {"flags": {"paymentFailure": {"defaultVariant": "50%"}}})
    monkeypatch.setattr(chaos, "set_flag", lambda ns, f, v: calls.append((f, v)))
    gh = FakeGitHub(history_with_bad_deploy())
    assert executor(gh).execute("disable_feature_flag", "paymentFailure") == "flag paymentFailure set to off"
    assert calls == [("paymentFailure", "off")] and gh.calls == []


def graph_run(tmp_path, gh, merge_result, verified):
    def verify(alert):
        verified.append(alert.service)
        return {"recovered": True, "after_s": 150.0, "checked": "HighErrorRate · checkout"}

    r = rem.Remediation(executor(gh), verify, await_merge=lambda pr: merge_result)
    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("That is enough.")]), checkpointer=cp, remediation=r)
        cfg = {"configurable": {"thread_id": "inc-1"}}
        graph.invoke({"alert": ALERT.model_copy()}, cfg)
        return graph.invoke(Command(resume=rem.make_decision(True, by="dartit")), cfg)


def test_approved_rollback_opens_a_pr_waits_for_the_merge_then_verifies(tmp_path):
    gh, verified = FakeGitHub(history_with_bad_deploy()), []
    final = graph_run(tmp_path, gh, {"merged": True, "after_s": 240.0}, verified)
    assert len(gh.prs) == 1 and final["execution"]["pr"]["number"] == 1
    assert "pull/1" in final["execution"]["output"]
    assert verified == ["checkout"] and final["verification"]["recovered"] is True
    assert final["verification"]["merge_wait_s"] == 240.0


def test_unmerged_pr_is_not_reported_as_recovered_and_is_never_verified(tmp_path):
    gh, verified = FakeGitHub(history_with_bad_deploy()), []
    final = graph_run(tmp_path, gh, {"merged": False, "after_s": 1800.0, "detail": "PR #1 was not merged within 30 min"}, verified)
    assert verified == [] and final["verification"]["recovered"] is False
    assert "not merged" in final["verification"]["detail"]


def test_without_approval_no_pr_exists(tmp_path):
    gh = FakeGitHub(history_with_bad_deploy())
    with open_checkpointer(str(tmp_path / "cp.sqlite")) as cp:
        graph = build_graph(FakeBackend.from_file(FIXTURE), ScriptedLLM([ai("That is enough.")]), checkpointer=cp,
                            remediation=rem.Remediation(executor(gh), lambda a: {}))
        graph.invoke({"alert": ALERT.model_copy()}, {"configurable": {"thread_id": "inc-2"}})
    assert gh.prs == {} and not any(m in ("POST", "PUT") for m, _ in gh.calls)


# ---------------------------------------------------------------- configuration and bootstrap
def test_gitops_mode_requires_repo_and_token():
    with pytest.raises(ValueError, match="GITOPS_REPO"):
        gitops.gitops_remediation(None, Settings(gitops_repo="", gitops_token=None))
    r = gitops.gitops_remediation(History(), Settings(gitops_repo=REPO, gitops_token="t"))
    assert isinstance(r.executor, gitops.GitOpsExecutor) and r.await_merge is not None


def test_break_service_makes_a_change_the_plan_can_revert():
    broken = gitops.break_service(dump(BASE))
    assert yaml.safe_load(broken)["components"]["checkout"]["envOverrides"] == BAD_ENV["envOverrides"]
    gh = FakeGitHub([BASE, yaml.safe_load(broken)], ["bootstrap", "bad deploy"])
    assert yaml.safe_load(rollback_for(gh).plan("checkout").new_text) == BASE
    assert gitops.break_service(broken) == broken                       # idempotent


def test_merge_values_follows_helm_semantics():
    a = {"x": {"keep": 1, "over": 1, "list": [1, 2]}}
    b = {"x": {"over": 2, "list": [3]}, "y": 1}
    assert gitops.merge_values(a, b) == {"x": {"keep": 1, "over": 2, "list": [3]}, "y": 1}


def test_bootstrap_writes_a_valid_application_that_reads_values_from_the_repo(tmp_path):
    values = Path(__file__).resolve().parents[1] / "infra" / "otel-demo-values.yaml"
    files = gitops.bootstrap(tmp_path, "https://github.com/dartit/k8s-gitops-demo", [values], "0.42.1")
    assert {f.name for f in files} == {"otel-demo.yaml", "application.yaml", "README.md"}
    app = yaml.safe_load((tmp_path / "argocd" / "application.yaml").read_text())
    chart, repo = app["spec"]["sources"]
    assert chart["chart"] == "opentelemetry-demo" and chart["targetRevision"] == "0.42.1"
    assert chart["helm"]["valueFiles"] == ["$values/values/otel-demo.yaml"] and repo["ref"] == "values"
    assert "components" in yaml.safe_load((tmp_path / "values" / "otel-demo.yaml").read_text())
