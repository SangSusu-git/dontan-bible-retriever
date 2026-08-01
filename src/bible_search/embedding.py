from typing import Protocol
import numpy as np


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        ...


class KureEmbedder:
    def __init__(self, model_name: str = "nlpai-lab/KURE-v1",
                 device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
