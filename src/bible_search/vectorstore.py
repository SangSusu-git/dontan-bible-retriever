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
                      dtype: str = "float16", dim: int | None = None) -> int:
    """verses를 임베딩해 numpy 인덱스로 저장한다.

    dim이 주어지면 L2 정규화된 전체 차원 행렬에 SVD를 적용해 상위 dim개
    특이벡터(Vt[:dim])를 기저로 삼아 투영·재정규화한 벡터를 저장하고,
    그 기저를 basis.npy에 float32로 별도 저장한다(투영 정확도를 위해
    항상 float32 — dtype 인자는 벡터 저장에만 적용된다).
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    basis: np.ndarray | None = None

    if verses:
        embeddings = embedder.encode([v.text for v in verses]).astype(np.float32)
        embeddings = _l2_normalize(embeddings)

        if dim is not None:
            orig_dim = embeddings.shape[1]
            if dim >= orig_dim:
                raise ValueError(
                    f"dim({dim})은 임베딩 차원({orig_dim})보다 작아야 합니다."
                )
            _, _, Vt = np.linalg.svd(embeddings, full_matrices=False)
            basis = Vt[:dim].astype(np.float32)
            embeddings = _l2_normalize(embeddings @ basis.T)

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

    basis_path = out_path / "basis.npy"
    if basis is not None:
        np.save(basis_path, basis)
    elif basis_path.exists():
        # dim 없이 재빌드하면(예: 이전에 dim으로 빌드했던 out_dir 재사용)
        # 오래된 기저 파일이 남아 load_numpy_index가 잘못된 기저를
        # 돌려주지 않도록 지운다.
        basis_path.unlink()

    return len(ids)


def load_numpy_index(out_dir: str) -> tuple[np.ndarray, list[str], np.ndarray | None]:
    out_path = Path(out_dir)
    # 저장은 float16(용량 절감)으로 하되, 계산 정확도를 위해 float32로 올린다.
    vectors = np.load(out_path / "vectors.npy").astype(np.float32)
    with open(out_path / "ids.json", "r", encoding="utf-8") as f:
        ids = json.load(f)
    basis_path = out_path / "basis.npy"
    basis = np.load(basis_path).astype(np.float32) if basis_path.exists() else None
    return vectors, ids, basis


class NumpyDenseRetriever:
    def __init__(self, vectors: np.ndarray, ids: list[str], verses: list[Verse],
                 embedder: Embedder, threshold: float = 0.8,
                 basis: np.ndarray | None = None) -> None:
        if basis is not None and basis.shape[0] != vectors.shape[1]:
            raise ValueError(
                f"basis 출력 차원({basis.shape[0]})이 vectors 차원"
                f"({vectors.shape[1]})과 일치하지 않습니다. 인덱스와 기저가 "
                "짝이 맞는지 확인하세요."
            )
        self._vectors = vectors
        self._ids = ids
        self._embedder = embedder
        self._threshold = threshold
        self._basis = basis
        self._by_id = {v.id: v for v in verses}

    def search(self, query: str) -> list[SearchResult]:
        if len(self._ids) == 0:
            return []
        q = self._embedder.encode([query])[0].astype(np.float32)
        if self._basis is not None:
            q = q @ self._basis.T
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
