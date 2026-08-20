import os
import json
import re
from typing import List, Dict, Any, Tuple

import PyPDF2
from google.cloud import storage
from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.generative_models import GenerativeModel


# =========================
# Configuration (edit these)
# =========================
PROJECT_ID = os.environ.get("PROJECT_ID", "YOUR_GCP_PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "europe-west4")

PDF_PATH = os.environ.get("PDF_PATH", "data/stats_sample_doc.pdf")

# IMPORTANT: bucket names must be globally unique
BUCKET_NAME = os.environ.get("BUCKET_NAME", "vertex-12345-rag-bucket")
INDEX_NAME = os.environ.get("INDEX_NAME", "stats_index")

SENTENCES_JSONL = os.environ.get("SENTENCES_JSONL", "data/stats_sentences.jsonl")
EMBEDDINGS_PATH = os.environ.get("EMBEDDINGS_PATH", "data/stats_embeddings.json")

EMBED_MODEL_NAME = os.environ.get("EMBED_MODEL_NAME", "text-embedding-004")
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "768"))

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Query settings
NUM_NEIGHBORS = int(os.environ.get("NUM_NEIGHBORS", "10"))


# =========================
# Init Vertex AI clients
# =========================
def init_clients() -> None:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    vertexai.init(project=PROJECT_ID, location=LOCATION)


# =========================
# PDF -> text -> sentences
# =========================
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF (best-effort)."""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        parts: List[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts)


def split_into_sentences(text: str) -> List[str]:
    """Simple sentence splitter (regex-based)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    return sentences


