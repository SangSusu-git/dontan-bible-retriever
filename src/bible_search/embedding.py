import os
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


class HfApiEmbedder:
    """HF Inference API로 KURE-v1과 동일한 임베딩을 얻는다 (로컬 모델 불필요).

    검증 결과(scripts/verify_hf_embedding.py): 코사인 일치도 1.00000,
    이미 L2 정규화됨, 기존 Chroma 인덱스에 대해 top-5 검색 결과 동일.
    """

    def __init__(self, model_name: str = "nlpai-lab/KURE-v1",
                 token: str | None = None) -> None:
        from huggingface_hub import InferenceClient, get_token

        resolved_token = token or os.environ.get("HF_TOKEN") or get_token()
        if not resolved_token:
            raise ValueError(
                "HF 토큰을 찾을 수 없습니다. token 인자, HF_TOKEN 환경변수, "
                "또는 huggingface-cli login 중 하나로 설정하세요."
            )

        self._model_name = model_name
        self._client = InferenceClient(token=resolved_token)

    def _encode_one(self, text: str) -> np.ndarray:
        out = self._client.feature_extraction(text, model=self._model_name)
        arr = np.asarray(out, dtype=np.float32)

        if arr.ndim == 1:
            vec = arr
        elif arr.ndim == 2 and arr.shape[0] == 1:
            vec = arr[0]
        else:
            raise ValueError(
                f"예상치 못한 임베딩 형태 {arr.shape} — 토큰 단위 출력일 수 있습니다. "
                "평균 풀링을 임의로 적용하지 않습니다."
            )

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = [self._encode_one(text) for text in texts]
        return np.vstack(vecs).astype(np.float32)
