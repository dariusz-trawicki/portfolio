# GCP Vertex AI RAG (PDF → Vector Search → Gemini)

This repo contains a course-style, end-to-end example:

1. Read a local PDF
2. Split into sentences and save to `stats_sentences.jsonl`
3. Create embeddings with Vertex AI and save to `stats_embeddings.jsonl`
4. Upload both files to a Google Cloud Storage bucket
5. Create a Vertex AI Vector Search (Matching Engine) index from the GCS data
6. Create an Index Endpoint and deploy the index
7. Run a query: embed the question → `find_neighbors` → build context → ask Gemini

> **Costs & time:** Creating a Vector Search index/endpoint may take several minutes and can incur charges.

## Prerequisites

- A Google Cloud project with billing enabled
- IAM permissions:
  - Vertex AI Admin (or enough to create Matching Engine indexes/endpoints)
  - Storage Admin (or enough to create bucket/upload)
- APIs enabled:
  - `aiplatform.googleapis.com`
  - `storage.googleapis.com`
- Python 3.9+ recommended

Authenticate (one of):
- Local: `gcloud auth application-default login`
- Cloud Shell: usually already authenticated
- Colab: use `google.colab` auth + ADC as needed

Enable APIs (Cloud Shell / terminal):

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com storage.googleapis.com
```


## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade google-cloud-aiplatform google-cloud-storage vertexai PyPDF2
```

## Files

- `rag_pdf_vertex_vector_search.py` — main script
- Outputs created at runtime:
  - `stats_sentences.jsonl`
  - `stats_embeddings.jsonl`

## Configure

You can edit constants in the script, or set environment variables:

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export LOCATION="europe-west4"
export PDF_PATH="data/stats_sample_doc.pdf"

# Bucket name must be globally unique:
export BUCKET_NAME="vertex-12345-rag-bucket"

export INDEX_NAME="stats_index"
export QUESTION="What is correlation?"
```

Optional:

```bash
export EMBED_MODEL_NAME="text-embedding-004"
export EMBED_DIMENSIONS="768"
export GEMINI_MODEL="gemini-1.5-flash"
export NUM_NEIGHBORS="10"
```

## Run

```bash
python rag.py
```

You should see:
- sentence count
- uploads to `gs://...`
- index/endpoint creation + deploy
- retrieved IDs + context preview
- Gemini answer

## Cleanup (recommended)

After testing, delete resources to avoid ongoing costs:
- Vector Search index
- Index endpoint
- GCS bucket (or at least uploaded objects)

You can delete from the GCP Console:
- Vertex AI → Vector Search
- Cloud Storage → Buckets
