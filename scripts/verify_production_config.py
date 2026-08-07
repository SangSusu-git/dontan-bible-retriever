"""현재 설정으로 factory가 조립한 실제 서비스를 3개 평가 세트로 검증한다.

손으로 조립한 비교 하니스가 아니라 build_search_service()가 만든 것을
그대로 쓰므로, 설정·캐시·인덱스·투영이 프로덕션 경로에서 맞물리는지 확인된다.

사용법:
    PYTHONPATH=src BIBLE_API_KEY=x BIBLE_TOKENIZER=mecab \
    BIBLE_VECTOR_STORE=numpy BIBLE_USE_TOKEN_CACHE=true \
    python scripts/verify_production_config.py
"""

import json
import time
from pathlib import Path

from bible_search.config import get_settings
from bible_search.factory import build_search_service

EVAL_FILES = {
    "keyword": Path("tests/data/eval_keywords_66.jsonl"),
    "paraphrase": Path("tests/data/eval_paraphrase.jsonl"),
    "famous": Path("tests/data/eval_set.jsonl"),
}


def load_rows():
    rows = []
    for tier, path in EVAL_FILES.items():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                r = json.loads(line)
                r["tier"] = tier
                rows.append(r)
    return rows


def main() -> None:
    s = get_settings()
    print("현재 설정:")
    print(f"  tokenizer     : {s.tokenizer}")
    print(f"  vector_store  : {s.vector_store}")
    print(f"  embedder      : {s.embedder}")
    print(f"  token cache   : {s.use_token_cache} ({s.token_cache_path})")
    print(f"  dense 임계값   : {s.dense_threshold}")
    print(f"  bm25_top_k    : {s.bm25_top_k}\n")

    t0 = time.time()
    svc = build_search_service(s)
    build_s = time.time() - t0
    dim = svc._dense._vectors.shape[1] if hasattr(svc._dense, "_vectors") else "?"
    print(f"서비스 구성 완료 {build_s:.1f}s (벡터 차원 {dim})\n")

    rows = load_rows()
    tiers = list(EVAL_FILES)
    stat = {t: {"n": 0, "top1": 0, "top3": 0, "top10": 0} for t in tiers}
    lat = []
    for r in rows:
        t1 = time.time()
        resp = svc.search(r["query"])
        lat.append(time.time() - t1)
        got = [m.verse.id for m in resp.exact_matches + resp.related_matches]
        exp = set(r["expected_ids"])
        st = stat[r["tier"]]
        st["n"] += 1
        if exp & set(got[:1]):
            st["top1"] += 1
        if exp & set(got[:3]):
            st["top3"] += 1
        if exp & set(got[:10]):
            st["top10"] += 1

    print(f"{'세트':<12} {'질의':>5} {'top1':>7} {'top3':>7} {'top10':>7}")
    print("-" * 44)
    for t in tiers:
        st = stat[t]
        print(f"{t:<12} {st['n']:>5} {st['top1']:>7} {st['top3']:>7} {st['top10']:>7}")
    print("-" * 44)
    print(f"평균 응답 {1000 * sum(lat) / len(lat):.0f}ms\n")

    print("샘플 검색:")
    for q in ["사랑은 오래 참고", "여호와 목자 부족", "멜기세덱의 반차를"]:
        resp = svc.search(q)
        m = resp.exact_matches + resp.related_matches
        top = f"{m[0].verse.id.split(':', 1)[1]} | {m[0].verse.text[:32]}" if m else "없음"
        print(f"  \"{q}\" ({len(m)}건)\n     -> {top}")


if __name__ == "__main__":
    main()
