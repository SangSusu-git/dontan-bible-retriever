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
