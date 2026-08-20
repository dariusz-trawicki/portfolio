import streamlit as st
from dotenv import load_dotenv
import pdfplumber

from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


# -----------------------------
# PDF processing
# -----------------------------

def extract_text_from_pdfs(uploaded_files):
    full_text = ""
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                full_text += page.extract_text() or ""
    return full_text


def split_text_into_chunks(text):
    splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1200,
        chunk_overlap=100,
        length_function=len
    )
    return splitter.split_text(text)


# -----------------------------
# Vector store
# -----------------------------

def build_vector_store(chunks):
    embeddings = OpenAIEmbeddings()
    return FAISS.from_texts(chunks, embeddings)


# -----------------------------
# Conversation chain (RAG)
# -----------------------------

def create_rag_chain(vector_store):
    # llm = ChatOpenAI(
    #     model="gpt-4o-mini",   # change to "gpt-4" if needed
    #     temperature=0
    # )
    llm = ChatOpenAI()
    chat_memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        input_key="question"
    )

    retriever = vector_store.as_retriever(search_kwargs={"k": 4})

    prompt = PromptTemplate.from_template(
        "Answer using ONLY the context and chat history.\n"
        "If the answer is not present, say:\n"
        "\"Sorry, I could not find an answer in the provided documents.\"\n\n"
        "Chat history:\n{chat_history}\n\n"
        "Context:\n{context}\n\n"
        "Question:\n{question}\n"
        "Answer:"
    )

    rag_chain = (
        {
            "context": retriever,
            "question": RunnablePassthrough(),
            "chat_history": lambda _: chat_memory.load_memory_variables({})["chat_history"]
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    st.session_state.chat_memory = chat_memory
    return rag_chain


# -----------------------------
# Chat handling
# -----------------------------

def handle_chat_input(user_query):
    if not st.session_state.rag_chain:
        st.error("Upload documents and click Process first.")
        return

    answer = st.session_state.rag_chain.invoke(user_query)

    st.session_state.chat_memory.save_context(
        {"question": user_query},
        {"output": answer}
    )

    st.session_state.chat_log.append(
        {"role": "user", "content": user_query}
    )
    st.session_state.chat_log.append(
        {"role": "ai", "content": answer}
    )

    for msg in st.session_state.chat_log:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


# -----------------------------
# Streamlit app
# -----------------------------

def main():
    load_dotenv()
    st.set_page_config(page_title="PDF RAG Assistant")

    if "rag_chain" not in st.session_state:
        st.session_state.rag_chain = None
    if "chat_log" not in st.session_state:
        st.session_state.chat_log = []
    if "chat_memory" not in st.session_state:
        st.session_state.chat_memory = None

    st.header("PDF Document Assistant")

    user_input = st.chat_input("Ask a question about your documents...")
    if user_input:
        handle_chat_input(user_input)

    with st.sidebar:
        st.subheader("Upload PDFs")

        uploaded_pdfs = st.file_uploader(
            "Upload PDF files and click Process",
            accept_multiple_files=True
        )

        if st.button("Process"):
            if not uploaded_pdfs:
                st.error("Please upload at least one PDF.")
                return

            with st.spinner("Processing documents..."):
                raw_text = extract_text_from_pdfs(uploaded_pdfs)

                if not raw_text.strip():
                    st.error("No text could be extracted from the PDFs.")
                    return

                text_chunks = split_text_into_chunks(raw_text)
                vector_store = build_vector_store(text_chunks)

                st.session_state.rag_chain = create_rag_chain(vector_store)
                st.session_state.chat_log = []

                st.success(
                    f"Processed {len(uploaded_pdfs)} document(s) successfully."
                )


if __name__ == "__main__":
    main()
