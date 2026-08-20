import streamlit as st
import time
import os
from dotenv import load_dotenv

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings, ChatNVIDIA
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS

load_dotenv()
os.environ["NVIDIA_API_KEY"] = os.getenv("NVIDIA_API_KEY", "")

for key in ("embeddings", "loader", "docs", "text_splitter", "final_documents", "vectors"):
    st.session_state.setdefault(key, None)

llm = ChatNVIDIA(model="meta/llama3-70b-instruct")


def vector_embedding():
    if st.session_state.get("vectors") is None:
        st.session_state.embeddings = NVIDIAEmbeddings()
        st.session_state.loader = PyPDFDirectoryLoader("./pdfs")
        st.session_state.docs = st.session_state.loader.load()

        if not st.session_state.docs:
            st.warning("No PDFs found in ./pdfs. Please add some files.")
            return

        st.session_state.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
        )
        split_docs = st.session_state.text_splitter.split_documents(
            st.session_state.docs[:10]
        )
        st.session_state.final_documents = split_docs
        st.session_state.vectors = FAISS.from_documents(
            st.session_state.final_documents,
            st.session_state.embeddings,
        )


st.title("PDF Question Answering with NVIDIA Embeddings and LLMs")

prompt = ChatPromptTemplate.from_template(
    """
Answer the questions based on the provided context only.
Please provide the most accurate response based on the question.

<context>
{context}
</context>
Question: {input}
"""
)

if st.button("Document Embedding", key="embed_btn"):
    vector_embedding()
    if st.session_state.get("vectors") is not None:
        st.success("FAISS Vector Store DB is ready using NVIDIA Embeddings")

user_q = st.text_input("Enter your question from documents")
response = None


if user_q:
    if st.session_state.get("vectors") is None:
        vector_embedding()

    if st.session_state.get("vectors") is not None:
        retriever = st.session_state.vectors.as_retriever()

        # ── LCEL chain (zamiennik create_stuff + create_retrieval) ──
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain = (
            {
                "context": retriever | format_docs,
                "input": RunnablePassthrough()
            }
            | prompt
            | llm
            | StrOutputParser()
        )

        t0 = time.perf_counter()
        answer = rag_chain.invoke(user_q)
        st.caption(f"Response time: {time.perf_counter() - t0:.2f}s")
        st.write(answer)

        # zachowaj dla ekspandera
        response = {
            "answer": answer,
            "context": retriever.invoke(user_q)  # pobierz chunki do wyświetlenia
        }
    else:
        st.warning("Please add PDFs to ./pdfs and build the vector index first.")


if response and "context" in response:
    with st.expander("Document Similarity Search"):
        for i, doc in enumerate(response["context"]):
            st.write(doc.page_content)
            st.write("-----------------------------")
else:
    st.info("Run a query to see document similarity results.")
