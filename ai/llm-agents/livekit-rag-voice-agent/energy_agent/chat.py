"""Text-mode chat with the agent – try every tool without a microphone or LiveKit.

Usage:  python -m energy_agent.chat          (needs GROQ_API_KEY and an ingested knowledge base)
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from config import settings
from energy_agent.agent import build_agent


def main() -> None:
    agent = build_agent()
    history: list = []
    print(f"{settings.company_name} assistant – type your message, or 'quit' to exit.\n")

    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in {"quit", "exit", "q"}:
            break
        if not user:
            continue

        history.append(HumanMessage(user))
        result = agent.invoke({"messages": history})
        for msg in result["messages"][len(history):]:
            if isinstance(msg, AIMessage):
                for call in msg.tool_calls:  # show which tools the agent used
                    print(f"  ↳ {call['name']}({call['args']})")
        history = result["messages"]
        print(f"agent > {history[-1].content}\n")


if __name__ == "__main__":
    main()
