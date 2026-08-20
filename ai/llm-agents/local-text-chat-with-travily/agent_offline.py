# /// script
# dependencies = [
#   "chainlit==2.6.0",
#   "langchain==1.0.2",
#   "langchain-ollama==1.0.0",
#   "langgraph==1.0.1",
#   "loguru==0.7.3",
# ]
# ///

import chainlit as cl
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from loguru import logger

# Local model from Ollama 
# (make sure it's downloaded: ollama pull qwen3:4b-instruct-2507-q4_K_M)
model = ChatOllama(
    model="qwen3:4b-instruct-2507-q4_K_M",
)


@tool
def count_words(text: str) -> int:
    """Count how many words are in the given text."""
    count = len(text.split())
    logger.info(f"🔢 Counting words in: {text!r} -> {count}")
    return count


@tool
def reverse_text(text: str) -> str:
    """Return the text reversed (character by character)."""
    reversed_text = text[::-1]
    logger.info(f"🔁 Reversing text: {text!r} -> {reversed_text!r}")
    return reversed_text


tools = [count_words, reverse_text]

system_prompt = """You are a friendly local assistant.
You can:
- count how many words are in a text using the `count_words` tool,
- reverse text using the `reverse_text` tool.

When the user asks:
- "how many words" / "count words" → use the count_words tool,
- "reverse this" / "reverse_text" → use the reverse_text tool,
Otherwise, answer normally in a helpful and conversational way.
Always explain briefly what you did when you used a tool.
"""

checkpointer = InMemorySaver()

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=checkpointer,
)


@cl.on_message
async def on_message(msg: cl.Message):
    """Handling any message from the user in the Chainlit UI."""

    final_answer = cl.Message(content="")

    # We pass the user's message as a HumanMessage to the agent
    for message_chunk, metadata in agent.stream(
        {"messages": [HumanMessage(content=msg.content)]},
        {"configurable": {"thread_id": "demo-thread-1"}},
        stream_mode="messages",
    ):
        # We are only interested in responses from the "model" node (i.e. from LLM)
        if message_chunk.content and metadata["langgraph_node"] == "model":
            await final_answer.stream_token(message_chunk.content)

    await final_answer.send()


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
