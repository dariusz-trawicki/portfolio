import math
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st

warnings.filterwarnings("ignore", category=DeprecationWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

TOP_K_MEMORIES = 3
MAX_HISTORY_TURNS = 10
DEDUP_THRESHOLD = 0.15      # cosine distance — below this value = duplicate
CALC_TIMEOUT_SEC = 2
MODEL_NAME = "llama3.2"


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(page_title="AI Memory Agent", layout="centered")
st.title("🤖 AI Memory-Enabled Assistant")


# =============================================================================
# CACHED RESOURCES
# =============================================================================

@st.cache_resource
def load_llm():
    return ChatOllama(model=MODEL_NAME)


@st.cache_resource
def load_embeddings():
    return OllamaEmbeddings(model=MODEL_NAME)


@st.cache_resource
def load_vector_store():
    return Chroma(
        collection_name="agent_memory",
        embedding_function=load_embeddings(),
        persist_directory="./memory_db"
    )


llm = load_llm()
vector_store = load_vector_store()


# =============================================================================
# SESSION STATE
# =============================================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False


# =============================================================================
# CLEAR MEMORY BUTTON (two-step confirmation)
# =============================================================================

col1, col2 = st.columns([4, 1])

with col2:
    if st.button("🗑️ Clear Memory"):
        st.session_state.confirm_clear = True

if st.session_state.confirm_clear:
    st.warning("⚠️ This will permanently delete all memories. Are you sure?")
    col_yes, col_no = st.columns(2)

    if col_yes.button("✅ Yes, clear everything"):
        vector_store.delete_collection()
        st.cache_resource.clear()
        st.session_state.clear()
        st.rerun()

    if col_no.button("❌ Cancel"):
        st.session_state.confirm_clear = False
        st.rerun()


# =============================================================================
# CALCULATOR TOOL
# =============================================================================

def safe_calculate(expression: str) -> str | None:
    """
    Evaluates expression as math. Returns result string or None.

    Uses ThreadPoolExecutor instead of signal.SIGALRM — signal doesn't work
    in Streamlit's background threads and fails on Windows.
    """
    def _eval():
        # __builtins__={} blocks open(), exec(), __import__() etc.
        # vars(math) exposes sin(), cos(), sqrt(), pi, e ...
        return eval(expression, {"__builtins__": {}}, vars(math))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_eval)
        try:
            return str(future.result(timeout=CALC_TIMEOUT_SEC))
        except FuturesTimeoutError:
            future.cancel()
            return None
        except Exception:
            return None


# =============================================================================
# MEMORY HELPERS
# =============================================================================

def retrieve_memories(query: str) -> str:
    docs = vector_store.similarity_search(query, k=TOP_K_MEMORIES)
    if not docs:
        return ""
    memory_lines = "\n".join(f"- {doc.page_content}" for doc in docs)
    return f"\nRelevant past memories:\n{memory_lines}\n"


def store_memory(query: str, answer: str) -> None:
    memory_entry = f"User: {query}\nAssistant: {answer}"

    # Skip storing if a very similar memory already exists
    results = vector_store.similarity_search_with_score(query, k=1)
    if results:
        _, score = results[0]
        if score < DEDUP_THRESHOLD:
            return

    vector_store.add_documents([Document(page_content=memory_entry)])
    # Note: vector_store.persist() is deprecated since ChromaDB >= 0.4.x


def format_history(history: list[dict]) -> str:
    # Sliding window — prevents exceeding the model's context window
    recent = history[-(MAX_HISTORY_TURNS * 2):]
    return "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in recent)


# =============================================================================
# RENDER CHAT HISTORY
# =============================================================================

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =============================================================================
# CHAT INPUT
# =============================================================================

if prompt := st.chat_input("Ask something..."):

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.chat_history.append({"role": "user", "content": prompt})

    math_result = safe_calculate(prompt)

    if math_result is not None:
        response_text = f"🧮 **Answer:** {math_result}"

    else:
        memory_context = retrieve_memories(prompt)
        history_text = format_history(st.session_state.chat_history)

        system_msg = SystemMessage(content=(
            "You are a helpful AI assistant with long-term memory. "
            "Use the provided memories and conversation history to give "
            "consistent, context-aware responses."
        ))

        human_msg = HumanMessage(content=f"""\
{memory_context}
Conversation history:
{history_text}

User: {prompt}""")

        try:
            with st.spinner("Thinking..."):
                response = llm.invoke([system_msg, human_msg])
            response_text = response.content

        except Exception as e:
            response_text = f"⚠️ Error: {e}"
            st.error("Make sure Ollama is running: `ollama serve`")

        if not response_text.startswith("⚠️"):
            store_memory(prompt, response_text)

    with st.chat_message("assistant"):
        st.markdown(response_text)

    st.session_state.chat_history.append({"role": "assistant", "content": response_text})
