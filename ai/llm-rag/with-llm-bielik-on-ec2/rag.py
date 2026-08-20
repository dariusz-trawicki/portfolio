import httpx
import weaviate
from openai import OpenAI
from weaviate.collections.classes.grpc import MetadataQuery

BASE_URL = "http://35.159.106.157:8000/v1"
LIT_SERVER_API_KEY = "your_key"

COLLECTION_NAME = "ExampleData"
EMB_MODEL = "ipipan/silver-retriever-base-v1"

# === Clients ===
EMB_CLIENT = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="unused"
)

LLM_CLIENT = OpenAI(
    base_url=BASE_URL,
    api_key="unused",
    http_client=httpx.Client(
        headers={"X-API-Key": LIT_SERVER_API_KEY},
        timeout=60.0
    )
)

def embed(text: str):
    r = EMB_CLIENT.embeddings.create(
        model=EMB_MODEL,
        input="</s>" + text
    )
    return r.data[0].embedding

def generate(prompt: str):
    r = LLM_CLIENT.chat.completions.create(
        model="lit",
        messages=[
            {"role": "system", "content": "You respond in English, using only the provided documents."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=512,
        temperature=0.2
    )
    return r.choices[0].message.content

def main():
    question = "What does Xxxx IT offer?"

    qvec = embed(question)

    DB = weaviate.connect_to_local(
        host="localhost",
        port=8081,
        grpc_port=50051
    )

    try:
        col = DB.collections.get(COLLECTION_NAME)
        res = col.query.near_vector(
            near_vector=qvec,
            limit=3,
            return_metadata=MetadataQuery(distance=True)
        )

        docs = [o.properties["text"] for o in res.objects]

    finally:
        DB.close()

    prompt = (
        f"Question: {question}\n\n"
        "Documents:\n" +
        "\n\n".join(f"- {d}" for d in docs)
    )

    print(generate(prompt))

if __name__ == "__main__":
    main()
