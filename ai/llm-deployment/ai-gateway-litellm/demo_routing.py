"""
Demo 5 — Smart routing vs. load balancing
==========================================

Two related ideas that are easy to conflate:

A. SMART ROUTING — different TASKS go to different MODELS.
   A cheap, fast classifier decides where a request should go before any
   money is spent on an expensive model. Question it answers:
   "Which model fits THIS task?"

B. LOAD BALANCING — the same task may go to ANY deployment in a pool of
   equivalent models behind one alias. Question it answers:
   "Which of these interchangeable resources should take this request?"
   (spreading load, staying under per-key rate limits)
"""

from common import FAST_MODEL, GROQ_MODEL, SMART_MODEL, header, takeaway  # noqa: I001

from collections import Counter

from litellm import Router, completion

# ---------------------------------------------------------------------------
# A. Smart routing: classify the task, then pick the model
# ---------------------------------------------------------------------------

ROUTES = {
    "code": SMART_MODEL,  # complex reasoning -> strongest model
    "summary": FAST_MODEL,  # simple transformation -> cheaper tier
    "general": GROQ_MODEL,  # chit-chat / trivia -> fastest, cheapest
}
DEFAULT_ROUTE = "general"


def classify_task(query: str) -> str:
    """Cheap first-pass classifier running on Groq."""
    response = completion(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Classify the request below with EXACTLY one word: "
                    f"{', '.join(ROUTES)}.\n\nRequest: {query}\n\nLabel:"
                ),
            }
        ],
        # gpt-oss is a reasoning model: hidden "thinking" tokens count toward
        # max_tokens. With a tiny limit (e.g. 5) the whole budget is spent on
        # reasoning and `content` comes back empty. Hence a roomier limit and
        # low reasoning effort for a trivial classification task.
        max_tokens=300,
        reasoning_effort="low",
    )
    # LLMs rarely answer with a perfectly clean token: "Code.", "'summary'",
    # "This is code". Exact dict lookup would silently send everything to
    # the default route, so match labels as substrings instead.
    raw = (response.choices[0].message.content or "").strip().lower()
    return next((label for label in ROUTES if label in raw), DEFAULT_ROUTE)


def run_smart_routing_demo() -> None:
    header("DEMO 5a: Smart routing — the task decides the model")

    queries = [
        "Write a Python function that returns the n-th Fibonacci number.",
        "Summarize in two sentences what the attention mechanism does.",
        "Tell me a fun fact about elephants.",
    ]
    for query in queries:
        task = classify_task(query)
        model = ROUTES[task]
        answer = completion(
            model=model,
            messages=[{"role": "user", "content": query}],
            max_tokens=300,
        ).choices[0].message.content
        print(f"\nQuery: {query}")
        print(f"   classified as: {task}")
        print(f"   routed to:     {model}")
        print(f"   answer:        {(answer or '').strip()[:140].replace(chr(10), ' ')}...")


# ---------------------------------------------------------------------------
# B. Load balancing: several deployments behind one alias
# ---------------------------------------------------------------------------


def run_load_balancing_demo() -> None:
    header("DEMO 5b: Load balancing — one alias, several deployments")

    router = Router(
        model_list=[
            {
                "model_name": "chat-pool",
                "litellm_params": {"model": FAST_MODEL},
                "model_info": {"id": "anthropic-haiku"},
            },
            {
                "model_name": "chat-pool",
                "litellm_params": {"model": GROQ_MODEL},
                "model_info": {"id": "groq-gpt-oss"},
            },
        ],
        routing_strategy="simple-shuffle",
    )

    hits: Counter[str] = Counter()
    for i in range(1, 7):
        r = router.completion(
            model="chat-pool",  # an alias, NOT a concrete model
            messages=[{"role": "user", "content": f"Say hello (request {i})."}],
            max_tokens=300,  # headroom for gpt-oss reasoning tokens
        )
        deployment = r._hidden_params.get("model_id", "?")
        hits[deployment] += 1
        print(f"  request #{i} -> {deployment}")

    print("\nLoad distribution:")
    for deployment, count in hits.most_common():
        print(f"   {deployment}: {'#' * count} ({count})")

    takeaway(
        "The application calls the abstract alias `chat-pool`. Deployments can "
        "be added or removed from the pool without touching application code."
    )


def run_demo() -> None:
    run_smart_routing_demo()
    run_load_balancing_demo()


if __name__ == "__main__":
    run_demo()
