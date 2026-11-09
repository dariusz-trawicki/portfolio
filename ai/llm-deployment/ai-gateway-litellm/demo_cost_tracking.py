"""
Demo 4 — Cost tracking
=======================

LiteLLM ships a pricing table for hundreds of models, so every call can be
priced in USD without hand-multiplying tokens by rates from a pricing page.
Tagged per team or feature (e.g. the `user=` parameter), this answers
"WHO is spending the budget?" instead of one opaque monthly invoice.
"""

from common import FAST_MODEL, SMART_MODEL, header, takeaway  # noqa: I001  (must be first)

from litellm import completion, completion_cost

PROMPT = "Write a haiku about artificial intelligence. Output only the haiku."


def run_demo() -> None:
    header("DEMO 4: Cost tracking — exact USD cost of every call")

    print(f"\n{'Model':<28}{'In tok':>8}{'Out tok':>9}{'Cost (USD)':>14}")
    print("-" * 59)
    for model in [SMART_MODEL, FAST_MODEL]:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=100,
            user="team-portfolio-demo",  # attribution tag for internal chargeback
        )
        cost = completion_cost(completion_response=response)
        u = response.usage
        print(f"{model:<28}{u.prompt_tokens:>8}{u.completion_tokens:>9}{cost:>14.6f}")

    takeaway(
        "Same prompt, different tiers: per-call pricing makes the cost/quality "
        "trade-off measurable — the basis for routing decisions in Demo 5."
    )


if __name__ == "__main__":
    run_demo()
