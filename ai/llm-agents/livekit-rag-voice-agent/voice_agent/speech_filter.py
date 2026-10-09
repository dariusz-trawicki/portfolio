"""Keeps tool output out of text-to-speech.

LiveKit's LangChain adapter streams the graph with `stream_mode="messages"` and
speaks anything that has a `content` field – including raw ToolMessages. This
wrapper uses an allow-list: only non-empty AIMessageChunk tokens reach TTS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessageChunk


def is_speakable(item: Any) -> bool:
    token = item[0] if isinstance(item, tuple) and len(item) == 2 else item
    return isinstance(token, AIMessageChunk) and bool(token.content)


class SpokenTokensOnly:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        # Call the inner graph eagerly so a TypeError on unsupported kwargs
        # surfaces immediately – the adapter relies on that to retry.
        inner = self._graph.astream(*args, **kwargs)

        async def _filtered() -> AsyncIterator[Any]:
            async for item in inner:
                if is_speakable(item):
                    yield item

        return _filtered()
