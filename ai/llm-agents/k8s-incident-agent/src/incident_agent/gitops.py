"""Step 5e: rollback as a pull request that ArgoCD applies (GitOps) instead of `kubectl rollout undo`.

Why: with ArgoCD the Git repository is the source of truth. A `kubectl rollout undo` is drift that the next
sync can silently undo, and it leaves no review trail. A rollback PR is reviewable, auditable and reversible
(revert the PR), and Git history records who approved what.

What the PR contains: the agent finds the most recent commit that changed `components.<service>` in the values
file (a bad image tag, env var, resource limit... all live in that one section) and restores the section to
its state before that commit. That works for every kind of change, and the human sees WHICH commit is being
undone on the approval page, before approving. If Git shows no recent change to the service, the fault was
applied outside Git (e.g. `kubectl set env`): a PR cannot fix that, so the proposal is not automated.

The flow keeps the rule "the agent never fixes anything on its own" and adds a SECOND human gate:

    approve on the page (human #1)  ->  agent opens the PR  (the only write)
    merge the PR in GitHub (human #2)  ->  ArgoCD syncs  ->  the verifier watches the alert / fast probe

What the agent may write: one branch `incident-agent/revert-*` and one PR in the GitOps repository. It never
writes to the base branch (enforced here, and the token should not be allowed to either: protect `main`).
Feature-flag fixes are runtime state, not Git state, so they still go through the flagd-ui API.
"""

from __future__ import annotations

import base64
import copy
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from .config import Settings
from .remediation import (Executor, LiveExecutor, Remediation, make_probe, verify_recovery)

BRANCH_PREFIX = "incident-agent/"
DEFAULT_IMAGE_REPOSITORY = "ghcr.io/open-telemetry/demo"   # chart default (values.yaml: default.image.repository)


# ---------------------------------------------------------------- pure helpers (no I/O)
COMMITS_TO_SCAN = 10      # how far back in the values file's history we look for the culprit


def section(values: dict[str, Any] | None, service: str) -> Any:
    return ((values or {}).get("components") or {}).get(service)


def changed_keys(now: Any, before: Any) -> list[str]:
    """Which settings of the service section differ, e.g. ['envOverrides', 'imageOverride']."""
    now, before = now if isinstance(now, dict) else {}, before if isinstance(before, dict) else {}
    return sorted(k for k in set(now) | set(before) if now.get(k) != before.get(k))


def restore_section(values: dict[str, Any], service: str, good: Any) -> dict[str, Any]:
    """Copy of `values` where components.<service> is `good` (absent -> the key is removed)."""
    out = copy.deepcopy(values)      # NOT a dump/load round trip: safe_dump sorts keys and rewrites the whole file
    comps = out.setdefault("components", {})
    if good is None:
        comps.pop(service, None)
    else:
        comps[service] = good
    return out


