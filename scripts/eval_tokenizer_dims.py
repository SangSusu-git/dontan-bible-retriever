"""토크나이저×벡터차원 구성별 검색 품질 비교: Kiwi·1024 vs MeCab·1024 vs MeCab·384.

세 구성 모두 실제 프로덕션 파이프라인(ExactMatcher + BM25 + Dense + RRF,
SearchService 그대로)을 사용한다. 질의 임베딩은 로컬 KURE-v1로 한 번만
계산해 세 구성이 공유하므로(HF API와 동일함이 검증됨), 차이는 오직
토크나이저와 벡터 차원에서만 발생한다.

평가 세트:
  - keyword   (132): 66권 전권, 낯선 구절의 희귀 어절 2개 질의 (BM25/토크나이저 시험)
  - paraphrase (24): 덜 유명한 사건의 현대어 패러프레이즈 (Dense/융합 시험)
  - famous     (27): 기존 유명 구절 세트 (회귀 확인)

사용법:
    PYTHONPATH=src BIBLE_API_KEY=x python scripts/eval_tokenizer_dims.py
"""

import json
import time
from pathlib import Path

import numpy as np

from bible_search.config import get_settings
from bible_search.data.loader import load_verses
from bible_search.embedding import KureEmbedder
from bible_search.retrievers.bm25 import BM25Retriever
from bible_search.retrievers.exact import ExactMatcher
from bible_search.search_service import SearchService
from bible_search.token_cache import load_token_cache
from bible_search.tokenizer import KiwiTokenizer
from bible_search.vectorstore import NumpyDenseRetriever, load_numpy_index

EVAL_FILES = {
    "keyword": Path("tests/data/eval_keywords_66.jsonl"),
    "paraphrase": Path("tests/data/eval_paraphrase.jsonl"),
    "famous": Path("tests/data/eval_set.jsonl"),
}
REDUCED_DIM = 384


class MecabTokenizer:
    """MeCab 기반 내용어 토크나이저 — KiwiTokenizer와 동일 인터페이스/태그 정책."""

    CONTENT_TAGS = KiwiTokenizer.CONTENT_TAGS

    def __init__(self) -> None:
        import mecab_ko

        self._tagger = mecab_ko.Tagger()

    def tokenize(self, text: str) -> list[str]:
        out = []
        for line in self._tagger.parse(text).splitlines():
            if line == "EOS" or "\t" not in line:
                continue
            surface, feat = line.split("\t", 1)
            if feat.split(",", 1)[0] in self.CONTENT_TAGS:
                out.append(surface.lower())
        return out


class CachedEmbedder:
    """미리 계산된 질의 임베딩을 서빙 (선택적 투영 행렬 적용)."""

    def __init__(self, table: dict[str, np.ndarray], basis: np.ndarray | None = None):
        self._table = table
        self._basis = basis

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for t in texts:
            v = self._table[t]
            if self._basis is not None:
                v = v @ self._basis.T
                n = np.linalg.norm(v)
                v = v / n if n > 0 else v
            rows.append(v.astype(np.float32))
        return np.vstack(rows)


def l2n(a: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(a, axis=1, keepdims=True)
    return a / np.where(n == 0, 1, n)


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


def main() -> None:
    s = get_settings()
    verses = load_verses(s.data_path)
    rows = load_rows()
    queries = sorted({r["query"] for r in rows})
    print(f"구절 {len(verses):,}개 / 평가 질의 {len(rows)}개")

    print("질의 임베딩 계산 중 (로컬 KURE-v1, 1회)...")
    kure = KureEmbedder()
    Q = kure.encode(queries)  # 이미 L2 정규화됨
    table = {q: Q[i] for i, q in enumerate(queries)}

    vectors1024, ids = load_numpy_index(s.numpy_index_path)
    vectors1024 = l2n(vectors1024.astype(np.float32))

    print(f"SVD 계산 중 ({REDUCED_DIM}차원 투영 기저)...")
    _, _, Vt = np.linalg.svd(vectors1024, full_matrices=False)
    basis = Vt[:REDUCED_DIM]  # (384, 1024)
    vectors384 = l2n(vectors1024 @ basis.T)

    exact = ExactMatcher(verses)

    print("Kiwi 코퍼스: 캐시 로드 / MeCab 코퍼스: 토큰화 중...")
    kiwi_corpus = load_token_cache(s.token_cache_path, verses)
    mecab_tok = MecabTokenizer()
    t0 = time.time()
    mecab_corpus = [mecab_tok.tokenize(v.text) for v in verses]
    print(f"  MeCab 전체 토큰화 {time.time() - t0:.1f}s")

    configs = {
        "Kiwi·1024": (
            BM25Retriever(verses, KiwiTokenizer(), corpus=kiwi_corpus),
            NumpyDenseRetriever(vectors1024, ids, verses,
                                CachedEmbedder(table), threshold=s.dense_threshold),
        ),
        "MeCab·1024": (
            BM25Retriever(verses, mecab_tok, corpus=mecab_corpus),
            NumpyDenseRetriever(vectors1024, ids, verses,
                                CachedEmbedder(table), threshold=s.dense_threshold),
        ),
        "MeCab·384": (
            BM25Retriever(verses, mecab_tok, corpus=mecab_corpus),
            NumpyDenseRetriever(vectors384, ids, verses,
                                CachedEmbedder(table, basis=basis),
                                threshold=s.dense_threshold),
        ),
    }

    tiers = list(EVAL_FILES)
    results: dict[str, dict] = {}
    for name, (bm25, dense) in configs.items():
        svc = SearchService(exact, bm25, dense, rrf_k=s.rrf_k,
                            max_results=s.max_results, bm25_top_k=s.bm25_top_k)
        stat = {t: {"n": 0, "top1": 0, "top3": 0, "top10": 0} for t in tiers}
        lat = []
        misses = []
        for r in rows:
            t0 = time.time()
            resp = svc.search(r["query"])
            lat.append(time.time() - t0)
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
            elif r["tier"] != "famous":
                misses.append((r["tier"], r["query"], r["expected_ids"][0]))
        results[name] = {"stat": stat, "lat_ms": 1000 * sum(lat) / len(lat),
                         "misses": misses}

    # ---- 리포트 ----
    print("\n" + "=" * 74)
    header = f"{'구성':<12}"
    for t in tiers:
        n = results[next(iter(results))]["stat"][t]["n"]
        header += f" | {t}({n}) top1/top3/top10"
    print(header)
    print("-" * 74)
    for name, res in results.items():
        line = f"{name:<12}"
        for t in tiers:
            st = res["stat"][t]
            line += (f" |   {st['top1']:>3}/{st['top3']:>4}/{st['top10']:>4}   ")
        line += f"  {res['lat_ms']:.0f}ms/질의"
        print(line)
    print("=" * 74)

    for name, res in results.items():
        if res["misses"]:
            print(f"\n[{name}] top-10 실패 ({len(res['misses'])}건):")
            for tier, q, exp in res["misses"][:8]:
                print(f"  ({tier}) \"{q[:36]}\" -> {exp.split(':', 1)[1]}")


if __name__ == "__main__":
    main()
