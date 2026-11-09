"""
Demo 7 — Gateway inside a LangChain application
=================================================

`ChatLiteLLM` lets any LangChain chain (prompt | model | parser) run on any
provider LiteLLM supports, with no other code changes.

Note the two DIFFERENT fallback mechanisms in this project:
  * `completion(..., fallbacks=[...])` (Demo 2) — fallback inside LiteLLM;
  * `model.with_fallbacks([...])` (here)       — fallback inside LangChain,
    works with ANY LangChain runnable, LiteLLM-backed or not.
"""

from common import BROKEN_MODEL, SMART_MODEL, header, takeaway  # noqa: I001  (must be first)

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a concise AI engineering tutor. Keep answers short."),
        ("user", "{question}"),
    ]
)


def run_basic_chain_demo() -> None:
    header("DEMO 7a: LCEL chain through ChatLiteLLM")

    llm = ChatLiteLLM(model=SMART_MODEL, temperature=0.3, max_tokens=250)
    chain = PROMPT | llm | StrOutputParser()
    print("\n" + chain.invoke({"question": "What is an AI gateway? Answer in 3 bullet points."}))

    takeaway("Swapping the provider for the whole chain = changing one model string.")


def run_fallback_chain_demo() -> None:
    header("DEMO 7b: LangChain-level fallback (.with_fallbacks)")

    primary = ChatLiteLLM(model=BROKEN_MODEL)  # simulated outage
    backup = ChatLiteLLM(model=SMART_MODEL, temperature=0.2, max_tokens=250)

    chain = PROMPT | primary.with_fallbacks([backup]) | StrOutputParser()
    print("\n" + chain.invoke({"question": "Name the 3 biggest benefits of an AI gateway."}))

    takeaway("The primary failed; the chain recovered without the caller noticing.")


def run_demo() -> None:
    run_basic_chain_demo()
    run_fallback_chain_demo()


if __name__ == "__main__":
    run_demo()