def merge_values(*docs: dict[str, Any]) -> dict[str, Any]:
    """Helm semantics for several -f files: maps merge recursively, everything else (lists too) is replaced."""
    out: dict[str, Any] = {}
    for doc in docs:
        for k, v in (doc or {}).items():
            out[k] = merge_values(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# ---------------------------------------------------------------- GitHub
class GitHub:
    """The few REST calls the agent needs. Everything goes through one httpx client (mockable in tests)."""

    def __init__(self, repo: str, token: str, api_url: str = "https://api.github.com",
                 client: httpx.Client | None = None):
        self.repo = repo
        self.http = client or httpx.Client(
            base_url=api_url.rstrip("/"), timeout=20,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})

    def _req(self, method: str, path: str, **kw) -> Any:
        r = self.http.request(method, f"/repos/{self.repo}{path}", **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub {method} {path} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else {}

    def get_file(self, path: str, ref: str) -> tuple[str, str]:
        d = self._req("GET", f"/contents/{path}", params={"ref": ref})
        return base64.b64decode(d["content"]).decode(), d["sha"]

    def list_commits(self, path: str, ref: str, limit: int = COMMITS_TO_SCAN) -> list[dict[str, Any]]:
        """Newest first. Only commits that touched `path`."""
        return self._req("GET", "/commits", params={"path": path, "sha": ref, "per_page": limit})

    def branch_sha(self, branch: str) -> str:
        return self._req("GET", f"/git/ref/heads/{branch}")["object"]["sha"]

    def create_branch(self, branch: str, sha: str) -> None:
        self._req("POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha})

    def put_file(self, path: str, text: str, message: str, branch: str, sha: str) -> None:
        self._req("PUT", f"/contents/{path}", json={
            "message": message, "branch": branch, "sha": sha,
            "content": base64.b64encode(text.encode()).decode()})

    def open_pr(self, title: str, body: str, head: str, base: str) -> dict[str, Any]:
        return self._req("POST", "/pulls", json={"title": title, "body": body, "head": head, "base": base})

    def find_open_pr(self, head: str) -> dict[str, Any] | None:
        owner = self.repo.split("/")[0]
        found = self._req("GET", "/pulls", params={"state": "open", "head": f"{owner}:{head}"})
        return found[0] if found else None

    def get_pr(self, number: int) -> dict[str, Any]:
        return self._req("GET", f"/pulls/{number}")

    def can_read(self, path: str, ref: str) -> str:
        self.get_file(path, ref)
        return f"{self.repo}:{path}@{ref}"


# ---------------------------------------------------------------- planning and opening the PR
class NothingToRevert(RuntimeError):
    """Git has no recent change to the service section: the fault did not come from Git."""


@dataclass
class RevertPlan:
    service: str
    culprit_sha: str
    culprit_title: str
    culprit_url: str
    keys: list[str]
    new_text: str
    file_sha: str

    @property
    def summary(self) -> str:
        return f"revert {self.culprit_sha[:7]} \"{self.culprit_title}\" (changes {', '.join(self.keys)})"


@dataclass
class RollbackPR:
    gh: GitHub
    base: str
    values_path: str

    def plan(self, service: str) -> RevertPlan:
        commits = self.gh.list_commits(self.values_path, self.base)
        if len(commits) < 2:
            raise NothingToRevert(f"{self.values_path} has fewer than 2 commits on '{self.base}' — nothing to revert to")
        versions = [yaml.safe_load(self.gh.get_file(self.values_path, c["sha"])[0]) or {} for c in commits]
        for i in range(len(commits) - 1):
            now, before = section(versions[i], service), section(versions[i + 1], service)
            if now != before:                        # commits[i] is the newest commit that changed this service
                head_text, head_sha = self.gh.get_file(self.values_path, self.base)
                good = restore_section(yaml.safe_load(head_text) or {}, service, before)
                c = commits[i]
                return RevertPlan(
                    service=service, culprit_sha=c["sha"], culprit_url=c.get("html_url", ""),
                    culprit_title=(c.get("commit", {}).get("message") or "").splitlines()[0][:80],
                    keys=changed_keys(now, before) or ["(section added/removed)"],
                    new_text=yaml.safe_dump(good, sort_keys=False, default_flow_style=False), file_sha=head_sha)
        raise NothingToRevert(f"no change to components.{service} in the last {len(commits)} commits of "
                              f"{self.values_path} — the fault was applied outside Git (drift), a PR cannot undo it")

    def open(self, plan: RevertPlan, why: str = "") -> dict[str, Any]:
        branch = f"{BRANCH_PREFIX}revert-{plan.service}-{plan.culprit_sha[:7]}"
        if branch == self.base or not branch.startswith(BRANCH_PREFIX):
            raise RuntimeError(f"refusing to write to branch '{branch}'")
        existing = self.gh.find_open_pr(branch)            # idempotent: a second approval reuses the PR
        if existing:
            return {"number": existing["number"], "url": existing["html_url"], "branch": branch, "reused": True}
        title = f"rollback({plan.service}): revert {plan.culprit_sha[:7]} {plan.culprit_title}"
        self.gh.create_branch(branch, self.gh.branch_sha(self.base))
        self.gh.put_file(self.values_path, plan.new_text, title, branch, plan.file_sha)
        body = (f"Opened by the incident agent after a human approved this rollback.\n\n"
                f"- service: `{plan.service}`\n- undoes: {plan.culprit_url or plan.culprit_sha} "
                f"(`components.{plan.service}`: {', '.join(plan.keys)})\n"
                + (f"- reason: {why}\n" if why else "")
                + "\nMerging this PR makes ArgoCD roll the service back. Closing it changes nothing.")
        pr = self.gh.open_pr(title, body, branch, self.base)
        return {"number": pr["number"], "url": pr["html_url"], "branch": branch, "reused": False}


def wait_for_merge(gh: GitHub, pr: dict[str, Any], *, timeout_s: float, poll_s: float = 30,
                   sleep: Callable[[float], None] = time.sleep,
                   clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Blocks until a human merges (or closes) the PR. API errors are retried until the timeout."""
    start = clock()
    while True:
        elapsed = round(clock() - start, 1)
        try:
            state = gh.get_pr(pr["number"])
            if state.get("merged") or state.get("merged_at"):
                return {"merged": True, "after_s": elapsed}
            if state.get("state") == "closed":
                return {"merged": False, "after_s": elapsed, "detail": f"PR #{pr['number']} was closed without merging"}
        except Exception:
            pass
        if elapsed >= timeout_s:
            return {"merged": False, "after_s": elapsed,
                    "detail": f"PR #{pr['number']} was not merged within {timeout_s / 60:.0f} min — merge it, or fix by hand"}
        sleep(poll_s)


# ---------------------------------------------------------------- executor
class GitOpsExecutor(LiveExecutor):
    """Rollbacks become PRs; feature-flag fixes stay as they were (runtime state)."""

    def __init__(self, namespace: str, backend, rollback: RollbackPR):
        super().__init__(namespace, backend)
        self.rollback = rollback

    def validate(self, action: str, target: str) -> tuple[bool, str]:
        ok, why = super().validate(action, target)
        if not ok or action != "rollback_deployment":
            return ok, why
        try:
            plan = self.rollback.plan(target)
        except NothingToRevert as e:
            return False, str(e)
        except Exception as e:
            return False, f"cannot read the GitOps repository: {str(e)[:150]}"
        return True, f"{why}; Git: {plan.summary}"

    def describe(self, action: str, target: str) -> str:
        if action != "rollback_deployment":
            return super().describe(action, target)
        plan = self.rollback.plan(target)
        return (f"open a PR in {self.rollback.gh.repo} that will {plan.summary} in {self.rollback.values_path}; "
                "a human merges it and ArgoCD applies it")

    def execute(self, action: str, target: str):
        if action != "rollback_deployment":
            return super().execute(action, target)
        ok, why = super().validate(action, target)             # the world may have changed while we waited
        if not ok:
            raise RuntimeError(f"refused: {why}")
        plan = self.rollback.plan(target)
        pr = self.rollback.open(plan)
        verb = "already open" if pr["reused"] else "opened"
        return {"output": f"PR #{pr['number']} {verb}: {pr['url']} — it will {plan.summary}; merge it to roll "
                          f"{target} back (ArgoCD applies it)", "pr": pr}


def gitops_remediation(backend, s: Settings, gh: GitHub | None = None) -> Remediation:
    """Live remediation whose rollbacks are PRs. Needs GITOPS_REPO and GITOPS_TOKEN."""
    if not s.gitops_repo or not s.gitops_token:
        raise ValueError("GitOps rollback needs GITOPS_REPO (owner/name) and GITOPS_TOKEN")
    gh = gh or GitHub(s.gitops_repo, s.gitops_token, s.github_api_url)
    rollback = RollbackPR(gh, s.gitops_base_branch, s.gitops_values_path)

    def verify(alert):
        return verify_recovery(backend.firing_alerts, alert, timeout_s=15 * 60,
                               probe=make_probe(backend.prom_query, alert, s.namespace))

    def await_merge(pr):
        return wait_for_merge(gh, pr, timeout_s=s.gitops_merge_timeout_min * 60)

    return Remediation(GitOpsExecutor(s.namespace, backend, rollback), verify, await_merge=await_merge)


# ---------------------------------------------------------------- bootstrap of the GitOps repo
APPLICATION = """\
# ArgoCD Application for the OpenTelemetry Demo: the Helm chart comes from the chart repository,
# the values come from THIS repository (values/otel-demo.yaml) — the file the incident agent's PRs edit.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: otel-demo
  namespace: argocd
spec:
  project: default
  destination:
    server: https://kubernetes.default.svc
    namespace: otel-demo
  sources:
    - repoURL: https://open-telemetry.github.io/opentelemetry-helm-charts
      chart: opentelemetry-demo
      targetRevision: {chart_version}
      helm:
        releaseName: otel-demo            # same name as the helm release made by `make demo`: ArgoCD adopts it
        valueFiles:
          - $values/values/otel-demo.yaml
    - repoURL: {repo_url}
      targetRevision: {branch}
      ref: values
  syncPolicy:
    # Merge = deploy. prune/selfHeal stay off in this lab: chaos tooling and `make probes` change live objects.
    automated: {{prune: false, selfHeal: false}}
    syncOptions: [CreateNamespace=true, RespectIgnoreDifferences=true]
  ignoreDifferences:
    # Added by `make probes` (infra/cart-readiness-probe.yaml): the chart schema cannot express a gRPC probe.
    - group: apps
      kind: Deployment
      name: cart
      jsonPointers: [/spec/template/spec/containers/0/readinessProbe]
"""

REPO_README = """\
# k8s-gitops-demo

GitOps repository for the OpenTelemetry Demo lab. ArgoCD watches `values/otel-demo.yaml`.

- Generated by `incident-agent gitops-bootstrap` (k8s-incident-agent). Humans edit this file through PRs too.
- The incident agent opens PRs named `incident-agent/rollback-<service>-<tag>` that pin
  `components.<service>.imageOverride`. **Protect `main`** (require a pull request) so nothing
  — including the agent's token — can push to it directly. Merging the PR is the second human approval.
"""


def bootstrap(out_dir: Path, repo_url: str, value_files: list[Path], chart_version: str, branch: str = "main") -> list[Path]:
    """Writes the files of the GitOps repository: merged values + ArgoCD Application + README."""
    merged = merge_values(*(yaml.safe_load(p.read_text()) or {} for p in value_files))
    files = {
        "values/otel-demo.yaml": yaml.safe_dump(merged, sort_keys=False, default_flow_style=False),
        "argocd/application.yaml": APPLICATION.format(chart_version=chart_version, repo_url=repo_url, branch=branch),
        "README.md": REPO_README,
    }
    written = []
    for rel, text in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        written.append(p)
    return written


# ---------------------------------------------------------------- demo: a bad deploy that goes through Git
def break_service(values_text: str, service: str = "checkout", env_name: str = "PAYMENT_ADDR",
                  env_value: str = "payment-v2:8080") -> str:
    """The GitOps version of the lab's `payment-unreachable-deploy`: a values change (components.<svc>.envOverrides,
    valid per the chart schema) that points checkout at a payment host that does not exist. Commit and merge it
    like any other change; ArgoCD deploys it, the alert fires, the agent proposes to revert exactly that commit."""
    values = yaml.safe_load(values_text) or {}
    comp = values.setdefault("components", {}).setdefault(service, {})
    comp["envOverrides"] = [e for e in comp.get("envOverrides", []) if e.get("name") != env_name] + \
        [{"name": env_name, "value": env_value}]
    return yaml.safe_dump(values, sort_keys=False, default_flow_style=False)
