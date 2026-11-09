"""
Demo 2 — Automatic fallback
============================

When the primary provider fails (outage, rate limit, revoked key, retired
model), the gateway transparently tries the next model in the list. The
calling code never sees the failure.

The outage is simulated with a model ID that does not exist, so the demo
is reproducible without waiting for a real incident.
"""

from common import BROKEN_MODEL, SMART_MODEL, header, takeaway  # noqa: I001  (must be first)

from litellm import completion


def run_demo() -> None:
    header("DEMO 2: Automatic fallback (primary fails -> backup answers)")
    print(f"Primary:  {BROKEN_MODEL}   (simulated outage)")
    print(f"Fallback: {SMART_MODEL}")

    response = completion(
        model=BROKEN_MODEL,
        messages=[{"role": "user", "content": "What is an AI gateway? Answer in two sentences."}],
        fallbacks=[SMART_MODEL],
        max_tokens=200,
    )

    print("\n[OK] The application still got an answer although the primary failed.")
    print(f"Model that actually answered: {response.model}")
    print(f"Answer: {response.choices[0].message.content.strip()}")

    takeaway(
        "`fallbacks=[...]` is an ordered list of backups. Downstream code (UI, "
        "agents) never needs to know which provider served the request."
    )


if __name__ == "__main__":
    run_demo()
