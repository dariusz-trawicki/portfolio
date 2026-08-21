import warnings
warnings.filterwarnings("ignore")

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from typing import TypedDict
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

# ─────────────────────────────────────────
# 1. STATE
# ─────────────────────────────────────────
class AgentState(TypedDict):
    question: str
    search_results: str
    answer: str
    needs_search: bool

# ─────────────────────────────────────────
# 2. LLM + TOOLS
# ─────────────────────────────────────────
llm = ChatOpenAI(model="gpt-4o", temperature=0)
search_tool = TavilySearch(max_results=3)

class AnalysisResult(BaseModel):
    needs_search: bool
    reason: str

# ─────────────────────────────────────────
# 3. NODES
# ─────────────────────────────────────────
def analyze(state: AgentState):
    structured_llm = llm.with_structured_output(AnalysisResult)
    result = structured_llm.invoke(f"""
        Does answering this question require up-to-date data from the internet?
        Question: {state['question']}
        Examples requiring search: weather, exchange rates, current news.
        Examples NOT requiring search: math, definitions, history.
    """)
    print(f"[analyze] needs_search={result.needs_search} | reason={result.reason}")
    return {"needs_search": result.needs_search}


def search(state: AgentState):
    print(f"[search] searching for: {state['question']}")
    results = search_tool.invoke(state["question"])
    print(f"[search] results found")
    return {"search_results": results}


def answer(state: AgentState):
    if state.get("search_results"):
        prompt = f"""
            Question: {state['question']}
            Current data from the internet: {state['search_results']}
            Answer concisely based on the above data.
        """
    else:
        prompt = f"Answer the following question: {state['question']}"

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"[answer] {response.content}")
    return {"answer": response.content}

# ─────────────────────────────────────────
# 4. ROUTER
# ─────────────────────────────────────────
def router(state: AgentState):
    if state["needs_search"]:
        return "search"
    return "answer"

# ─────────────────────────────────────────
# 5. GRAPH
# ─────────────────────────────────────────
graph = StateGraph(AgentState)

graph.add_node("analyze", analyze)
graph.add_node("search", search)
graph.add_node("answer", answer)

graph.set_entry_point("analyze")

graph.add_conditional_edges("analyze", router, {
    "search": "search",
    "answer": "answer"
})

graph.add_edge("search", "answer")
graph.add_edge("answer", END)

app = graph.compile()

# ─────────────────────────────────────────
# 6. RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    result = app.invoke({"question": "What is the weather like in Warsaw today?"})
    print("\n✅ Answer:", result["answer"])

    print("\n" + "─"*50 + "\n")

    result = app.invoke({"question": "What is 2 to the power of 10?"})
    print("\n✅ Answer:", result["answer"])
