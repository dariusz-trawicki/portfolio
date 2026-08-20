# PDF RAG Assistant (LangChain + Streamlit)

A lightweight `Retrieval-Augmented Generation` (RAG) application that allows users to chat with their own PDF documents using OpenAI models.

This project demonstrates how to build a clean, production-style RAG pipeline with document ingestion, vector search, conversational memory, and a simple Streamlit UI.

---

## Features

- Upload one or multiple PDF documents
- Automatic text extraction and chunking
- Semantic search using FAISS vector store
- Conversational question answering with memory
- Powered by OpenAI (gpt-4o-mini by default)
- Safe answers: no guessing, no hallucinations
- Minimal and cost-efficient prompt design

---

## Tech Stack

- Python 3.11+
- Streamlit (UI)
- LangChain (RAG orchestration)
- OpenAI API (LLM and embeddings)
- FAISS (vector database)
- pdfplumber (PDF text extraction)
- uv (dependency and environment management)

---

## How It Works (RAG Pipeline)

1. PDF documents are uploaded via the Streamlit interface
2. Text is extracted and split into chunks
3. Each chunk is converted into embeddings
4. FAISS stores vectors for semantic retrieval
5. User questions retrieve the most relevant chunks
6. The LLM answers strictly based on retrieved context
7. Conversation history is preserved in memory

---

## Run

### 1. Create the environment using uv
```bash
uv venv
uv sync
```

### 2. Configure environment variables
Create a .env file:
```env
OPENAI_API_KEY=your_api_key_here
```


### 3. Run the Application

```bash
uv run streamlit run app.py
```

Open your browser at:
```
http://localhost:8501
```

---

## Example Questions

- What is the title of the raport?
- Invoice no.?

---

## Prompt Safety

The assistant is instructed to:
- Not use external knowledge
- Not guess or hallucinate answers
- Respond only if the information exists in the documents

If the answer cannot be found, the assistant responds:
"Sorry, I could not find an answer in the provided documents."

---

## Configuration

### Change the model
```python
ChatOpenAI(
    model="gpt-4o-mini",  # or "gpt-4"
    temperature=0
)
```

### Adjust retrieval depth
```python
retriever = vector_store.as_retriever(search_kwargs={"k": 4})
```

---

## Possible Improvements

- Add source citations per answer
- Implement context compression
- Support metadata-based filtering
- Add OCR for scanned PDFs
- Enable streaming responses
- Provide a FastAPI backend
