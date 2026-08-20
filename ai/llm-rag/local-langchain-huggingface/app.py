import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import shutil
import streamlit as st

from config import load_llm_pipeline
from ingest import ingest_pdfs
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFacePipeline

UPLOAD_DIR = "pdfs"
VECTORSTORE_DIR = "vectorstore"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

@st.cache_resource
def load_rag_chain():
    print("⏳ Loading RAG chain...")
    vectordb = load_vectorstore()
    pipe = load_llm_pipeline()
    llm = HuggingFacePipeline(pipeline=pipe)
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectordb.as_retriever(search_kwargs={"k": 1}),
        chain_type="stuff",
        return_source_documents=True
    )
    print("✅ RAG chain ready.")
    return chain

# --- UI ---
st.title("🔍 RAG AI with Hugging Face & PDF Upload")

# Upload section
uploaded_files = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

if st.button("Build Knowledge Base"):
    if uploaded_files:
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for file in uploaded_files:
            file_path = os.path.join(UPLOAD_DIR, file.name)
            with open(file_path, "wb") as f:
                f.write(file.read())
        with st.spinner("Building knowledge base..."):
            ingest_pdfs()
        st.success("✅ Knowledge base created.")
        st.cache_resource.clear()  # odśwież chain po nowych PDFach
    else:
        st.warning("⚠️ No files uploaded.")

# Q&A section
question = st.text_input("Ask a question")

if question:
    with st.spinner("Thinking..."):
        rag_chain = load_rag_chain()
        result = rag_chain.invoke({"query": question})

    answer = result["result"]
    source_docs = result["source_documents"]

    st.subheader("🤖 Answer")
    st.write(answer)

    st.subheader("📚 Sources")
    for doc in source_docs:
        with st.expander(doc.metadata.get("source", "Unknown")):
            st.write(doc.page_content[:500] + "...")
