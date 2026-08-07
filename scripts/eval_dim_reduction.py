"""벡터 차원 축소가 검색 품질에 미치는 영향을 정량 검증한다.

기존 1024차원 임베딩을 SVD로 k차원에 투영하고, 라벨된 평가 세트로
top-3 적중률과 원본 대비 top-10 일치율을 측정한다.

투영은 질의에도 동일하게 적용해야 하므로, 투영 행렬(components)을
인덱스와 함께 저장한다는 전제로 평가한다.

사용법:
    PYTHONPATH=src BIBLE_API_KEY=x python scripts/eval_dim_reduction.py
"""

import json
from pathlib import Path

import numpy as np

DIMS = [1024, 512, 384, 256, 192, 128, 96, 64]
EVAL_PATH = Path("tests/data/eval_set.jsonl")


def l2n(a: np.ndarray) -> np.ndarray:
    """행 단위 L2 정규화 (1차원이면 벡터 하나로 취급)."""
    if a.ndim == 1:
        n = np.linalg.norm(a)
        return a / n if n > 0 else a
    n = np.linalg.norm(a, axis=1, keepdims=True)
    return a / np.where(n == 0, 1, n)


def load_eval():
    rows = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    from bible_search.config import get_settings
    from bible_search.embedding import KureEmbedder
    from bible_search.vectorstore import load_numpy_index

    s = get_settings()
    vectors, ids, _basis = load_numpy_index(s.numpy_index_path)
    vectors = l2n(vectors.astype(np.float32))
    print(f"인덱스: {vectors.shape[0]:,}개 × {vectors.shape[1]}차원")

    rows = load_eval()
    queries = [r["query"] for r in rows]
    expected = [set(r["expected_ids"]) for r in rows]
    print(f"평가 세트: 질의 {len(rows)}개\n")

    print("질의 임베딩 생성 중(로컬 모델, HF와 동일함이 검증됨)...")
    embedder = KureEmbedder()
    Q = l2n(embedder.encode(queries).astype(np.float32))

    # SVD는 한 번만 계산하고 상위 k개 성분을 잘라 쓴다.
    print(f"SVD 계산 중 (최대 {max(DIMS)}차원)...")
    # (n, d) 행렬의 우특이벡터 Vt: (d, d). 상위 k행이 k차원 투영 기저.
    _, _, Vt = np.linalg.svd(vectors, full_matrices=False)

    id_index = {vid: i for i, vid in enumerate(ids)}

    def topk(mat, q, k=10):
        sims = mat @ q
        idx = np.argpartition(-sims, k)[:k]
        return [ids[i] for i in idx[np.argsort(-sims[idx])]]

    base_top10 = [topk(vectors, Q[i]) for i in range(len(queries))]

    print(f"\n{'차원':>6} {'메모리':>9} {'top3 적중':>10} {'top10 일치':>11} {'1위 동일':>9}")
    print("-" * 52)

    for d in DIMS:
        if d == vectors.shape[1]:
            red, redQ = vectors, Q
        else:
            basis = Vt[:d]                      # (d, 1024)
            red = l2n(vectors @ basis.T)        # (n, d)
            redQ = l2n(Q @ basis.T)             # (q, d)

        hits = overlap = same_first = 0
        for i in range(len(queries)):
            got = topk(red, redQ[i])
            if expected[i] & set(got[:3]):
                hits += 1
            overlap += len(set(got) & set(base_top10[i]))
            same_first += got[0] == base_top10[i][0]

        mem = red.shape[0] * d * 4 / 1024 / 1024
        print(f"{d:>6} {mem:>7.0f}MB {hits}/{len(queries):<8} "
              f"{overlap / (10 * len(queries)):>10.1%} {same_first}/{len(queries):>7}")

    print("-" * 52)
    print("top3 적중 = 정답 구절이 상위 3위 안에 든 질의 수 (실사용 품질)")
    print("top10 일치 = 1024차원 결과와 겹치는 비율")
    print("* 투영 행렬(1024×k)도 함께 저장해야 하며, 질의에도 같은 투영을 적용해야 한다.")


if __name__ == "__main__":
    main()
