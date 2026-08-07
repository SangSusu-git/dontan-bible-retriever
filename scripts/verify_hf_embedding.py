"""HF Inference API가 로컬 KURE-v1 임베딩을 대체할 수 있는지 검증한다.

기존 코드는 전혀 수정하지 않는다. 이 스크립트는 읽기 전용 비교만 수행한다.

검증 항목:
  1) 벡터 일치도  — HF API 임베딩 vs 로컬 모델 임베딩의 코사인 유사도 (1.0에 가까워야 함)
  2) 정규화 여부  — HF가 L2 정규화된 벡터를 주는지 (안 주면 우리가 정규화)
  3) 검색 결과 일치 — 기존 Chroma 인덱스에 두 벡터로 각각 질의해 top-k 비교
  4) 지연 시간   — HF API 호출에 걸리는 시간
사용법:
    export HF_TOKEN=hf_xxx
    PYTHONPATH=src python scripts/verify_hf_embedding.py
"""

import os
import time

import numpy as np

MODEL = "nlpai-lab/KURE-v1"

# 성경 검색에서 실제로 쓰일 법한 질의들
QUERIES = [
    "사랑은 오래 참고",
    "여호와 목자 부족",
    "첫사랑을 잊었도다",
    "태초에 하나님이 천지를 창조",
    "수고하고 무거운 짐 진 자들아",
]


def l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def embed_via_hf(client, text: str) -> np.ndarray:
    """HF Inference API로 임베딩. 반환 형태가 (dim,) 또는 (1, dim)일 수 있어 정리한다."""
    out = client.feature_extraction(text, model=MODEL)
    arr = np.asarray(out, dtype=np.float32)
    while arr.ndim > 1:
        # (1, dim) → (dim,), 토큰별 (seq, dim)이 오면 평균 풀링은 하지 않고 경고 대상
        if arr.shape[0] == 1:
            arr = arr[0]
        else:
            raise ValueError(f"예상치 못한 임베딩 형태 {arr.shape} — 토큰 단위 출력일 수 있음")
    return arr


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN 환경변수가 필요합니다.  export HF_TOKEN=hf_xxx")

    from huggingface_hub import InferenceClient

    from bible_search.embedding import KureEmbedder

    print("로컬 KURE-v1 로드 중...")
    local = KureEmbedder()
    client = InferenceClient(token=token)

    print(f"\n{'질의':<28} {'코사인일치':>10} {'HF노름':>8} {'HF지연':>8}")
    print("-" * 60)

    sims, latencies = [], []
    hf_vecs, local_vecs = {}, {}

    for q in QUERIES:
        local_v = local.encode([q])[0]  # 이미 L2 정규화됨

        t0 = time.time()
        hf_raw = embed_via_hf(client, q)
        dt = time.time() - t0

        hf_norm_before = float(np.linalg.norm(hf_raw))
        hf_v = l2_normalize(hf_raw)

        sim = float(np.dot(local_v, hf_v))
        sims.append(sim)
        latencies.append(dt)
        hf_vecs[q], local_vecs[q] = hf_v, local_v

        print(f"{q:<28} {sim:>10.5f} {hf_norm_before:>8.3f} {dt:>7.2f}s")

    print("-" * 60)
    print(f"평균 코사인 일치도: {np.mean(sims):.5f}   (1.0에 가까울수록 동일)")
    print(f"평균 지연: {np.mean(latencies):.2f}s")
    print(f"HF 원본 노름이 1.0이면 이미 정규화됨 / 아니면 우리가 정규화하면 됨")

    # ---- 실제 인덱스로 검색 결과 비교 ----
    print("\n=== 기존 Chroma 인덱스로 검색 결과 비교 ===")
    import chromadb

    from bible_search.config import get_settings

    os.environ.setdefault("BIBLE_API_KEY", "verify")
    s = get_settings()
    col = chromadb.PersistentClient(s.chroma_path).get_collection(s.chroma_collection)

    def top_ids(vec, k=5):
        r = col.query(query_embeddings=[vec.tolist()], n_results=k)
        return r["ids"][0]

    all_match = True
    for q in QUERIES:
        a = top_ids(local_vecs[q])
        b = top_ids(hf_vecs[q])
        same = a == b
        all_match &= same
        mark = "동일" if same else "다름"
        print(f"\n  질의: {q}   → top-5 {mark}")
        if not same:
            print(f"    로컬: {[x.split(':', 1)[1] for x in a]}")
            print(f"    HF  : {[x.split(':', 1)[1] for x in b]}")

    print("\n" + "=" * 60)
    if np.mean(sims) > 0.99 and all_match:
        print("✅ 결론: HF API로 대체 가능. 재인덱싱 불필요.")
    elif np.mean(sims) > 0.99:
        print("△ 결론: 벡터는 일치하나 일부 top-k 순서가 다름 — 검토 필요.")
    else:
        print("❌ 결론: 벡터가 다름 → HF API로 대체하려면 재인덱싱 필요.")


if __name__ == "__main__":
    main()
