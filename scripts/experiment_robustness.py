"""커버리지 신호의 과적합·강건성 검증.

우려: keyword 평가셋(132개)은 "정답 구절에서 뽑은 어절 2개"로 생성되어
정답이 항상 모든 질의어를 포함한다. 커버리지 신호는 이 구조를 직접 이용하므로
개선폭이 부풀려졌을 수 있다(순환 논리).

그래서 커버리지에 불리하거나 중립인 3종 시나리오를 별도로 만들어 검증한다:
  R1 부분기억  — 질의어 중 하나가 정답에 없음(사용자가 한 단어를 잘못 기억)
  R2 변형기억  — 정답의 어절을 조사만 바꾸거나 축약(리터럴 매칭이 깨짐)
  R3 실사용    — 손으로 만든 실제 검색 의도 질의(생성 로직과 무관)

사용법: 실험 하네스와 동일한 환경변수로 실행.
"""

import json
import random
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.embedding import KureEmbedder
from bible_search.factory import _make_tokenizer
from bible_search.token_cache import load_token_cache
from bible_search.vectorstore import load_numpy_index

import importlib.util
spec = importlib.util.spec_from_file_location(
    "exp", str(Path(__file__).parent / "experiment_ranking.py"))
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)

SEED = 20260811

# R3: 실제 검색 의도로 손수 작성 (평가셋 생성 로직과 완전 무관)
REAL_QUERIES = [
    ("야베스 지경", "개역한글:역대상:4:10"),
    ("잃은 양 아흔아홉", "개역한글:누가복음:15:4"),
    ("겨자씨 믿음 산", "개역한글:마태복음:17:20"),
    ("선한 사마리아인 강도", "개역한글:누가복음:10:33"),
    ("돌아온 탕자 아버지", "개역한글:누가복음:15:20"),
    ("오병이어 남은 열두 바구니", "개역한글:마태복음:14:20"),
    ("엘리야 갈멜산 바알 선지자", "개역한글:열왕기상:18:22"),
    ("다니엘 사자굴", "개역한글:다니엘:6:16"),
    ("홍해 갈라짐 마른 땅", "개역한글:출애굽기:14:21"),
    ("여리고 성 무너짐", "개역한글:여호수아:6:20"),
    ("소돔 고모라 유황불", "개역한글:창세기:19:24"),
    ("모세 떨기나무 불꽃", "개역한글:출애굽기:3:2"),
    ("삼손 머리털 힘", "개역한글:사사기:16:17"),
    ("다윗 골리앗 물매돌", "개역한글:사무엘상:17:49"),
    ("에스더 죽으면 죽으리이다", "개역한글:에스더:4:16"),
    ("느헤미야 성벽 재건", "개역한글:느헤미야:6:15"),
    ("사드락 메삭 아벳느고 풀무", "개역한글:다니엘:3:23"),
    ("베드로 물 위를 걷다", "개역한글:마태복음:14:29"),
    ("바울 다메섹 빛", "개역한글:사도행전:9:3"),
    ("오순절 성령 불의 혀", "개역한글:사도행전:2:3"),
]


