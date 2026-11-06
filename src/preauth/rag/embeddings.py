import hashlib
from typing import Protocol, Sequence

import numpy as np


class Embedder(Protocol):
    name: str
    dimension: int

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class MiniLMEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype="float32")


class HashingEmbedder:
    """Deterministic, dependency-light test double; never used by the default CLI."""

    name = "test-hashing-v1"

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vectors[row, index] += 1
            norm = np.linalg.norm(vectors[row])
            if norm:
                vectors[row] /= norm
        return vectors
