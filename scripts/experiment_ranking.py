"""랭킹 구성 비교 실험 — 현재 방식 vs 문헌 기반 개선안.

조사 근거(.superpowers/sdd/ranking-research.md)에서 도출한 4개 신호를 검증한다:
  1) BM25 길이 정규화 b — 기본 0.75는 길이 편차 큰 코퍼스용. 균질한 짧은 구절엔 과할 수 있음.
  2) 커버리지(질의어 충족률) — Lucene coord() 제거 후 ES minimum_should_match / Vespa
     nativeFieldMatch로 이관된 신호. 하드 계층 대신 점수 항목으로 반영.
  3) 근접도 — Tao & Zhai(SIGIR 2007). 매칭 단어들이 가까울수록 가산.
  4) 융합 방식 — RRF(순위만, 점수 크기 버림) vs 정규화 가중합(Weaviate relativeScoreFusion).

공정성: 질의 임베딩·Dense 후보는 1회 계산해 전 구성이 공유한다. Dense 임계값은
사용자 요청대로 0.7 고정. Exact(연속 문자열) 최상단 배치도 전 구성 동일.

지표: MRR@10(주 지표), top1/top3/top10 적중률.
검정: 짝지은 부트스트랩 10,000회(MRR 차이 95% CI), McNemar(top-3 적중 차이).

사용법:
    PYTHONPATH=src BIBLE_API_KEY=x BIBLE_TOKENIZER=mecab \
    BIBLE_VECTOR_STORE=numpy BIBLE_USE_TOKEN_CACHE=true BIBLE_EMBEDDER=local \
    python scripts/experiment_ranking.py
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.embedding import KureEmbedder
from bible_search.factory import _make_tokenizer
from bible_search.retrievers.exact import _normalize
from bible_search.token_cache import load_token_cache
from bible_search.vectorstore import load_numpy_index

EVAL_FILES = {
    "keyword": Path("tests/data/eval_keywords_66.jsonl"),
    "paraphrase": Path("tests/data/eval_paraphrase.jsonl"),
    "famous": Path("tests/data/eval_set.jsonl"),
}
TOP_N = 10          # 지표 산정 깊이
BM25_CAND = 100     # 후보 생성 폭(현재 노출 상한 30보다 넓게 잡아 랭킹 실험 여지 확보)
BOOTSTRAP = 10_000
SEED = 20260811


@dataclass
class Config:
    """랭킹 구성 하나."""
    name: str
    b: float = 0.75                # BM25 길이 정규화
    fusion: str = "rrf"            # "rrf" | "norm"
    w_bm25: float = 1.0
    w_dense: float = 1.0
    w_cov: float = 0.0             # 커버리지 가중치(norm 융합에서만)
    w_prox: float = 0.0            # 근접 가중치(norm 융합에서만)
    cov_gate: float = 0.0          # 이 비율 미만 커버리지는 후보에서 제외
    rrf_k: int = 60
    desc: str = ""


def load_rows() -> list[dict]:
    rows = []
    for tier, path in EVAL_FILES.items():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                r = json.loads(line)
                r["tier"] = tier
                rows.append(r)
    return rows


def coverage_and_proximity(query: str, text: str) -> tuple[float, float]:
    """리터럴 어절 기준 커버리지(0~1)와 근접도(0~1)를 계산한다.

    커버리지: 질의를 공백으로 나눈 단어 중 본문에 등장하는 비율.
      형태소 분석이 고유명사를 쪼개는 문제("야베스"→"베스")를 우회하려고
      리터럴 부분문자열로 판정한다(조사가 붙어도 매칭됨).
    근접도: 매칭된 단어들이 본문에서 차지하는 최소 구간이 좁을수록 1에 가깝다.
      단어가 1개 이하로 매칭되면 0.
    """
    words = [w for w in query.split() if w]
    if not words:
        return 0.0, 0.0
    positions = []
    hit = 0
    for w in words:
        i = text.find(w)
        if i >= 0:
            hit += 1
            positions.append(i)
    cov = hit / len(words)
    if len(positions) < 2:
        return cov, 0.0
    span = max(positions) - min(positions) + 1
    # 매칭 단어들이 붙어 있을 때의 이상적 폭 대비 실제 폭
    ideal = sum(len(w) for w in words if w in text)
    prox = min(1.0, ideal / span) if span > 0 else 0.0
    return cov, prox


def minmax(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return {k: 1.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


class Ranker:
    """구성에 따라 후보를 생성·정렬한다. Exact는 전 구성 공통으로 최상단."""

    def __init__(self, verses, corpus, tokenizer, vectors, ids, bm25_by_b):
        self.verses = verses
        self.ids = ids
        self.byid = {v.id: v for v in verses}
        self.tokenizer = tokenizer
        self.vectors = vectors
        self.bm25_by_b = bm25_by_b
        self.norm_texts = [(_normalize(v.text), v.id) for v in verses]

    def exact_ids(self, query: str) -> list[str]:
        q = _normalize(query)
        if not q:
            return []
        return [vid for nt, vid in self.norm_texts if q in nt]

    def rank(self, query: str, qvec: np.ndarray, cfg: Config,
             dense_pairs: list[tuple[str, float]]) -> list[str]:
        ex = self.exact_ids(query)
        ex_set = set(ex)

        # --- 후보 생성 ---
        qt = self.tokenizer.tokenize(query)
        bm = self.bm25_by_b[cfg.b]
        bm_scores: dict[str, float] = {}
        if qt:
            raw = bm.get_scores(qt)
            top_idx = np.argpartition(-raw, min(BM25_CAND, len(raw) - 1))[:BM25_CAND]
            top_idx = top_idx[np.argsort(-raw[top_idx])]
            for i in top_idx:
                if raw[i] > 0:
                    bm_scores[self.ids[i]] = float(raw[i])
        dense_scores = dict(dense_pairs)

        cand = set(bm_scores) | set(dense_scores)
        cand -= ex_set

        # --- 커버리지/근접 계산 + 게이트 ---
        cov_map, prox_map = {}, {}
        for vid in cand:
            c, p = coverage_and_proximity(query, self.byid[vid].text)
            cov_map[vid], prox_map[vid] = c, p
        if cfg.cov_gate > 0:
            cand = {v for v in cand if cov_map[v] >= cfg.cov_gate}
            if not cand:  # 게이트가 전부 걸러내면 완화(문헌의 progressive relaxation)
                cand = set(bm_scores) | set(dense_scores)
                cand -= ex_set

        # --- 점수 계산 ---
        if cfg.fusion == "rrf":
            bm_rank = {vid: i for i, vid in enumerate(
                sorted(bm_scores, key=lambda v: -bm_scores[v]))}
            dn_rank = {vid: i for i, vid in enumerate(
                sorted(dense_scores, key=lambda v: -dense_scores[v]))}
            score = {}
            for vid in cand:
                s = 0.0
                if vid in bm_rank:
                    s += cfg.w_bm25 / (cfg.rrf_k + bm_rank[vid] + 1)
                if vid in dn_rank:
                    s += cfg.w_dense / (cfg.rrf_k + dn_rank[vid] + 1)
                score[vid] = s
        else:  # 정규화 가중합
            nb = minmax({k: v for k, v in bm_scores.items() if k in cand})
            nd = minmax({k: v for k, v in dense_scores.items() if k in cand})
            score = {}
            for vid in cand:
                score[vid] = (cfg.w_bm25 * nb.get(vid, 0.0)
                              + cfg.w_dense * nd.get(vid, 0.0)
                              + cfg.w_cov * cov_map.get(vid, 0.0)
                              + cfg.w_prox * prox_map.get(vid, 0.0))

        ranked = sorted(cand, key=lambda v: -score[v])
        return ex + ranked


def evaluate(ranker, rows, qvecs, dense_cache, cfg) -> dict:
    """구성 하나를 183질의로 평가해 질의별 RR과 적중 여부를 돌려준다."""
    per_q = []
    for i, r in enumerate(rows):
        got = ranker.rank(r["query"], qvecs[i], cfg, dense_cache[i])[:TOP_N]
        exp = set(r["expected_ids"])
        rr = 0.0
        for pos, vid in enumerate(got, 1):
            if vid in exp:
                rr = 1.0 / pos
                break
        per_q.append({
            "tier": r["tier"], "rr": rr,
            "t1": bool(exp & set(got[:1])),
            "t3": bool(exp & set(got[:3])),
            "t10": bool(exp & set(got[:10])),
        })
    return per_q


def summarize(per_q, tiers) -> dict:
    out = {"MRR": float(np.mean([p["rr"] for p in per_q]))}
    for t in tiers + ["ALL"]:
        sel = per_q if t == "ALL" else [p for p in per_q if p["tier"] == t]
        out[t] = {
            "n": len(sel),
            "t1": sum(p["t1"] for p in sel),
            "t3": sum(p["t3"] for p in sel),
            "t10": sum(p["t10"] for p in sel),
            "mrr": float(np.mean([p["rr"] for p in sel])) if sel else 0.0,
        }
    return out


def paired_bootstrap(a: list[float], b: list[float], rng) -> tuple[float, float, float]:
    """MRR 차이(b-a)의 95% CI와 b가 더 나을 확률을 부트스트랩으로 추정."""
    a_arr, b_arr = np.array(a), np.array(b)
    n = len(a_arr)
    diffs = np.empty(BOOTSTRAP)
    for i in range(BOOTSTRAP):
        idx = rng.integers(0, n, n)
        diffs[i] = b_arr[idx].mean() - a_arr[idx].mean()
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float((diffs > 0).mean())


def mcnemar(a_hits: list[bool], b_hits: list[bool]) -> tuple[int, int, float]:
    """top-3 적중의 짝지은 비교. (a만 성공, b만 성공, 양측 p값)"""
    from math import comb
    n01 = sum(1 for x, y in zip(a_hits, b_hits) if x and not y)  # a만 성공
    n10 = sum(1 for x, y in zip(a_hits, b_hits) if y and not x)  # b만 성공
    n = n01 + n10
    if n == 0:
        return n01, n10, 1.0
    k = min(n01, n10)
    p = sum(comb(n, i) for i in range(k + 1)) / (2 ** n) * 2
    return n01, n10, min(1.0, p)


def main() -> None:
    s = get_settings()
    rng = np.random.default_rng(SEED)
    verses = load_verses(s.data_path)
    rows = load_rows()
    tiers = list(EVAL_FILES)
    print(f"구절 {len(verses):,} / 평가 질의 {len(rows)}개 "
          f"(keyword {sum(r['tier']=='keyword' for r in rows)}, "
          f"paraphrase {sum(r['tier']=='paraphrase' for r in rows)}, "
          f"famous {sum(r['tier']=='famous' for r in rows)})")

    tokenizer = _make_tokenizer(s)
    corpus = load_token_cache(s.token_cache_path, verses, tokenizer=tokenizer)
    vectors, ids, basis = load_numpy_index(s.numpy_index_path)
    vectors = vectors.astype(np.float32)

    print("질의 임베딩 계산(1회, 전 구성 공유)...")
    emb = KureEmbedder()
    Q = emb.encode([r["query"] for r in rows]).astype(np.float32)
    if basis is not None:
        Q = Q @ basis.T
        Q /= np.linalg.norm(Q, axis=1, keepdims=True)

    print(f"Dense 후보 계산(임계값 {s.dense_threshold} 고정)...")
    dense_cache = []
    for i in range(len(rows)):
        sims = vectors @ Q[i]
        idx = np.where(sims >= s.dense_threshold)[0]
        idx = idx[np.argsort(-sims[idx])]
        dense_cache.append([(ids[j], float(sims[j])) for j in idx])
    n_empty = sum(1 for d in dense_cache if not d)
    print(f"  Dense 결과 0건인 질의: {n_empty}/{len(rows)}")

    b_values = sorted({0.0, 0.2, 0.4, 0.75})
    print(f"BM25 인덱스 구축 (b={b_values})...")
    bm25_by_b = {}
    for b in b_values:
        t0 = time.time()
        bm25_by_b[b] = BM25Okapi(corpus, b=b)
        print(f"  b={b}: {time.time()-t0:.0f}s")

    ranker = Ranker(verses, corpus, tokenizer, vectors, ids, bm25_by_b)

    configs = [
        Config("C0 현재(RRF,b=.75)", b=0.75, fusion="rrf",
               desc="베이스라인 — 지금 배포된 방식"),
        Config("C1 RRF,b=.4", b=0.4, fusion="rrf", desc="길이정규화만 완화"),
        Config("C2 RRF,b=.2", b=0.2, fusion="rrf", desc="길이정규화 더 완화"),
        Config("C3 RRF,b=0", b=0.0, fusion="rrf", desc="길이정규화 제거"),
        Config("C4 정규화융합", b=0.4, fusion="norm", w_bm25=1.0, w_dense=1.0,
               desc="RRF→정규화 가중합"),
        Config("C5 +커버리지", b=0.4, fusion="norm", w_bm25=1.0, w_dense=1.0,
               w_cov=1.0, desc="커버리지 신호 추가"),
        Config("C6 +근접", b=0.4, fusion="norm", w_bm25=1.0, w_dense=1.0,
               w_prox=0.5, desc="근접 신호 추가"),
        Config("C7 +커버리지+근접", b=0.4, fusion="norm", w_bm25=1.0, w_dense=1.0,
               w_cov=1.0, w_prox=0.5, desc="둘 다"),
        Config("C8 커버리지강조", b=0.4, fusion="norm", w_bm25=0.7, w_dense=1.0,
               w_cov=2.0, w_prox=0.5, desc="커버리지 가중 2배"),
        Config("C9 +게이트", b=0.4, fusion="norm", w_bm25=1.0, w_dense=1.0,
               w_cov=1.0, w_prox=0.5, cov_gate=0.5,
               desc="커버리지 50% 미만 후보 제외"),
    ]

    results = {}
    for cfg in configs:
        t0 = time.time()
        per_q = evaluate(ranker, rows, Q, dense_cache, cfg)
        results[cfg.name] = {"per_q": per_q, "sum": summarize(per_q, tiers),
                             "sec": time.time() - t0, "cfg": cfg}
        print(f"  평가 완료: {cfg.name} ({time.time()-t0:.0f}s)")

    # ---- 결과표 ----
    print("\n" + "=" * 96)
    print(f"{'구성':<20} {'MRR@10':>7} | {'keyword(132)':>16} | {'paraphrase(24)':>16} | {'famous(27)':>14}")
    print(f"{'':<20} {'':>7} | {'t1/t3/t10':>16} | {'t1/t3/t10':>16} | {'t1/t3/t10':>14}")
    print("-" * 96)
    for cfg in configs:
        r = results[cfg.name]["sum"]
        def cell(t):
            d = r[t]
            return f"{d['t1']:>3}/{d['t3']:>3}/{d['t10']:>3}"
        print(f"{cfg.name:<20} {r['MRR']:>7.4f} | {cell('keyword'):>16} | "
              f"{cell('paraphrase'):>16} | {cell('famous'):>14}")
    print("=" * 96)

    # ---- 통계 검정: 각 구성 vs 베이스라인 ----
    base_name = configs[0].name
    base = results[base_name]["per_q"]
    base_rr = [p["rr"] for p in base]
    base_t3 = [p["t3"] for p in base]

    print(f"\n통계 검정 (베이스라인 = {base_name}, 부트스트랩 {BOOTSTRAP:,}회)")
    print(f"{'구성':<20} {'ΔMRR':>8} {'95% CI':>20} {'우세확률':>8}  {'McNemar top-3':>22}")
    print("-" * 84)
    for cfg in configs[1:]:
        pq = results[cfg.name]["per_q"]
        rr = [p["rr"] for p in pq]
        t3 = [p["t3"] for p in pq]
        lo, hi, pwin = paired_bootstrap(base_rr, rr, rng)
        n01, n10, pval = mcnemar(base_t3, t3)
        d = float(np.mean(rr) - np.mean(base_rr))
        sig = "유의" if (lo > 0 or hi < 0) else "무의미"
        print(f"{cfg.name:<20} {d:>+8.4f} [{lo:>+7.4f},{hi:>+7.4f}] {pwin:>7.1%}  "
              f"기존만{n01:>3} 신규만{n10:>3} p={pval:.3f} {sig}")

    # ---- 최종 판정 ----
    best = max(results.items(), key=lambda kv: kv[1]["sum"]["MRR"])
    print("\n" + "=" * 84)
    print(f"최고 MRR 구성: {best[0]} (MRR={best[1]['sum']['MRR']:.4f}, "
          f"베이스라인 {results[base_name]['sum']['MRR']:.4f})")
    if best[0] != base_name:
        rr_b = [p["rr"] for p in best[1]["per_q"]]
        lo, hi, pwin = paired_bootstrap(base_rr, rr_b, rng)
        verdict = ("교체 권장 — 개선이 통계적으로 유의" if lo > 0
                   else "교체 보류 — 개선이 통계적으로 불확실(현재 유지)")
        print(f"  ΔMRR={np.mean(rr_b)-np.mean(base_rr):+.4f}, 95% CI=[{lo:+.4f},{hi:+.4f}], "
              f"우세확률={pwin:.1%}")
        print(f"  판정: {verdict}")
    else:
        print("  판정: 현재 구성이 최고 — 변경 불필요")

    # 실패 사례 저장(수동 점검용)
    out = Path(".superpowers/sdd/ranking-experiment-results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {n: {"summary": r["sum"], "desc": r["cfg"].desc} for n, r in results.items()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n상세 결과 저장: {out}")


if __name__ == "__main__":
    main()
