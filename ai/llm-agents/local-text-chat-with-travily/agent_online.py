# /// script
# dependencies = [
#   "chainlit==2.6.0",
#   "langchain==1.0.2",
#   "langchain-ollama==1.0.0",
#   "langgraph==1.0.1",
#   "loguru==0.7.3",
#   "langchain-tavily==0.2.12",
#   "python-dotenv==1.0.1",
# ]
# ///

import os
import chainlit as cl
from dotenv import load_dotenv
from loguru import logger

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver

# Load environment variables from .env (including TAVILY_API_KEY)
load_dotenv()

# Optional: log a warning if the Tavily key is missing
tavily_key = os.getenv("TAVILY_API_KEY")
if not tavily_key:
    logger.warning(
        "TAVILY_API_KEY is not set. TavilySearch will fail to initialize "
        "unless you provide the API key in a .env file or environment variable."
    )

# Local model from Ollama
# Make sure it's pulled first:
#   ollama pull qwen3:4b-instruct-2507-q4_K_M
model = ChatOllama(
    model="qwen3:4b-instruct-2507-q4_K_M",
)


# ---------- TOOLS ----------

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


# Tavily – web search tool
# If TAVILY_API_KEY is set in the environment, TavilySearch will pick it up 
# automatically.
tavily_search = TavilySearch(
    max_results=5,
    # You could also pass the key explicitly:
    # tavily_api_key=tavily_key,
)

tools = [count_words, reverse_text, tavily_search]


# ---------- SYSTEM PROMPT ----------

system_prompt = """You are a friendly local assistant connected to a web search tool.

You can:
- count how many words are in a text using the `count_words` tool,
- reverse text using the `reverse_text` tool,
- search the web for up-to-date information using the Tavily search tool.

When the user asks:
- "how many words" / "count words" → use the count_words tool,
- "reverse this" → use the reverse_text tool,
- any question that clearly needs fresh or external information → use the Tavily search tool.

Always briefly explain what you did when you used a tool.
Keep your tone warm, clear, and conversational.
"""


# ---------- AGENT (LangChain + LangGraph) ----------

checkpointer = InMemorySaver()

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=checkpointer,
)


# ---------- CHAINLIT HANDLER ----------

@cl.on_message
async def on_message(msg: cl.Message):
    """Handle each incoming message from the user in the Chainlit UI."""
    final_answer = cl.Message(content="")

    # Pass the user's message as a HumanMessage into the agent
    for message_chunk, metadata in agent.stream(
        {"messages": [HumanMessage(content=msg.content)]},
        {"configurable": {"thread_id": "online-thread-1"}},
        stream_mode="messages",
    ):
        # Only stream content coming from the LLM node ("model")
        if message_chunk.content and metadata["langgraph_node"] == "model":
            await final_answer.stream_token(message_chunk.content)

    await final_answer.send()


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
