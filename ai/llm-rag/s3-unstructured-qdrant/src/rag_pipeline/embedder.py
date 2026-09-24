"""Turns text into dense vectors using a local sentence-transformers model."""

from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model_name: str, batch_size: int = 32):
        self._model = SentenceTransformer(model_name)
        self.batch_size = batch_size
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Normalized vectors make cosine similarity equivalent to a dot product.
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
