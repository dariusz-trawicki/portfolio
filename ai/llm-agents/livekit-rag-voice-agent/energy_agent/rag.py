"""Knowledge-base retrieval (RAG), plus a small CLI for testing it without voice.

Usage:  python -m energy_agent.rag "How do I submit a meter reading?"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from config import settings
from energy_agent.resources import get_embedder, get_qdrant

# BGE models retrieve better when short queries carry this instruction prefix.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@dataclass(frozen=True)
class Passage:
    text: str
    source: str
    score: float


def retrieve(query: str, top_k: int | None = None, min_score: float | None = None) -> list[Passage]:
    """Return the most similar document chunks, dropping weak matches."""
    prefix = QUERY_PREFIX if "bge" in settings.embedding_model.lower() else ""
    vector = get_embedder().encode(prefix + query, normalize_embeddings=True).tolist()
    result = get_qdrant().query_points(
        collection_name=settings.collection_name,
        query=vector,
        limit=top_k or settings.retrieval_top_k,
        score_threshold=settings.retrieval_min_score if min_score is None else min_score,
        with_payload=True,
    )
    return [
        Passage(
            text=point.payload["chunk_text"],
            source=point.payload.get("source", "?"),
            score=round(point.score, 3),
        )
        for point in result.points
    ]


def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(
        f'<passage n="{i}" source="{p.source}">\n{p.text}\n</passage>' for i, p in enumerate(passages, 1)
    )


ANSWER_PROMPT = (
    f"You are a customer support assistant for {settings.company_name}. "
    "Answer using ONLY the passages provided. If they don't contain the answer, say so plainly. "
    "Keep it to one or two sentences – the answer will be read aloud."
)


def answer(question: str) -> tuple[str, list[Passage]]:
    """End-to-end RAG: retrieve passages, then ask the LLM to answer from them."""
    from langchain_groq import ChatGroq

    passages = retrieve(question)
    if not passages:
        return "I couldn't find that in our documentation.", []

    llm = ChatGroq(model=settings.groq_model, temperature=settings.llm_temperature)
    reply = llm.invoke(
        [
            ("system", ANSWER_PROMPT),
            ("user", f"{format_passages(passages)}\n\nQuestion: {question}"),
        ]
    )
    return reply.content, passages


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What tariffs does Kestrel Energy offer?"
    print(f"Question: {question}\n")
    text, passages = answer(question)
    print(f"ANSWER:\n{text}\n\nSOURCES:")
    for p in passages:
        print(f"  - {p.source} (similarity {p.score})")


if __name__ == "__main__":
    main()
