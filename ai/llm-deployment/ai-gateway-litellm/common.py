"""
Shared setup for every demo: logging, environment, model registry, spend tracking.

Import this module FIRST in every demo file. Logging levels must be set
before LiteLLM emits anything, so import order matters here.
"""

import logging
import warnings

# --- 1. Logging -------------------------------------------------------------
# LiteLLM logs a full traceback even for errors it has already handled
# (e.g. a failed primary model that a fallback recovered from). It does so
# via `logger.exception(...)`, i.e. at ERROR level, so a threshold of ERROR
# is NOT enough to hide it. CRITICAL is. Real failures are unaffected:
# they surface as exceptions raised into the caller, not as log records.
warnings.filterwarnings("ignore")
_LITELLM_LOGGERS = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")
for _name in _LITELLM_LOGGERS:
    logging.getLogger(_name).setLevel(logging.CRITICAL)

import litellm  # noqa: E402  (deliberately imported after logging setup)
from dotenv import load_dotenv  # noqa: E402

litellm.suppress_debug_info = True
for _name in _LITELLM_LOGGERS:  # re-apply in case LiteLLM reset levels on import
    logging.getLogger(_name).setLevel(logging.CRITICAL)

load_dotenv()

# --- 2. Model registry --------------------------------------------------------
# The ONLY place where provider model IDs live. Providers retire models
# regularly (Groq shut down `llama-3.3-70b-versatile` in Aug 2026); with a
# single registry, a deprecation is a one-line change instead of a grep
# across the codebase.
SMART_MODEL = "claude-sonnet-4-6"  # strongest reasoning, highest price
FAST_MODEL = "claude-haiku-4-5-20251001"  # cheaper Anthropic tier
GROQ_MODEL = "groq/openai/gpt-oss-120b"  # open-weight model on Groq's fast inference
BROKEN_MODEL = "groq/this-model-does-not-exist"  # used to simulate an outage


# --- 3. Spend tracking across the whole run -------------------------------
_spend = {"calls": 0, "usd": 0.0}


def _record_spend(kwargs, completion_response, start_time, end_time) -> None:
    cost = kwargs.get("response_cost") or 0.0
    _spend["calls"] += 1
    _spend["usd"] += cost


def enable_spend_tracking() -> None:
    """Register a success callback that sums the cost of every successful call."""
    if _record_spend not in litellm.success_callback:
        litellm.success_callback.append(_record_spend)


def spend_summary() -> str:
    return f"{_spend['calls']} successful LLM calls, total cost ${_spend['usd']:.4f}"


# --- 4. Console helpers ----------------------------------------------------------
def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def takeaway(text: str) -> None:
    print(f"\nTakeaway: {text}")
