"""정규화 가중합 융합과 커버리지/근접 신호.

scripts/experiment_ranking.py에서 검증된 winning config(C8: MRR 0.674→0.928,
183개 평가 질의 + 284개 강건성 세트, McNemar 회귀 0건/개선 30건)를 그대로
프로덕션에 이식한다. coverage_and_proximity()와 minmax()는 실험에서 측정된
그 함수의 의미를 정확히 그대로 옮긴 것이다 — 수정하면 검증 결과가 더 이상
적용되지 않는다.
"""

from bible_search.models import SearchResult, Verse


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


def minmax(scores: dict[str, float]) -> dict[str, float]:
    """min-max 정규화. 전부 동일하면 전원 1.0, 빈 dict는 빈 dict."""
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def weighted_fusion(
    bm25: list[SearchResult],
    dense: list[SearchResult],
    query: str,
    *,
    w_bm25: float,
    w_dense: float,
    w_cov: float,
    w_prox: float,
) -> list[SearchResult]:
    """BM25/Dense 채널을 정규화 가중합으로 융합하고 커버리지/근접 신호를 더한다."""
    bm25_scores: dict[str, float] = {}
    dense_scores: dict[str, float] = {}
    verses: dict[str, Verse] = {}

    for r in bm25:
        bm25_scores[r.verse.id] = r.score
        verses.setdefault(r.verse.id, r.verse)
    for r in dense:
        dense_scores[r.verse.id] = r.score
        verses.setdefault(r.verse.id, r.verse)

    candidates = set(bm25_scores) | set(dense_scores)

    nb = minmax(bm25_scores)
    nd = minmax(dense_scores)

    fused: list[SearchResult] = []
    for vid in candidates:
        verse = verses[vid]
        cov, prox = coverage_and_proximity(query, verse.text)
        score = (
            w_bm25 * nb.get(vid, 0.0)
            + w_dense * nd.get(vid, 0.0)
            + w_cov * cov
            + w_prox * prox
        )
        fused.append(SearchResult(verse=verse, score=score, source="hybrid"))

    fused.sort(key=lambda r: r.score, reverse=True)
    return fused
