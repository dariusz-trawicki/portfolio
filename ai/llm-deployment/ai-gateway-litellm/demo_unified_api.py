"""
Demo 1 — Unified API
=====================

Every provider ships its own SDK, request schema, response schema and auth.
A gateway exposes ONE interface. Here the only thing that changes between
Anthropic and Groq is the model string; the call and the response shape
(`response.choices[0].message.content`) stay identical.
"""

from common import GROQ_MODEL, SMART_MODEL, header, takeaway  # noqa: I001  (must be first)

from litellm import completion

PROMPT = "Explain retrieval-augmented generation (RAG) in one sentence."


def run_demo() -> None:
    header("DEMO 1: Unified API — one function, multiple providers")

    for label, model in [("Anthropic", SMART_MODEL), ("Groq     ", GROQ_MODEL)]:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=300,
        )
        print(f"\n{label} ({model}):\n   {response.choices[0].message.content.strip()}")

    takeaway(
        "Same call, same response shape — only the model string differs. "
        "The provider is resolved from the model name (`groq/` prefix -> Groq, "
        "`claude-*` -> Anthropic)."
    )


if __name__ == "__main__":
    run_demo()
