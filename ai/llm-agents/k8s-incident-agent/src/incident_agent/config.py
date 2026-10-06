from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    namespace: str = field(default_factory=lambda: _env("TARGET_NAMESPACE", "otel-demo"))
    helm_release: str = field(default_factory=lambda: _env("HELM_RELEASE", "otel-demo"))
    prometheus_url: str = field(default_factory=lambda: _env("PROMETHEUS_URL", "http://localhost:9090"))
    opensearch_url: str = field(default_factory=lambda: _env("OPENSEARCH_URL", "http://localhost:9200"))
    logs_index: str = field(default_factory=lambda: _env("LOGS_INDEX", "otel-logs-*"))
    flagd_url: str = field(default_factory=lambda: _env("FLAGD_OFREP_URL", "http://localhost:8016"))
    # flagd-ui (via frontend-proxy, path /feature): GET /api/read returns full flag definitions
    # including targeting rules. OFREP without context cannot see flags enabled only for
    # specific targets (e.g. productCatalogFailure for a single product).
    flagd_ui_url: str = field(default_factory=lambda: _env("FLAGD_UI_URL", "http://localhost:8080/feature"))
    # "provider:model" format for langchain.chat_models.init_chat_model, e.g.
    #   anthropic:claude-sonnet-5
    #   openai:gpt-5-mini
    #   openai:speakleash/Bielik-11B-v2.6-Instruct  (+ OPENAI_BASE_URL=http://<vllm>/v1)
    model: str = field(default_factory=lambda: _env("AGENT_MODEL", "anthropic:claude-sonnet-5"))
    # Some newer models (e.g. Claude Sonnet 5) reject `temperature`.
    # Empty = the parameter is not sent; set e.g. 0 for models that accept it.
    temperature: float | None = field(
        default_factory=lambda: float(os.environ["AGENT_TEMPERATURE"]) if os.getenv("AGENT_TEMPERATURE") else None
    )
    # Language of the agent's free text and the report: "en" (default) or "pl".
    # Enum values (category, action) and JSON keys always stay in English.
    language: str = field(default_factory=lambda: _env("AGENT_LANGUAGE", "en").lower())
    # Hard limits — the agent cannot loop forever or burn through the budget.
    max_tool_calls: int = field(default_factory=lambda: int(_env("AGENT_MAX_TOOL_CALLS", "12")))
    max_tool_output_chars: int = field(default_factory=lambda: int(_env("AGENT_MAX_TOOL_OUTPUT_CHARS", "4000")))
    # Checkpoints AND the incident list (step 5c): a SQLite path, or a Postgres URL
    # (postgresql://user:password@host:5432/db) when the agent runs in the cluster.
    checkpoint_db: str = field(default_factory=lambda: _env("CHECKPOINT_DB", ".data/checkpoints.sqlite"))
    # Webhook (step 3). Empty token = no authentication (fine on localhost only).
    webhook_token: str | None = field(default_factory=lambda: os.getenv("WEBHOOK_TOKEN") or None)
    # How long after its last alert resolves an incident still absorbs echoes and flapping alerts.
    dedup_window_minutes: int = field(default_factory=lambda: int(_env("DEDUP_WINDOW_MINUTES", "30")))
    # Step 5e: how rollbacks are applied. "kubectl" = `rollout undo` (default); "gitops" = a pull request in the
    # GitOps repository that a human merges and ArgoCD applies. The token is a secret (never in the ConfigMap).
    rollback_mode: str = field(default_factory=lambda: _env("ROLLBACK_MODE", "kubectl").lower())
    gitops_repo: str = field(default_factory=lambda: _env("GITOPS_REPO", ""))                  # owner/name
    gitops_token: str | None = field(default_factory=lambda: os.getenv("GITOPS_TOKEN") or None)
    gitops_base_branch: str = field(default_factory=lambda: _env("GITOPS_BASE_BRANCH", "main"))
    gitops_values_path: str = field(default_factory=lambda: _env("GITOPS_VALUES_PATH", "values/otel-demo.yaml"))
    github_api_url: str = field(default_factory=lambda: _env("GITHUB_API_URL", "https://api.github.com"))
    gitops_merge_timeout_min: int = field(default_factory=lambda: int(_env("GITOPS_MERGE_TIMEOUT_MIN", "30")))
