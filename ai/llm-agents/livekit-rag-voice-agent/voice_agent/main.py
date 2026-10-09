"""Kestrel Energy voice agent (LiveKit Agents + a LangChain agent graph).

Talk to it from your terminal (local mic and speakers):
    python -m voice_agent.main console
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from livekit import agents  # noqa: E402
from livekit.agents import Agent, AgentServer, AgentSession, TurnHandlingOptions, inference  # noqa: E402
from livekit.plugins import langchain as lk_langchain  # noqa: E402

from config import settings  # noqa: E402
from energy_agent import build_agent  # noqa: E402
from energy_agent.resources import get_embedder  # noqa: E402
from voice_agent.speech_filter import SpokenTokensOnly  # noqa: E402


class KestrelAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=f"You are the {settings.company_name} customer support voice assistant.",
            llm=lk_langchain.LLMAdapter(graph=SpokenTokensOnly(build_agent())),
        )


def prewarm(_proc: agents.JobProcess) -> None:
    """Load the embedding model before a caller connects, so the first
    knowledge-base lookup doesn't stall the conversation. Qdrant is opened
    later, inside the call, to avoid holding the embedded-DB lock in idle workers."""
    get_embedder()
    build_agent()


# The first-ever model download can take longer than the default 10 s.
server = AgentServer(setup_fnc=prewarm, initialize_process_timeout=90.0)


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext) -> None:
    session = AgentSession(
        stt=inference.STT(model=settings.stt_model, language=settings.stt_language),
        tts=inference.TTS(
            model=settings.tts_model,
            voice=settings.tts_voice,
            language=settings.tts_language,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            endpointing={
                "mode": "fixed",
                "min_delay": settings.endpointing_min_delay,
                "max_delay": settings.endpointing_max_delay,
            },
        ),
    )

    await session.start(agent=KestrelAssistant(), room=ctx.room)
    await session.generate_reply(
        instructions=f"Briefly greet the caller as the {settings.company_name} assistant and ask how you can help."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
