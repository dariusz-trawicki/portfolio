from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Category = Literal[
    "bad_deploy",         # a new version/image broke the service
    "config_change",      # env/config change
    "feature_flag",       # an enabled flag changed behaviour
    "resource_limits",    # limits too low -> OOMKilled / throttling
    "memory_leak",
    "cpu_saturation",
    "dependency_failure", # the service is healthy, something it depends on is failing
    "application_bug",
    "queue_backlog",
    "unknown",
]

Action = Literal[
    "rollback_deployment",
    "disable_feature_flag",
    "increase_resources",
    "restart_pods",
    "scale_up",
    "escalate_to_human",
    "none",
]


class Alert(BaseModel):
    name: str
    service: str
    severity: str = "warning"
    summary: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    started_at: str | None = None


class Diagnosis(BaseModel):
    """The structured investigation result — this is what we score against ground truth."""

    root_cause: str = Field(description="One or two sentences: what the root cause is.")
    culprit_service: str = Field(description="Service where the cause lies (may differ from the alerting one).")
    category: Category
    confidence: float = Field(ge=0.0, le=1.0, description="Diagnosis confidence 0-1.")
    evidence: list[str] = Field(description="Concrete facts from the tools that support the diagnosis.")
    recommended_action: Action
    action_target: str = Field(description="What to act on: deployment name or flag name.")
    rationale: str = Field(description="Why this action, what the risk is, how to verify it helped.")


def merge_dicts(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """Reducer: parallel evidence-gathering nodes add their own keys."""
    return {**(left or {}), **(right or {})}


def sum_usage(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    """Reducer: sums token usage across all LLM calls."""
    out = dict(left or {})
    for k, v in (right or {}).items():
        out[k] = out.get(k, 0) + int(v or 0)
    return out


class IncidentState(TypedDict, total=False):
    alert: Alert
    evidence: Annotated[dict[str, str], merge_dicts]
    messages: Annotated[list[AnyMessage], add_messages]
    tool_calls_used: int
    budget_exhausted: bool
    usage: Annotated[dict[str, int], sum_usage]
    diagnosis: Diagnosis
    # remediation branch (step 5) — plain dicts so they serialise into checkpoints as-is
    proposal: dict
    decision: dict
    execution: dict
    verification: dict
    report: str
