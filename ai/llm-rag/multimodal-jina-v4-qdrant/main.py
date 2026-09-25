"""
Multimodal search demo: jina-embeddings-v4 + Qdrant (in-memory).

Text and images live in ONE embedding space, so they are stored in ONE
collection and searched with ONE query - in all four directions:
text->text, text->image, image->text, image->image.
"""
import base64
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()

API_URL = "https://api.jina.ai/v1/embeddings"
MODEL = "jina-embeddings-v4"
DIM = 1024          # 2048 by default, can be truncated down to 128
COLLECTION = "docs"
IMG_DIR = "images"

TEXTS = [
    "Kubernetes orchestrates containers across a cluster of machines, handling scaling and self-healing.",
    "Company A dominates the cloud market with a 45% share, followed by Company B with 30%.",
    "Revenue grew every quarter in 2025, reaching 3.1 million USD in Q4.",
    "To bake sourdough bread, mix flour, water and starter, then let the dough rise overnight.",
    "GPU instances on AWS such as g5.xlarge cost around one dollar per hour.",
    "Terraform describes cloud infrastructure as code and applies it with a single command.",
]


# ---------------------------------------------------------------------------
# 1. Sample images - generated locally, so the demo needs no downloads
# ---------------------------------------------------------------------------
def save_fig(fig, name: str) -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    path = os.path.join(IMG_DIR, name)
    fig.savefig(path, dpi=80, bbox_inches="tight")
    plt.close(fig)
    return path


def make_images() -> tuple[list[str], str]:
    quarters = ["Q1", "Q2", "Q3", "Q4"]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(quarters, [1.2, 1.8, 2.4, 3.1], color="steelblue")
    ax.set_title("Revenue 2025 (M USD)")
    bar = save_fig(fig, "revenue_bar_chart.png")

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie([45, 30, 25], labels=["Company A", "Company B", "Others"], autopct="%1.0f%%")
    ax.set_title("Cloud market share")
    pie = save_fig(fig, "market_share_pie.png")

    fig, ax = plt.subplots(figsize=(5, 2.5))
    ax.axis("off")
    table = ax.table(
        cellText=[["t3.medium", "2", "4 GB", "$0.04"],
                  ["g5.xlarge", "4", "16 GB", "$1.01"],
                  ["p4d.24xlarge", "96", "1152 GB", "$32.77"]],
        colLabels=["Instance", "vCPU", "RAM", "Price / h"],
        loc="center",
    )
    table.scale(1, 1.6)
    ax.set_title("AWS EC2 on-demand pricing")
    tbl = save_fig(fig, "ec2_pricing_table.png")

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.axis("off")
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 2)
    for i, label in enumerate(["User", "API Gateway", "Database"]):
        x = 0.3 + i * 2
        ax.add_patch(plt.Rectangle((x, 0.6), 1.4, 0.8, fill=False, lw=2))
        ax.text(x + 0.7, 1.0, label, ha="center", va="center")
        if i < 2:
            ax.annotate("", xy=(x + 2, 1.0), xytext=(x + 1.4, 1.0),
                        arrowprops=dict(arrowstyle="->", lw=2))
    ax.set_title("System architecture")
    arch = save_fig(fig, "architecture_diagram.png")

    # Query-only image - NOT stored in the database
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.plot(quarters, [0.9, 1.5, 2.2, 2.9], marker="o", color="green")
    ax.set_title("Sales growth per quarter")
    query_img = save_fig(fig, "query_sales_line_chart.png")

    return [bar, pie, tbl, arch], query_img


def b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ---------------------------------------------------------------------------
# 2. Embeddings via Jina API - text and images go through the same model
# ---------------------------------------------------------------------------
def embed(items: list[dict], task: str) -> list[list[float]]:
    """items: [{"text": "..."}] or [{"image": "<base64 or URL>"}], mixed is fine."""
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {os.environ['JINA_API_KEY']}"},
        json={"model": MODEL, "task": task, "dimensions": DIM, "input": items},
        timeout=120,
    )
    if not resp.ok:
        sys.exit(f"Jina API error {resp.status_code}: {resp.text}")
    usage = resp.json().get("usage", {})
    print(f"  [{task}] {len(items)} input(s), tokens used: {usage.get('total_tokens', '?')}")
    return [d["embedding"] for d in resp.json()["data"]]


# ---------------------------------------------------------------------------
# 3. One collection for everything
# ---------------------------------------------------------------------------
def build_index(client: QdrantClient, image_paths: list[str]) -> None:
    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
    )
    items = [{"text": t} for t in TEXTS] + [{"image": b64(p)} for p in image_paths]
    payloads = ([{"type": "text", "content": t} for t in TEXTS]
                + [{"type": "image", "content": os.path.basename(p)} for p in image_paths])

    vectors = embed(items, task="retrieval.passage")
    client.upsert(COLLECTION, points=[
        models.PointStruct(id=i, vector=v, payload=p)
        for i, (v, p) in enumerate(zip(vectors, payloads))
    ])


def search(client: QdrantClient, title: str, query: dict,
           only: str | None = None, limit: int = 3) -> None:
    vec = embed([query], task="retrieval.query")[0]
    flt = None
    if only:
        flt = models.Filter(must=[models.FieldCondition(
            key="type", match=models.MatchValue(value=only))])
    hits = client.query_points(COLLECTION, query=vec, query_filter=flt, limit=limit).points

    print(f"\n=== {title} ===")
    for h in hits:
        content = h.payload["content"]
        if len(content) > 80:
            content = content[:77] + "..."
        print(f"  {h.score:.3f}  [{h.payload['type']:5}]  {content}")


def main() -> None:
    if not os.getenv("JINA_API_KEY"):
        sys.exit("Set JINA_API_KEY (free key: https://jina.ai/embeddings)")

    print("Generating sample images...")
    image_paths, query_img = make_images()

    print("Indexing texts and images into ONE Qdrant collection...")
    client = QdrantClient(":memory:")
    build_index(client, image_paths)

    print("\nSearching...")
    search(client, "1. Text -> Text",
           {"text": "How do I run containers on many servers?"}, only="text")
    search(client, "2. Text -> Image",
           {"text": "chart showing revenue per quarter"}, only="image")
    search(client, "3. Image -> Text  (query: market_share_pie.png)",
           {"image": b64(os.path.join(IMG_DIR, "market_share_pie.png"))}, only="text")
    search(client, "4. Image -> Image (query: query_sales_line_chart.png, not in DB)",
           {"image": b64(query_img)}, only="image")
    search(client, "5. All at once - no filter, mixed results",
           {"text": "How much does a GPU server cost per hour?"}, limit=4)


if __name__ == "__main__":
    main()
