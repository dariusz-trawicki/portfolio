"""The speech filter must pass model tokens to TTS and drop everything else."""

import asyncio

from langchain_core.messages import AIMessageChunk, ToolMessage

from voice_agent.speech_filter import SpokenTokensOnly, is_speakable


class FakeGraph:
    def __init__(self, items):
        self.items = items
        self.kwargs = None

    def astream(self, *args, **kwargs):
        self.kwargs = kwargs

        async def gen():
            for item in self.items:
                yield item

        return gen()


def collect(graph, **kwargs):
    async def run():
        return [item async for item in SpokenTokensOnly(graph).astream({}, **kwargs)]

    return asyncio.run(run())


def test_only_ai_tokens_are_spoken():
    items = [
        (AIMessageChunk(content=""), {}),  # tool-call chunk with no text
        (ToolMessage(content='{"balance": 86.4}', tool_call_id="1"), {}),
        (AIMessageChunk(content="You owe "), {}),
        (AIMessageChunk(content="£86.40."), {}),
    ]
    spoken = [token.content for token, _ in collect(FakeGraph(items))]
    assert spoken == ["You owe ", "£86.40."]


def test_kwargs_are_forwarded():
    graph = FakeGraph([])
    collect(graph, stream_mode="messages")
    assert graph.kwargs == {"stream_mode": "messages"}


def test_is_speakable_accepts_bare_tokens():
    assert is_speakable(AIMessageChunk(content="hi"))
    assert not is_speakable("raw string")
