"""numpy 기반 경량 벡터 저장소: Chroma 없이 dense 검색을 수행한다.

3만여 절 규모(31,017 x 1024)에서는 브루트포스 행렬곱이 밀리초 단위로 끝나므로,
배포 시 무거운 chromadb 의존성(onnxruntime, kubernetes 등) 없이도 충분하다.
"""
import json
from pathlib import Path

import numpy as np

from bible_search.embedding import Embedder
from bible_search.models import SearchResult, Verse


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def build_numpy_index(verses: list[Verse], embedder: Embedder, out_dir: str,
                      dtype: str = "float16") -> int:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if verses:
        embeddings = embedder.encode([v.text for v in verses]).astype(np.float32)
        embeddings = _l2_normalize(embeddings)
        vectors = embeddings.astype(dtype)
        ids = [v.id for v in verses]
    else:
        vectors = np.zeros((0, 0), dtype=dtype)
        ids = []

    # np.save/json.dump overwrite the target file in place, so re-running
    # this against the same out_dir is idempotent.
    np.save(out_path / "vectors.npy", vectors)
    with open(out_path / "ids.json", "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)

    return len(ids)


def load_numpy_index(out_dir: str) -> tuple[np.ndarray, list[str]]:
    out_path = Path(out_dir)
    # 저장은 float16(용량 절감)으로 하되, 계산 정확도를 위해 float32로 올린다.
    vectors = np.load(out_path / "vectors.npy").astype(np.float32)
    with open(out_path / "ids.json", "r", encoding="utf-8") as f:
        ids = json.load(f)
    return vectors, ids


class NumpyDenseRetriever:
    def __init__(self, vectors: np.ndarray, ids: list[str], verses: list[Verse],
                 embedder: Embedder, threshold: float = 0.8) -> None:
        self._vectors = vectors
        self._ids = ids
        self._embedder = embedder
        self._threshold = threshold
        self._by_id = {v.id: v for v in verses}

    def search(self, query: str) -> list[SearchResult]:
        if len(self._ids) == 0:
            return []
        q = self._embedder.encode([query])[0].astype(np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
        sims = self._vectors @ q
        out: list[SearchResult] = []
        for vid, sim in zip(self._ids, sims):
            sim = float(sim)
            if sim >= self._threshold and vid in self._by_id:
                out.append(SearchResult(verse=self._by_id[vid], score=sim, source="dense"))
        out.sort(key=lambda r: r.score, reverse=True)
        return out
