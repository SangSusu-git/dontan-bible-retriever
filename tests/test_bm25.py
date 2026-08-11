import pytest
from bible_search.tokenizer import KiwiTokenizer
from bible_search.retrievers.bm25 import BM25Retriever

def test_bm25_matches_stem_despite_archaic_ending(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    # "태초 창조" 질의가 "...창조하시니라"(고어체) 구절을 찾아낸다
    results = r.search("태초 창조")
    ids = [x.verse.id for x in results]
    assert "개역개정:창세기:1:1" in ids
    assert all(x.source == "bm25" for x in results)

def test_bm25_excludes_zero_score(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    results = r.search("여호와")
    # 매칭된 구절만(점수>0) 나와야 하고, 무관한 구절(창세기 1:1)은 없어야 한다
    ids = [x.verse.id for x in results]
    assert "개역개정:시편:23:1" in ids
    assert "개역개정:창세기:1:1" not in ids
    assert all(x.score > 0 for x in results)

def test_bm25_no_match_returns_empty(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    assert r.search("컴퓨터프로그래밍") == []

def test_bm25_limit_caps_results(verses):
    r = BM25Retriever(verses, KiwiTokenizer())
    results = r.search("여호와", limit=1)
    assert len(results) <= 1

def test_bm25_with_pretokenized_corpus_matches_default(verses):
    tokenizer = KiwiTokenizer()
    corpus = [tokenizer.tokenize(v.text) for v in verses]
    cached = BM25Retriever(verses, tokenizer, corpus=corpus)
    default = BM25Retriever(verses, tokenizer)

    for query in ("태초 창조", "여호와"):
        cached_ids = [x.verse.id for x in cached.search(query)]
        default_ids = [x.verse.id for x in default.search(query)]
        assert cached_ids == default_ids

def test_bm25_mismatched_corpus_length_raises(verses):
    tokenizer = KiwiTokenizer()
    short_corpus = [["a"]]
    with pytest.raises(ValueError):
        BM25Retriever(verses, tokenizer, corpus=short_corpus)

def test_bm25_b_default_matches_explicit_075(verses):
    # 기본 생성자 결과와 b=0.75(rank_bm25 기본값)를 명시한 결과가 같아야,
    # 새 b 파라미터가 기존 기본 동작을 바꾸지 않았음을 확인할 수 있다.
    default = BM25Retriever(verses, KiwiTokenizer())
    explicit_075 = BM25Retriever(verses, KiwiTokenizer(), b=0.75)
    for query in ("여호와", "태초 창조"):
        d = [(x.verse.id, x.score) for x in default.search(query)]
        e = [(x.verse.id, x.score) for x in explicit_075.search(query)]
        assert d == e

def test_bm25_b_is_configurable_and_changes_ranking(verses):
    # 길이 편차가 있는 fixture 구절들에서, b=0(길이 정규화 없음)과 b=0.75
    # (rank_bm25 기본값)는 "여호와" 질의에 대해 서로 다른 순위를 낸다.
    r0 = BM25Retriever(verses, KiwiTokenizer(), b=0.0)
    r75 = BM25Retriever(verses, KiwiTokenizer(), b=0.75)
    ids0 = [x.verse.id for x in r0.search("여호와")]
    ids75 = [x.verse.id for x in r75.search("여호와")]
    assert ids0 != ids75
    assert ids0[0] == "개역개정:시편:23:1"
    assert ids75[0] == "개역개정:이사야:40:31"
