from openai import OpenAI
from pathlib import Path
import weaviate
from weaviate.classes.config import Configure, Property, DataType, VectorDistances

COLLECTION_NAME = "ExampleData"
EXAMPLE_DATA_PATH = "./example_data"

CLIENT = OpenAI(base_url="http://localhost:8080/v1", api_key="anything")


def calculate_embedding(text):
    response = CLIENT.embeddings.create(input="</s>" + text, model="ipipan/silver-retriever-base-v1")
    embedding = response.data[0].embedding
    return embedding



def load_text_data(data_path):
    texts = []
    for file in Path(data_path).glob("*.md"):
        texts.append(
            file.read_text()
        )
    return texts

def chunk_text(text, chunk_size, chunk_overlap):
    result = []

    for i in range(0, len(text), chunk_size - chunk_overlap):
        text_chunk = text[i: i + chunk_size]
        result.append(text_chunk)

    return result


def main():
    texts = load_text_data(EXAMPLE_DATA_PATH)

    text_chunks = []
    for text in texts:
        text_chunks.extend(chunk_text(text, 512, 128))

    embeddings = [calculate_embedding(ch) for ch in text_chunks]

    DB_CLIENT = weaviate.connect_to_local(
        host="localhost",
        port=8081,      # <- weaviate REST on localhost
        grpc_port=50051
    )

    try:
        # reset collection on each run (dev-friendly)
        if DB_CLIENT.collections.exists(COLLECTION_NAME):
            DB_CLIENT.collections.delete(COLLECTION_NAME)

        DB_CLIENT.collections.create(
            COLLECTION_NAME,
            properties=[
                Property(name="text", data_type=DataType.TEXT),
            ],
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE
                )
            ),
        )
        collection = DB_CLIENT.collections.get(COLLECTION_NAME)

        for text_chunk, embedding in zip(text_chunks, embeddings):
            collection.data.insert(
                properties={"text": text_chunk},
                vector=embedding,
            )

        total_count = collection.aggregate.over_all(total_count=True).total_count
        print(total_count)

    finally:
        DB_CLIENT.close()


if __name__ == "__main__":
    main()
