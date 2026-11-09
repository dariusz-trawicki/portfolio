"""
Demo 3 — Response caching
==========================

If many users ask the exact same question, there is no reason to pay the
provider every time. The second identical request is served from cache:
no API call, near-zero latency, zero cost.

Limitation (on purpose, for a self-contained demo): `Cache(type="local")`
lives in process memory and disappears on restart. In production use a
shared, persistent backend such as Redis so every gateway instance shares
the same cache.
"""

from common import SMART_MODEL, header, takeaway  # noqa: I001  (must be first)

import time

import litellm
from litellm import completion
from litellm.caching import Cache

PROMPT = "What does the acronym LLM stand for? Answer in one line."


def _timed_call() -> tuple[float, str]:
    start = time.perf_counter()
    r = completion(
        model=SMART_MODEL,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=100,
        caching=True,
    )
    return time.perf_counter() - start, r.choices[0].message.content.strip()


def run_demo() -> None:
    header("DEMO 3: Caching — the second identical request is free")

    litellm.cache = Cache(type="local")
    try:
        t1, a1 = _timed_call()
        print(f"\n1st call (provider API): {t1:.2f}s  — {a1}")
        t2, a2 = _timed_call()
        print(f"2nd call (cache hit):    {t2:.4f}s — {a2}")
        if t2 > 0:
            print(f"\nSpeed-up: {t1 / t2:.0f}x faster, and the 2nd call cost $0.")
    finally:
        litellm.cache = None  # don't leak the cache into other demos

    takeaway("In-memory cache is per-process. Production: Redis (shared, survives restarts).")


if __name__ == "__main__":
    run_demo()
