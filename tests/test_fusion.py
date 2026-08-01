from bible_search.models import Verse, SearchResult
from bible_search.fusion import reciprocal_rank_fusion


def _v(i):
    return Verse(id=str(i), book="b", chapter=1, verse=i, text=f"t{i}", translation="개역개정")


def test_rrf_rewards_agreement():
    v1, v2, v3 = _v(1), _v(2), _v(3)
    list_a = [SearchResult(v1, 5.0, "bm25"), SearchResult(v2, 3.0, "bm25")]
    list_b = [SearchResult(v2, 0.9, "dense"), SearchResult(v3, 0.8, "dense")]
    fused = reciprocal_rank_fusion([list_a, list_b])
    # v2는 두 리스트 모두에 등장 -> 최상위
    assert fused[0].verse.id == "2"
    assert all(r.source == "rrf" for r in fused)


def test_rrf_handles_different_lengths():
    v1, v2, v3, v4 = _v(1), _v(2), _v(3), _v(4)
    long = [SearchResult(_v(i), 1.0, "bm25") for i in range(1, 5)]
    short = [SearchResult(v4, 0.9, "dense")]
    fused = reciprocal_rank_fusion([long, short])
    ids = [r.verse.id for r in fused]
    assert set(ids) == {"1", "2", "3", "4"}
    # v4는 양쪽에 등장 -> 1위
    assert fused[0].verse.id == "4"


def test_rrf_empty_input():
    assert reciprocal_rank_fusion([[], []]) == []
