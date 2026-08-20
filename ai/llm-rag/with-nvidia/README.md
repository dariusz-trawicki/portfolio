# RAG: PDF Question Answering with NVIDIA Embeddings and Llama 3 (70B)

This demo showcases how to use **NVIDIA AI Endpoints** with **LangChain** and **Streamlit**
to build a simple **question-answering application** powered by **vector search** and **Large Language Models (LLMs)**.

The app loads PDF files, generates vector embeddings using **NVIDIA Embeddings**, 
stores them in a **FAISS vector database**, and allows you to ask natural language questions about the documents.

---

## Features

- Load multiple PDF files from a local folder  
- Automatically split text into small overlapping chunks  
- Generate embeddings using **NVIDIA Embeddings API**  
- Store embeddings in **FAISS vector store**  
- Use **Llama 3 70B-Instruct** via NVIDIA API for question answering  
- Retrieve and display similar document sections for transparency  
- Interactive web UI built with **Streamlit**

---

## Run

### 1. Create and activate a virtual environment
Using Conda (recommended):
```bash
conda create -p ./venv python=3.12 -y
conda activate ./venv
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Environment Setup

Create a `.env` file in the project root with your NVIDIA API key:

```
NVIDIA_API_KEY="nvidia_api_key_here"
```

Get the key from the **NVIDIA AI Foundation Models Catalog**:  
[https://build.nvidia.com](https://build.nvidia.com)

---

## Prepare PDF Documents

Place the PDF files in a folder named `./pdfs/`, e.g.:

```
pdfs/
├─ file-01.pdf
├─ file-02.pdf
└─ file-03pdf
```

The app will automatically read and embed up to 10 documents for demo purposes.

---

## Run the Application

Start the Streamlit app:
```bash
streamlit run pdf-app.py
```

Open your browser at:
[http://localhost:8501](http://localhost:8501)

Enter Your Question From Documents, for example:
`Give me the content of Article I, Section 1.`

---

## How It Works

1️⃣ **Document Loading** – reads PDF files and extracts text  
2️⃣ **Text Splitting** – splits text into ~400-character overlapping chunks  
3️⃣ **Embedding Generation** – sends chunks to NVIDIA API for vector embeddings  
4️⃣ **Vector Storage** – stores embeddings in a FAISS index  
5️⃣ **Retrieval + LLM** – retrieves the most relevant chunks and sends them to **Llama 3 70B-Instruct**  
6️⃣ **Answer Display** – shows the generated answer and relevant document excerpts

---

## Cost & API Usage

- This demo uses **free NVIDIA API credits** (several thousand upon signup).  
- When credits run out, you’ll see an error like `insufficient credits`.  
- You can request more credits or connect a payment method on [build.nvidia.com](https://build.nvidia.com).


---

## CLEAN UP

```bash
conda deactivate
conda remove -p ./venv --all
```