# =========================
# Embeddings + save JSONL
# =========================
def generate_text_embeddings(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a list of texts using Vertex AI embedding model."""
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL_NAME)

    embeddings: List[List[float]] = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        res = model.get_embeddings(batch)
        embeddings.extend([r.values for r in res])

    return embeddings


def save_sentences_jsonl(sentences: List[str], out_path: str) -> None:
    """Writes sentences as JSONL: one record per line."""
    with open(out_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(sentences):
            f.write(json.dumps({"id": i, "sentence": s}, ensure_ascii=False) + "\n")


def save_embeddings_jsonl(embeddings, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        for i, emb in enumerate(embeddings):
            f.write(json.dumps({"id": str(i), "embedding": emb}) + "\n")


def generate_and_save_embeddings(pdf_path: str, sentences_path: str, embeds_path: str) -> None:
    print("Reading PDF...")
    text = extract_text_from_pdf(pdf_path)

    print("Splitting into sentences...")
    sentences = split_into_sentences(text)
    print(f"Sentence count: {len(sentences)}")

    print("Saving sentences JSONL...")
    save_sentences_jsonl(sentences, sentences_path)

    print("Generating embeddings (Vertex AI)...")
    embeds = generate_text_embeddings(sentences)

    if embeds and len(embeds[0]) != EMBED_DIMENSIONS:
        raise ValueError(
            f"Embedding dimension mismatch: got {len(embeds[0])}, expected {EMBED_DIMENSIONS}. "
            "Set EMBED_DIMENSIONS to match your embedding model."
        )

    print("Saving embeddings JSONL...")
    save_embeddings_jsonl(embeds, embeds_path)

    print(f"Done. Wrote: {sentences_path}, {embeds_path}")


# =========================
# GCS upload
# =========================
def ensure_bucket(bucket_name: str) -> storage.Bucket:
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        print(f"Creating bucket: {bucket_name} (location={LOCATION})")
        bucket = client.create_bucket(bucket_name, location=LOCATION)
    return bucket


def upload_file(bucket_name: str, file_path: str, prefix: str = "") -> str:
    bucket = ensure_bucket(bucket_name)
    blob_name = f"{prefix.rstrip('/')}/{os.path.basename(file_path)}" if prefix else os.path.basename(file_path)
    blob = bucket.blob(blob_name)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"Uploading {file_path} -> {gcs_uri}")
    blob.upload_from_filename(file_path)
    return gcs_uri


# =========================
# Vector Search: create index + endpoint + deploy
# =========================
def create_vector_index(bucket_name: str, index_name: str):
    """
    Creates a Matching Engine Index (tree-ah) using contents_delta_uri pointing to a GCS folder.
    NOTE: contents_delta_uri can point to a bucket/folder where the embeddings JSONL lives.
    """
    contents_uri = f"gs://{bucket_name}/vector_data"
    print(f"Creating MatchingEngineIndex from: {contents_uri}")

    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=index_name,
        contents_delta_uri=contents_uri,
        dimensions=EMBED_DIMENSIONS,
        approximate_neighbors_count=10,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        # Workaround: ensure algorithmConfig is populated
        leaf_node_embedding_count=1000,         # OK for small datasets
        leaf_nodes_to_search_percent=7,         # a common default
    )

    print("Creating Index Endpoint...")
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=index_name,
        public_endpoint_enabled=True,
    )

    print("Deploying index to endpoint...")
    endpoint.deploy_index(index=index, deployed_index_id=index_name)

    print("Index + Endpoint ready.")
    return index, endpoint


# =========================
# Load sentences + build context
# =========================
def load_jsonl(path: str) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def generate_context(ids: List[str], data: List[Dict[str, Any]]) -> str:
    id_set = set(str(i) for i in ids)
    lines: List[str] = []
    for entry in data:
        if str(entry.get("id")) in id_set:
            lines.append(entry.get("sentence", ""))
    return "\n".join([l for l in lines if l]).strip()


# =========================
# Ask (query -> embedding -> neighbors -> context -> Gemini)
# =========================
def ask_question(
    index_ep: aiplatform.MatchingEngineIndexEndpoint,
    deployed_index_id: str,
    question: str,
    sentences_data: List[Dict[str, Any]],
    num_neighbors: int = 10,
) -> Tuple[str, List[str], str]:
    # 1) Embed the question
    q_emb = generate_text_embeddings([question])[0]

    # 2) Vector Search
    response = index_ep.find_neighbors(
        deployed_index_id=deployed_index_id,
        queries=[q_emb],
        num_neighbors=num_neighbors,
    )

    # 3) Extract IDs
    matching_ids = [neighbor.id for sublist in response for neighbor in sublist]

    # 4) Build context
    context = generate_context(matching_ids, sentences_data)

    # 5) Ask Gemini using only the retrieved context
    prompt = f"""    Answer the question ONLY using the context in triple backticks.
If the answer isn't in the context, say: "I don't know based on the document."

CONTEXT:
```{context}```

QUESTION:
{question}

ANSWER:
""".strip()

    model = GenerativeModel(GEMINI_MODEL)
    chat = model.start_chat(history=[])
    ans = chat.send_message(prompt).text
    return ans, matching_ids, context


def main() -> None:
    init_clients()

    # Step A: Create sentences + embeddings locally
    generate_and_save_embeddings(PDF_PATH, SENTENCES_JSONL, EMBEDDINGS_PATH)

    # Step B: Upload JSONL files to GCS
    upload_file(BUCKET_NAME, SENTENCES_JSONL, prefix="sentences")
    upload_file(BUCKET_NAME, EMBEDDINGS_PATH, prefix="vector_data")

    # Step C: Create index + endpoint + deploy
    _, index_ep = create_vector_index(BUCKET_NAME, INDEX_NAME)

    # Step D: Load local sentences to map ids -> sentence text
    sentences_data = load_jsonl(SENTENCES_JSONL)

    # Step E: Example question
    question = os.environ.get("QUESTION", "What is correlation?")
    answer, ids, context = ask_question(
        index_ep=index_ep,
        deployed_index_id=INDEX_NAME,
        question=question,
        sentences_data=sentences_data,
        num_neighbors=NUM_NEIGHBORS,
    )

    print("\n=== Retrieved IDs ===")
    print(ids)
    print("\n=== Context (preview) ===")
    print(context[:800] + ("..." if len(context) > 800 else ""))
    print("\n=== Gemini Answer ===")
    print(answer)


if __name__ == "__main__":
    main()
