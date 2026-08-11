from bible_search.models import Verse, SearchResult
from bible_search.ranking import coverage_and_proximity, minmax, weighted_fusion


def _verse(vid, text):
    return Verse(id=vid, book="테스트", chapter=1, verse=1, text=text, translation="개역개정")


# --- coverage_and_proximity ---

def test_coverage_all_words_present():
    cov, _ = coverage_and_proximity("여호와 목자", "여호와는 나의 목자시니")
    assert cov == 1.0


def test_coverage_half_words_present():
    cov, _ = coverage_and_proximity("여호와 컴퓨터", "여호와는 나의 목자시니")
    assert cov == 0.5


def test_coverage_no_words_present():
    cov, _ = coverage_and_proximity("컴퓨터 프로그래밍", "여호와는 나의 목자시니")
    assert cov == 0.0


def test_coverage_empty_query_returns_zero_zero():
    assert coverage_and_proximity("", "여호와는 나의 목자시니") == (0.0, 0.0)


def test_proximity_zero_when_fewer_than_two_matched():
    _, prox = coverage_and_proximity("여호와 컴퓨터", "여호와는 나의 목자시니")
    assert prox == 0.0


def test_proximity_adjacent_words_score_higher_than_far_apart():
    query = "여호와 목자"
    close_text = "여호와 목자시니 내게 부족함이 없으리로다"
    far_text = "여호와를 향한 나의 오랜 생각과 기다림 끝에 마침내 나타나신 선한 목자"
    _, prox_close = coverage_and_proximity(query, close_text)
    _, prox_far = coverage_and_proximity(query, far_text)
    assert prox_close > prox_far


# --- minmax ---

def test_minmax_normal_range_maps_min_to_zero_max_to_one():
    out = minmax({"a": 1.0, "b": 2.0, "c": 3.0})
    assert out["a"] == 0.0
    assert out["c"] == 1.0
    assert out["b"] == 0.5


def test_minmax_all_equal_returns_all_one():
    out = minmax({"a": 5.0, "b": 5.0, "c": 5.0})
    assert out == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_minmax_empty_returns_empty():
    assert minmax({}) == {}


# --- weighted_fusion ---

def test_full_coverage_verse_outranks_partial_coverage_when_cov_weighted():
    full = _verse("full", "여호와는 나의 목자시니")
    partial = _verse("partial", "여호와를 앙망하는 자는 새 힘을 얻으리니")
    bm25 = [
        SearchResult(verse=partial, score=2.0, source="bm25"),
        SearchResult(verse=full, score=1.0, source="bm25"),
    ]
    dense = []
    results = weighted_fusion(
        bm25, dense, "여호와 목자",
        w_bm25=0.7, w_dense=1.0, w_cov=2.0, w_prox=0.5,
    )
    ids = [r.verse.id for r in results]
    assert ids.index("full") < ids.index("partial")


def test_weighted_fusion_source_is_hybrid():
    v = _verse("v1", "여호와는 나의 목자시니")
    bm25 = [SearchResult(verse=v, score=1.0, source="bm25")]
    results = weighted_fusion(bm25, [], "여호와", w_bm25=1.0, w_dense=1.0, w_cov=1.0, w_prox=0.5)
    assert all(r.source == "hybrid" for r in results)


def test_weighted_fusion_sorted_descending():
    v1 = _verse("v1", "여호와는 나의 목자시니")
    v2 = _verse("v2", "여호와를 앙망하는 자는 새 힘을 얻으리니")
    bm25 = [
        SearchResult(verse=v1, score=1.0, source="bm25"),
        SearchResult(verse=v2, score=2.0, source="bm25"),
    ]
    results = weighted_fusion(bm25, [], "여호와", w_bm25=1.0, w_dense=1.0, w_cov=1.0, w_prox=0.5)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_weighted_fusion_handles_one_empty_channel():
    v = _verse("v1", "여호와는 나의 목자시니")
    dense = [SearchResult(verse=v, score=0.9, source="dense")]
    results = weighted_fusion([], dense, "여호와", w_bm25=0.7, w_dense=1.0, w_cov=2.0, w_prox=0.5)
    assert len(results) == 1
    assert results[0].verse.id == "v1"
    assert results[0].source == "hybrid"
