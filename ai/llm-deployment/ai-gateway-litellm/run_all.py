"""
Run all seven demos in sequence and print the total spend of the run.

    uv run run_all.py

Requires ANTHROPIC_API_KEY and GROQ_API_KEY in `.env` (see `.env.example`).
"""

from common import enable_spend_tracking, header, spend_summary  # noqa: I001  (must be first)

import demo_caching
import demo_cost_tracking
import demo_fallback
import demo_guardrails
import demo_langchain
import demo_routing
import demo_unified_api

DEMOS = [
    demo_unified_api,
    demo_fallback,
    demo_caching,
    demo_cost_tracking,
    demo_routing,
    demo_guardrails,
    demo_langchain,
]

if __name__ == "__main__":
    enable_spend_tracking()
    for demo in DEMOS:
        demo.run_demo()
    header("RUN SUMMARY")
    print(f"Total: {spend_summary()}")
