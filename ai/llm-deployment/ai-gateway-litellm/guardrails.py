"""
Input guardrails applied before a request ever reaches an LLM provider.

Two deliberately different policies:

1. PII  -> REDACT AND CONTINUE
   The user did nothing malicious; they just over-shared. Sensitive values
   are replaced with typed placeholders ([EMAIL], [CARD], ...) and the
   request proceeds. The model gets the intent, never the data.

2. Prompt injection -> BLOCK
   Someone is trying to take control of the model. There is nothing to
   "fix", so a GuardrailViolation is raised and no request leaves the
   process (no provider call, no token cost).

Design note — why not `litellm.input_callback`?
-------------------------------------------------
In the LiteLLM SDK, `input_callback` is a *logging* hook, not a control
hook. Verified against the library source and empirically:
  * any exception raised inside the callback is caught and swallowed,
    so a "blocking" guardrail silently lets the request through;
  * the callback receives the request after it has been built, so
    mutating messages there does not change what is sent.
Guardrails therefore run explicitly in `guarded_completion()`. (Blocking
pre-call hooks do exist in the LiteLLM Proxy server — `async_pre_call_hook`.)

Design note — regex overlap
----------------------------
Formats overlap: a 9-digit phone pattern without digit boundaries matches
the first 9 digits of an 11-digit national ID, leaving the last 2 digits
exposed ("[PHONE]59"). Fixes: (1) every numeric pattern is anchored with
`(?<!\\d)` / `(?!\\d)` so it cannot start or end inside a longer number;
(2) patterns run from longest to shortest format.
"""

from __future__ import annotations

import re
from typing import Callable

import litellm


class GuardrailViolation(Exception):
    """Raised when a guardrail blocks a request."""


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------


def _luhn_valid(number: str) -> bool:
    """Luhn checksum — filters out random digit runs that only look like cards."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        checksum += d
    return checksum % 10 == 0


_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")

# Order matters: longest numeric formats first (card -> national ID -> phone).
PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # Polish national ID (PESEL): exactly 11 digits, not part of a longer run
    ("NATIONAL_ID", re.compile(r"(?<!\d)\d{11}(?!\d)")),
    # Phone: optional +48 country code, then 9 digits (123 456 789 / 123-456-789)
    ("PHONE", re.compile(r"(?<![\d+])(?:\+48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)")),
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, list_of_detected_pii_types)."""
    found: list[str] = []

    def _card(match: re.Match[str]) -> str:
        if _luhn_valid(match.group()):
            found.append("CARD")
            return "[CARD]"
        return match.group()

    text = _CARD.sub(_card, text)  # cards first: the longest numeric format
    for label, pattern in PII_PATTERNS:
        text, n = pattern.subn(f"[{label}]", text)
        found.extend([label] * n)
    return text, found


def pii_input_guardrail(messages: list[dict]) -> list[dict]:
    """Return a NEW message list with PII redacted (input is not mutated)."""
    cleaned: list[dict] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            redacted, found = redact_pii(content)
            if found:
                print(f"[GUARDRAIL] PII redacted: {', '.join(found)}")
                print(f"   Sent to model: {redacted}")
            msg = {**msg, "content": redacted}
        cleaned.append(msg)
    return cleaned


# ---------------------------------------------------------------------------
# Prompt-injection blocking
# ---------------------------------------------------------------------------

# Heuristic phrase list (English + Polish). Good enough to demonstrate the
# BLOCK policy; trivially bypassed by paraphrasing. Production systems add a
# dedicated classifier model (e.g. Llama Guard / Prompt Guard) behind this.
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions|rules)",
        r"(reveal|show|print)\s+(me\s+)?(your\s+)?system\s+prompt",
        r"you\s+are\s+now\s+(unrestricted|unfiltered|without\s+(any\s+)?(rules|limits))",
        r"\bDAN\b|\bjailbreak\b",
        r"ignoruj\w*\s+(wszystkie\s+)?(poprzednie|wcześniejsze)\s+instrukcj",
        r"jesteś\s+teraz\s+bez\s+(żadnych\s+)?ogranicze",
    ]
]


def injection_guardrail(messages: list[dict]) -> list[dict]:
    """Raise GuardrailViolation if any message looks like a prompt injection."""
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        for pattern in INJECTION_PATTERNS:
            if pattern.search(content):
                raise GuardrailViolation(
                    f"prompt injection detected (pattern: {pattern.pattern!r})"
                )
    return messages


# ---------------------------------------------------------------------------
# Guarded call
# ---------------------------------------------------------------------------

Guardrail = Callable[[list[dict]], list[dict]]


def guarded_completion(*, guardrails: list[Guardrail], messages: list[dict], **kwargs):
    """
    Drop-in wrapper around `litellm.completion()`.

    Guardrails run in order. Each one either returns (possibly transformed)
    messages or raises GuardrailViolation, in which case no provider call
    is made.
    """
    for guardrail in guardrails:
        messages = guardrail(messages)
    return litellm.completion(messages=messages, **kwargs)