def main() -> None:
    s = get_settings()
    rng = random.Random(SEED)
    nprng = np.random.default_rng(SEED)
    verses = load_verses(s.data_path)
    byid = {v.id: v for v in verses}

    tokenizer = _make_tokenizer(s)
    corpus = load_token_cache(s.token_cache_path, verses, tokenizer=tokenizer)
    vectors, ids, basis = load_numpy_index(s.numpy_index_path)
    vectors = vectors.astype(np.float32)

    # --- R1/R2 시나리오 생성 (keyword 평가셋을 변형) ---
    kw = [json.loads(l) for l in
          open("tests/data/eval_keywords_66.jsonl", encoding="utf-8") if l.strip()]
    all_words = [w for r in kw for w in r["query"].split()]

    r1, r2 = [], []
    for r in kw:
        words = r["query"].split()
        tgt = byid[r["expected_ids"][0]]
        # R1: 두 단어 중 하나를 정답에 없는 다른 단어로 교체 → 커버리지 50%
        alien = rng.choice([w for w in all_words if w not in tgt.text])
        r1.append({"query": f"{words[0]} {alien}", "expected_ids": r["expected_ids"],
                   "tier": "R1부분기억"})
        # R2: 어절 끝 1글자를 잘라 리터럴 매칭을 깨뜨림(조사/어미 변형 모사)
        mangled = [w[:-1] if len(w) > 2 else w for w in words]
        r2.append({"query": " ".join(mangled), "expected_ids": r["expected_ids"],
                   "tier": "R2변형기억"})

    r3 = []
    for q, vid in REAL_QUERIES:
        if vid in byid:
            r3.append({"query": q, "expected_ids": [vid], "tier": "R3실사용"})
        else:
            print(f"  ⚠️ 정답 id 없음(제외): {vid} ← {q!r}")

    rows = r1 + r2 + r3
    print(f"강건성 세트: R1부분기억 {len(r1)} / R2변형기억 {len(r2)} / R3실사용 {len(r3)}"
          f" = 총 {len(rows)}개")

    emb = KureEmbedder()
    Q = emb.encode([r["query"] for r in rows]).astype(np.float32)
    if basis is not None:
        Q = Q @ basis.T
        Q /= np.linalg.norm(Q, axis=1, keepdims=True)

    dense_cache = []
    for i in range(len(rows)):
        sims = vectors @ Q[i]
        idx = np.where(sims >= s.dense_threshold)[0]
        idx = idx[np.argsort(-sims[idx])]
        dense_cache.append([(ids[j], float(sims[j])) for j in idx])

    bm25_by_b = {b: BM25Okapi(corpus, b=b) for b in (0.4, 0.75)}
    ranker = exp.Ranker(verses, corpus, tokenizer, vectors, ids, bm25_by_b)

    configs = [
        exp.Config("C0 현재", b=0.75, fusion="rrf"),
        exp.Config("C7 커버리지+근접", b=0.4, fusion="norm", w_cov=1.0, w_prox=0.5),
        exp.Config("C8 커버리지강조", b=0.4, fusion="norm", w_bm25=0.7,
                   w_cov=2.0, w_prox=0.5),
    ]

    tiers = ["R1부분기억", "R2변형기억", "R3실사용"]
    results = {}
    for cfg in configs:
        per_q = exp.evaluate(ranker, rows, Q, dense_cache, cfg)
        results[cfg.name] = per_q

    print("\n" + "=" * 82)
    print(f"{'구성':<18} {'MRR':>7} | " + " | ".join(f"{t}(t1/t3/t10)" for t in tiers))
    print("-" * 82)
    for cfg in configs:
        pq = results[cfg.name]
        cells = []
        for t in tiers:
            sel = [p for p in pq if p["tier"] == t]
            cells.append(f"{sum(p['t1'] for p in sel):>3}/{sum(p['t3'] for p in sel):>3}/"
                         f"{sum(p['t10'] for p in sel):>3}")
        mrr = float(np.mean([p["rr"] for p in pq]))
        print(f"{cfg.name:<18} {mrr:>7.4f} | " + " | ".join(f"{c:>15}" for c in cells))
    print("=" * 82)

    base = results["C0 현재"]
    base_rr = [p["rr"] for p in base]
    print(f"\n베이스라인 대비 (부트스트랩 {exp.BOOTSTRAP:,}회)")
    for cfg in configs[1:]:
        rr = [p["rr"] for p in results[cfg.name]]
        lo, hi, pwin = exp.paired_bootstrap(base_rr, rr, nprng)
        n01, n10, pval = exp.mcnemar([p["t3"] for p in base],
                                     [p["t3"] for p in results[cfg.name]])
        sig = "유의" if (lo > 0 or hi < 0) else "무의미"
        print(f"  {cfg.name:<18} ΔMRR={np.mean(rr)-np.mean(base_rr):+.4f} "
              f"CI=[{lo:+.4f},{hi:+.4f}] 우세={pwin:.1%} "
              f"McNemar(기존만{n01},신규만{n10},p={pval:.3f}) {sig}")

    # 시나리오별 세부 — 커버리지가 해가 되는 구간이 있는지
    print("\n시나리오별 ΔMRR (음수면 그 상황에서 손해):")
    for t in tiers:
        b_sel = [p["rr"] for p in base if p["tier"] == t]
        line = f"  {t:<10}"
        for cfg in configs[1:]:
            c_sel = [p["rr"] for p in results[cfg.name] if p["tier"] == t]
            line += f"  {cfg.name.split()[0]}={np.mean(c_sel)-np.mean(b_sel):+.4f}"
        print(line)

    # R3 실사용 개별 결과(사용자 체감과 직결)
    print("\nR3 실사용 질의 개별 순위 (정답이 몇 위인가):")
    print(f"  {'질의':<26} {'C0현재':>7} {'C8신규':>7}")
    for i, r in enumerate(rows):
        if r["tier"] != "R3실사용":
            continue
        line = f"  {r['query']:<26}"
        for cfg in (configs[0], configs[2]):
            got = ranker.rank(r["query"], Q[i], cfg, dense_cache[i])[:10]
            exp_ids = set(r["expected_ids"])
            pos = next((j + 1 for j, v in enumerate(got) if v in exp_ids), None)
            line += f" {str(pos) if pos else '>10':>7}"
        print(line)


if __name__ == "__main__":
    main()
